import time
import logging
import pandas as pd
from pathlib import Path


from src.decoders.asterix_file_reader import AsterixFileReader
from src.types.enums import Category
from src.exporters.asterix_exporter import AsterixExporter
from src.utils.asterix_filter import AsterixFilter
from src.utils.handlers import decode_records


def main():
    # ============================================================
    # LOGGING CONFIGURATION
    # ============================================================
    LOG_LEVEL = logging.WARNING

    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("src").setLevel(LOG_LEVEL)

    # ============================================================
    # PATHS
    # ============================================================
    base_dir = Path(__file__).resolve().parent.parent
    input_file = base_dir / "data" / "samples" / "datos_asterix_adsb.ast"
    output_dir = base_dir / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "asterix_processed.csv"

    print(f"\n{'=' * 70}")
    print("ASTERIX Unified Decoder & Processor (CAT021 + CAT048)")
    print(f"{'=' * 70}")
    print(f"Input file: {input_file}")
    print(f"{'=' * 70}\n")

if __name__ == "__main__":
    main()
