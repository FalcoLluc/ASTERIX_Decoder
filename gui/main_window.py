from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableView, QLabel, QLineEdit, QSpinBox,
    QCheckBox, QMessageBox, QProgressDialog, QGroupBox, QHeaderView,
    QTabWidget, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QAction
import pandas as pd
import numpy as np
from multiprocessing import Pool, cpu_count
from gui.pandas_model import PandasModel
from gui.map_widget import MapWidget
from src.decoders.asterix_file_reader import AsterixFileReader
from src.exporters.asterix_exporter import AsterixExporter
from src.utils.asterix_filter import AsterixFilter

# ============================================================
# COLUMN DEFINITIONS FOR EACH CATEGORY
# ============================================================
CAT021_COLUMNS = [
    'CAT', 'SAC', 'SIC', 'Time', 'Time_sec',
    'LAT', 'LON', 'H(m)', 'H(ft)',
    'FL', 'TA', 'TI', 'BP', 'SIM', 'TST',
    'ATP', 'ARC', 'RC', 'DCR', 'GBS',
]

CAT048_COLUMNS = [
    'CAT', 'SAC', 'SIC', 'Time', 'Time_sec',
    'RHO', 'THETA', 'LAT', 'LON', 'H_WGS84',
    'FL', 'TA', 'TI',
    'TN', 'GS_TVP(kt)', 'GS_BDS(kt)', 'HDG',
    'TYP', 'SIM', 'RDP', 'SPI', 'RAB',
    'ModeS', 'BP', 'RA', 'TTA', 'TAR', 'TAS',
    'MG_HDG', 'IAS', 'MACH', 'BAR', 'IVV',
    'STAT_code', 'STAT',
]


# ============================================================
# WORKER FUNCTION (must be at module level for pickling)
# ============================================================
def process_records_chunk(records_chunk):
    """Decode a chunk of records and return a DataFrame (used by multiprocessing)."""
    from src.utils.handlers import decode_records
    from src.exporters.asterix_exporter import AsterixExporter
    import pandas as pd

    try:
        decoded = decode_records(records_chunk)
        df_chunk = AsterixExporter.records_to_dataframe(decoded)
        return df_chunk
    except Exception as e:
        import traceback
        print(f"Error in worker: {e}\n{traceback.format_exc()}")
        return pd.DataFrame()


# ============================================================
# BACKGROUND THREAD WITH MULTIPROCESSING
# ============================================================
class ProcessingThread(QThread):
    """Background worker to read and decode ASTERIX files with progress reporting.

    Can process sequentially or using multiprocessing depending on cores.
    """
    finished = Signal(pd.DataFrame)
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, file_path, use_multiprocessing=True):
        """Configure worker with file path and chosen processing mode."""
        super().__init__()
        self.file_path = file_path
        self.use_multiprocessing = use_multiprocessing

        total_cores = cpu_count()
        if total_cores <= 2:
            self.n_workers = 1
        elif total_cores <= 4:
            self.n_workers = total_cores - 1
        else:
            self.n_workers = total_cores - 2

    def run(self):
        """Read, decode and aggregate records, emitting progress and final DataFrame."""
        try:
            self.progress.emit(5, "Counting records...")
            reader_count = AsterixFileReader(self.file_path)
            total_records = sum(1 for _ in reader_count.read_records())

            self.progress.emit(10, "Reading records...")
            reader_decode = AsterixFileReader(self.file_path)
            all_records = list(reader_decode.read_records())

            if self.use_multiprocessing and self.n_workers > 1:
                df_raw = self._process_parallel(all_records, total_records)
            else:
                df_raw = self._process_sequential(all_records, total_records)

            self.progress.emit(100, "Complete!")
            self.finished.emit(df_raw)

        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n\n{traceback.format_exc()}")

    def _process_sequential(self, all_records, total_records):
        """Decode records sequentially in batches, emitting progress updates."""
        self.progress.emit(15, "Processing records (single-core)...")
        BATCH_SIZE = 50000
        all_dfs = []
        total_processed = 0

        for i in range(0, len(all_records), BATCH_SIZE):
            batch = all_records[i:i + BATCH_SIZE]
            df_batch = process_records_chunk(batch)
            all_dfs.append(df_batch)

            total_processed += len(batch)
            progress_pct = 15 + int((total_processed / total_records) * 75)
            self.progress.emit(progress_pct, f"Processed {total_processed:,} / {total_records:,} records...")

        self.progress.emit(85, "Merging results...")
        df_merged = pd.concat(all_dfs, ignore_index=True)

        self.progress.emit(90, "Applying QNH correction...")
        df_corrected = self._apply_qnh_with_corrector(df_merged)

        return df_corrected

    def _process_parallel(self, all_records, total_records):
        """Decode records in parallel using a worker Pool, emitting progress."""
        self.progress.emit(15, f"Processing records ({self.n_workers} cores)...")
        chunk_size = max(10000, len(all_records) // (self.n_workers * 4))
        chunks = [all_records[i:i + chunk_size] for i in range(0, len(all_records), chunk_size)]

        all_dfs = []
        total_processed = 0

        with Pool(processes=self.n_workers) as pool:
            for df_chunk in pool.imap_unordered(process_records_chunk, chunks):
                if not df_chunk.empty:
                    all_dfs.append(df_chunk)

                total_processed += chunk_size
                progress_pct = 15 + min(int((total_processed / total_records) * 75), 75)
                self.progress.emit(
                    progress_pct,
                    f"Processed {min(total_processed, total_records):,} / {total_records:,} records..."
                )

        self.progress.emit(85, "Merging results...")
        df_merged = pd.concat(all_dfs, ignore_index=True)

        self.progress.emit(90, "Applying QNH correction...")
        df_corrected = self._apply_qnh_with_corrector(df_merged)

        return df_corrected

    def _apply_qnh_with_corrector(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply QNH correction using QNHCorrector (temporal state tracking)."""
        from src.utils.qnh_corrector import QNHCorrector

        if df.empty or 'FL' not in df.columns:
            return df

        # ✅ Sort by time and aircraft to ensure temporal order
        if 'Time_sec' in df.columns and 'TA' in df.columns:
            df = df.sort_values(['TA', 'Time_sec'], na_position='last').reset_index(drop=True)


        # ✅ Use new vectorized method
        corrector = QNHCorrector()
        df = corrector.correct_dataframe(df)

        return df

# ============================================================
# MAIN WINDOW
# ============================================================
class AsterixGUI(QMainWindow):
    """Main application window: loads files, shows table/map and manages filters."""
    def __init__(self):
        super().__init__()
        self.df_raw = None
        self.df_display = None
        self.model = None
        self.filters_dirty = False
        self.pending_filters = False
        self.p3_callsigns = None
        self.init_ui()

    def init_ui(self):
        """Set up menus, tabs, table view, map widget, and filter panels."""
        self.setWindowTitle("ASTERIX Unified Decoder & Viewer")
        self.setGeometry(100, 100, 1800, 1000)

        self.create_menu()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        load_toolbar = self.create_load_toolbar()
        layout.addLayout(load_toolbar)

        self.status_label = QLabel("Ready — Load an ASTERIX file to begin.")
        layout.addWidget(self.status_label)

        self.tabs = QTabWidget()

        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table_layout.addWidget(self.table)
        self.tabs.addTab(table_widget, "📋 Table View")

        self.map_widget = MapWidget()
        self.map_widget.view_mode_changed = self.on_map_view_changed
        self.tabs.addTab(self.map_widget, "🗺 Map View")

        layout.addWidget(self.tabs)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self.create_category_filter_panel())
        filter_layout.addWidget(self.create_detection_filter_panel())
        filter_layout.addWidget(self.create_altitude_filter_panel())
        filter_layout.addWidget(self.create_status_filter_panel())
        layout.addLayout(filter_layout)

        layout.addWidget(self.create_custom_filter_panel())

    def create_menu(self):
        """Create File menu with actions to open, export and exit."""
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_action = QAction("📂 &Open ASTERIX File", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.load_file)
        file_menu.addAction(open_action)

        export_action = QAction("💾 &Export CSV", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_csv)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        exit_action = QAction("🚪 E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def create_load_toolbar(self):
        """Build the top toolbar with load/apply/export/reset buttons."""
        layout = QHBoxLayout()
        self.load_btn = QPushButton("📁 Load ASTERIX File")
        self.load_btn.clicked.connect(self.load_file)
        layout.addWidget(self.load_btn)
        layout.addStretch()
        self.apply_btn = QPushButton("✅ Apply Filters")
        self.apply_btn.clicked.connect(self.apply_dynamic_filters)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet(
            "QPushButton:enabled { background-color: #4CAF50; color: white; font-weight: bold; } "
            "QPushButton:disabled { background-color: #cccccc; color: white; }"
        )
        layout.addWidget(self.apply_btn)
        self.export_btn = QPushButton("💾 Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)
        self.reset_btn = QPushButton("🔄 Reset All Filters")
        self.reset_btn.clicked.connect(self.reset_filters)
        self.reset_btn.setEnabled(False)
        layout.addWidget(self.reset_btn)
        return layout

    def create_category_filter_panel(self):
        """Create category filter group (CAT021/CAT048 checkboxes)."""
        group = QGroupBox("📡 ASTERIX Category")
        layout = QVBoxLayout()
        self.cat021_check = QCheckBox("CAT021 (ADS-B)")
        self.cat021_check.setChecked(True)
        self.cat021_check.stateChanged.connect(self.on_filter_changed)
        layout.addWidget(self.cat021_check)
        self.cat048_check = QCheckBox("CAT048 (Radar)")
        self.cat048_check.setChecked(True)
        self.cat048_check.stateChanged.connect(self.on_filter_changed)
        layout.addWidget(self.cat048_check)
        group.setLayout(layout)
        return group

    def create_detection_filter_panel(self):
        """Create detection filter group (noise and fixed transponder filters)."""
        group = QGroupBox("🎯 Detection")
        layout = QVBoxLayout()
        self.white_noise_check = QCheckBox("Remove White Noise (PSR-only)")
        self.white_noise_check.setChecked(True)
        self.white_noise_check.stateChanged.connect(self.on_filter_changed)
        layout.addWidget(self.white_noise_check)
        self.fixed_transponder_check = QCheckBox("Remove Fixed Transponders (7777)")
        self.fixed_transponder_check.setChecked(True)
        self.fixed_transponder_check.stateChanged.connect(self.on_filter_changed)
        layout.addWidget(self.fixed_transponder_check)
        group.setLayout(layout)
        return group

    def create_altitude_filter_panel(self):
        """Create altitude filter group with min/max FL spinners."""
        group = QGroupBox("📏 Altitude")
        layout = QVBoxLayout()
        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("Min FL:"))
        self.min_fl_spin = QSpinBox()
        self.min_fl_spin.setRange(0, 600)
        self.min_fl_spin.setValue(0)
        self.min_fl_spin.setMaximumWidth(80)
        self.min_fl_spin.valueChanged.connect(self.on_filter_changed)
        min_layout.addWidget(self.min_fl_spin)
        min_layout.addStretch()
        layout.addLayout(min_layout)
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max FL:"))
        self.max_fl_spin = QSpinBox()
        self.max_fl_spin.setRange(0, 600)
        self.max_fl_spin.setValue(600)
        self.max_fl_spin.setMaximumWidth(80)
        self.max_fl_spin.valueChanged.connect(self.on_filter_changed)
        max_layout.addWidget(self.max_fl_spin)
        max_layout.addStretch()
        layout.addLayout(max_layout)
        group.setLayout(layout)
        return group

    def create_status_filter_panel(self):
        """Create status filter group (airborne/on‑ground toggles)."""
        group = QGroupBox("✈️ Status")
        layout = QVBoxLayout()
        self.airborne_check = QCheckBox("Airborne Only")
        self.airborne_check.setChecked(False)
        self.airborne_check.stateChanged.connect(self.on_filter_changed)
        layout.addWidget(self.airborne_check)
        self.ground_check = QCheckBox("On Ground Only")
        self.ground_check.setChecked(False)
        self.ground_check.stateChanged.connect(self.on_filter_changed)
        layout.addWidget(self.ground_check)
        group.setLayout(layout)
        return group

    def create_custom_filter_panel(self):
        """Create custom filters (callsign, min speed, geo bounds, P3 Excel)."""
        group = QGroupBox("🔍 Custom Filters")
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Callsign:"))
        self.callsign_input = QLineEdit()
        self.callsign_input.setPlaceholderText("e.g., RYR")
        self.callsign_input.setMaximumWidth(200)
        self.callsign_input.textChanged.connect(self.on_filter_changed)
        layout.addWidget(self.callsign_input)

        layout.addWidget(QLabel("Min Speed (kt):"))
        self.min_speed_spin = QSpinBox()
        self.min_speed_spin.setRange(0, 600)
        self.min_speed_spin.setValue(0)
        self.min_speed_spin.setMaximumWidth(80)
        self.min_speed_spin.valueChanged.connect(self.on_filter_changed)
        layout.addWidget(self.min_speed_spin)

        self.geo_filter_check = QCheckBox("Geographic Bounds (Barcelona)")
        self.geo_filter_check.setChecked(True)
        self.geo_filter_check.stateChanged.connect(self.on_filter_changed)
        layout.addWidget(self.geo_filter_check)

        layout.addSpacing(15)
        p3_layout = QVBoxLayout()
        p3_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_load_p3 = QPushButton("📂 Load P3 Excel")
        self.btn_load_p3.clicked.connect(self.load_p3_excel)
        self.btn_load_p3.setFixedSize(110, 25)
        p3_layout.addWidget(self.btn_load_p3)

        self.check_p3_only = QCheckBox("Only P3 Take-offs")
        self.check_p3_only.setEnabled(False)
        self.check_p3_only.stateChanged.connect(self.on_filter_changed)
        p3_layout.addWidget(self.check_p3_only)

        self.check_show_separation = QCheckBox("📏 Show Separation")
        self.check_show_separation.setEnabled(False)
        self.check_show_separation.stateChanged.connect(self.update_map_separation)
        p3_layout.addWidget(self.check_show_separation)

        layout.addLayout(p3_layout)
        layout.addStretch()
        group.setLayout(layout)
        return group

    def load_p3_excel(self):
        """Load Excel file with departure list"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select P3 Departures Excel", "", "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return

        try:
            df_excel = pd.read_excel(file_path)

            if 'Indicativo' not in df_excel.columns:
                QMessageBox.warning(self, "Error", "El Excel no tiene columna 'Indicativo'.")
                return

            col_hora = next((c for c in df_excel.columns if 'Hora' in c or 'Time' in c or 'hora' in c), None)
            if not col_hora:
                QMessageBox.warning(self, "Error", "No se encuentra columna de Hora.")
                return

            # Obtener callsigns que existen en el radar
            if self.df_raw is not None and 'TI' in self.df_raw.columns:
                radar_callsigns = set(self.df_raw['TI'].dropna().astype(str).str.strip().str.upper())
            else:
                radar_callsigns = None

            def parse_time(t):
                """Parse time with Timedelta support"""
                if pd.isna(t):
                    return 999999

                try:
                    # Si es Timedelta (pandas)
                    if isinstance(t, pd.Timedelta):
                        return int(t.total_seconds())

                    # Si es timedelta (Python nativo)
                    if hasattr(t, 'total_seconds'):
                        return int(t.total_seconds())

                    # Si es string
                    if isinstance(t, str):
                        t = t.strip().split('.')[0]
                        if ':' in t:
                            parts = list(map(int, t.split(':')))
                            if len(parts) == 3:
                                return parts[0] * 3600 + parts[1] * 60 + parts[2]
                            elif len(parts) == 2:
                                return parts[0] * 60 + parts[1]

                    # Si es datetime/time
                    if hasattr(t, 'hour'):
                        return t.hour * 3600 + t.minute * 60 + t.second

                    # Si es número
                    if isinstance(t, (int, float)):
                        seconds = t * 86400
                        return int(seconds)

                except Exception:
                    return 999999

                return 999999

            df_excel['sec'] = df_excel[col_hora].apply(parse_time)
            df_excel['Indicativo_clean'] = df_excel['Indicativo'].astype(str).str.strip().str.upper()

            # FILTRAR: Solo vuelos que existen en el radar
            if radar_callsigns:
                df_excel = df_excel[df_excel['Indicativo_clean'].isin(radar_callsigns)]

            df_sorted = df_excel.sort_values('sec')

            schedule = list(zip(
                df_sorted['Indicativo_clean'],
                df_sorted['sec']
            ))

            if hasattr(self, 'map_widget'):
                self.map_widget.set_departure_schedule(schedule)

            self.p3_callsigns = set(df_sorted['Indicativo_clean'])

            self.check_p3_only.setEnabled(True)
            self.check_p3_only.setChecked(True)
            self.check_show_separation.setEnabled(True)
            self.btn_load_p3.setText("✅ Excel Loaded")
            self.btn_load_p3.setStyleSheet("background-color: #e8f5e9; color: #2e7d32; font-weight: bold;")
            self.status_label.setText(f"✅ Loaded {len(self.p3_callsigns)} flights from Excel (matched with radar).")
            self.on_filter_changed()

        except Exception as e:
            import traceback
            QMessageBox.critical(self, "Error", f"Error loading Excel:\n{str(e)}\n\n{traceback.format_exc()}")

    def update_map_separation(self):
        """Toggle separation visualization on the map based on checkbox state."""
        if hasattr(self, 'map_widget'):
            self.map_widget.set_separation_mode(self.check_show_separation.isChecked())

    def on_filter_changed(self):
        """Mark filters as dirty and update UI hints; enable Apply button when data loaded."""
        if self.df_raw is None:
            self.pending_filters = True
            if hasattr(self, 'status_label'):
                self.status_label.setText("⚙️ Filters selected — will apply after loading.")
            return
        self.filters_dirty = True
        self.apply_btn.setEnabled(True)
        self.status_label.setText("⚠️ Filters changed — click 'Apply Filters' to update.")

    def load_file(self):
        """Open file dialog and start background processing of selected ASTERIX file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open ASTERIX File", "", "ASTERIX Files (*.ast);;All Files (*)"
        )
        if not file_path:
            return
        progress = QProgressDialog("Loading file...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(True)
        self.thread = ProcessingThread(file_path)
        self.thread.finished.connect(self.on_load_complete)
        self.thread.error.connect(self.on_load_error)
        self.thread.progress.connect(lambda val, msg: (progress.setValue(val), progress.setLabelText(msg)))
        self.thread.start()

    @Slot(pd.DataFrame)
    def on_load_complete(self, df_raw):
        """Handle successful load: store data, enable actions and apply filters."""
        self.df_raw = df_raw
        self.df_display = df_raw
        self.export_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.apply_btn.setEnabled(False)
        self.filters_dirty = False
        self.apply_dynamic_filters()

    @Slot(str)
    def on_load_error(self, msg):
        """Show error dialog when background loading fails."""
        QMessageBox.critical(self, "Error", f"Failed to load file:\n{msg}")

    def display_dataframe(self, df):
        """Populate the QTableView with the selected columns and auto-size headers."""
        if df is None or df.empty:
            return
        cat021_selected = self.cat021_check.isChecked()
        cat048_selected = self.cat048_check.isChecked()
        if cat021_selected and cat048_selected:
            df_display = df
        elif cat021_selected:
            cols = [col for col in CAT021_COLUMNS if col in df.columns]
            df_display = df[cols]
        else:
            cols = [col for col in CAT048_COLUMNS if col in df.columns]
            df_display = df[cols]
        self.model = PandasModel(df_display)
        self.table.setModel(self.model)
        header = self.table.horizontalHeader()
        for col in range(min(15, df_display.shape[1])):
            self.table.resizeColumnToContents(col)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    def apply_dynamic_filters(self):
        """Apply all active filters to raw data, update table, map and status bar."""
        if self.df_raw is None:
            return
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            df = self.df_raw

            if 'CAT' in df.columns:
                cat_mask = np.zeros(len(df), dtype=bool)
                if self.cat021_check.isChecked():
                    cat_mask |= (df['CAT'].to_numpy(copy=False) == 21)
                if self.cat048_check.isChecked():
                    cat_mask |= (df['CAT'].to_numpy(copy=False) == 48)
                df = df[cat_mask]

            if self.white_noise_check.isChecked():
                df = AsterixFilter.filter_white_noise(df)

            if self.fixed_transponder_check.isChecked():
                df = AsterixFilter.filter_fixed_transponders(df)

            min_fl = self.min_fl_spin.value()
            max_fl = self.max_fl_spin.value()
            if min_fl > 0 or max_fl < 600:
                df = AsterixFilter.filter_by_altitude(df, min_fl=min_fl, max_fl=max_fl)

            if self.airborne_check.isChecked():
                df = AsterixFilter.filter_airborne(df)

            if self.ground_check.isChecked():
                df = AsterixFilter.filter_on_ground(df)

            callsign_text = self.callsign_input.text().strip()
            if callsign_text and 'TI' in df.columns:
                df = AsterixFilter.filter_by_callsign(df, callsign_text)

            min_speed = self.min_speed_spin.value()
            if min_speed > 0:
                df = AsterixFilter.filter_by_speed(df, min_speed=min_speed)

            if self.geo_filter_check.isChecked():
                df = AsterixFilter.filter_by_geographic_bounds(df)

            if self.check_p3_only.isChecked() and self.p3_callsigns:
                if 'TI' in df.columns:
                    temp_ti = df['TI'].astype(str).str.strip().str.upper()
                    df = df[temp_ti.isin(self.p3_callsigns)]

            self.df_display = df

            cats_in_data = set(self.df_display['CAT'].unique()) if 'CAT' in self.df_display.columns else set()
            only_cat021 = (cats_in_data == {21})
            self.airborne_check.setEnabled(not only_cat021)
            self.ground_check.setEnabled(not only_cat021)

            if only_cat021:
                self.airborne_check.blockSignals(True)
                self.ground_check.blockSignals(True)
                self.airborne_check.setChecked(False)
                self.ground_check.setChecked(False)
                self.airborne_check.blockSignals(False)
                self.ground_check.blockSignals(False)

            self.display_dataframe(self.df_display)
            self.update_map()
            self.update_status_label()
            self.filters_dirty = False
            self.apply_btn.setEnabled(False)

        except Exception as e:
            QMessageBox.critical(self, "Filtering Error", f"Error applying filters:\n{str(e)}")
        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def reset_filters(self):
        self.cat021_check.setChecked(True)
        self.cat048_check.setChecked(True)
        self.white_noise_check.setChecked(True)
        self.fixed_transponder_check.setChecked(True)
        self.min_fl_spin.setValue(0)
        self.max_fl_spin.setValue(600)
        self.airborne_check.setChecked(False)
        self.ground_check.setChecked(False)
        self.callsign_input.clear()
        self.min_speed_spin.setValue(0)
        self.geo_filter_check.setChecked(True)

        self.check_p3_only.setChecked(False)
        self.check_p3_only.setEnabled(False)
        self.check_show_separation.setChecked(False)
        self.check_show_separation.setEnabled(False)
        self.p3_callsigns = None
        self.btn_load_p3.setText("📂 Load P3 Excel")
        self.btn_load_p3.setStyleSheet("")

        self.apply_dynamic_filters()

    def update_map(self):
        if self.df_display is None or self.df_display.empty:
            return
        map_columns = ['LAT', 'LON', 'TI', 'TA', 'Time_sec', 'CAT', 'FL', 'H(ft)',
                       'Mode3/A', 'GS(kt)', 'GS_TVP(kt)', 'GS_BDS(kt)']
        available_cols = [col for col in map_columns if col in self.df_display.columns]
        if len(available_cols) < 3:
            return
        try:
            map_data = self.df_display[available_cols]
            self.map_widget.load_data(map_data)
        except Exception as e:
            print(f"❌ Error updating map: {str(e)}")

    def update_status_label(self):
        if self.df_display is None:
            return
        cat021_count = (self.df_display['CAT'] == 21).sum() if 'CAT' in self.df_display.columns else 0
        cat048_count = (self.df_display['CAT'] == 48).sum() if 'CAT' in self.df_display.columns else 0
        total_count = len(self.df_display)
        self.status_label.setText(
            f"📊 Displaying: {total_count:,} records (CAT021: {cat021_count:,}, CAT048: {cat048_count:,}) | Total: {total_count:,} records"
        )

    def export_csv(self):
        if self.df_display is None or self.df_display.empty:
            QMessageBox.warning(self, "Warning", "No data to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "asterix_filtered.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return
        try:
            AsterixExporter.export_to_csv(self.df_display, file_path)
            QMessageBox.information(
                self, "Export Complete",
                f"✅ Exported {len(self.df_display):,} records to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def on_map_view_changed(self, is_3d: bool):
        """Deshabilitar checkbox de separación en 3D"""
        if hasattr(self, 'check_show_separation'):
            if is_3d:
                self.check_show_separation.setEnabled(False)
                self.check_show_separation.setChecked(False)
            else:
                self.check_show_separation.setEnabled(bool(self.p3_callsigns))



if __name__ == '__main__':
    import multiprocessing
    import sys
    from PySide6.QtWidgets import QApplication

    multiprocessing.set_start_method('spawn', force=True)
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = AsterixGUI()
    window.show()
    sys.exit(app.exec())
