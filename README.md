# ASTERIX Decoder

Unified ASTERIX (EUROCONTROL) decoder and viewer for Category 021 (ADS-B) and Category 048 (Primary/Secondary Radar).

This repository provides:
- A command‑line pipeline to read .ast files, decode CAT021/CAT048, export to pandas, filter, and write CSV.
- A desktop GUI (PySide6/Qt) to load files, filter interactively, view data in a table, and visualize aircraft on a Leaflet map.
- Minimal tests around the ASTERIX file reader.


## Stack
- Language: Python
- Frameworks/Libraries: PySide6 (Qt for Python, incl. QtWebEngine), pandas, numpy
- Testing: pytest
- Package manager: pip (requirements.txt)

TODO:
- Confirm supported Python versions (inferred >=3.9 due to dependencies; please verify your target version).
- Add packaging/entry points if distribution is desired.


## Project structure
```
ASTERIX_Decoder/
├─ data/
│  ├─ output/
│  │  ├─ asterix_processed.csv
│  │  └─ asterix_raw_unfiltered.csv
│  └─ samples/
│     ├─ datos_asterix_adsb.ast
│     ├─ datos_asterix_combinado.ast
│     └─ datos_asterix_radar.ast
├─ gui/
│  ├─ __init__.py
│  ├─ main_window.py        # GUI entry point (PySide6)
│  ├─ map_widget.py         # Map visualization using Leaflet in QtWebEngine
│  └─ pandas_model.py       # Qt model for displaying pandas DataFrames
├─ src/
│  ├─ __init__.py
│  ├─ main.py               # CLI/demo entry point
│  ├─ decoders/
│  │  ├─ asterix_decoder_base.py
│  │  ├─ asterix_file_reader.py
│  │  ├─ cat021_decoder.py
│  │  └─ cat048_decoder.py
│  ├─ exporters/
│  │  └─ asterix_exporter.py
│  ├─ models/
│  │  ├─ item.py
│  │  └─ record.py
│  ├─ types/
│  │  └─ enums.py
│  └─ utils/
│     ├─ asterix_filter.py
│     ├─ coordinate_transformer.py
│     ├─ handlers.py
│     └─ qnh_corrector.py
├─ tests/
│  ├─ __init__.py
│  └─ test_asterix_file_reader.py
├─ requirements.txt
└─ README.md
```


## Requirements
- Python: TODO confirm version (likely 3.10–3.12; PySide6 6.10 supports modern Python versions)
- OS: Windows, macOS, or Linux
- Pip and a virtual environment tool (venv or conda)

Dependencies are listed in requirements.txt, including:
- PySide6==6.10.0 (Qt for Python, incl. shiboken6 and WebEngine)
- pandas, numpy
- pytest (for tests)


## Installation
1) Clone the repository and move into the project root:
   git clone <your-fork-or-origin-url>
   cd ASTERIX_Decoder

2) Create and activate a virtual environment (example with venv):
   python -m venv .venv
   # Windows
   .venv\\Scripts\\activate
   # macOS/Linux
   source .venv/bin/activate

3) Install dependencies:
   pip install -r requirements.txt


## Running
There are two main ways to run the project: CLI pipeline and GUI.

- CLI entry point (from project root):
  python -m src.main
  # or
  python src/main.py

  This will read a sample .ast file from data/samples, decode it, apply filters, and write CSV outputs to data/output.

- GUI entry point (desktop app):
  python -m gui.main_window
  # or
  python gui/main_window.py

  Use the GUI to load .ast files, inspect the table, filter results, export CSV, and view aircraft on a map.

Note: The GUI uses QtWebEngine for the embedded map. On some Linux environments you may need additional system packages. If you encounter WebEngine errors, please consult PySide6/QtWebEngine platform notes.


## Scripts and common commands
There is no packaging or script runner configured. Use these commands directly:
- Run CLI pipeline: python -m src.main
- Run GUI: python -m gui.main_window
- Run tests: pytest -q
- Lint/format: TODO add tools (e.g., ruff/black) if desired


## Environment variables
No mandatory environment variables are required for basic usage.

Optional/TODO:
- Add variables for input/output paths if you want to parameterize src/main.py behavior.
- Add configuration for map defaults if needed.


## Data, inputs, and outputs
- Sample inputs: data/samples/*.ast
- Default output directory: data/output/
  - asterix_processed.csv (filtered/processed)
  - asterix_raw_unfiltered.csv (when exporting from GUI)

You can also export custom CSVs from the GUI via the Export button.


## Testing
Run tests with pytest from the project root:
  pytest -q

Current tests focus on the ASTERIX file reader. Feel free to expand test coverage for decoders, exporters, and filters.


## Known limitations / TODOs
- Confirm supported Python versions and platform-specific notes for PySide6 WebEngine.
- Add CLI arguments to src/main.py to choose input/output paths and filters.
- Add continuous integration and style/typing checks.
- Expand unit tests for decoders (CAT021/CAT048) and utilities.
- Add packaging (pyproject.toml) and console scripts if distribution is needed.
- Provide documentation on ASTERIX field mapping and any QNH correction details.


## License
TODO: Add a LICENSE file and specify the license here (e.g., MIT, Apache-2.0).
