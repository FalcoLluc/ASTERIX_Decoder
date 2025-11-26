# ASTERIX Decoder

ASTERIX decoder and viewer for Category 021 (ADS-B) and Category 048 (Radar) aviation surveillance data.

## Purpose

This system provides comprehensive capabilities for processing aviation surveillance data:
- Binary `.ast` file parsing and ASTERIX record extraction
- Category-specific decoding with FSPEC-based item parsing for CAT021 and CAT048
- Data export to pandas DataFrames and CSV files with 47-column unified schema
- Comprehensive filtering (geographic, altitude, detection type, callsign, speed)
- Dual operational modes: CLI for batch processing and GUI for interactive analysis
- Interactive 2D/3D aircraft visualization with temporal playback controls

## Main Components

### Core Decoding Engine
- **AsterixFileReader**: Parses binary `.ast` files, extracts ASTERIX blocks and records
- **Cat021Decoder**: Handles ADS-B record decoding with FSPEC parsing
- **Cat048Decoder**: Processes radar records including Mode S BDS registers (4.0/5.0/6.0) 
- **decode_records()**: Routes records to appropriate decoder based on category

### Data Processing Layer
- **AsterixExporter**: Converts decoded records to pandas DataFrame with memory optimization
- **AsterixFilter**: Provides filtering by geographic bounds, altitude, detection type, callsign, and speed
- **QNHCorrector**: Applies barometric pressure correction for flights below transition altitude 
- **CoordinateTransformer**: Converts radar polar coordinates to WGS-84 latitude/longitude

### GUI Application
- **AsterixGUI**: Main window with tabbed interface (table/map views) and comprehensive filter panels
- **MapWidget**: Interactive visualization using Leaflet.js (2D) and deck.gl (3D) via QWebEngineView
- **ProcessingThread**: Background processing with multiprocessing Pool for responsive UI

## ASTERIX Category Data Items

The system supports two ASTERIX categories, each with specific data items that can be selectively filtered:

| Column        | Description                                                      | CAT021 | CAT048 |
|---------------|------------------------------------------------------------------|:------:|:------:|
| CAT           | ASTERIX Category (21=ADS-B, 48=Radar)                            |   ✔    |   ✔    |
| SAC           | System Area Code                                                 |   ✔    |   ✔    |
| SIC           | System Identification Code                                       |   ✔    |   ✔    |
| Time          | Time of day (HH:MM:SS.mmm)                                       |   ✔    |   ✔    |
| Time_sec      | Time in seconds from midnight                                    |   ✔    |   ✔    |
| LAT           | Latitude (degrees)                                               |   ✔    |   ✔    |
| LON           | Longitude (degrees)                                              |   ✔    |   ✔    |
| H_WGS84       | WGS-84 ellipsoidal height (m) (radar only)                      |        |   ✔    |
| H(m)          | Height in meters, QNH-corrected                                  |   ✔    |   ✔    |
| H(ft)         | Height in feet, QNH-corrected                                    |   ✔    |   ✔    |
| RHO           | Slant range (NM, radar only)                                     |        |   ✔    |
| THETA         | Azimuth angle (degrees, radar only)                              |        |   ✔    |
| Mode3/A       | Mode 3/A code (octal)                                            |   ✔    |   ✔    |
| FL            | Flight level (hundreds of feet)                                  |   ✔    |   ✔    |
| TA            | Target Address (24-bit ICAO, hex)                                |   ✔    |   ✔    |
| TI            | Target Identification (callsign)                                 |   ✔    |   ✔    |
| BP            | Barometric Pressure (hPa)                                        |   ✔    |   ✔    |
| ModeS         | BDS registers present (space-separated)                          |        |   ✔    |
| RA            | Roll Angle (deg, BDS 5.0)                                        |        |   ✔    |
| TTA           | True Track Angle (deg, BDS 5.0)                                  |        |   ✔    |
| GS_TVP(kt)    | Ground Speed (kt, radar)                                         |        |   ✔    |
| GS_BDS(kt)    | Ground Speed (kt, aircraft Mode S)                               |        |   ✔    |
| TAR           | Track Angle Rate (deg/s)                                         |        |   ✔    |
| TAS           | True Airspeed (kt, BDS 5.0)                                      |        |   ✔    |
| HDG           | Heading (deg, radar)                                             |        |   ✔    |
| MG_HDG        | Magnetic Heading (deg, BDS 6.0)                                  |        |   ✔    |
| IAS           | Indicated Airspeed (kt, BDS 6.0)                                 |        |   ✔    |
| MACH          | Mach Number (BDS 6.0)                                            |        |   ✔    |
| BAR           | Barometric Altitude Rate (ft/min, BDS 6.0)                       |        |   ✔    |
| IVV           | Inertial Vertical Velocity (ft/min, BDS 6.0)                     |        |   ✔    |
| TN            | Track Number                                                     |        |   ✔    |
| TST           | Test Target                                                      |   ✔    |   ✔    |
| TYP           | Detection type                                                   |        |   ✔    |
| SIM           | Simulated target indicator (0/1)                                 |   ✔    |   ✔    |
| RDP           | RDP Chain                                                        |        |   ✔    |
| SPI           | Special Position Identification (0/1)                            |   ✔    |   ✔    |
| RAB           | Report from field monitor (0/1)                                  |   ✔    |   ✔    |
| ATP           | Address Type (CAT021 only)                                       |   ✔    |        |
| ARC           | Altitude Reporting Capability (CAT021 only)                      |   ✔    |        |
| RC            | Range Check (CAT021 only)                                        |   ✔    |        |
| DCR           | Differential Correction (CAT021 only)                            |   ✔    |        |
| GBS           | Ground Bit Set (CAT021 only)                                     |   ✔    |        |
| STAT_code     | Status code - COM/ACAS                                           |   ✔    |   ✔    |
| STAT          | Status description - COM/ACAS                                    |   ✔    |   ✔    |

> Not all columns will be present for every record—fields depend on category and detailed report content.

### Category Filtering
You can filter data to show only specific categories using the GUI filter panels:
- **CAT021 (ADS-B)**: Shows aircraft position broadcasts from aircraft transponders
- **CAT048 (Radar)**: Shows primary/secondary radar detections from ground stations
- **Both**: Displays combined surveillance data for comprehensive analysis

## Main Technologies

| Layer | Technology | Usage |
|-------|------------|-------|
| **Language** | Python | Core implementation |
| **GUI Framework** | PySide6 | Qt-based desktop interface with WebEngine |
| **Data Processing** | pandas | DataFrame operations, CSV export |
| **Data Processing** | numpy | Numerical operations, filtering |
| **Web Mapping** | Leaflet.js | 2D map visualization embedded in Qt |
| **Web Mapping** | deck.gl | 3D WebGL visualization |
| **Excel Integration** | openpyxl | P3 departure schedule loading |

## Performance Architecture

### Batch Processing
The system processes large ASTERIX files efficiently using batch processing:
- **Sequential Mode**: Processes 50,000-record batches in single-core mode
- **Parallel Mode**: Divides records into optimal chunks (10,000+ records) for multiprocessing

### Multiprocessing
Leverages multiple CPU cores for accelerated decoding:
- **Worker Pool**: Uses `multiprocessing.Pool` with dynamic worker allocation 
- **Core Optimization**: Allocates `cpu_count() - 2` workers for systems with >4 cores, or `cpu_count() - 1` for simpler systems
- **Parallel Execution**: Processes chunks simultaneously using `imap_unordered()`

## Quick Guide

### Running the Application

#### GUI Mode (Interactive Analysis)

Opens desktop application with:
- **File Loading**: Use File → Open ASTERIX File or toolbar button
- **Table View**: Inspect decoded data in sortable table
- **Map View**: Interactive 2D/3D visualization with playback controls
- **Filtering**: Apply category, altitude, geographic, and custom filters
- **Export**: Save filtered data as CSV

### Basic Workflow

1. **Load Data**: Open `.ast` file containing CAT021/CAT048 records
2. **Apply Filters**: Use filter panels to focus on specific flights or areas
3. **Analyze**: View data in table or visualize on map with temporal playback
4. **Export**: Save filtered results to CSV for further analysis

### Key Features

- **Dual Visualization**: Toggle between 2D Leaflet map and 3D view
- **Temporal Playback**: Control simulation speed and scrub through timeline
- **P3 Integration**: Load Excel departure schedules for separation analysis and departures filtering
- **Real-time Filtering**: Apply filters dynamically without reloading data
- **Memory Optimization**: Efficient processing of large files via chunking and dtype downcasting
- **Category Filtering**: Show only CAT021, CAT048, or combined data sources
- **Parallel Processing**: Utilize multiple CPU cores for faster decoding of large files