import time
import logging
import pandas as pd
from pathlib import Path

from src.decoders.asterix_file_reader import AsterixFileReader
from src.decoders.cat021_decoder import Cat021Decoder
from src.exporters.cat021_exporter import Cat021Exporter
from src.utils.preprocessor import AsterixPreprocessor
from src.utils.filters import Cat021AnalysisHelper


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
    output_dir.mkdir(exist_ok=True)
    output_csv = output_dir / "cat021_processed.csv"

    print(f"\n{'=' * 60}")
    print("ASTERIX CAT021 Decoder & Processor (ADS-B)")
    print(f"{'=' * 60}")
    print(f"Input file: {input_file}")
    print(f"{'=' * 60}\n")

    # ============================================================
    # STEP 1: READ & DECODE (Pure extraction)
    # ============================================================
    print("📖 Step 1: Reading and decoding ASTERIX records...")

    reader = AsterixFileReader(str(input_file))
    records = list(reader.read_records())

    decoder = Cat021Decoder()
    start_time = time.perf_counter()

    for rec in records:
        decoder.decode_record(rec)

    elapsed_time = time.perf_counter() - start_time

    print(f"   ✅ Decoded {len(records):,} records in {elapsed_time:.4f}s")
    print(f"   ⚡ Throughput: {len(records) / elapsed_time:.2f} records/sec")
    if records:
        print(f"   📊 Items per record: {len(records[0].items)}")

    # ============================================================
    # STEP 2: EXPORT TO RAW DATAFRAME (No transformations)
    # ============================================================
    print("\n📋 Step 2: Converting to raw DataFrame...")

    df_raw = Cat021Exporter.records_to_dataframe(records)

    print(f"   ✅ Created DataFrame: {len(df_raw):,} rows × {len(df_raw.columns)} columns")
    print(f"   📝 Columns: {', '.join(df_raw.columns[:10])}{'...' if len(df_raw.columns) > 10 else ''}")

    # ============================================================
    # STEP 3: PREPROCESS (geographic + ground filtering, optional QNH)
    # ============================================================
    print("\n🔧 Step 3: Applying preprocessing...")

    initial_count = len(df_raw)

    df_processed = AsterixPreprocessor.process_cat021(
        df_raw,
        apply_filters=True,  # Geographic + ground filtering
        apply_qnh=False  # Usually not needed for ADS-B
    )

    filtered_count = initial_count - len(df_processed)
    ground_removed = df_raw['GBS'].sum() if 'GBS' in df_raw.columns else 0

    print(f"   ✅ Geographic filtering: {filtered_count:,} records removed")
    print(f"   ✅ Ground targets removed: {ground_removed:,} records")
    print(f"   ✅ Final dataset: {len(df_processed):,} records")

    # ============================================================
    # STEP 4: PREVIEW
    # ============================================================
    if not df_processed.empty:
        print("\n📊 Data Preview (first 5 rows):")
        pd.set_option('display.max_columns', 12)
        pd.set_option('display.width', 120)

        # Updated column names
        preview_cols = ['Time', 'Target_address', 'Target_identification',
                        'Flight_Level', 'h_ft', 'Latitud', 'Longitud', 'GBS']  # ✅ Fixed
        available_cols = [c for c in preview_cols if c in df_processed.columns]

        if available_cols:
            print(df_processed[available_cols].head(5))

    # ============================================================
    # STEP 5: STATISTICS
    # ============================================================
    print(f"\n{'=' * 60}")
    print("📈 Dataset Statistics")
    print(f"{'=' * 60}")

    stats = Cat021AnalysisHelper.get_statistics(df_processed)
    for key, value in stats.items():
        if isinstance(value, tuple):
            print(f"  {key:30s}: {value[0]:.2f} - {value[1]:.2f}")
        elif isinstance(value, float):
            print(f"  {key:30s}: {value:.2f}")
        else:
            print(f"  {key:30s}: {value}")

    # ============================================================
    # STEP 6: ANALYSIS EXAMPLES
    # ============================================================
    print(f"\n{'=' * 60}")
    print("🔍 Analysis Examples")
    print(f"{'=' * 60}")

    airborne_count = len(Cat021AnalysisHelper.filter_airborne(df_processed))
    high_altitude = len(Cat021AnalysisHelper.filter_by_altitude(df_processed, min_fl=300))
    ryanair = len(Cat021AnalysisHelper.filter_by_callsign(df_processed, 'RYR'))
    vueling = len(Cat021AnalysisHelper.filter_by_callsign(df_processed, 'VLG'))

    print(f"  Airborne aircraft:          {airborne_count:,}")
    print(f"  Aircraft above FL300:       {high_altitude:,}")
    print(f"  Ryanair flights (RYR):      {ryanair:,}")
    print(f"  Vueling flights (VLG):      {vueling:,}")

    # Show top aircraft by number of records
    if len(df_processed) > 0:
        print(f"\n  Top 5 aircraft by records:")
        top_aircraft = Cat021AnalysisHelper.get_top_aircraft_by_records(df_processed, n=5)
        for idx, row in top_aircraft.iterrows():
            # Updated column names
            callsign = row['Target_identification'] if pd.notna(row['Target_identification']) else 'N/A'  # ✅ Fixed
            print(f"    {row['Target_address']:6s} ({callsign:8s}): {row['record_count']:5d} records")  # ✅ Fixed

    # ============================================================
    # STEP 7: EXPORT TO CSV
    # ============================================================
    print(f"\n{'=' * 60}")
    print("💾 Exporting to CSV...")
    print(f"{'=' * 60}")

    AsterixPreprocessor.export_to_csv(df_processed, str(output_csv))
    print(f"   📁 File: {output_csv}")
    print(f"   📊 Size: {output_csv.stat().st_size / 1024:.2f} KB")

    print(f"\n{'=' * 60}")
    print("✅ Processing Complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
