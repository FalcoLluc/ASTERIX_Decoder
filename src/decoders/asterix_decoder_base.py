from abc import ABC, abstractmethod
import logging
from src.models.record import Record


class AsterixDecoderBase(ABC):
    def __init__(self) -> None:
        # Initialize a per-instance logger; subclasses should call super().__init__()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def decode_record(self, record: Record) -> Record:
        pass