from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableView, QLabel, QComboBox,
    QCheckBox, QMessageBox, QProgressDialog, QGroupBox, QHeaderView
)
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction
import pandas as pd
import sys

from gui.pandas_model import PandasModel
from src.decoders.asterix_file_reader import AsterixFileReader
from src.decoders.cat048_decoder import Cat048Decoder
from src.decoders.cat021_decoder import Cat021Decoder
from src.exporters.cat048_exporter import Cat048Exporter
from src.exporters.cat021_exporter import Cat021Exporter
from src.utils.preprocessor import AsterixPreprocessor


# ============================================================
# BACKGROUND THREAD
# ============================================================
class ProcessingThread(QThread):
    """Thread to read, decode, and preprocess ASTERIX files."""
    finished = Signal(pd.DataFrame, str)
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, file_path, category, apply_filters, apply_qnh):
        super().__init__()
        self.file_path = file_path
        self.category = category
        self.apply_filters = apply_filters
        self.apply_qnh = apply_qnh

    def run(self):
        try:
            self.progress.emit(10, "Reading file...")
            reader = AsterixFileReader(self.file_path)
            records = list(reader.read_records())

            self.progress.emit(40, f"Decoding {len(records)} records...")

            if self.category == 'CAT048':
                decoder = Cat048Decoder()
                for rec in records:
                    decoder.decode_record(rec)
                df = Cat048Exporter.records_to_dataframe(records)
                self.progress.emit(70, "Preprocessing...")
                df = AsterixPreprocessor.process_cat048(df, self.apply_filters, self.apply_qnh)
            else:
                decoder = Cat021Decoder()
                for rec in records:
                    decoder.decode_record(rec)
                df = Cat021Exporter.records_to_dataframe(records)
                self.progress.emit(70, "Preprocessing...")
                df = AsterixPreprocessor.process_cat021(df, self.apply_filters, False)

            self.progress.emit(100, "Complete!")
            self.finished.emit(df, self.category)

        except Exception as e:
            self.error.emit(str(e))


# ============================================================
# MAIN WINDOW
# ============================================================
class AsterixGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.df = None
        self.category = None
        self.model = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("ASTERIX Decoder Viewer (Read-Only)")
        self.setGeometry(100, 100, 1400, 900)

        # Menu bar
        self.create_menu()

        # Central layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Toolbar
        toolbar = self.create_toolbar()
        layout.addLayout(toolbar)

        # Status
        self.status_label = QLabel("Ready — Load an ASTERIX file to begin.")
        layout.addWidget(self.status_label)

        # Table (QTableView with model) ✅ CHANGED
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)  # Optional: allows column sorting
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        # Filter panel
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
    # Toolbar
    # ------------------------------------------------------------
    def create_toolbar(self):
        layout = QHBoxLayout()

        self.load_btn = QPushButton("📁 Load File")
        self.load_btn.clicked.connect(self.load_file)
        layout.addWidget(self.load_btn)

        layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(['CAT048 (Radar)', 'CAT021 (ADS-B)'])
        layout.addWidget(self.category_combo)

        self.filter_check = QCheckBox("Apply Geographic Filter")
        self.filter_check.setChecked(True)
        layout.addWidget(self.filter_check)

        self.qnh_check = QCheckBox("Apply QNH Correction")
        self.qnh_check.setChecked(True)
        layout.addWidget(self.qnh_check)

        layout.addStretch()

        self.export_btn = QPushButton("💾 Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)

        return layout

    # ------------------------------------------------------------
    # Filter tools (future expansion, simple placeholder)
    # ------------------------------------------------------------
    def create_filter_panel(self):
        group = QGroupBox("🔍 Viewer Info")
        layout = QHBoxLayout()
        layout.addWidget(QLabel("Use toolbar to load a file. Data will appear below."))
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

        category_text = self.category_combo.currentText()
        self.category = 'CAT048' if 'CAT048' in category_text else 'CAT021'

        progress = QProgressDialog("Loading file...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(True)

        self.thread = ProcessingThread(
            file_path,
            self.category,
            self.filter_check.isChecked(),
            self.qnh_check.isChecked()
        )
        self.thread.finished.connect(self.on_load_complete)
        self.thread.error.connect(self.on_load_error)
        self.thread.progress.connect(lambda val, msg: (progress.setValue(val), progress.setLabelText(msg)))
        self.thread.start()

    @Slot(pd.DataFrame, str)
    def on_load_complete(self, df, category):
        self.df = df
        self.category = category
        self.display_dataframe(df)
        self.export_btn.setEnabled(True)
        self.status_label.setText(f"✅ Loaded {len(df):,} records ({category})")

    @Slot(str)
    def on_load_error(self, msg):
        QMessageBox.critical(self, "Error", f"Failed to load file:\n{msg}")

    # ------------------------------------------------------------
    # Display DataFrame ✅ CHANGED: Uses PandasModel
    # ------------------------------------------------------------
    def display_dataframe(self, df):
        """Display DataFrame using model/view (fast for large datasets)"""
        self.model = PandasModel(df)
        self.table.setModel(self.model)

        # Resize first 12 columns to contents (avoid resizing ALL for performance)
        header = self.table.horizontalHeader()
        for col in range(min(12, df.shape[1])):
            self.table.resizeColumnToContents(col)

        # Allow manual resizing for remaining columns
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

    # ------------------------------------------------------------
    # Export CSV
    # ------------------------------------------------------------
    def export_csv(self):
        if self.df is None or self.df.empty:
            QMessageBox.warning(self, "Warning", "No data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", f"{self.category.lower()}_output.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            self.df.to_csv(file_path, index=False)
            QMessageBox.information(self, "Export Complete", f"Exported {len(self.df)} records.")
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
