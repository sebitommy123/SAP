from dataclasses import dataclass
from .scope import Scope

@dataclass
class QueryScope:
    scope: Scope
    conditions: list[tuple[str, str, str]]  # (field, operator, value)
