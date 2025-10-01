from pathlib import Path
from src.decoders.asterix_file_reader import AsterixFileReader
from src.decoders.cat048_decoder import Cat048Decoder

def main():
    base_dir = Path(__file__).resolve().parent.parent  # Navigate to the project root
    file_path = base_dir / "data" / "samples" / "datos_asterix_radar.ast"

    reader = AsterixFileReader(str(file_path))
    records = list(reader.read_records())

    decoder = Cat048Decoder()
    h=decoder._parse_fspec(records[0].raw_data)
    print(h)


if __name__ == "__main__":
    main()
