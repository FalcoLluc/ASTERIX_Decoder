from src.decoders.cat021_decoder import Cat021Decoder
from src.decoders.cat048_decoder import Cat048Decoder
from src.models.record import Record
from src.types.enums import Category
from typing import List
import logging

def decode_records(records: List[Record]) -> List[Record]:
    """
    Decode a list of records by routing each to the appropriate decoder based on category.

    Args:
        records: List of Record objects with raw data

    Returns:
        Same list of records, now with decoded items populated
    """
    # Initialize decoders
    cat021_decoder = Cat021Decoder()
    cat048_decoder = Cat048Decoder()

    # Decode each record based on its category
    for record in records:
        if record.category == Category.CAT021:
            cat021_decoder.decode_record(record)
        elif record.category == Category.CAT048:
            cat048_decoder.decode_record(record)
        else:
            logging.warning(f"Unknown category: {record.category}")

    return records