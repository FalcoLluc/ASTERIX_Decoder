from src.utils.asterix_decoder_base import AsterixDecoderBase
from src.types.enums import CAT048ItemType
from src.models.record import Record

class Cat048Decoder(AsterixDecoderBase):
    def __init__(self):
        # Map FSPEC bits (item types) to decoding methods
        self.FSPEC_TO_DECODER = {
            CAT048ItemType.TARGET_REPORT_DESCRIPTOR: self._decode_target_report_descriptor,
            # Add more mappings as needed
        }

    def decode_record(self, record: Record) -> Record:
        return record

    def _decode_target_report_descriptor(self, record: Record) -> Record:
        pass