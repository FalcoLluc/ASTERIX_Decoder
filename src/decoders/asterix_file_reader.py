import mmap
from typing import Iterator
from src.models.record import Record
from src.types.enums import Category


class AsterixFileReader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def read_records(self) -> Iterator[Record]:
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
                    category_int = mmapped_file[position]
                    position += 1
                    try:
                        category = Category(category_int)
                    except ValueError:
                        # Skip unsupported categories by reading length and advancing position
                        if position + 1 >= file_size:
                            break
                        length_bytes = mmapped_file[position:position + 2]
                        length = int.from_bytes(length_bytes, byteorder="big")
                        position += 2
                        if length < 3 or position + (length - 3) > file_size:
                            break
                        # Skip payload of unsupported category
                        position += (length - 3)
                        continue

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
                    base_record = Record(
                        category=category,
                        length=length,
                        raw_data=data,
                        block_offset=block_offset,
                        items=[]
                    )
                    yield base_record

    def read_record_at_position(self, start_position: int) -> Record:
        """Read a specific record at given byte position in file."""
        position = start_position
        with open(self.file_path, 'rb') as file:
            with mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                if position >= len(mmapped_file) - 3:
                    raise ValueError("Position beyond file size")

                # Read category (1 byte)
                category_int = mmapped_file[position]
                position += 1
                try:
                    category = Category(category_int)
                except ValueError:
                    # Skip unsupported categories
                    return None
                length = (mmapped_file[position + 1] << 8) | mmapped_file[position + 2]

                if length < 3 or position + length > len(mmapped_file):
                    raise ValueError("Invalid record at position")

                data = mmapped_file[position + 3:position + length]

                # Create appropriate record
                return Record(category, length, data, start_position, [])