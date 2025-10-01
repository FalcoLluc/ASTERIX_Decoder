from pathlib import Path
from src.decoders.asterix_file_reader import AsterixFileReader
from src.decoders.cat048_decoder import Cat048Decoder


def main():
    base_dir = Path(__file__).resolve().parent.parent
    file_path = base_dir / "data" / "samples" / "datos_asterix_radar.ast"

    reader = AsterixFileReader(str(file_path))
    records = list(reader.read_records())

    decoder = Cat048Decoder()

    print("First 10 records and their items:")
    print("=" * 50)

    for i, rec in enumerate(records[:10]):  # First 10 records
        print(f"\nRecord {i}:")
        print(f"  Block offset: {rec.block_offset}")
        print(f"  Length: {rec.length} bytes")
        print(f"  Raw data length: {len(rec.raw_data)} bytes")

        # Parse FSPEC to see what items are present
        fspec_items, data_start = decoder._parse_fspec(rec)

        print(f"  Items in FSPEC ({len(fspec_items)}):")
        for j, item_type in enumerate(fspec_items):
            decoder_func = decoder.decoder_map.get(item_type)
            print(f"    {j + 1}. {item_type.name} -> {decoder_func.__name__}")

        # Actually decode the record to see the values
        decoded_record = decoder.decode_record(rec)
        print(f"  Decoded items: {len(decoded_record.items)}")

        # Show the actual decoded values for first few items
        for k, item in enumerate(decoded_record.items[:3]):  # First 3 items
            print(f"    {k + 1}. {item.item_type.name}: {item.value}")


if __name__ == "__main__":
    main()