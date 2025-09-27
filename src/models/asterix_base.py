from dataclasses import dataclass

@dataclass
class AsterixBase:
    """Base class for Asterix data models."""
    category: int
    length: int
    raw_data: bytes
    block_offset: int