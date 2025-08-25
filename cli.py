import argparse
import importlib
from typing import Callable, List

from .server import SAPServer


def _load_callable(target: str) -> Callable[[], List[dict]]:
    if ":" not in target:
        raise ValueError("--fetch must be in the form module.path:callable_name")
    mod_name, func_name = target.split(":", 1)
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, func_name)
    if not callable(fn):
        raise TypeError(f"{target} is not callable")
    return fn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an SAP provider from a Python callable")
    parser.add_argument("--name", required=True, help="Provider name")
    parser.add_argument("--description", default="", help="Provider description")
    parser.add_argument("--fetch", required=True, help="Fetch function in form module.path:callable")
    parser.add_argument("--interval", type=float, default=300.0, help="Fetch interval in seconds")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default 8080)")
    parser.add_argument("--auto-port", action="store_true", help="If set, try next ports if taken")
    parser.add_argument("--register", action="store_true", help="Register URL in ~/.sa/saps.txt")
    parser.add_argument("--require-initial", action="store_true", help="Wait for first fetch to succeed before serving")
    parser.add_argument("--initial-timeout", type=float, default=30.0, help="Timeout for initial fetch wait")
    args = parser.parse_args()

    fetch_fn = _load_callable(args.fetch)

    server = SAPServer(
        provider=dict(name=args.name, description=args.description),
        fetch_fn=fetch_fn,
        interval_seconds=float(args.interval),
    )
    server.run(
        host=args.host,
        port=args.port,
        auto_port=bool(args.auto_port),
        register_with_shell=bool(args.register),
        require_initial_fetch=bool(args.require_initial),
        initial_fetch_timeout_seconds=float(args.initial_timeout),
    )


if __name__ == "__main__":
    main()