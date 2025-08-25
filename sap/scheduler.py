from __future__ import annotations
import threading
import time
from typing import Any, Callable, List, Optional, Iterable, Union


class IntervalCacheRunner:
    def __init__(
        self,
        fetch_fn: Callable[[], Union[List[dict], Iterable[dict]]],
        interval_seconds: float,
        run_immediately: bool = True,
        postprocess: Optional[Callable[[List[dict]], List[dict]]] = None,
        fetch_timeout_seconds: Optional[float] = 120.0,
    ) -> None:
        self._fetch_fn = fetch_fn
        self._interval_seconds = max(0.0, float(interval_seconds))
        self._run_immediately = run_immediately
        self._postprocess = postprocess
        self._fetch_timeout_seconds = fetch_timeout_seconds

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._in_flight = False
        self._last_started_at: Optional[float] = None
        self._last_completed_at: Optional[float] = None
        self._last_error: Optional[str] = None
        self._cache: List[dict] = []

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="sap-interval-runner", daemon=True)
        self._thread.start()

    def stop(self, timeout: Optional[float] = 5.0) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def get_cached(self) -> List[dict]:
        with self._lock:
            return list(self._cache)

    def get_status(self) -> dict:
        with self._lock:
            return {
                "last_started_at": self._last_started_at,
                "last_completed_at": self._last_completed_at,
                "last_error": self._last_error,
                "interval_seconds": self._interval_seconds,
                "is_running": self._thread.is_alive() if self._thread else False,
                "in_flight": self._in_flight,
                "fetch_timeout_seconds": self._fetch_timeout_seconds,
            }

    def run_now(self, blocking: bool = False) -> None:
        if blocking:
            self._run_once()
            return
        t = threading.Thread(target=self._run_once, name="sap-interval-runner-now", daemon=True)
        t.start()

    def _run_once(self) -> None:
        # Guard: do not overlap fetches
        with self._lock:
            if self._in_flight:
                return
            self._in_flight = True
        try:
            self._last_started_at = time.time()

            result_holder: dict = {}
            error_holder: dict = {}
            done_event = threading.Event()

            def _call():
                try:
                    result_holder["data"] = self._fetch_fn()
                except Exception as exc:
                    error_holder["err"] = exc
                finally:
                    done_event.set()

            t = threading.Thread(target=_call, name="sap-fetch-call", daemon=True)
            t.start()

            timeout = self._fetch_timeout_seconds
            if timeout is not None:
                finished = done_event.wait(timeout)
                if not finished:
                    # Timed out; do not kill thread, but record error; next loop can try again
                    raise TimeoutError(f"fetch exceeded {timeout} seconds")
            else:
                done_event.wait()

            if "err" in error_holder:
                raise error_holder["err"]

            result = result_holder.get("data", [])
            if not isinstance(result, list):
                try:
                    result = list(result)  # type: ignore[arg-type]
                except TypeError:
                    raise TypeError("fetch function must return a list or iterable of dicts")
            if any(not isinstance(item, dict) for item in result):
                try:
                    result = [item.to_json() if hasattr(item, "to_json") else item for item in result]
                except Exception:
                    raise TypeError("each item must be a dict or provide to_json()")
            if self._postprocess is not None:
                result = self._postprocess(result)
            with self._lock:
                self._cache = result
                self._last_completed_at = time.time()
                self._last_error = None
        except Exception as exc:
            with self._lock:
                self._last_error = f"{type(exc).__name__}: {exc}"
                self._last_completed_at = time.time()
        finally:
            with self._lock:
                self._in_flight = False

    def _run_loop(self) -> None:
        if self._run_immediately:
            self._run_once()
        while not self._stop_event.is_set():
            waited = 0.0
            while waited < self._interval_seconds and not self._stop_event.is_set():
                sleep_chunk = min(0.5, self._interval_seconds - waited)
                time.sleep(sleep_chunk)
                waited += sleep_chunk
            if self._stop_event.is_set():
                break
            self._run_once()