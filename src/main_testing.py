"""
Visualizador de registros decodificados ASTERIX CAT048 y CAT021
Muestra los primeros 10 registros de cada archivo con todos sus items decodificados
"""

from pathlib import Path
from src.decoders.asterix_file_reader import AsterixFileReader
from src.decoders.cat048_decoder import Cat048Decoder
from src.decoders.cat021_decoder import Cat021Decoder
import logging


def show_cat048_records():
    """Muestra los primeros 10 registros CAT048 (Radar)"""
    print("\n" + "=" * 80)
    print(" ASTERIX CAT048 - PRIMEROS 10 REGISTROS (RADAR)")
    print("=" * 80)

    base_dir = Path(__file__).resolve().parent.parent
    file_path = base_dir / "data" / "samples" / "datos_asterix_radar.ast"

    reader = AsterixFileReader(str(file_path))
    records = list(reader.read_records())

    decoder = Cat048Decoder()

    for i, rec in enumerate(records[:10]):  # First 10 records
        print(f"\n{'─' * 80}")
        print(f" REGISTRO CAT048 #{i + 1}")
        print(f"{'─' * 80}")
        print(f"  Block offset: {rec.block_offset}")
        print(f"  Length: {rec.length} bytes")
        print(f"  Raw data length: {len(rec.raw_data)} bytes")

        # Parse FSPEC to see what items are present
        fspec_items, data_start = decoder._parse_fspec(rec)
        print(f"  Items en FSPEC: {len(fspec_items)}")

        # Actually decode the record
        decoded_record = decoder.decode_record(rec)
        print(f"  Items decodificados: {len(decoded_record.items)}")

        print(f"\n  VALORES DECODIFICADOS:")
        # Show the actual decoded values
        for k, item in enumerate(decoded_record.items, 1):
            print(f"    {k}. {item.item_type.name}:")
            print(f"       {item.value}")


def show_cat021_records():
    """Muestra los primeros 10 registros CAT021 (ADS-B)"""
    print("\n" + "=" * 80)
    print(" ASTERIX CAT021 - PRIMEROS 10 REGISTROS (ADS-B)")
    print("=" * 80)

    base_dir = Path(__file__).resolve().parent.parent
    file_path = base_dir / "data" / "samples" / "datos_asterix_adsb.ast"

    reader = AsterixFileReader(str(file_path))
    records = list(reader.read_records())

    decoder = Cat021Decoder()

    for i, rec in enumerate(records[:50]):  # First 10 records
        print(f"\n{'─' * 80}")
        print(f" REGISTRO CAT021 #{i + 1}")
        print(f"{'─' * 80}")
        print(f"  Block offset: {rec.block_offset}")
        print(f"  Length: {rec.length} bytes")
        print(f"  Raw data length: {len(rec.raw_data)} bytes")

        # Parse FSPEC to see what items are present
        fspec_items, data_start = decoder._parse_fspec(rec)
        print(f"  Items en FSPEC: {len(fspec_items)}")

        # Actually decode the record
        decoded_record = decoder.decode_record(rec)
        print(f"  Items decodificados: {len(decoded_record.items)}")

        print(f"\n   VALORES DECODIFICADOS:")
        # Show the actual decoded values
        for k, item in enumerate(decoded_record.items, 1):
            print(f"    {k}. {item.item_type.name}:")

            # Format specific items for better readability
            if item.item_type.name == "DATA_SOURCE_IDENTIFICATION":
                print(f"       SAC: {item.value['SAC']}, SIC: {item.value['SIC']}")
            elif item.item_type.name == "POSITION_WGS84_HIGH_RES":
                print(f"       Lat: {item.value['latitude']:.8f}°")
                print(f"       Lon: {item.value['longitude']:.8f}°")
            elif item.item_type.name == "TARGET_ADDRESS":
                print(f"       ICAO: {item.value['target_address_hex']}")
            elif item.item_type.name == "TARGET_IDENTIFICATION":
                print(f"       Callsign: '{item.value['callsign']}'")
            elif item.item_type.name == "FLIGHT_LEVEL":
                print(f"       FL: {item.value['flight_level']:.2f} ({item.value['altitude_feet']:.0f} ft)")
            elif item.item_type.name == "TIME_MESSAGE_RECEPTION_POSITION":
                print(f"       Time: {item.value['time_string']}")
            else:
                print(f"       {item.value}")


def main():
    # Configure root logging once at startup
    logging.basicConfig(
        level=logging.WARNING,  # Changed to WARNING to reduce output verbosity
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Optional: be explicit about your project's logger tree
    logging.getLogger("src").setLevel(logging.WARNING)

    print("\n" + "=" * 80)
    print(" VISUALIZADOR DE REGISTROS ASTERIX")
    print("=" * 80)

    # Show CAT048 records
    show_cat048_records()

    # Show CAT021 records
    show_cat021_records()

    print("\n" + "=" * 80)
    print(" VISUALIZACIÓN COMPLETADA")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
