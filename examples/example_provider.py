from datetime import datetime, timezone, timedelta
from sap import SAPServer, make_object, timestamp, link, Scope
import time
import random
import uuid


def generate_swipe_data():
    """Generate 5 years of swipe data for employees with realistic times."""
    employees = [
        {"id": "emp_001", "name": "Alice Johnson", "department": "Engineering"},
        {"id": "emp_002", "name": "Bob Smith", "department": "Engineering"},
        {"id": "emp_003", "name": "Carol Davis", "department": "Design"},
        {"id": "emp_004", "name": "David Wilson", "department": "Marketing"},
        {"id": "emp_005", "name": "Eva Brown", "department": "Sales"},
        {"id": "emp_006", "name": "Frank Miller", "department": "HR"},
        {"id": "emp_007", "name": "Grace Lee", "department": "Finance"},
        {"id": "emp_008", "name": "Henry Taylor", "department": "Operations"},
        {"id": "emp_009", "name": "Ivy Chen", "department": "Engineering"},
        {"id": "emp_010", "name": "Jack Anderson", "department": "Design"},
    ]
    
    swipes = []
    start_date = datetime.now(timezone.utc) - timedelta(days=5*365)  # 5 years ago
    
    for emp in employees:
        current_date = start_date
        while current_date <= datetime.now(timezone.utc):
            # Skip weekends (Saturday=5, Sunday=6)
            if current_date.weekday() < 5:
                # Generate realistic entrance time (7:00 AM - 10:00 AM)
                entrance_hour = random.randint(7, 9)
                entrance_minute = random.randint(0, 59)
                entrance_time = current_date.replace(hour=entrance_hour, minute=entrance_minute, second=0, microsecond=0)
                
                # Generate realistic exit time (4:00 PM - 8:00 PM, at least 6 hours after entrance)
                exit_hour = random.randint(16, 19)
                exit_minute = random.randint(0, 59)
                exit_time = current_date.replace(hour=exit_hour, minute=exit_minute, second=0, microsecond=0)
                
                # Ensure exit is after entrance
                if exit_time <= entrance_time:
                    exit_time = entrance_time + timedelta(hours=8)
                
                # Create entrance swipe
                swipes.append(make_object(
                    id=f"swipe_{uuid.uuid4().hex[:8]}",
                    types=["swipe", "entrance"],
                    source="badge_system",
                    properties={
                        "employee_id": emp["id"],
                        "employee_name": emp["name"],
                        "department": emp["department"],
                        "date": entrance_time.strftime("%Y-%m-%d"),
                        "time": entrance_time.strftime("%H:%M:%S"),
                        "entrance_or_exit": "entrance",
                        "timestamp": timestamp(entrance_time),
                    }
                ))
                
                # Create exit swipe
                swipes.append(make_object(
                    id=f"swipe_{uuid.uuid4().hex[:8]}",
                    types=["swipe", "exit"],
                    source="badge_system",
                    properties={
                        "employee_id": emp["id"],
                        "employee_name": emp["name"],
                        "department": emp["department"],
                        "date": exit_time.strftime("%Y-%m-%d"),
                        "time": exit_time.strftime("%H:%M:%S"),
                        "entrance_or_exit": "exit",
                        "timestamp": timestamp(exit_time),
                    }
                ))
            
            current_date += timedelta(days=1)
    
    return swipes


def fetch_data():    
    # Also include some basic employee records
    employees = [
        make_object(
            id="emp_001",
            types=["person", "employee"],
            source="hr_system",
            properties={
                "name": "Alice Johnson",
                "department": "Engineering",
                "hired_at": timestamp(datetime.now(timezone.utc)),
                "swipes": link("swipe[.employee_id == 'emp_001']", "Swipes"),
                "date": '2025-06-06'
            }
        ),
        make_object(
            id="emp_002",
            types=["person", "employee"],
            source="hr_system",
            properties={
                "name": "Bob Smith",
                "department": "Engineering",
                "hired_at": timestamp(datetime.now(timezone.utc)),
                "swipes": link("swipe[.employee_id == 'emp_002']", "Swipes"),
                "date": '2025-06-05'
            }
        ),
        make_object(
            id="emp_003",
            types=["person", "employee"],
            source="hr_system",
            properties={
                "name": "Carol Davis",
                "department": "Design",
                "hired_at": timestamp(datetime.now(timezone.utc)),
                "swipes": link("swipe[.employee_id == 'emp_003']", "Swipes"),
                "date": '2025-06-04'
            }
        ),
    ]
    
    return employees


def lazy_load_data(scope: Scope, conditions: list[tuple[str, str, str]], plan_only: bool, id_types: set[tuple[str, str]]) -> tuple[list[dict], str]:
    """
    Lazy load data based on the query scope.
    
    Args:
        scope: The scope for the query
        conditions: The conditions for the query
        plan_only: If True, only return the plan without fetching data
        id_types: The id_types for the query
    Returns:
        Tuple of (sa_objects, plan_description)
    """
    # Build plan description
    plan_parts = [f"Lazy loading {scope.type} objects"]
    if conditions:
        plan_parts.append(f"with conditions: {conditions}")
    if plan_only:
        plan_parts.append("(plan only - no data fetched)")
    else:
        plan_parts.append("(data fetched)")
    
    plan = " | ".join(plan_parts)
    
    if plan_only:
        return [], plan
    
    if scope.type == "swipe":
        # Check if date condition is provided
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
        
        # Generate swipes for the specific date
        try:
            target_date = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise Exception(f"Invalid date format: '{value}'. Expected format: YYYY-MM-DD")
        swipes = generate_swipes_for_date(target_date)

        return swipes, plan
    
    elif scope.type == "employee":
        employee_ids = [id_ for id_, type_ in id_types if type_ == "employee"]

        if len(employee_ids) == 0:
            return [], plan

        if len(employee_ids) != 1:
            raise Exception(f"You can only get one employee at a time, got {len(employee_ids)}")
        
        # Generate employee with favorite fields
        employee = generate_employee_with_favorites(employee_ids[0])
        
        return [employee], plan
    elif scope.type == "simple":
        return [
            make_object(
                id="simple_001",
                types=["simple"],
                source="simple_provider",
                properties={
                    "one": "one",
                    "two": "two",
                    "three": "three"
                }
            ),
            make_object(
                id="simple_002",
                types=["simple"],
                source="simple_provider",
                properties={
                    "one": "one",
                    "two": "two",
                    "three": "three"
                }
            ),
            make_object(
                id="simple_003",
                types=["simple"],
                source="simple_provider",
                properties={
                    "one": "one",
                    "two": "two",
                    "three": "three"
                }
            ),
        ], plan
    else:
        # Decline request for unsupported types
        raise Exception(f"Lazy loading not supported for type: {scope.type}")


def generate_swipes_for_date(target_date: datetime.date) -> list[dict]:
    """Generate swipes for a specific date."""
    employees = [
        {"id": "emp_001", "name": "Alice Johnson", "department": "Engineering"},
        {"id": "emp_002", "name": "Bob Smith", "department": "Engineering"},
        {"id": "emp_003", "name": "Carol Davis", "department": "Design"},
        {"id": "emp_004", "name": "David Wilson", "department": "Marketing"},
        {"id": "emp_005", "name": "Eva Brown", "department": "Sales"},
        {"id": "emp_006", "name": "Frank Miller", "department": "HR"},
        {"id": "emp_007", "name": "Grace Lee", "department": "Finance"},
        {"id": "emp_008", "name": "Henry Taylor", "department": "Operations"},
        {"id": "emp_009", "name": "Ivy Chen", "department": "Engineering"},
        {"id": "emp_010", "name": "Jack Anderson", "department": "Design"},
    ]
    
    swipes = []
    
    # Skip weekends
    if target_date.weekday() >= 5:
        return swipes
    
    for emp in employees:
        # Generate realistic entrance time (7:00 AM - 10:00 AM)
        entrance_hour = random.randint(7, 9)
        entrance_minute = random.randint(0, 59)
        entrance_time = datetime.combine(target_date, datetime.min.time().replace(hour=entrance_hour, minute=entrance_minute))
        entrance_time = entrance_time.replace(tzinfo=timezone.utc)
        
        # Generate realistic exit time (4:00 PM - 8:00 PM, at least 6 hours after entrance)
        exit_hour = random.randint(16, 19)
        exit_minute = random.randint(0, 59)
        exit_time = datetime.combine(target_date, datetime.min.time().replace(hour=exit_hour, minute=exit_minute))
        exit_time = exit_time.replace(tzinfo=timezone.utc)
        
        # Ensure exit is after entrance
        if exit_time <= entrance_time:
            exit_time = entrance_time + timedelta(hours=8)

        date_tomorrow = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Create entrance swipe
        swipes.append(make_object(
            id=f"swipe_{uuid.uuid4().hex[:8]}",
            types=["swipe"],
            source="badge_system",
            properties={
                "employee_id": emp["id"],
                "employee_name": emp["name"],
                "department": emp["department"],
                "date": entrance_time.strftime("%Y-%m-%d"),
                "time": entrance_time.strftime("%H:%M:%S"),
                "entrance_or_exit": "entrance",
                "timestamp": timestamp(entrance_time),
                "next_entrance": link(f"swipe[.employee_id == '{emp['id']}'][.entrance_or_exit == 'entrance'][.date == '{date_tomorrow}']", "Next entrance")
            }
        ))
        
        # Create exit swipe
        swipes.append(make_object(
            id=f"swipe_{uuid.uuid4().hex[:8]}",
            types=["swipe"],
            source="badge_system",
            properties={
                "employee_id": emp["id"],
                "employee_name": emp["name"],
                "department": emp["department"],
                "date": exit_time.strftime("%Y-%m-%d"),
                "time": exit_time.strftime("%H:%M:%S"),
                "entrance_or_exit": "exit",
                "timestamp": timestamp(exit_time),
                "next_exit": link(f"swipe[.employee_id == '{emp['id']}'][.entrance_or_exit == 'exit'][.date == '{date_tomorrow}']", "Next exit")
            }
        ))
    
    return swipes


def generate_employee_with_favorites(employee_id: str) -> dict:
    """Generate an employee with favorite fields based on their ID."""
    # Define employee data with favorite fields
    employee_data = {
        "emp_001": {
            "name": "Alice Johnson",
            "department": "Engineering",
            "favorite_color": "blue",
            "favorite_number": 42,
            "favorite_shape": "circle"
        },
        "emp_002": {
            "name": "Bob Smith", 
            "department": "Engineering",
            "favorite_color": "green",
            "favorite_number": 7,
            "favorite_shape": "triangle"
        },
        "emp_003": {
            "name": "Carol Davis",
            "department": "Design", 
            "favorite_color": "purple",
            "favorite_number": 13,
            "favorite_shape": "hexagon"
        },
        "emp_004": {
            "name": "David Wilson",
            "department": "Marketing",
            "favorite_color": "red",
            "favorite_number": 99,
            "favorite_shape": "square"
        },
        "emp_005": {
            "name": "Eva Brown",
            "department": "Sales",
            "favorite_color": "yellow",
            "favorite_number": 3,
            "favorite_shape": "diamond"
        },
        "emp_006": {
            "name": "Frank Miller",
            "department": "HR",
            "favorite_color": "orange",
            "favorite_number": 21,
            "favorite_shape": "oval"
        },
        "emp_007": {
            "name": "Grace Lee",
            "department": "Finance",
            "favorite_color": "pink",
            "favorite_number": 8,
            "favorite_shape": "star"
        },
        "emp_008": {
            "name": "Henry Taylor",
            "department": "Operations",
            "favorite_color": "teal",
            "favorite_number": 55,
            "favorite_shape": "rectangle"
        },
        "emp_009": {
            "name": "Ivy Chen",
            "department": "Engineering",
            "favorite_color": "indigo",
            "favorite_number": 14,
            "favorite_shape": "pentagon"
        },
        "emp_010": {
            "name": "Jack Anderson",
            "department": "Design",
            "favorite_color": "coral",
            "favorite_number": 1,
            "favorite_shape": "heart"
        }
    }
    
    if employee_id not in employee_data:
        raise Exception(f"Employee with ID '{employee_id}' not found")
    
    emp_info = employee_data[employee_id]
    
    return make_object(
        id=employee_id,
        types=["person", "employee"],
        source="hr_system_extra",
        properties={
            "favorite_color": emp_info["favorite_color"],
            "favorite_number": emp_info["favorite_number"],
            "favorite_shape": emp_info["favorite_shape"],
            "entrances": link(f"swipe[.employee_id == '{employee_id}'][.entrance_or_exit == 'entrance']", "Entrance swipes")
        }
    )


if __name__ == "__main__":
    # Define lazy loading scopes
    lazy_scopes = [
        Scope(type="swipe", fields=["employee_id", "employee_name", "department", "date", "time", "entrance_or_exit", "timestamp"], filtering_fields=['date'], needs_id_types=False),
        Scope(type="employee", fields=["favorite_color", "favorite_number", "favorite_shape", "entrances"], filtering_fields=[], needs_id_types=True),
        Scope(type="simple", fields=["one", "two", "three"], filtering_fields=[], needs_id_types=False)
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