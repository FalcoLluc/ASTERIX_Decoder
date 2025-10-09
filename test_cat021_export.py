from pathlib import Path
from src.decoders.asterix_file_reader import AsterixFileReader
from src.decoders.cat021_decoder import Cat021Decoder
from src.exporters.cat021_csv_exporter import Cat021CSVExporter, Cat021AnalysisHelper


def main():
    print("\n" + "=" * 80)
    print(" CAT021 CSV EXPORTER - TEST CON FILTROS OBLIGATORIOS")
    print("=" * 80)

    base_dir = Path(__file__).resolve().parent
    input_file = base_dir / "data" / "samples" / "datos_asterix_adsb.ast"
    output_file = base_dir / "data" / "output" / "cat021_adsb_decoded.csv"

    output_file.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n Archivo entrada: {input_file.name}")
    print(f" Archivo salida: {output_file.name}\n")

    if not input_file.exists():
        print(f" ERROR: No se encuentra el archivo {input_file}")
        return

    # === PASO 1: LEER ARCHIVO ===
    print(" Paso 1: Leyendo archivo ASTERIX...")
    reader = AsterixFileReader(str(input_file))
    records = list(reader.read_records())
    print(f" {len(records):,} registros leídos\n")

    # === PASO 2: DECODIFICAR ===
    print(" Paso 2: Decodificando registros CAT021...")
    decoder = Cat021Decoder()
    for record in records:
        decoder.decode_record(record)
    print(f" {len(records):,} registros decodificados\n")

    # === PASO 3: EXPORTAR CON FILTROS ===
    print(" Paso 3: Exportando a CSV con filtros obligatorios...")
    print("   Filtros aplicados:")
    print("   - Área geográfica Barcelona (40.9-41.7°N, 1.5-2.6°E)")
    print("   - Eliminar aeronaves en tierra (GBS=1)")
    print("   - Corrección QNH para altitudes < 6000 ft\n")

    df = Cat021CSVExporter.export_to_csv(records, str(output_file), apply_filters=True)

    print(f"\n {len(df):,} filas exportadas al CSV")
    print(f" Archivo guardado: {output_file}\n")

    # === PASO 4: ESTADÍSTICAS ===
    print("=" * 80)
    print(" ESTADÍSTICAS DEL DATASET FILTRADO")
    print("=" * 80)
    stats = Cat021AnalysisHelper.get_statistics(df)

    print(f"\n Registros totales:          {stats['total_records']:,}")
    print(f"✈  Aeronaves únicas:           {stats['unique_aircraft']:,}")
    print(f"️  Indicativos únicos:         {stats['unique_callsigns']:,}")

    if stats['airborne_count'] is not None:
        print(f"\n En vuelo (airborne):        {stats['airborne_count']:,}")
        print(f" En tierra (ground):         {stats['ground_count']:,}")

    if stats['avg_altitude_ft'] is not None:
        print(f"\n Altitud promedio:           {stats['avg_altitude_ft']:,.0f} ft")
        print(f" Flight Level promedio:      FL{stats['avg_flight_level']:.1f}")
        print(
            f"  Rango altitud:              FL{stats['altitude_range'][0]:.0f} - FL{stats['altitude_range'][1]:.0f}")

    if stats['lat_range'] is not None:
        print(f"\n Rango latitud:              {stats['lat_range'][0]:.4f}° - {stats['lat_range'][1]:.4f}°")
        print(f" Rango longitud:             {stats['lon_range'][0]:.4f}° - {stats['lon_range'][1]:.4f}°")

    if stats['simulated_count'] is not None:
        print(f"\n Objetivos simulados:        {stats['simulated_count']:,}")
        print(f" Objetivos de prueba:        {stats['test_target_count']:,}")

    # === PASO 5: EJEMPLOS DE FILTROS ===
    print("\n" + "=" * 80)
    print(" EJEMPLOS DE FILTROS ADICIONALES")
    print("=" * 80)

    airborne = Cat021AnalysisHelper.filter_airborne(df)
    print(f"\n️  Solo airborne:               {len(airborne):,} registros")

    cruise_alt = Cat021AnalysisHelper.filter_by_altitude(df, min_fl=250, max_fl=400)
    print(f" Altitud crucero FL250-400:   {len(cruise_alt):,} registros")

    real_data = Cat021AnalysisHelper.filter_simulated(
        Cat021AnalysisHelper.filter_test_targets(df, include_test=False),
        include_sim=False
    )
    print(f" Solo datos reales:           {len(real_data):,} registros")

    # === PASO 6: TOP AERONAVES ===
    print("\n" + "=" * 80)
    print(" TOP 10 AERONAVES MÁS RASTREADAS")
    print("=" * 80)
    top_aircraft = Cat021AnalysisHelper.get_top_aircraft_by_records(df, n=10)
    print("\n" + top_aircraft.to_string(index=False))

    # === PASO 7: VERIFICAR COLUMNA QNH ===
    print("\n" + "=" * 80)
    print(" VERIFICACIÓN CORRECCIÓN QNH")
    print("=" * 80)
    if 'ALT_QNH_ft' in df.columns:
        print("\n Columna ALT_QNH_ft creada correctamente")

        # Mostrar algunos ejemplos de corrección
        below_6000 = df[df['ALT_ft'] < 6000].head(5)
        if not below_6000.empty:
            print("\nEjemplos de corrección QNH (aeronaves < 6000 ft):")
            cols_to_show = ['TA', 'TI', 'ALT_ft', 'ALT_QNH_ft']
            if 'BPS' in below_6000.columns:
                cols_to_show.append('BPS')
            print(below_6000[cols_to_show].to_string(index=False))

    else:
        print("\n️  Columna ALT_QNH_ft no encontrada")

    # === PASO 8: MUESTRA DE DATOS ===
    print("\n" + "=" * 80)
    print(" MUESTRA DE DATOS (Primeras 5 filas)")
    print("=" * 80)
    print("\n" + df.head(5).to_string(index=False))

    # === PASO 9: INFO DEL CSV ===
    print("\n" + "=" * 80)
    print(" INFORMACIÓN DEL CSV EXPORTADO")
    print("=" * 80)
    print(f"\n Columnas: {list(df.columns)}")
    print(f" Dimensiones: {df.shape[0]:,} filas × {df.shape[1]} columnas")
    print(f" Tamaño en memoria: {df.memory_usage(deep=True).sum() / 1024 ** 2:.2f} MB")

    print("\n" + "=" * 80)
    print("  TEST COMPLETADO CON ÉXITO")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
