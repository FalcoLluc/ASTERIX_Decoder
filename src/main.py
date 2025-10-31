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

    # ============================================================
    # STEP 1: READ ASTERIX FILE
    # ============================================================
    print("📖 Step 1: Reading ASTERIX file...")

    reader = AsterixFileReader(str(input_file))
    records = list(reader.read_records())

    # Count records by category
    cat021_count = sum(1 for r in records if r.category == Category.CAT021)
    cat048_count = sum(1 for r in records if r.category == Category.CAT048)

    print(f"   ✅ Read {len(records):,} records total")
    print(f"   📡 CAT021 (ADS-B): {cat021_count:,} records")
    print(f"   📡 CAT048 (Radar): {cat048_count:,} records")

    # ============================================================
    # STEP 2: DECODE RECORDS
    # ============================================================
    print("\n🔧 Step 2: Decoding records...")

    start_time = time.perf_counter()
    records = decode_records(records)
    elapsed_time = time.perf_counter() - start_time

    print(f"   ✅ Decoded {len(records):,} records in {elapsed_time:.4f}s")
    print(f"   ⚡ Throughput: {len(records) / elapsed_time:.2f} records/sec")
    print(records[0].items)
    print(records[1].items)
    if records:
        avg_items = sum(len(r.items) for r in records) / len(records)
        print(f"   📊 Average items per record: {avg_items:.1f}")

    # ============================================================
    # STEP 3: EXPORT TO DATAFRAME (with QNH correction)
    # ============================================================
    print("\n📋 Step 3: Exporting to unified DataFrame...")

    df = AsterixExporter.records_to_dataframe(records, apply_qnh=True)
    # QNH Correction applied by default

    print(f"   ✅ Created DataFrame: {len(df):,} rows × {len(df.columns)} columns")

    # Count QNH corrections applied
    qnh_corrected = df['H(ft)'].notna().sum()
    print(f"   🌡️  QNH corrections applied: {qnh_corrected:,} records")

    # ============================================================
    # STEP 4: APPLY FILTERS
    # ============================================================
    print("\n🔍 Step 4: Applying filters...")

    initial_count = len(df)

    # Apply filters sequentially
    df_filtered = df.copy()

    # Filter 1: Remove white noise (PSR-only detections)
    df_filtered = AsterixFilter.filter_white_noise(df_filtered)
    white_noise_removed = initial_count - len(df_filtered)

    # Filter 2: Geographic filtering
    df_filtered = AsterixFilter.filter_by_geographic_bounds(df_filtered)
    geo_removed = initial_count - white_noise_removed - len(df_filtered)

    print(f"   🗑️  White noise (PSR-only):     {white_noise_removed:,} records removed")
    print(f"   🗑️  Outside geographic bounds:  {geo_removed:,} records removed")
    print(f"   ✅ Final dataset:               {len(df_filtered):,} records")

    # ============================================================
    # STEP 5: DATA PREVIEW
    # ============================================================
    if not df_filtered.empty:
        print("\n📊 Data Preview (first 5 rows):")
        pd.set_option('display.max_columns', 20)
        pd.set_option('display.width', 150)

        preview_cols = ['CAT', 'Time', 'TA', 'TI', 'FL', 'H(ft)', 'LAT', 'LON',
                        'GS', 'HDG', 'TYP', 'SIM']
        available_cols = [c for c in preview_cols if c in df_filtered.columns]

        if available_cols:
            print(df_filtered[available_cols].head(5).to_string(index=False))

    # ============================================================
    # STEP 6: STATISTICS BY CATEGORY
    # ============================================================
    print(f"\n{'=' * 70}")
    print("📈 Dataset Statistics")
    print(f"{'=' * 70}")

    stats = AsterixFilter.get_statistics(df_filtered)

    print("\n🔢 Overall Statistics:")
    print(f"   Total records:              {stats['total_records']:,}")
    print(f"   Unique aircraft:            {stats['unique_aircraft']:,}")
    print(f"   Unique callsigns:           {stats['unique_callsigns']:,}")

    if 'airborne_count' in stats and stats['airborne_count'] is not None:
        print(f"   Airborne:                   {stats['airborne_count']:,}")
        print(f"   On ground:                  {stats['ground_count']:,}")

    if 'avg_altitude_ft' in stats and stats['avg_altitude_ft'] is not None:
        print(f"   Avg altitude (corrected):   {stats['avg_altitude_ft']:.0f} ft")

    if 'avg_flight_level' in stats and stats['avg_flight_level'] is not None:
        print(f"   Avg flight level:           FL{stats['avg_flight_level']:.0f}")

    # Category breakdown
    print(f"\n📡 Category Breakdown:")
    cat021_final = (df_filtered['CAT'] == 21).sum()
    cat048_final = (df_filtered['CAT'] == 48).sum()
    print(f"   CAT021 (ADS-B):             {cat021_final:,} records")
    print(f"   CAT048 (Radar):             {cat048_final:,} records")

    # ============================================================
    # STEP 7: ANALYSIS EXAMPLES
    # ============================================================
    print(f"\n{'=' * 70}")
    print("🔍 Analysis Examples")
    print(f"{'=' * 70}")

    # High altitude aircraft
    high_altitude = AsterixFilter.filter_by_altitude(df_filtered, min_fl=300)
    print(f"   Aircraft above FL300:       {len(high_altitude):,}")

    # Fast aircraft
    fast_aircraft = AsterixFilter.filter_by_speed(df_filtered, min_speed=400)
    print(f"   Aircraft > 400kt:           {len(fast_aircraft):,}")

    # Specific airline (example: Ryanair)
    ryanair = AsterixFilter.filter_by_callsign(df_filtered, 'RYR')
    print(f"   Ryanair flights (RYR):      {len(ryanair):,}")

    # Airborne aircraft
    airborne = AsterixFilter.filter_airborne(df_filtered)
    print(f"   Total airborne:             {len(airborne):,}")

    # ============================================================
    # STEP 8: EXPORT TO CSV
    # ============================================================
    print(f"\n{'=' * 70}")
    print("💾 Exporting to CSV...")
    print(f"{'=' * 70}")

    AsterixExporter.export_to_csv(df_filtered, str(output_csv))
    print(f"   📁 File: {output_csv}")
    print(f"   📊 Size: {output_csv.stat().st_size / 1024:.2f} KB")

    # ============================================================
    # STEP 9: OPTIONAL - Export raw unfiltered data
    # ============================================================
    if len(df) != len(df_filtered):
        output_csv_raw = output_dir / "asterix_raw_unfiltered.csv"
        AsterixExporter.export_to_csv(df, str(output_csv_raw))
        print(f"   📁 Raw data: {output_csv_raw}")
        print(f"   📊 Size: {output_csv_raw.stat().st_size / 1024:.2f} KB")

    print(f"\n{'=' * 70}")
    print("✅ Processing Complete!")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
