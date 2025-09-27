import mmap
from typing import Iterator, Union
from src.models.asterix_base import AsterixBase
from src.models.cat021_record import CAT021Record
from src.models.cat048_record import CAT048Record


class AsterixFileReader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def read_records(self) -> Iterator[Union[CAT021Record, CAT048Record]]:
        """Efficiently read Asterix records using memory mapping."""
        with open(self.file_path, 'rb') as file:
            with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                position = 0
                file_size = len(mmapped_file)

                # Ensures there are at least 3 bytes left (minimum ASTERIX record = 1 byte category + 2 bytes length)
                # If we are further than that, no more records exist in the file
                while position < file_size - 3:
                    # Store Block Offset (position of the record in the file)
                    block_offset = position

                    # Read category (1 byte)
                    category = mmapped_file[position]
                    position += 1

                    # Read length (2 bytes, big-endian)
                    if position + 1 >= file_size:
                        break

                    length_bytes = mmapped_file[position:position + 2]
                    length = int.from_bytes(length_bytes, byteorder="big")
                    position += 2

                    # Validate length
                    if length < 3 or position + (length - 3) > file_size:
                        break

                    # Extract data
                    data = mmapped_file[position:position + (length - 3)]
                    position += (length - 3)

                    # Create appropriate record based on category
                    base_record = AsterixBase(
                        category=category,
                        length=length,
                        raw_data=data,
                        block_offset=block_offset
                    )

                    if category == 21:
                        yield CAT021Record(**base_record.__dict__)
                    elif category == 48:
                        yield CAT048Record(**base_record.__dict__)
                    else:
                        # Skip unsupported categories or handle as base
                        continue