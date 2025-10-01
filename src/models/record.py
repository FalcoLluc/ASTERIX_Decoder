from dataclasses import dataclass, field
from typing import List
from .item import Item
from src.types.enums import Category


@dataclass
class Record:
    """Unified record model for ASTERIX data."""
    category: Category
    length: int
    raw_data: bytes
    block_offset: int # Inici Record Respecte Arxiu
    items: List[Item]