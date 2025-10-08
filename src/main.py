import time
import logging
import pandas as pd
from pathlib import Path

from src.decoders.asterix_file_reader import AsterixFileReader
from src.decoders.cat048_decoder import Cat048Decoder
from src.utils.csv_exporter import Cat048CSVExporter, Cat048AnalysisHelper


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
    logging.getLogger("src").setLevel(LOG_LEVEL)

    # ============================================================
    # PATHS
    # ============================================================
    base_dir = Path(__file__).resolve().parent.parent
    input_file = base_dir / "data" / "samples" / "datos_asterix_radar.ast"
    output_dir = base_dir / "data" / "output"
    output_dir.mkdir(exist_ok=True)
    output_csv = output_dir / "cat048_decoded.csv"

    # ============================================================
    # READ RAW RECORDS
    # ============================================================
    reader = AsterixFileReader(str(input_file))
    records = list(reader.read_records())

    print(f"\n{'=' * 60}")
    print("ASTERIX CAT048 Decoder")
    print(f"{'=' * 60}")
    print(f"Input file: {input_file}")
    print(f"Total records loaded: {len(records)}")
    if records:
        print(f"Before decoding: Record 0 has {len(records[0].items)} items")
    print(f"{'=' * 60}\n")

    # ============================================================
    # DECODE
    # ============================================================
    decoder = Cat048Decoder()
    start_time = time.perf_counter()

    for rec in records:
        decoder.decode_record(rec)

    elapsed_time = time.perf_counter() - start_time

    print(f"\n{'=' * 60}")
    print("Decoding Results")
    print(f"{'=' * 60}")
    if records:
        print(f"After decoding: Record 0 has {len(records[0].items)} items")
    print("\nPerformance Metrics:")
    print(f"  Total time:          {elapsed_time:.4f} seconds")
    if records:
        print(f"  Time per record:     {elapsed_time / len(records) * 1000:.3f} ms")
    print(f"  Throughput:          {len(records) / elapsed_time:.2f} records/sec" if elapsed_time > 0 else "  Throughput:          N/A")
    print(f"{'=' * 60}\n")

    # ============================================================
    # CONVERT TO PANDAS DATAFRAME (one row per record)
    # Includes QNH correction: ALT_QNH_ft, QNH_CORRECTED
    # ============================================================
    print("Converting to pandas DataFrame...")
    exporter = Cat048CSVExporter()
    df = exporter.records_to_dataframe(records)

    print(f"DataFrame created: {len(df)} rows x {len(df.columns)} columns")
    print(f"\nColumns: {', '.join(df.columns.tolist())}")

    if not df.empty:
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print("\nPreview (top 10):")
        print(df.head(10))

    # ============================================================
    # STATISTICS
    # ============================================================
    print(f"\n{'=' * 60}")
    print("Dataset Statistics:")
    print(f"{'=' * 60}")
    stats = Cat048AnalysisHelper.get_statistics(df)
    for key, value in stats.items():
        print(f"{key:25s}: {value}")

    # ============================================================
    # EXAMPLE FILTERS
    # ============================================================
    print(f"\n{'=' * 60}")
    print("Example Filters:")
    print(f"{'=' * 60}")
    print(f"Airborne aircraft:     {len(Cat048AnalysisHelper.filter_airborne(df))}")
    print(f"Aircraft above FL300:  {len(Cat048AnalysisHelper.filter_by_altitude(df, min_fl=300))}")
    print(f"Ryanair flights:       {len(Cat048AnalysisHelper.filter_by_callsign(df, 'RYR'))}")

    # ============================================================
    # EXPORT TO CSV
    # ============================================================
    df.to_csv(output_csv, index=False, na_rep='N/A')

    print(f"\n{'=' * 60}")
    print(f"CSV exported to: {output_csv}")
    print(f"{'=' * 60}\n")

    print([i.item_type for i in records[4].items])


if __name__ == "__main__":
    main()
