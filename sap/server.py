from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple, Union
import logging

import os
import time
import threading
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from .scheduler import IntervalCacheRunner
from .scope import Scope

# Configure logging for SAP
logger = logging.getLogger(__name__)


def configure_logging(level: str = "INFO", enable_debug: bool = False) -> None:
    """
    Configure logging for SAP library.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_debug: If True, enable debug logging for lazy loading details
    """
    # Get the SAP logger
    sap_logger = logging.getLogger("sap")
    
    # Only configure if not already configured
    if not sap_logger.handlers:
        sap_logger.setLevel(getattr(logging, level.upper()))
        
        # Create console handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        sap_logger.addHandler(handler)
        
        # Prevent propagation to root logger to avoid duplicates
        sap_logger.propagate = False
        
        print(f"SAP logging configured: level={level}, debug={enable_debug}")
    else:
        # Just update the level if already configured
        sap_logger.setLevel(getattr(logging, level.upper()))
    
    # Enable debug logging for lazy loading if requested
    if enable_debug:
        lazy_logger = logging.getLogger("sap.server")
        lazy_logger.setLevel(logging.DEBUG)


@dataclass
class ProviderInfo:
    name: str
    description: str
    version: str = "0.1.0"
    lazy_loading_scopes: List[Scope] = None


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
        lazy_load_fn: Optional[Callable[[Scope, list[tuple[str, str, str]], bool, set[tuple[str, str]]], Tuple[List[dict], str]]] = None,
        enable_logging: bool = True,
        log_level: str = "INFO",
        enable_debug: bool = False,
    ) -> None:
        # Configure logging automatically if enabled
        if enable_logging:
            configure_logging(level=log_level, enable_debug=enable_debug)
        
        if isinstance(provider, dict):
            self.provider = ProviderInfo(
                name=provider.get("name", "SAP Provider"),
                description=provider.get("description", ""),
                version=provider.get("version", "0.1.0"),
                lazy_loading_scopes=provider.get("lazy_loading_scopes", []),
            )
        else:
            self.provider = provider
        
        self.lazy_load_fn = lazy_load_fn
        
        # Log provider configuration
        logger.info(f"Initializing SAP server: {self.provider.name} v{self.provider.version}")
        logger.info(f"Description: {self.provider.description}")
        logger.info(f"Fetch interval: {interval_seconds}s")
        logger.info(f"Run immediately: {run_immediately}")
        
        if self.lazy_load_fn:
            lazy_types = [scope.type for scope in (self.provider.lazy_loading_scopes or [])]
            logger.info(f"Lazy loading enabled for types: {lazy_types}")
        else:
            logger.info("Lazy loading disabled")

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
            logger.info("Provider info requested via /hello endpoint")
            lazy_scopes = [
                {
                    "type": scope.type,
                    "fields": scope.fields,
                    "filtering_fields": scope.filtering_fields,
                    "needs_id_types": scope.needs_id_types
                } for scope in (provider.lazy_loading_scopes or [])
            ]
            logger.debug(f"Returning lazy loading scopes: {lazy_scopes}")
            return jsonify({
                "name": provider.name,
                "description": provider.description,
                "version": provider.version,
                "lazy_loading_scopes": lazy_scopes
            })

        @app.route("/all_data")
        def all_data():
            return jsonify(runner.get_cached())

        @app.route("/lazy_load", methods=["POST"])
        def lazy_load():
            logger.info("Received lazy loading request")
            
            if not self.lazy_load_fn:
                logger.warning("Lazy loading requested but not supported by this provider")
                return jsonify({"error": "Lazy loading not supported by this provider"}), 400
            
            try:
                data = request.get_json()
                if not data:
                    logger.warning("Lazy loading request with no JSON data")
                    return jsonify({"error": "No JSON data provided"}), 400
                
                # Parse QueryScope from request
                scope_data = data.get("scope", {})
                conditions = data.get("conditions", [])
                plan_only = data.get("plan_only", False)
                id_types = data.get("id_types", [])
                
                logger.info(f"Lazy loading request: type={scope_data.get('type', 'unknown')}, "
                           f"fields={scope_data.get('fields', 'unknown')}, "
                           f"conditions={len(conditions)}, plan_only={plan_only}, id_types={id_types}")
                
                if not scope_data or "type" not in scope_data:
                    logger.warning("Lazy loading request with invalid scope (missing type)")
                    return jsonify({"error": "Invalid scope: missing type"}), 400
                
                scope = Scope(
                    type=scope_data["type"],
                    fields=scope_data.get("fields", "*"),
                    filtering_fields=scope_data.get("filtering_fields", []),
                    needs_id_types=scope_data.get("needs_id_types", False)
                )
                
                # Check if the type is supported for lazy loading
                supported_types = {s.type for s in (provider.lazy_loading_scopes or [])}
                if scope.type not in supported_types:
                    logger.warning(f"Lazy loading requested for unsupported type: {scope.type}")
                    return jsonify({"error": f"Type '{scope.type}' not supported for lazy loading"}), 400
                
                logger.info(f"Delegating lazy loading to provider function for type: {scope.type}")
                
                # Call the lazy load function
                try:
                    start_time = time.time()
                    sa_objects, plan = self.lazy_load_fn(scope, conditions, plan_only, id_types)
                    duration = time.time() - start_time
                    
                    logger.info(f"Lazy loading completed: {len(sa_objects)} objects returned in {duration:.3f}s")
                    logger.debug(f"Lazy loading plan: {plan}")
                    
                    return jsonify({
                        "sa_objects": sa_objects,
                        "plan": plan
                    })
                except Exception as e:
                    # Provider declined the request
                    logger.error(f"Provider declined lazy loading request: {str(e)}")
                    return jsonify({"error": str(e)})
                    
            except Exception as e:
                logger.error(f"Error processing lazy loading request: {str(e)}")
                return jsonify({"error": f"Invalid request: {str(e)}"}), 400

        @app.route("/wtf")
        def wtf():
            """What the fuck is this server? Returns server type."""
            return jsonify({"type": "SAP"})

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
            endpoints = {
                "/wtf": "Server type identification",
                "/hello": "Provider information",
                "/all_data": "All SAObject data",
                "/health": "Health probe",
                "/status": "Runner status",
            }
            if self.lazy_load_fn:
                endpoints["/lazy_load"] = "Lazy load data with query scope"
            
            return jsonify({
                "service": provider.name,
                "endpoints": endpoints,
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
        logger.info(f"Starting SAP server on {host}:{port} (auto_port={auto_port})")
        
        # Start the fetch runner
        logger.info("Starting data fetch runner")
        self.runner.start()
        
        if require_initial_fetch:
            logger.info(f"Waiting for initial fetch (timeout: {initial_fetch_timeout_seconds}s)")
            deadline = time.time() + float(initial_fetch_timeout_seconds)
            while time.time() < deadline:
                st = self.runner.get_status()
                if st.get("last_completed_at") is not None and st.get("last_error") is None:
                    logger.info("Initial fetch completed successfully")
                    break
                time.sleep(0.1)
            else:
                logger.warning("Initial fetch timeout reached")

        # Create WSGI server (binds socket here)
        logger.info("Creating WSGI server")
        bound_host, actual_port = self._create_server(host, port, auto_port)
        logger.info(f"Server bound to {bound_host}:{actual_port}")

        if register_with_shell:
            # Prefer localhost in registry for easy shell access
            reg_url = f"http://localhost:{actual_port}"
            logger.info(f"Registering with SA shell: {reg_url}")
            _register_with_shell(reg_url)

        # Start serving in background
        def _serve():
            assert self._wsgi_server is not None
            logger.info("Starting HTTP server thread")
            self._wsgi_server.serve_forever()

        self._server_thread = threading.Thread(target=_serve, name="sap-wsgi-server", daemon=True)
        self._server_thread.start()
        logger.info("SAP server started successfully")
        return bound_host, actual_port

    def stop(self, timeout: Optional[float] = 5.0) -> None:
        logger.info(f"Stopping SAP server (timeout: {timeout}s)")
        try:
            if self._wsgi_server is not None:
                logger.info("Shutting down WSGI server")
                self._wsgi_server.shutdown()
        finally:
            logger.info("Stopping data fetch runner")
            self.runner.stop(timeout=timeout)
            if self._server_thread and self._server_thread.is_alive():
                logger.info("Waiting for server thread to finish")
                self._server_thread.join(timeout=timeout)
        logger.info("SAP server stopped")

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
        logger.info(f"Starting SAP server run mode (debug={debug})")
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
            logger.info(f"SAP provider running at http://{bound_host}:{actual_port}")
            # Block main thread until interrupted
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down")
        finally:
            self.stop()


def run_server(
    name: str,
    description: str,
    fetch_fn: Callable[[], List[dict]],
    interval_seconds: float,
    version: str = "0.1.0",
    lazy_loading_scopes: List[Scope] = None,
    lazy_load_fn: Optional[Callable[[Scope, list[tuple[str, str, str]], bool, set[tuple[str, str]]], Tuple[List[dict], str]]] = None,
    host: str = "0.0.0.0",
    port: int = 8080,
    run_immediately: bool = True,
    debug: bool = False,
    auto_port: bool = False,
    register_with_shell: bool = False,
    require_initial_fetch: bool = False,
    initial_fetch_timeout_seconds: float = 30.0,
    enable_logging: bool = True,
    log_level: str = "INFO",
    enable_debug: bool = False,
) -> None:
    server = SAPServer(
        ProviderInfo(name=name, description=description, version=version, lazy_loading_scopes=lazy_loading_scopes),
        fetch_fn=fetch_fn,
        interval_seconds=interval_seconds,
        run_immediately=run_immediately,
        lazy_load_fn=lazy_load_fn,
        enable_logging=enable_logging,
        log_level=log_level,
        enable_debug=enable_debug,
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