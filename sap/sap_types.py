from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence, Union


def _to_ns(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1_000_000_000)


@dataclass(frozen=True)
class Timestamp:
    value_ns: int

    @staticmethod
    def from_datetime(dt: datetime) -> "Timestamp":
        return Timestamp(_to_ns(dt))

    @staticmethod
    def from_seconds(seconds: float) -> "Timestamp":
        return Timestamp(int(seconds * 1_000_000_000))

    def to_sa_primitive(self) -> dict[str, int]:
        return {"__sa_type__": "timestamp", "timestamp": self.value_ns}


@dataclass(frozen=True)
class Link:
    query: str
    show_text: str

    def to_sa_primitive(self) -> dict[str, str]:
        return {"__sa_type__": "link", "query": self.query, "show_text": self.show_text}


def timestamp(value: Union[datetime, float, int]) -> Timestamp:
    if isinstance(value, datetime):
        return Timestamp.from_datetime(value)
    if isinstance(value, float):
        return Timestamp.from_seconds(value)
    if isinstance(value, int):
        return Timestamp(value)
    raise TypeError("timestamp() expects datetime, float seconds, or int nanoseconds")


def link(query: str, show_text: str) -> Link:
    return Link(query=query, show_text=show_text)


def encode_value(value: Any) -> Any:
    # Custom types
    if isinstance(value, Timestamp):
        return value.to_sa_primitive()
    if isinstance(value, Link):
        return value.to_sa_primitive()
    # Auto-convert datetimes to Timestamp
    if isinstance(value, datetime):
        return Timestamp.from_datetime(value).to_sa_primitive()
    # Collections
    if isinstance(value, Mapping):
        return {k: encode_value(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [encode_value(v) for v in value]
    return value