from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableView, QLabel, QLineEdit, QSpinBox,
    QCheckBox, QMessageBox, QProgressDialog, QGroupBox, QHeaderView,
    QTabWidget
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QAction
import pandas as pd
import numpy as np
import sys

from gui.pandas_model import PandasModel
from gui.map_widget import MapWidget
from src.decoders.asterix_file_reader import AsterixFileReader
from src.exporters.asterix_exporter import AsterixExporter
from src.utils.asterix_filter import AsterixFilter
from src.utils.handlers import decode_records, decode_records_iter

# ============================================================
# COLUMN DEFINITIONS FOR EACH CATEGORY
# ============================================================
CAT021_COLUMNS = [
    'CAT', 'SAC', 'SIC', 'Time', 'Time_sec',
    'LAT', 'LON', 'H(m)', 'H(ft)',
    'FL', 'TA', 'TI', 'BP', 'SIM', 'TST',
    'ATP', 'ARC', 'RC', 'DCR',  'GBS',
]

CAT048_COLUMNS = [
    'CAT', 'SAC', 'SIC', 'Time', 'Time_sec',
    'RHO', 'THETA', 'LAT', 'LON', 'H_WGS84',
    'FL', 'TA', 'TI',
    'TN','GS_TVP(kt)', 'GS_BDS(kt)', 'HDG',
    'TYP', 'SIM', 'RDP', 'SPI', 'RAB',
    'ModeS', 'BP', 'RA', 'TTA', 'TAR', 'TAS',
    'MG_HDG', 'IAS', 'MACH', 'BAR', 'IVV',
    'STAT_code', 'STAT',
]

# ============================================================
# BACKGROUND THREAD
# ============================================================
class ProcessingThread(QThread):
    """Thread to read, decode, and export ASTERIX files (unified)."""
    finished = Signal(pd.DataFrame)
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit(10, "Reading and decoding records…")
            reader = AsterixFileReader(self.file_path)
            # Lazy decode to avoid materializing the entire records list in memory
            records_iter = decode_records_iter(reader.read_records())

            self.progress.emit(60, "Exporting to DataFrame…")
            df_raw = AsterixExporter.records_to_dataframe(records_iter)

            self.progress.emit(100, "Complete!")
            self.finished.emit(df_raw)

        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n\n{traceback.format_exc()}")


# ============================================================
# MAIN WINDOW
# ============================================================
class AsterixGUI(QMainWindow):
    """Main GUI window for ASTERIX Unified Decoder & Viewer with DYNAMIC filters."""

    def __init__(self):
        super().__init__()
        self.df_raw = None
        self.df_display = None
        self.model = None
        self.filters_dirty = False
        self.pending_filters = False
        self.init_ui()

    def init_ui(self):
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

        # Tab 1: Table view
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        table_layout.addWidget(self.table)
        self.tabs.addTab(table_widget, "📋 Table View")

        # Tab 2: Map view
        self.map_widget = MapWidget()
        self.tabs.addTab(self.map_widget, "🗺 Map View")

        layout.addWidget(self.tabs)

        # Filter panels
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(self.create_category_filter_panel())
        filter_layout.addWidget(self.create_detection_filter_panel())
        filter_layout.addWidget(self.create_altitude_filter_panel())
        filter_layout.addWidget(self.create_status_filter_panel())
        layout.addLayout(filter_layout)

        layout.addWidget(self.create_custom_filter_panel())

    # ============================================================
    # Menu bar
    # ============================================================
    def create_menu(self):
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

    # ============================================================
    # Load toolbar
    # ============================================================
    def create_load_toolbar(self):
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

    # ============================================================
    # Filter Panels
    # ============================================================
    def create_category_filter_panel(self):
        """Category ASTERIX filter panel"""
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
        """Detection filter panel"""
        group = QGroupBox("🎯 Detection")
        layout = QVBoxLayout()

        self.white_noise_check = QCheckBox("Remove White Noise (PSR-only)")
        self.white_noise_check.setChecked(True)
        self.white_noise_check.stateChanged.connect(self.on_filter_changed)
        layout.addWidget(self.white_noise_check)

        # NEW: Fixed transponder filter
        self.fixed_transponder_check = QCheckBox("Remove Fixed Transponders (7777)")
        self.fixed_transponder_check.setChecked(True)
        self.fixed_transponder_check.stateChanged.connect(self.on_filter_changed)
        layout.addWidget(self.fixed_transponder_check)

        group.setLayout(layout)
        return group

    def create_altitude_filter_panel(self):
        """Altitude / Flight Level filter panel"""
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
        """Status filter panel"""
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
        """Custom filters: Callsign, Speed, Geographic"""
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

        layout.addStretch()
        group.setLayout(layout)
        return group

    # ============================================================
    # Signal handler
    # ============================================================
    def on_filter_changed(self):
        """Called when any filter changes"""
        if self.df_raw is None:
            self.pending_filters = True
            if hasattr(self, 'status_label'):
                self.status_label.setText("⚙️ Filters selected — they will be applied automatically after loading.")
            return

        self.filters_dirty = True
        self.apply_btn.setEnabled(True)
        self.status_label.setText("⚠️ Filters changed — click 'Apply Filters' to update.")

    # ============================================================
    # Load and process ASTERIX file
    # ============================================================
    def load_file(self):
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
        """Handle completion of file load and decode"""
        self.df_raw = df_raw
        self.df_display = df_raw

        # Enable filter controls
        self.export_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.apply_btn.setEnabled(False)
        self.filters_dirty = False

        # ✅ FIX: Apply filters and then display
        self.apply_dynamic_filters()

    @Slot(str)
    def on_load_error(self, msg):
        QMessageBox.critical(self, "Error", f"Failed to load file:\n{msg}")

    # ============================================================
    # Display DataFrame with smart column filtering
    # ============================================================
    def display_dataframe(self, df):
        """Display DataFrame - all columns if both CAT selected, else category-specific"""
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

    # ============================================================
    # Apply filters on demand
    # ============================================================
    def apply_dynamic_filters(self):
        """Apply all filters using AsterixFilter methods"""
        if self.df_raw is None:
            return

        self.setCursor(Qt.CursorShape.WaitCursor)

        try:
            df = self.df_raw

            # 1. CATEGORY FILTER (✅ FIX: Use boolean array directly)
            if 'CAT' in df.columns:
                cat_mask = np.zeros(len(df), dtype=bool)
                if self.cat021_check.isChecked():
                    cat_mask |= (df['CAT'].to_numpy(copy=False) == 21)
                if self.cat048_check.isChecked():
                    cat_mask |= (df['CAT'].to_numpy(copy=False) == 48)
                df = df[cat_mask]

            # 2. WHITE NOISE FILTER
            if self.white_noise_check.isChecked():
                df = AsterixFilter.filter_white_noise(df)

            # 3. FIXED TRANSPONDER FILTER (NEW)
            if self.fixed_transponder_check.isChecked():
                df = AsterixFilter.filter_fixed_transponders(df)

            # 4. ALTITUDE FILTER
            min_fl = self.min_fl_spin.value()
            max_fl = self.max_fl_spin.value()
            if min_fl > 0 or max_fl < 600:
                df = AsterixFilter.filter_by_altitude(
                    df,
                    min_fl=min_fl if min_fl > 0 else None,
                    max_fl=max_fl if max_fl < 600 else None
                )

            # 5. AIRBORNE FILTER
            if self.airborne_check.isChecked():
                df = AsterixFilter.filter_airborne(df)

            # 6. ON GROUND FILTER
            if self.ground_check.isChecked():
                df = AsterixFilter.filter_on_ground(df)

            # 7. CALLSIGN FILTER (simplified: single pattern only)
            callsign_text = self.callsign_input.text().strip()
            if callsign_text and 'TI' in df.columns:
                df = AsterixFilter.filter_by_callsign(df, callsign_text)

            # 8. SPEED FILTER
            min_speed = self.min_speed_spin.value()
            if min_speed > 0:
                df = AsterixFilter.filter_by_speed(df, min_speed=min_speed)

            # 9. GEOGRAPHIC FILTER
            if self.geo_filter_check.isChecked():
                df = AsterixFilter.filter_by_geographic_bounds(df)

            self.df_display = df

            cats_in_data = set(self.df_display['CAT'].unique()) if 'CAT' in self.df_display.columns else set()
            only_cat021 = (cats_in_data == {21})
            self.airborne_check.setEnabled(not only_cat021)
            self.ground_check.setEnabled(not only_cat021)
            if only_cat021:
                self.airborne_check.setChecked(False)
                self.ground_check.setChecked(False)

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
        """Reset all filters to defaults"""
        self.cat021_check.setChecked(True)
        self.cat048_check.setChecked(True)
        self.white_noise_check.setChecked(True)
        self.fixed_transponder_check.setChecked(True)  # NEW
        self.min_fl_spin.setValue(0)
        self.max_fl_spin.setValue(600)
        self.airborne_check.setChecked(False)
        self.ground_check.setChecked(False)
        self.callsign_input.clear()
        self.min_speed_spin.setValue(0)
        self.geo_filter_check.setChecked(True)

        self.apply_dynamic_filters()

    # ============================================================
    # Helper methods
    # ============================================================
    def update_map(self):
        """Update map with filtered data"""
        if self.df_display is None or self.df_display.empty:
            print("⚠️ No data to display on map")
            return

        map_columns = ['LAT', 'LON', 'TI', 'TA', 'Time_sec', 'CAT', 'FL', 'GS_TVP(kt)', 'GS_BDS(kt)']
        available_cols = [col for col in map_columns if col in self.df_display.columns]

        if len(available_cols) < 3:
            print(f"⚠️ Insufficient map columns: {available_cols}")
            return

        try:
            map_data = self.df_display[available_cols]
            self.map_widget.load_data(map_data)
        except Exception as e:
            print(f"❌ Error updating map: {str(e)}")

    def update_status_label(self):
        """Update status bar with filter statistics"""
        if self.df_display is None:
            return
        cat021_count = (self.df_display['CAT'] == 21).sum() if 'CAT' in self.df_display.columns else 0
        cat048_count = (self.df_display['CAT'] == 48).sum() if 'CAT' in self.df_display.columns else 0
        total_count = len(self.df_display)
        self.status_label.setText(
            f"📊 Displaying: {total_count:,} records (CAT021: {cat021_count:,}, CAT048: {cat048_count:,}) | Total: {total_count:,} records"
        )

    # ============================================================
    # Export CSV
    # ============================================================
    def export_csv(self):
        """Export currently displayed DataFrame to CSV file"""
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


# ============================================================
# Entry point
# ============================================================
if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = AsterixGUI()
    window.show()
    sys.exit(app.exec())
