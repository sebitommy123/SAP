from dataclasses import dataclass
from typing import Literal, Union

@dataclass
class Scope:
    type: str
    fields: Union[list[str], Literal["*"]]
    filtering_fields: list[str]
    needs_id_types: bool
