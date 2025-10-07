import time
import logging
from pathlib import Path
from src.decoders.asterix_file_reader import AsterixFileReader
from src.decoders.cat048_decoder import Cat048Decoder


def main():
    # ============================================================
    # LOGGING CONFIGURATION - Change level here as needed
    # ============================================================
    LOG_LEVEL = logging.WARNING  # Change to DEBUG, INFO, WARNING, ERROR, or CRITICAL

    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Ensure all src.* loggers respect the same level
    logging.getLogger("src").setLevel(LOG_LEVEL)

    # ============================================================
    # DECODING PROCESS
    # ============================================================
    base_dir = Path(__file__).resolve().parent.parent
    file_path = base_dir / "data" / "samples" / "datos_asterix_radar.ast"

    # Read records
    reader = AsterixFileReader(str(file_path))
    records = list(reader.read_records())

    print(f"\n{'=' * 60}")
    print(f"ASTERIX CAT048 Decoder")
    print(f"{'=' * 60}")
    print(f"Total records loaded: {len(records)}")
    print(f"Before decoding: Record 0 has {len(records[0].items)} items")
    print(f"{'=' * 60}\n")

    # Initialize decoder
    decoder = Cat048Decoder()

    # Decode with timing
    start_time = time.perf_counter()  # Use perf_counter for better precision

    for rec in records:
        decoder.decode_record(rec)

    elapsed_time = time.perf_counter() - start_time

    # Results
    print(f"\n{'=' * 60}")
    print(f"Decoding Results")
    print(f"{'=' * 60}")
    print(f"After decoding: Record 0 has {len(records[0].items)} items")
    print(f"\nPerformance Metrics:")
    print(f"  Total time:          {elapsed_time:.4f} seconds")
    print(f"  Time per record:     {elapsed_time / len(records) * 1000:.3f} ms")
    print(f"  Throughput:          {len(records) / elapsed_time:.2f} records/sec")
    print(f"{'=' * 60}\n")

    print(records[0].items)

if __name__ == "__main__":
    main()
