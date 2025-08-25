from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple, Union

import os
import time
import threading
from flask import Flask, jsonify
from werkzeug.serving import make_server

from .scheduler import IntervalCacheRunner


@dataclass
class ProviderInfo:
    name: str
    description: str
    version: str = "0.1.0"
    mode: str = "ALL_AT_ONCE"


def _ensure_sa_dir() -> str:
    home_dir = os.path.expanduser("~")
    sa_dir = os.path.join(home_dir, ".sa")
    if not os.path.exists(sa_dir):
        os.makedirs(sa_dir, exist_ok=True)
    return sa_dir


def _register_with_shell(url: str) -> None:
    sa_dir = _ensure_sa_dir()
    providers_file = os.path.join(sa_dir, "saps.txt")
    existing: set[str] = set()
    if os.path.exists(providers_file):
        with open(providers_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    existing.add(line)
    if url not in existing:
        os.makedirs(os.path.dirname(providers_file), exist_ok=True)
        need_leading_newline = os.path.exists(providers_file) and os.path.getsize(providers_file) > 0
        with open(providers_file, "a") as f:
            if need_leading_newline:
                f.write("\n")
            f.write(url + "\n")


class SAPServer:
    def __init__(
        self,
        provider: Union[ProviderInfo, dict],
        fetch_fn: Callable[[], List[dict]],
        interval_seconds: float,
        run_immediately: bool = True,
    ) -> None:
        if isinstance(provider, dict):
            self.provider = ProviderInfo(
                name=provider.get("name", "SAP Provider"),
                description=provider.get("description", ""),
                version=provider.get("version", "0.1.0"),
                mode=provider.get("mode", "ALL_AT_ONCE"),
            )
        else:
            self.provider = provider

        from .models import normalize_objects, deduplicate_objects

        def _postprocess(data):
            return deduplicate_objects(normalize_objects(data))

        self.runner = IntervalCacheRunner(
            fetch_fn=fetch_fn,
            interval_seconds=interval_seconds,
            run_immediately=run_immediately,
            postprocess=_postprocess,
        )
        self.app = Flask("sap-provider")
        self._configure_routes()

        self._wsgi_server = None
        self._server_thread: Optional[threading.Thread] = None

    def _configure_routes(self) -> None:
        app = self.app
        provider = self.provider
        runner = self.runner

        @app.route("/hello")
        def hello():
            return jsonify({
                "name": provider.name,
                "mode": provider.mode,
                "description": provider.description,
                "version": provider.version,
            })

        @app.route("/all_data")
        def all_data():
            return jsonify(runner.get_cached())

        @app.route("/health")
        def health():
            return jsonify({"status": "ok", "count": len(runner.get_cached())})

        @app.route("/status")
        def status():
            info = runner.get_status()
            info["count"] = len(runner.get_cached())
            return jsonify(info)

        # Manual refresh; gated by optional token env var
        @app.route("/refresh")
        def refresh():
            token = os.environ.get("SAP_REFRESH_TOKEN")
            if token:
                from flask import request
                if request.args.get("token") != token:
                    return jsonify({"error": "unauthorized"}), 401
            runner.run_now(blocking=False)
            return jsonify({"status": "refresh_started"})

        @app.route("/")
        def root():
            return jsonify({
                "service": provider.name,
                "endpoints": {
                    "/hello": "Provider information",
                    "/all_data": "All SAObject data",
                    "/health": "Health probe",
                    "/status": "Runner status",
                },
                "status": "running",
            })

    def _create_server(self, host: str, port: int, auto_port: bool) -> Tuple[str, int]:
        desired_port = int(port)
        attempts = [desired_port]
        if auto_port:
            attempts.extend([desired_port + i for i in range(1, 21)])
        last_err = None
        for p in attempts:
            try:
                server = make_server(host, p, self.app)
                self._wsgi_server = server
                actual_port = server.server_port
                return host, actual_port
            except OSError as e:
                last_err = e
                continue
        raise last_err  # type: ignore

    def start_background(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        auto_port: bool = False,
        register_with_shell: bool = False,
        require_initial_fetch: bool = False,
        initial_fetch_timeout_seconds: float = 30.0,
    ) -> Tuple[str, int]:
        # Start the fetch runner
        self.runner.start()
        if require_initial_fetch:
            deadline = time.time() + float(initial_fetch_timeout_seconds)
            while time.time() < deadline:
                st = self.runner.get_status()
                if st.get("last_completed_at") is not None and st.get("last_error") is None:
                    break
                time.sleep(0.1)

        # Create WSGI server (binds socket here)
        bound_host, actual_port = self._create_server(host, port, auto_port)

        if register_with_shell:
            # Prefer localhost in registry for easy shell access
            reg_url = f"http://localhost:{actual_port}"
            _register_with_shell(reg_url)

        # Start serving in background
        def _serve():
            assert self._wsgi_server is not None
            self._wsgi_server.serve_forever()

        self._server_thread = threading.Thread(target=_serve, name="sap-wsgi-server", daemon=True)
        self._server_thread.start()
        return bound_host, actual_port

    def stop(self, timeout: Optional[float] = 5.0) -> None:
        try:
            if self._wsgi_server is not None:
                self._wsgi_server.shutdown()
        finally:
            self.runner.stop(timeout=timeout)
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=timeout)

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        debug: bool = False,
        auto_port: bool = False,
        register_with_shell: bool = False,
        require_initial_fetch: bool = False,
        initial_fetch_timeout_seconds: float = 30.0,
    ) -> None:
        try:
            bound_host, actual_port = self.start_background(
                host=host,
                port=port,
                auto_port=auto_port,
                register_with_shell=register_with_shell,
                require_initial_fetch=require_initial_fetch,
                initial_fetch_timeout_seconds=initial_fetch_timeout_seconds,
            )
            print(f"SAP provider running at http://{bound_host}:{actual_port}")
            # Block main thread until interrupted
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def run_server(
    name: str,
    description: str,
    fetch_fn: Callable[[], List[dict]],
    interval_seconds: float,
    version: str = "0.1.0",
    mode: str = "ALL_AT_ONCE",
    host: str = "0.0.0.0",
    port: int = 8080,
    run_immediately: bool = True,
    debug: bool = False,
    auto_port: bool = False,
    register_with_shell: bool = False,
    require_initial_fetch: bool = False,
    initial_fetch_timeout_seconds: float = 30.0,
) -> None:
    server = SAPServer(
        ProviderInfo(name=name, description=description, version=version, mode=mode),
        fetch_fn=fetch_fn,
        interval_seconds=interval_seconds,
        run_immediately=run_immediately,
    )
    server.run(
        host=host,
        port=port,
        debug=debug,
        auto_port=auto_port,
        register_with_shell=register_with_shell,
        require_initial_fetch=require_initial_fetch,
        initial_fetch_timeout_seconds=initial_fetch_timeout_seconds,
    )