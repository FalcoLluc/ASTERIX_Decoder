from pathlib import Path
from src.utils.asterix_file_reader import AsterixFileReader

def main():
    base_dir = Path(__file__).resolve().parent.parent  # Navigate to the project root
    file_path = base_dir / "data" / "samples" / "datos_asterix_adsb.ast"

    reader = AsterixFileReader(str(file_path))

    print(f"Reading records from: {file_path}\n")

    for record in reader.read_records():
        if record.category == 21:
            print(f"CAT021 Record at offset {record.block_offset}:")
            print(f"  Length: {record.length} bytes")
            print(f"  Raw Data (first 10 bytes): {record.raw_data[:10]}")
        elif record.category == 48:
            print(f"CAT048 Record at offset {record.block_offset}:")
            print(f"  Length: {record.length} bytes")
            print(f"  Raw Data (first 10 bytes): {record.raw_data[:10]}")
        else:
            print(f"Unsupported category {record.category} at offset {record.block_offset}")

if __name__ == "__main__":
    main()
