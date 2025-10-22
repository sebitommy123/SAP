# SAP (SA Provider Library)

Utilities to build SA-compliant providers easily. You focus on collecting data; SAP handles interval caching and serving it over a tiny HTTP API the SA Shell understands.

## Install

```bash
pip install -r requirements.txt  # ensures Flask
```

## Logging

SAP includes comprehensive logging to help you understand what's happening during lazy loading operations. You can configure logging levels and enable debug mode:

```python
from sap import configure_logging

# Basic logging setup
configure_logging(level="INFO")

# Enable debug logging for detailed lazy loading information
configure_logging(level="DEBUG", enable_debug=True)
```

**Log Levels:**
- `INFO`: General server operations, lazy loading requests, and results
- `DEBUG`: Detailed lazy loading plans, request parsing, and timing information
- `WARNING`: Non-critical issues like unsupported types or missing conditions
- `ERROR`: Critical errors like provider failures or invalid requests

**Example Log Output:**
```
2024-10-05 15:11:29 - sap.server - INFO - Received lazy loading request
2024-10-05 15:11:29 - sap.server - INFO - Lazy loading request: type=employee, fields=['favorite_color', 'favorite_number', 'favorite_shape'], conditions=1, plan_only=False
2024-10-05 15:11:29 - sap.server - INFO - Delegating lazy loading to provider function for type: employee
2024-10-05 15:11:29 - sap.server - INFO - Lazy loading completed: 1 objects returned in 0.001s
2024-10-05 15:11:29 - sap.server - DEBUG - Lazy loading plan: Lazy loading employee objects with conditions: [['__id__', '==', 'emp_001']] (data fetched)
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
- GET /hello → provider info with lazy loading scopes
- GET /all_data → cached list of SA objects
- POST /lazy_load → lazy load data with query scopes

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

## Lazy Loading

SAP supports lazy loading capabilities that allow clients to request specific data on-demand rather than loading everything at once. This is useful for large datasets or when you want to provide filtered, real-time data.

### Setting Up Lazy Loading

To enable lazy loading, you need to:

1. **Define Lazy Loading Scopes**: Specify what types of data can be lazy loaded and what fields are available
2. **Implement a Lazy Load Function**: Create a function that handles lazy loading requests
3. **Configure the Server**: Pass the lazy loading configuration to your SAP server

### Basic Lazy Loading Example

```python
from sap import SAPServer, make_object, timestamp, Scope
from datetime import datetime

def fetch_data():
    # Your regular data fetching function
    return [
        make_object(
            id="emp_001",
            types=["person", "employee"],
            source="hr_system",
            name="Alice Johnson",
            department="Engineering"
        )
    ]

def lazy_load_data(query_scope: QueryScope, plan_only: bool) -> tuple[list[dict], str]:
    """
    Handle lazy loading requests.
    
    Args:
        query_scope: Contains the scope (type and fields) and conditions
        plan_only: If True, only return the plan without fetching data
        
    Returns:
        Tuple of (sa_objects, plan_description)
    """
    scope = query_scope.scope
    conditions = query_scope.conditions
    
    # Build plan description
    plan = f"Lazy loading {scope.type} objects"
    if conditions:
        plan += f" with conditions: {conditions}"
    if plan_only:
        plan += " (plan only - no data fetched)"
    else:
        plan += " (data fetched)"
    
    if plan_only:
        return [], plan
    
    # Handle different types of lazy loading
    if scope.type == "employee":
        # Example: Return employee with additional fields
        return [make_object(
            id="emp_001",
            types=["person", "employee"],
            source="hr_system",
            favorite_color="blue",
            favorite_number=42,
            favorite_shape="circle"
        )], plan
    else:
        raise Exception(f"Lazy loading not supported for type: {scope.type}")

# Define lazy loading scopes
lazy_scopes = [
    Scope(type="employee", fields=["favorite_color", "favorite_number", "favorite_shape"])
]

server = SAPServer(
    provider=dict(
        name="My Provider",
        description="Demo provider with lazy loading",
        lazy_loading_scopes=lazy_scopes
    ),
    fetch_fn=fetch_data,
    interval_seconds=300,
    lazy_load_fn=lazy_load_data,  # Enable lazy loading
)

if __name__ == "__main__":
    server.run(port=8080)
```

### Lazy Loading API

#### GET /hello
Returns provider information including available lazy loading scopes:

```json
{
    "name": "My Provider",
    "description": "Demo provider with lazy loading",
    "version": "0.1.0",
    "lazy_loading_scopes": [
        {
            "type": "employee",
            "fields": ["favorite_color", "favorite_number", "favorite_shape"]
        }
    ]
}
```

#### POST /lazy_load
Request specific data using query scopes:

```bash
curl -X POST http://localhost:8080/lazy_load \
  -H "Content-Type: application/json" \
  -d '{
    "scope": {
        "type": "employee",
        "fields": ["favorite_color", "favorite_number", "favorite_shape"]
    },
    "conditions": [["__id__", "==", "emp_001"]],
    "plan_only": false
  }'
```

**Request Format:**
- `scope`: Object with `type` (string) and `fields` (array of strings or "*")
- `conditions`: Array of `[field, operator, value]` tuples
- `plan_only`: Boolean - if true, only return the execution plan without data

**Response Format:**
```json
{
    "sa_objects": [
        {
            "__id__": "emp_001",
            "__types__": ["person", "employee"],
            "__source__": "hr_system",
            "favorite_color": "blue",
            "favorite_number": 42,
            "favorite_shape": "circle"
        }
    ],
    "plan": "Lazy loading employee objects with conditions: [['__id__', '==', 'emp_001']] (data fetched)"
}
```

### Advanced Lazy Loading Patterns

#### Date-Based Filtering (Swipes Example)

```python
def lazy_load_data(query_scope: QueryScope, plan_only: bool) -> tuple[list[dict], str]:
    scope = query_scope.scope
    conditions = query_scope.conditions
    
    if scope.type == "swipe":
        # Require date condition
        date_condition = None
        for condition in conditions:
            field, operator, value = condition
            if field == "date":
                date_condition = (field, operator, value)
                break
        
        if not date_condition:
            raise Exception("Swipe queries must include a 'date' condition")
        
        # Generate swipes for the requested date
        field, operator, value = date_condition
        if operator != "==":
            raise Exception("Only '==' operator is supported for date filtering")
        
        target_date = datetime.strptime(value, "%Y-%m-%d").date()
        swipes = generate_swipes_for_date(target_date)
        
        return swipes, f"Generated swipes for {value}"
    
    # ... handle other types
```

#### ID-Based Filtering (Employee Details)

```python
def lazy_load_data(query_scope: QueryScope, plan_only: bool) -> tuple[list[dict], str]:
    scope = query_scope.scope
    conditions = query_scope.conditions
    
    if scope.type == "employee":
        # Require __id__ condition
        id_condition = None
        for condition in conditions:
            field, operator, value = condition
            if field == "__id__":
                id_condition = (field, operator, value)
                break
        
        if not id_condition:
            raise Exception("Employee queries must include an '__id__' condition")
        
        # Return employee with additional fields
        field, operator, value = id_condition
        employee = get_employee_with_details(value)
        return [employee], f"Retrieved employee {value}"
    
    # ... handle other types
```

### Best Practices

1. **Validate Conditions**: Always check that required conditions are provided
2. **Handle Errors Gracefully**: Return meaningful error messages for invalid requests
3. **Support Plan-Only Mode**: Allow clients to get execution plans without fetching data
4. **Use Descriptive Plans**: Include details about what the lazy loading function will do
5. **Validate Types**: Check that the requested type is supported for lazy loading
6. **Return Consistent Data**: Ensure returned objects follow SA object schema

### Error Handling

The lazy loading endpoint returns appropriate HTTP status codes:

- `200`: Success with data
- `400`: Bad request (missing conditions, invalid data, etc.)
- `404`: Type not supported for lazy loading

Example error responses:
```json
{
    "error": "Swipe queries must include a 'date' condition"
}
```

```json
{
    "error": "Type 'unsupported_type' not supported for lazy loading"
}
```

### Testing Lazy Loading

You can test your lazy loading implementation using curl or any HTTP client:

```bash
# Test plan-only mode
curl -X POST http://localhost:8080/lazy_load \
  -H "Content-Type: application/json" \
  -d '{
    "scope": {"type": "employee", "fields": ["favorite_color"]},
    "conditions": [["__id__", "==", "emp_001"]],
    "plan_only": true
  }'

# Test with invalid type
curl -X POST http://localhost:8080/lazy_load \
  -H "Content-Type: application/json" \
  -d '{
    "scope": {"type": "invalid_type", "fields": ["field1"]},
    "conditions": []
  }'
```