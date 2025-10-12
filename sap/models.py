from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .sap_types import encode_value


@dataclass
class SAPObject:
    id: str
    types: List[str]
    source: str
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "__types__": list(self.types),
            "__id__": self.id,
            "__source__": self.source,
        }
        for key, value in self.properties.items():
            payload[key] = encode_value(value)
        return payload


def make_object(id: str, types: List[str], source: str, **properties: Any) -> Dict[str, Any]:
    return SAPObject(id=id, types=types, source=source, properties=properties).to_json()


def normalize_objects(objs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for i, obj in enumerate(objs):
        if not isinstance(obj, dict):
            raise TypeError(f"objects[{i}] must be a dict, got {type(obj).__name__}")
        if not all(k in obj for k in ("__id__", "__types__", "__source__")):
            raise ValueError(
                f"objects[{i}] missing one of required keys __id__, __types__, __source__"
            )
        if not isinstance(obj["__id__"], str):
            raise TypeError(f"objects[{i}].__id__ must be str")
        if not isinstance(obj["__source__"], str):
            raise TypeError(f"objects[{i}].__source__ must be str")
        types = obj["__types__"]
        if not isinstance(types, list) or not all(isinstance(t, str) for t in types):
            raise TypeError(f"objects[{i}].__types__ must be list[str]")
        # Encode custom values in all fields
        enc = {k: encode_value(v) for k, v in obj.items()}
        normalized.append(enc)
    return normalized


def deduplicate_objects(objs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for obj in objs:
        key = (obj.get("__id__"), obj.get("__source__"), tuple(obj.get("__types__", [])))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(obj)
    return deduped