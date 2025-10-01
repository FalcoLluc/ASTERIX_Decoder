from abc import ABC, abstractmethod
from src.models.record import Record


class AsterixDecoderBase(ABC):
    @abstractmethod
    def decode_record(self, record: Record) -> Record:
        pass