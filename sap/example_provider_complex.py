#!/usr/bin/env python3
"""
Example SAP Provider - Employee Data

This example demonstrates how to create a data provider using the SAP library.
It serves employee data with automatic caching and HTTP API endpoints.
"""

from datetime import datetime
from sap import SAPServer, make_object, timestamp, link


def fetch_employee_data():
    """
    Fetch employee data from your data source.
    
    In a real application, this could be:
    - Database queries
    - API calls to external services
    - File system operations
    - Web scraping
    
    Returns:
        List of SAP objects (dictionaries with SA metadata)
    """
    # Simulate fetching data from a database or external source
    employees = [
        make_object(
            id="emp_001",
            types=["person", "employee", "developer"],
            source="hr_system",
            name="Alice Johnson",
            email="alice.johnson@company.com",
            department="Engineering",
            position="Senior Developer",
            salary=85000,
            hired_at=timestamp(datetime(2022, 3, 15)),
            skills=["Python", "JavaScript", "React"],
            manager=link(".filter(.equals(.get_field('name'), 'Bob Smith'))", "Bob Smith"),
            profile_url="https://company.com/employees/alice-johnson",
            is_active=True,
            all=link("*", "All employees"),
        ),
        make_object(
            id="emp-42",
            types=["person", "employee", "developer"],
            source="hr_system",
            name="Alice Johnson",
            email="alice.johnson@company.com",
            department="Engineering",
            position="Senior Developer",
            salary=85000,
            hired_at=timestamp(datetime(2022, 3, 15)),
            skills=["Python", "JavaScript", "React"],
            manager=link(".filter(.equals(.get_field('name'), 'Bob Smith'))", "Bob Smith"),
            profile_url="https://company.com/employees/alice-johnson",
            is_active=True,
        ),
        make_object(
            id="emp_002",
            types=["person", "employee", "manager"],
            source="hr_system",
            name="Bob Smith",
            email="bob.smith@company.com",
            department="Engineering",
            position="Engineering Manager",
            salary=95000,
            hired_at=timestamp(datetime(2021, 6, 10)),
            skills=["Python", "Leadership", "Project Management"],
            team_size=8,
            reports_to=link("employee#emp_003", "Carol Davis"),
            profile_url="https://company.com/employees/bob-smith",
            is_active=True,
        ),
        make_object(
            id="emp_003",
            types=["person", "employee", "designer"],
            source="hr_system",
            name="Carol Davis",
            email="carol.davis@company.com",
            department="Design",
            position="UX Designer",
            salary=78000,
            hired_at=timestamp(datetime(2023, 1, 20)),
            skills=["Figma", "Adobe Creative Suite", "User Research"],
            portfolio_url="https://caroldavis.design",
            profile_url="https://company.com/employees/carol-davis",
            is_active=True,
        ),
        make_object(
            id="obj_A",
            types=["instance"],
            source="source_A",
            lol=42,
        ),
        make_object(
            id="obj_A",
            types=["mds", "instance"],
            source="source_B",
            lol=21,
        ),
        make_object(
            id="obj_A",
            types=["mds", "cpu_core"],
            source="source_C",
            hello=11,
        ),
        make_object(
            id="obj_B",
            types=["type_B"],
            source="source_B",
        ),
    ]

    print(42)

    # create 100k large objects
    for i in range(100000):
        break
        employees.append(make_object(
            id=f"emp_{i+10}",
            types=["person", "employee", "lol"],
            favorite_colors=["red", "blue"],
            source="hr_system",
            name=f"Employee {i}",
            best_friend=link("#emp_001", "Bob Smith"),
            **{f"field_{j}": j for j in range(50)},
        ))

    print(f"Created {len(employees)} employees")
    
    return employees


def main():
    """Main function to run the SAP provider server."""
    
    # Configure the SAP server
    server = SAPServer(
        provider=dict(
            name="Company HR Provider",
            description="Example HR data provider serving employee information",
            version="1.0.0"
        ),
        fetch_fn=fetch_employee_data,
        interval_seconds=60,  # Refresh data every 60 seconds
        run_immediately=True,  # Start fetching data immediately
    )
    
    print("Starting Company HR Provider...")
    print("Server will be available at: http://localhost:8080")
    print("Data will refresh every 60 seconds")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        # Start the server
        server.run(
            port=8080,
            register_with_shell=True,  # Register with SA shell if available
            auto_port=False,  # Use fixed port 8080
        )
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error running server: {e}")


if __name__ == "__main__":
    main()
