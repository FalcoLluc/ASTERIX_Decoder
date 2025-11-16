from src.decoders.cat021_decoder import Cat021Decoder
from src.decoders.cat048_decoder import Cat048Decoder
from src.models.record import Record
from src.types.enums import Category
from typing import List, Iterable, Iterator
import logging

_cat021_decoder = Cat021Decoder()
_cat048_decoder = Cat048Decoder()

def decode_records(records: List[Record]) -> List[Record]:
    """
    Decode a list of records by routing each to the appropriate decoder based on category.

    Uses module-level singleton decoders to avoid repeated initialization.
    """
    for record in records:
        if record.category == Category.CAT021:
            _cat021_decoder.decode_record(record)
        elif record.category == Category.CAT048:
            _cat048_decoder.decode_record(record)
        else:
            logging.warning(f"Unknown category: {record.category}")

    return records


def decode_records_iter(records: Iterable[Record]) -> Iterator[Record]:
    """
    Decode records lazily and yield them one by one.
    This avoids materializing the entire list before decoding/exporting.
    """
    for record in records:
        if record.category == Category.CAT021:
            _cat021_decoder.decode_record(record)
        elif record.category == Category.CAT048:
            _cat048_decoder.decode_record(record)
        else:
            logging.warning(f"Unknown category: {record.category}")
        yield record
