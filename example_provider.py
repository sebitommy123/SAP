from datetime import datetime
from sap import SAPServer, make_object, timestamp, link


def fetch_data():
    # In reality this could be a DB query or web scraping
    return [
        make_object(
            id="emp_001",
            types=["person", "employee"],
            source="demo",
            name="Alice",
            hired_at=timestamp(datetime.utcnow()),
            profile=link(".filter(.equals(.get_field('name'), 'Alice'))", "Alice's records"),
        )
    ]


if __name__ == "__main__":
    server = SAPServer(
        provider=dict(name="Demo SAP Provider", description="Example provider built with SAP"),
        fetch_fn=fetch_data,
        interval_seconds=60,
    )
    server.run(port=8080, register_with_shell=True)