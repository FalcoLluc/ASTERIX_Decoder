from dataclasses import dataclass
from typing import  Union, Any
from src.types.enums import CAT021ItemType, CAT048ItemType, Category

@dataclass
class Item:
    """Unified item model for ASTERIX records."""
    item_offset: int
    length: int
    frn: int
    item_type: Union[CAT021ItemType,CAT048ItemType]
    value: Any  # Decoded value of the item