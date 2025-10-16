from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableView, QLabel, QLineEdit, QSpinBox,
    QCheckBox, QMessageBox, QProgressDialog, QGroupBox, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction
import pandas as pd
import sys

from gui.pandas_model import PandasModel
from src.decoders.asterix_file_reader import AsterixFileReader
from src.exporters.asterix_exporter import AsterixExporter
from src.utils.asterix_filter import AsterixFilter
from src.utils.handlers import decode_records


# ============================================================
# BACKGROUND THREAD
# ============================================================
class ProcessingThread(QThread):
    """Thread to read, decode, and export ASTERIX files (unified)."""
    finished = Signal(pd.DataFrame, pd.DataFrame)  # raw_df, filtered_df
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, file_path, apply_geo_filter, apply_white_noise):
        super().__init__()
        self.file_path = file_path
        self.apply_geo_filter = apply_geo_filter
        self.apply_white_noise = apply_white_noise

    def run(self):
        try:
            self.progress.emit(10, "Reading file...")
            reader = AsterixFileReader(self.file_path)
            records = list(reader.read_records())

            self.progress.emit(40, f"Decoding {len(records)} records...")
            records = decode_records(records)

            self.progress.emit(60, "Exporting to DataFrame...")
            df_raw = AsterixExporter.records_to_dataframe(records)

            self.progress.emit(80, "Applying filters...")
            df_filtered = df_raw.copy()

            if self.apply_white_noise:
                df_filtered = AsterixFilter.filter_white_noise(df_filtered)

            if self.apply_geo_filter:
                df_filtered = AsterixFilter.filter_by_geographic_bounds(df_filtered)

            self.progress.emit(100, "Complete!")
            self.finished.emit(df_raw, df_filtered)

        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n\n{traceback.format_exc()}")


# ============================================================
# MAIN WINDOW
# ============================================================
class AsterixGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.df_raw = None  # Unfiltered data
        self.df_display = None  # Currently displayed (filtered) data
        self.model = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("ASTERIX Unified Decoder & Viewer")
        self.setGeometry(100, 100, 1600, 900)

        # Menu bar
        self.create_menu()

        # Central layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Load toolbar
        load_toolbar = self.create_load_toolbar()
        layout.addLayout(load_toolbar)

        # Status
        self.status_label = QLabel("Ready — Load an ASTERIX file to begin.")
        layout.addWidget(self.status_label)

        # Table view
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Filter panel (dynamic filters after loading)
        filter_panel = self.create_filter_panel()
        layout.addWidget(filter_panel)

    # ------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------
    def create_menu(self):
        menubar = self.menuBar()

        # File menu
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

    # ------------------------------------------------------------
    # Load toolbar
    # ------------------------------------------------------------
    def create_load_toolbar(self):
        layout = QHBoxLayout()

        self.load_btn = QPushButton("📁 Load ASTERIX File")
        self.load_btn.clicked.connect(self.load_file)
        layout.addWidget(self.load_btn)

        self.geo_filter_check = QCheckBox("Geographic Filter")
        self.geo_filter_check.setChecked(True)
        self.geo_filter_check.setToolTip("Filter to Barcelona area on load")
        layout.addWidget(self.geo_filter_check)

        self.white_noise_check = QCheckBox("Remove White Noise")
        self.white_noise_check.setChecked(True)
        self.white_noise_check.setToolTip("Remove PSR-only detections (CAT048)")
        layout.addWidget(self.white_noise_check)

        layout.addStretch()

        self.export_btn = QPushButton("💾 Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)

        return layout

    # ------------------------------------------------------------
    # Dynamic filter panel (applied after data is loaded)
    # ------------------------------------------------------------
    def create_filter_panel(self):
        group = QGroupBox("🔍 Dynamic Filters (Applied After Loading)")
        layout = QHBoxLayout()

        # Callsign filter
        layout.addWidget(QLabel("Callsign:"))
        self.callsign_input = QLineEdit()
        self.callsign_input.setPlaceholderText("e.g., RYR, IBE")
        self.callsign_input.setMaximumWidth(150)
        # ✅ Use returnPressed instead of textChanged
        self.callsign_input.returnPressed.connect(self.apply_dynamic_filters)
        layout.addWidget(self.callsign_input)

        # Altitude filter
        layout.addWidget(QLabel("Min FL:"))
        self.min_fl_spin = QSpinBox()
        self.min_fl_spin.setRange(0, 600)
        self.min_fl_spin.setValue(0)
        self.min_fl_spin.setMaximumWidth(80)
        # ✅ Don't connect to valueChanged - only trigger on Apply button
        layout.addWidget(self.min_fl_spin)

        layout.addWidget(QLabel("Max FL:"))
        self.max_fl_spin = QSpinBox()
        self.max_fl_spin.setRange(0, 600)
        self.max_fl_spin.setValue(600)
        self.max_fl_spin.setMaximumWidth(80)
        # ✅ Don't connect to valueChanged
        layout.addWidget(self.max_fl_spin)

        # Airborne only
        self.airborne_check = QCheckBox("Airborne Only")
        # ✅ Don't connect to stateChanged
        layout.addWidget(self.airborne_check)

        # Category filter
        layout.addWidget(QLabel("Category:"))
        self.cat021_check = QCheckBox("CAT021")
        self.cat021_check.setChecked(True)
        # ✅ Don't connect to stateChanged
        layout.addWidget(self.cat021_check)

        self.cat048_check = QCheckBox("CAT048")
        self.cat048_check.setChecked(True)
        # ✅ Don't connect to stateChanged
        layout.addWidget(self.cat048_check)

        # ✅ NEW: Apply Filters button
        self.apply_filter_btn = QPushButton("✅ Apply Filters")
        self.apply_filter_btn.clicked.connect(self.apply_dynamic_filters)
        self.apply_filter_btn.setEnabled(False)
        self.apply_filter_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        layout.addWidget(self.apply_filter_btn)

        # Reset button
        self.reset_btn = QPushButton("🔄 Reset")
        self.reset_btn.clicked.connect(self.reset_filters)
        self.reset_btn.setEnabled(False)
        layout.addWidget(self.reset_btn)

        layout.addStretch()
        group.setLayout(layout)
        return group

    # ------------------------------------------------------------
    # Load and process ASTERIX file
    # ------------------------------------------------------------
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open ASTERIX File", "", "ASTERIX Files (*.ast);;All Files (*)"
        )
        if not file_path:
            return

        progress = QProgressDialog("Loading file...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(True)

        self.thread = ProcessingThread(
            file_path,
            self.geo_filter_check.isChecked(),
            self.white_noise_check.isChecked()
        )
        self.thread.finished.connect(self.on_load_complete)
        self.thread.error.connect(self.on_load_error)
        self.thread.progress.connect(lambda val, msg: (progress.setValue(val), progress.setLabelText(msg)))
        self.thread.start()

    @Slot(pd.DataFrame, pd.DataFrame)
    def on_load_complete(self, df_raw, df_filtered):
        self.df_raw = df_raw
        self.df_display = df_filtered
        self.display_dataframe(df_filtered)

        # ✅ Enable filter controls
        self.export_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.apply_filter_btn.setEnabled(True)

        cat021_count = (df_filtered['CAT'] == 21).sum()
        cat048_count = (df_filtered['CAT'] == 48).sum()

        self.status_label.setText(
            f"✅ Loaded {len(df_filtered):,} records "
            f"(CAT021: {cat021_count:,}, CAT048: {cat048_count:,})"
        )

    @Slot(str)
    def on_load_error(self, msg):
        QMessageBox.critical(self, "Error", f"Failed to load file:\n{msg}")

    # ------------------------------------------------------------
    # Display DataFrame
    # ------------------------------------------------------------
    def display_dataframe(self, df):
        """Display DataFrame using PandasModel"""
        self.model = PandasModel(df)
        self.table.setModel(self.model)

        # Resize key columns
        header = self.table.horizontalHeader()
        for col in range(min(15, df.shape[1])):
            self.table.resizeColumnToContents(col)

        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    # ------------------------------------------------------------
    # Dynamic filtering (applied to already-loaded data)
    # ------------------------------------------------------------
    def apply_dynamic_filters(self):
        """Apply filters dynamically based on UI controls"""
        if self.df_raw is None:
            return

        # Show cursor as busy during filtering
        self.setCursor(Qt.CursorShape.WaitCursor)

        try:
            df = self.df_raw.copy()

            # Category filter
            cat_mask = pd.Series([False] * len(df))
            if self.cat021_check.isChecked():
                cat_mask |= (df['CAT'] == 21)
            if self.cat048_check.isChecked():
                cat_mask |= (df['CAT'] == 48)
            df = df[cat_mask]

            # Callsign filter
            callsign_text = self.callsign_input.text().strip()
            if callsign_text:
                df = AsterixFilter.filter_by_callsign(df, callsign_text)

            # Altitude filter
            min_fl = self.min_fl_spin.value()
            max_fl = self.max_fl_spin.value()
            if min_fl > 0 or max_fl < 600:
                df = AsterixFilter.filter_by_altitude(
                    df,
                    min_fl=min_fl if min_fl > 0 else None,
                    max_fl=max_fl if max_fl < 600 else None
                )

            # Airborne only
            if self.airborne_check.isChecked():
                df = AsterixFilter.filter_airborne(df)

            self.df_display = df
            self.display_dataframe(df)

            cat021_count = (df['CAT'] == 21).sum()
            cat048_count = (df['CAT'] == 48).sum()

            self.status_label.setText(
                f"🔍 Filtered: {len(df):,} records "
                f"(CAT021: {cat021_count:,}, CAT048: {cat048_count:,})"
            )

        finally:
            # Restore normal cursor
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def reset_filters(self):
        """Reset all dynamic filters to default"""
        self.callsign_input.clear()
        self.min_fl_spin.setValue(0)
        self.max_fl_spin.setValue(600)
        self.airborne_check.setChecked(False)
        self.cat021_check.setChecked(True)
        self.cat048_check.setChecked(True)

        if self.df_raw is not None:
            self.df_display = self.df_raw.copy()
            self.display_dataframe(self.df_display)

            cat021_count = (self.df_display['CAT'] == 21).sum()
            cat048_count = (self.df_display['CAT'] == 48).sum()

            self.status_label.setText(
                f"✅ Reset filters: {len(self.df_display):,} records "
                f"(CAT021: {cat021_count:,}, CAT048: {cat048_count:,})"
            )

    # ------------------------------------------------------------
    # Export CSV
    # ------------------------------------------------------------
    def export_csv(self):
        if self.df_display is None or self.df_display.empty:
            QMessageBox.warning(self, "Warning", "No data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "asterix_output.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            AsterixExporter.export_to_csv(self.df_display, file_path)
            QMessageBox.information(
                self, "Export Complete",
                f"Exported {len(self.df_display):,} records to:\n{file_path}"
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
