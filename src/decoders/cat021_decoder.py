from src.decoders.asterix_decoder_base import AsterixDecoderBase
from src.types.enums import CAT021ItemType
from src.models.record import Record

class Cat021Decoder(AsterixDecoderBase):
    def __init__(self):
        # Map FSPEC bits (item types) to decoding methods
        self.FSPEC_TO_DECODER = {
            CAT021ItemType.TARGET_REPORT_DESCRIPTOR: self._decode_target_report_descriptor,
            CAT021ItemType.TRACK_NUMBER: self._decode_track_number,
            # Add more mappings as needed
        }

    def decode_record(self, record: Record) -> Record:
        return record

    # TO BE IMPLEMENTED
    def _decode_target_report_descriptor(self, record: Record) -> Record:
        pass
    def _decode_track_number(self, record: Record) -> Record:
        pass