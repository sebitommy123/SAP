# SAP (SA Provider Library)

Utilities to build SA-compliant providers easily. You focus on collecting data; SAP handles interval caching and serving it over a tiny HTTP API the SA Shell understands.

## Install

```bash
pip install -r requirements.txt  # ensures Flask
```

## Quickstart

```python
# example_provider.py
from sap import SAPServer, make_object, timestamp, link
from datetime import datetime

# Your heavy function: return a list of SA JSON objects (dicts)
def fetch_data():
    objs = [
        make_object(
            id="emp_001",
            types=["person", "employee"],
            source="my_system",
            name="Alice",
            hired_at=timestamp(datetime.utcnow()),
            profile=link(".filter(.equals(.get_field('name'), 'Alice'))", "Alice's records"),
        )
    ]
    return objs

server = SAPServer(
    provider=dict(name="My Provider", description="Demo provider"),  # or ProviderInfo(...)
    fetch_fn=fetch_data,
    interval_seconds=300,
)

if __name__ == "__main__":
    server.run(port=8080)
```

Endpoints provided:
- GET /hello → provider info `{ name, mode: "ALL_AT_ONCE", description, version }`
- GET /all_data → cached list of SA objects

## Notes
- `interval_seconds` controls how often `fetch_fn` runs. Results are cached and served fast.
- Use `make_object` and helpers (`timestamp`, `link`) to avoid managing `__id__`, `__source__`, `__types__` and `__sa_type__` by hand.

## Advanced usage

- Fixed port by default: defaults to 8080. You can change with `port=` or `--port`. Auto-port fallback is opt-in via `auto_port=True` or `--auto-port`.
- Health and status:
  - GET `/health` → `{ status: "ok", count: <int> }`
  - GET `/status` → runner timings, error, count
- Initial fetch control: set `require_initial_fetch=True` to wait for the first successful fetch before advertising the endpoint.
- Register with shell: pass `register_with_shell=True` to write the URL to `~/.sa/saps.txt` (deduped).

### CLI

```bash
# Using module entrypoint
python -m sap.cli \
  --name "My Provider" \
  --description "Demo" \
  --fetch mypkg.my_module:build_data \
  --interval 300 \
  --register

# Or python -m sap (alias)
python -m sap --name "My Provider" --fetch mypkg.my_module:build_data
```

### Refresh endpoint

Optionally protect manual refresh with a token:
```bash
export SAP_REFRESH_TOKEN=mysecret
curl "http://localhost:8080/refresh?token=mysecret"
```

### Programmatic

```python
from sap import SAPServer

server = SAPServer(
    provider=dict(name="My Provider", description="Demo provider"),
    fetch_fn=fetch_data,
    interval_seconds=300,
)
server.run(register_with_shell=True, require_initial_fetch=True)
```

## Data schema

Each object returned by your `fetch_fn` must be a dict with at least:
- `__id__`: string
- `__types__`: list of strings
- `__source__`: string

Optional fields can be any JSON-serializable values. To include SA custom types:
- Use `timestamp(...)` to produce `{"__sa_type__":"timestamp", "timestamp": <ns>}`
- Use `link(query, show_text)` to produce `{"__sa_type__":"link", ...}`

You can build objects by hand or via helpers:
```python
from sap import make_object
obj = make_object(
  id="123", types=["person"], source="my_db", name="Alice"
)
```

Best practices:
- Keep `__id__` stable across runs.
- Use a consistent `__source__` identifier for your system.
- Prefer `make_object` and helpers to avoid subtle schema mistakes.

### Health and status semantics

- `/health` returns `200` JSON `{ status: "ok", count }` if server is running; it does not reflect fetch failure.
- `/status` includes `last_started_at`, `last_completed_at`, `last_error`, `in_flight`, `interval_seconds`, `fetch_timeout_seconds`, and `count`.

### Concurrency and timeouts
- Fetches never overlap. If a fetch is in-flight when a new interval elapses or `/refresh` is called, the new run is skipped.
- `fetch_timeout_seconds` (default 120s) limits a single fetch attempt; timeout is recorded in `last_error`.

### Deduplication
- By default, objects are deduped by `(__id__, __source__, tuple(__types__))` after normalization. Provide unique ids for distinct logical records.

### Signals and shutdown
- The server runs in a background WSGI thread. `Ctrl+C` or process termination triggers graceful shutdown of the runner and server.