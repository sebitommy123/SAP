from datetime import datetime, timezone, timedelta
from sap import SAPServer, make_object, timestamp, link, Scope
import time
import random
import uuid

def fetch_data():    
    # Also include some basic employee records
    employees = [
        make_object(
            id="emp_001",
            types=["person", "employee"],
            source="hr_system",
            properties={"name": "Alice Johnson"}
        )
    ]
    
    return employees

def lazy_load_data(scope: Scope, conditions: list[tuple[str, str, str]], plan_only: bool, id_types: set[tuple[str, str]]) -> tuple[list[dict], str]:
    return [
        make_object(
            id="simple_001",
            types=["simple"],
            source="simple_provider",
            properties={"one": "one"}
        ),
    ], "Plan"

if __name__ == "__main__":
    lazy_scopes = [
        Scope(type="simple", fields=["one"], filtering_fields=[], needs_id_types=False)
    ]
    
    server = SAPServer(
        provider=dict(
            name="Demo SAP Provider", 
            description="Example provider built with SAP",
            lazy_loading_scopes=lazy_scopes
        ),
        fetch_fn=fetch_data,
        interval_seconds=60,
        lazy_load_fn=lazy_load_data,
    )
    server.run(port=8080, register_with_shell=True)