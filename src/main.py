from pathlib import Path
from src.utils.asterix_file_reader import AsterixFileReader

def main():
    base_dir = Path(__file__).resolve().parent.parent  # Navigate to the project root
    file_path = base_dir / "data" / "samples" / "datos_asterix_adsb.ast"

    reader = AsterixFileReader(str(file_path))

if __name__ == "__main__":
    main()
