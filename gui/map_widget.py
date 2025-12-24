from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QSlider, QLabel, QComboBox, QCheckBox, QMessageBox,
                                QDialog, QTextBrowser)
from PySide6.QtGui import QShortcut, QKeySequence
import pandas as pd
import json
import math

#VALORES DISTANCIA p3 (Código adaptado a lo de los compañeros del p3)
# Constantes de proyección
TMA_CENTER_LAT = 41 + 6/60 + 56.560/3600  # 41°06'56.560"N
TMA_CENTER_LON = 1 + 41/60 + 33.010/3600  # 1°41'33.010"E
RADIO_ESFERA_CONFORME_NM = 3438.954

def geodetic_to_conformal_lat(lat_rad: float) -> float:
    e = 0.0818191908426
    sin_lat = math.sin(lat_rad)
    term1 = ((1 - e * sin_lat) / (1 + e * sin_lat)) ** (e / 2)
    term2 = math.tan(math.pi / 4 + lat_rad / 2)
    chi = 2 * math.atan(term1 * term2) - math.pi / 2
    return chi

class MapWidget(QWidget):
    """Widget for displaying aircraft positions on 2D/3D map with trajectory tracking."""

    def __init__(self):
        super().__init__()
        self.df = None
        self.current_time = 0
        self.min_time = 0
        self.max_time = 0
        self.is_playing = False
        self.speed_multiplier = 1.0
        self.base_time_increment = 1.0
        self._user_scrubbing = False
        self._was_playing = False
        self.is_3d_mode = False
        self.source_filter = "both"
        self._last_valid_rotation = {}
        self.show_labels = False
        self.show_heatmap = False
        self.show_separation = False
        self.departure_schedule = []
        self.first_radar_detections = {}
        self.prev_distances_to_thr = {}
        self.init_ui()


    def _format_hms(self, seconds: float) -> str:
        """Convert seconds to HH:MM:SS format."""

        try:
            s = int(max(0, seconds))
            h = s // 3600
            m = (s % 3600) // 60
            sec = s % 60
            return f"{h:02d}:{m:02d}:{sec:02d}"

        except Exception:
            return "--:--:--"

    def init_ui(self):
        """Initialize user interface components with improved layout."""
        layout = QVBoxLayout()
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # ============ ROW 1: View Controls ============
        view_controls_layout = QHBoxLayout()

        self.view_mode_btn = QPushButton("🌐 Vista 3D")
        self.view_mode_btn.clicked.connect(self.toggle_view_mode)
        view_controls_layout.addWidget(self.view_mode_btn)

        view_controls_layout.addWidget(QLabel("Source:"))
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Both", "ADS-B Only", "Radar Only"])
        self.source_combo.currentIndexChanged.connect(self.on_source_filter_changed)
        view_controls_layout.addWidget(self.source_combo)

        self.labels_check = QCheckBox("Show Labels")
        self.labels_check.setChecked(False)
        self.labels_check.stateChanged.connect(self.toggle_labels)
        view_controls_layout.addWidget(self.labels_check)

        self.heatmap_check = QCheckBox("Heat Map")
        self.heatmap_check.setChecked(False)
        self.heatmap_check.stateChanged.connect(self.toggle_heatmap)
        view_controls_layout.addWidget(self.heatmap_check)

        view_controls_layout.addStretch()

        self.aircraft_label = QLabel("Aircraft: 0")
        view_controls_layout.addWidget(self.aircraft_label)

        self.help_btn = QPushButton("❓ Help")
        self.help_btn.clicked.connect(self.show_help)
        view_controls_layout.addWidget(self.help_btn)

        layout.addLayout(view_controls_layout)

        # ============ ROW 2: Playback Controls + Time Slider ============
        playback_layout = QHBoxLayout()

        # Play/Reset buttons
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self.toggle_play)
        self.play_btn.setEnabled(False)
        self.play_btn.setFixedWidth(70)
        playback_layout.addWidget(self.play_btn)

        self.reset_btn = QPushButton("🔄")
        self.reset_btn.setToolTip("Reset to start")
        self.reset_btn.clicked.connect(self.reset_simulation)
        self.reset_btn.setEnabled(False)
        self.reset_btn.setFixedWidth(35)
        playback_layout.addWidget(self.reset_btn)

        playback_layout.addSpacing(10)

        # Speed slider (compact)
        playback_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider()
        self.speed_slider.setOrientation(Qt.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(50)
        self.speed_slider.setValue(1)
        self.speed_slider.setFixedWidth(100)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        playback_layout.addWidget(self.speed_slider)

        self.speed_label = QLabel("1x")
        self.speed_label.setMinimumWidth(30)
        playback_layout.addWidget(self.speed_label)

        playback_layout.addSpacing(15)

        # Current time display
        self.time_label = QLabel("Now: --:--:--")
        self.time_label.setMinimumWidth(110)
        playback_layout.addWidget(self.time_label)

        playback_layout.addSpacing(15)

        self.time_start_label = QLabel("--:--:--")
        self.time_start_label.setMinimumWidth(60)
        playback_layout.addWidget(self.time_start_label)

        self.time_slider = QSlider()
        self.time_slider.setOrientation(Qt.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setEnabled(False)
        self.time_slider.setMinimumHeight(22)
        self.time_slider.sliderPressed.connect(self._on_time_slider_pressed)
        self.time_slider.sliderReleased.connect(self._on_time_slider_released)
        self.time_slider.valueChanged.connect(self._on_time_slider_changed)
        playback_layout.addWidget(self.time_slider, stretch=10)  # ✅ Gets maximum space

        self.time_end_label = QLabel("--:--:--")
        self.time_end_label.setMinimumWidth(60)
        playback_layout.addWidget(self.time_end_label)

        layout.addLayout(playback_layout)

        self.setLayout(layout)

        # Timer and shortcuts
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)

        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.skip_time(-10))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.skip_time(10))

        self.load_base_map()

    def show_help(self):
        """Display help dialog with all controls and features explained."""

        help_text = """
        
    <h2>ASTERIX DECODER - USER GUIDE</h2>

    <h3>🎮 Playback Controls (Top Bar)</h3>
    <ul>
    <li><b>▶ Play / ⏸ Pause:</b> Start or pause the simulation replay</li>
    <li><b>🔄 Reset:</b> Return to the beginning of the recording</li>
    <li><b>Speed Slider:</b> Adjust playback speed from 1x to 60x</li>
    <li><b>Time Slider:</b> Manually scrub through the timeline (drag to jump to specific time)</li>
    <li><b>Time Display:</b> Shows start time, end time, and current time (Now: HH:MM:SS)</li>
    <li><b>Aircraft Counter:</b> Real-time count showing ADS-B and Radar detections</li>
    </ul>

    <h3>🗺 View Controls (Top Bar)</h3>
    <ul>
    <li><b>🌐 Vista 3D / 🗺️ Vista 2D:</b> Toggle between 2D Leaflet map and 3D deck.gl visualization
      <ul style="margin-top:5px;">
      <li><i>2D Mode:</i> Traditional top-down map view with all features</li>
      <li><i>3D Mode:</i> Perspective view with altitude-based positioning (separation distance in 3D)</li>
      </ul>
    </li>
    <li><b>Source Dropdown:</b> Filter which detection system to display
      <ul style="margin-top:5px;">
      <li><i>Both:</i> Show ADS-B (CAT021) and Radar (CAT048) simultaneously</li>
      <li><i>ADS-B Only:</i> Show only automatic dependent surveillance broadcasts</li>
      <li><i>Radar Only:</i> Show only primary/secondary radar detections</li>
      </ul>
    </li>
    <li><b>Show Labels:</b> Display aircraft callsigns as floating text near each aircraft (works in 2D and 3D)</li>
    <li><b>Heat Map:</b> Show traffic density heatmap using color gradient (2D only)
      <ul style="margin-top:5px;">
      <li><i>Blue:</i> Low traffic density</li>
      <li><i>Green/Yellow:</i> Medium traffic density</li>
      <li><i>Red:</i> High traffic density</li>
      </ul>
    </li>
    </ul>

    <h3>🔍 Filter Panel (Bottom Bar)</h3>
    <ul>
    <li><b>📡 ASTERIX Category:</b> Select which ASTERIX categories to display (CAT021 ADS-B / CAT048 Radar)</li>
    <li><b>🎯 Detection:</b> Remove white noise (PSR-only) and fixed transponders (Mode 7777)</li>
    <li><b>📏 Altitude:</b> Filter by Flight Level range (Min FL / Max FL)</li>
    <li><b>✈️ Status:</b> Filter by aircraft status (Airborne Only / On Ground Only)</li>
    <li><b>Callsign:</b> Filter by partial callsign match (e.g., "RYR" for Ryanair flights)</li>
    <li><b>Min Speed:</b> Filter aircraft below specified ground speed (in knots)</li>
    <li><b>Geographic Bounds:</b> Limit display to Barcelona TMA area</li>
    </ul>

    <h3>✈️ P3 Departure Analysis (Bottom Bar)</h3>
    <ul>
    <li><b>📂 Load P3 Excel:</b> Load an Excel file containing departure schedule
      <ul style="margin-top:5px;">
      <li>Excel must contain columns: <i>Indicativo</i> (callsign) and <i>Hora Despegue LEBL</i> (departure time)</li>
      <li>Only flights present in both Excel and radar data will be loaded</li>
      </ul>
    </li>
    <li><b>Only P3 Take-offs:</b> Show only aircraft from the loaded Excel departure list</li>
    <li><b>📏 Show Separation:</b> Display separation line and distance between last two consecutive departures
      <ul style="margin-top:5px;">
      <li><i>2D Mode:</i> Horizontal distance (great circle) in Nautical Miles</li>
      <li><i>3D Mode:</i> True 3D distance including altitude difference</li>
      <li>Line automatically updates as aircraft depart and new flights appear</li>
      <li>Distance calculated between current positions (real-time tracking)</li>
      </ul>
    </li>
    </ul>

    <h3>✈️ Aircraft Information</h3>
    <ul>
    <li><b>Click on any aircraft</b> to see detailed popup with:
      <ul style="margin-top:5px;">
      <li>Callsign / Address</li>
      <li>Detection source (ADS-B or Radar)</li>
      <li>Mode 3/A code</li>
      <li>Altitude (Flight Level or feet)</li>
      <li>Ground speed</li>
      </ul>
    </li>
    <li><b>Colored trails:</b> Each aircraft has a unique colored trajectory showing its path</li>
    <li><b>Popups persist:</b> They stay open during playback until manually closed</li>
    </ul>

    <h3>⌨️ Keyboard Shortcuts</h3>
    <ul>
    <li><b>Space:</b> Play/Pause toggle</li>
    <li><b>← Left Arrow:</b> Skip backward 10 seconds</li>
    <li><b>→ Right Arrow:</b> Skip forward 10 seconds</li>
    </ul>

    <h3>💡 Tips</h3>
    <ul>
    <li>Use filters to focus on specific flights or areas of interest</li>
    <li>Increase playback speed to quickly scan through long recordings</li>
    <li>In 3D mode, hold Shift and drag to adjust camera pitch</li>
    <li>Load P3 Excel before starting playback for real-time separation monitoring</li>
    <li>Combine multiple filters for precise analysis (e.g., P3 departures + altitude range)</li>
    </ul>
    """


        dialog = QDialog(self)
        dialog.setWindowTitle("ASTERIX DECODER - USER GUIDE")
        dialog.resize(800, 700)

        layout = QVBoxLayout()

        text_browser = QTextBrowser()
        text_browser.setHtml(help_text)
        text_browser.setOpenExternalLinks(False)
        layout.addWidget(text_browser)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()


    def toggle_labels(self, state):
        """Toggle aircraft labels on/off."""

        self.show_labels = (state == Qt.CheckState.Checked.value)
        if self.df is not None:
            self.update_aircraft_positions()

    def toggle_heatmap(self, state):
        """Toggle heatmap on/off."""

        self.show_heatmap = (state == Qt.CheckState.Checked.value)
        if self.show_heatmap and self.df is not None:
            self.generate_heatmap()

        else:
            self.web_view.page().runJavaScript(
                "if (window.heatLayer) { map.removeLayer(window.heatLayer); window.heatLayer = null; }")

    def generate_heatmap(self):
        """Generate heatmap from all trajectory data."""

        if self.df is None or self.df.empty:
            return

        heatmap_data = []

        for _, row in self.df.iterrows():
            if pd.notna(row.get('LAT')) and pd.notna(row.get('LON')):
                heatmap_data.append([float(row['LAT']), float(row['LON']), 0.5])

        if len(heatmap_data) > 10000:
            step = len(heatmap_data) // 10000
            heatmap_data = heatmap_data[::step]

        js_code = f"addHeatmap({json.dumps(heatmap_data)});"
        self.web_view.page().runJavaScript(js_code)

    def on_source_filter_changed(self, index):
        """Handle source filter selection change."""
        filters = ["both", "adsb", "radar"]
        self.source_filter = filters[index]

        if self.df is not None:
            self.web_view.page().runJavaScript("resetTrails();")
            self.update_aircraft_positions()

    def toggle_view_mode(self):
        """Switch between 2D and 3D map views."""

        self.is_3d_mode = not self.is_3d_mode
        if self.is_3d_mode:
            self.view_mode_btn.setText("🗺️ Vista 2D")
            self.heatmap_check.setEnabled(False)
            self.load_3d_map()

        else:
            self.view_mode_btn.setText("🌐 Vista 3D")
            self.heatmap_check.setEnabled(True)
            self.load_base_map()

        if self.df is not None:
            if self.show_heatmap and not self.is_3d_mode:
                self.generate_heatmap()
            self.update_aircraft_positions()

    def set_separation_mode(self, enabled: bool):
        """Activar/desactivar modo de separación."""

        self.show_separation = enabled
        if hasattr(self, 'web_view'):
            js_code = f"if(window.setSeparationMode) setSeparationMode({str(enabled).lower()});"
            self.web_view.page().runJavaScript(js_code)
        self.update_aircraft_positions()

    def set_departure_schedule(self, schedule):
        """Guardar horario de despegues desde Excel."""

        self.departure_schedule = schedule

    def calculate_separation_lines(self, aircraft_list):
        if not self.show_separation or not self.departure_schedule:
            return []

        detected_to_remove = [
            callsign for callsign, det_time in self.first_radar_detections.items()
            if det_time > self.current_time
        ]
        for callsign in detected_to_remove:
            del self.first_radar_detections[callsign]
            if callsign in self.prev_distances_to_thr:
                del self.prev_distances_to_thr[callsign]

        THRESHOLDS = {
            'LEBL-24L': {'lat': 41 + 17 / 60 + 31.99 / 3600, 'lon': 2 + 6 / 60 + 11.81 / 3600},
            'LEBL-06R': {'lat': 41 + 16 / 60 + 56.32 / 3600, 'lon': 2 + 4 / 60 + 27.66 / 3600},
            'LEBL-24R': {'lat': 41 + 16 / 60 + 56.32 / 3600, 'lon': 2 + 4 / 60 + 27.66 / 3600},
            'LEBL-06L': {'lat': 41 + 17 / 60 + 31.99 / 3600, 'lon': 2 + 6 / 60 + 11.81 / 3600}
        }

        live_positions = {}
        for ac in aircraft_list:
            raw_call = ac.get('callsign', '')
            if raw_call:
                clean_call = str(raw_call).strip().upper()
                if clean_call not in live_positions:
                    live_positions[clean_call] = ac
                elif ac.get('cat') == 48:
                    live_positions[clean_call] = ac

        schedule_dict = {callsign: (atot, runway) for callsign, atot, runway in self.departure_schedule}

        for callsign, (atot, runway) in schedule_dict.items():
            if callsign in self.first_radar_detections:
                continue

            if self.current_time < atot:
                continue

            if callsign not in live_positions:
                continue

            if runway not in THRESHOLDS:
                continue

            ac = live_positions[callsign]
            threshold = THRESHOLDS[runway]

            try:
                lat0_rad = math.radians(TMA_CENTER_LAT)
                lon0_rad = math.radians(TMA_CENTER_LON)
                chi0 = geodetic_to_conformal_lat(lat0_rad)

                lat_ac_rad = math.radians(ac['lat'])
                lon_ac_rad = math.radians(ac['lon'])
                chi_ac = geodetic_to_conformal_lat(lat_ac_rad)
                dlon_ac = lon_ac_rad - lon0_rad
                denom_ac = 1 + math.sin(chi0) * math.sin(chi_ac) + math.cos(chi0) * math.cos(chi_ac) * math.cos(dlon_ac)
                if abs(denom_ac) < 1e-10:
                    continue
                k_ac = (2 * RADIO_ESFERA_CONFORME_NM) / denom_ac
                x_ac = k_ac * math.cos(chi_ac) * math.sin(dlon_ac)
                y_ac = k_ac * (
                            math.cos(chi0) * math.sin(chi_ac) - math.sin(chi0) * math.cos(chi_ac) * math.cos(dlon_ac))

                lat_thr_rad = math.radians(threshold['lat'])
                lon_thr_rad = math.radians(threshold['lon'])
                chi_thr = geodetic_to_conformal_lat(lat_thr_rad)
                dlon_thr = lon_thr_rad - lon0_rad
                denom_thr = 1 + math.sin(chi0) * math.sin(chi_thr) + math.cos(chi0) * math.cos(chi_thr) * math.cos(
                    dlon_thr)
                if abs(denom_thr) < 1e-10:
                    continue
                k_thr = (2 * RADIO_ESFERA_CONFORME_NM) / denom_thr
                x_thr = k_thr * math.cos(chi_thr) * math.sin(dlon_thr)
                y_thr = k_thr * (math.cos(chi0) * math.sin(chi_thr) - math.sin(chi0) * math.cos(chi_thr) * math.cos(
                    dlon_thr))

                dist_to_thr = math.sqrt((x_ac - x_thr) ** 2 + (y_ac - y_thr) ** 2)

                prev_dist = self.prev_distances_to_thr.get(callsign)

                if prev_dist is not None and dist_to_thr >= 0.5 and dist_to_thr > prev_dist:
                    self.first_radar_detections[callsign] = self.current_time

                self.prev_distances_to_thr[callsign] = dist_to_thr

            except:
                continue

        departed = [
            callsign for callsign in self.first_radar_detections.keys()
            if callsign in live_positions
        ]

        if len(departed) < 2:
            return []

        departed_sorted = sorted(departed, key=lambda c: self.first_radar_detections[c])
        last_two = departed_sorted[-2:]

        penultimo_callsign = last_two[0]
        ultimo_callsign = last_two[1]

        ac1 = live_positions[penultimo_callsign]
        ac2 = live_positions[ultimo_callsign]

        lat1, lon1 = ac1['lat'], ac1['lon']
        lat2, lon2 = ac2['lat'], ac2['lon']

        try:
            lat0_rad = math.radians(TMA_CENTER_LAT)
            lon0_rad = math.radians(TMA_CENTER_LON)
            chi0 = geodetic_to_conformal_lat(lat0_rad)

            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            chi1 = geodetic_to_conformal_lat(lat1_rad)
            dlon1 = lon1_rad - lon0_rad
            denominator1 = 1 + math.sin(chi0) * math.sin(chi1) + math.cos(chi0) * math.cos(chi1) * math.cos(dlon1)
            if abs(denominator1) < 1e-10:
                return []
            k1 = (2 * RADIO_ESFERA_CONFORME_NM) / denominator1
            x1 = k1 * math.cos(chi1) * math.sin(dlon1)
            y1 = k1 * (math.cos(chi0) * math.sin(chi1) - math.sin(chi0) * math.cos(chi1) * math.cos(dlon1))

            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)
            chi2 = geodetic_to_conformal_lat(lat2_rad)
            dlon2 = lon2_rad - lon0_rad
            denominator2 = 1 + math.sin(chi0) * math.sin(chi2) + math.cos(chi0) * math.cos(chi2) * math.cos(dlon2)
            if abs(denominator2) < 1e-10:
                return []
            k2 = (2 * RADIO_ESFERA_CONFORME_NM) / denominator2
            x2 = k2 * math.cos(chi2) * math.sin(dlon2)
            y2 = k2 * (math.cos(chi0) * math.sin(chi2) - math.sin(chi0) * math.cos(chi2) * math.cos(dlon2))

            dist_horizontal_nm = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        except:
            return []

        if self.is_3d_mode:
            alt1_m = (ac1.get('fl') or 0) * 30.48
            alt2_m = (ac2.get('fl') or 0) * 30.48
            dist_vertical_km = abs(alt2_m - alt1_m) / 1000
            dist_3d_km = math.sqrt(dist_horizontal_nm ** 2 / (0.539957 ** 2) + dist_vertical_km ** 2)
            dist_nm = dist_3d_km * 0.539957
            dist_label = f"{dist_nm:.3f} NM"
        else:
            dist_nm = dist_horizontal_nm
            dist_label = f"{dist_nm:.3f} NM"

        return [{
            'from_lat': lat1,
            'from_lon': lon1,
            'to_lat': lat2,
            'to_lon': lon2,
            'from_alt': (ac1.get('fl') or 0) * 30.48,
            'to_alt': (ac2.get('fl') or 0) * 30.48,
            'dist': dist_label,
            'from_call': penultimo_callsign,
            'to_call': ultimo_callsign
        }]

    def load_base_map(self):

        html = """
        
        
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>ASTERIX Radar View</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
        <style>
        
            body { margin: 0; padding: 0; }
            #map { width: 100%; height: 100vh; }
            .aircraft-marker { background: transparent; border: none; display: flex; align-items: center; justify-content: center; font-size: 26px; text-shadow: 0 0 3px rgba(0,0,0,0.5); }
            .leaflet-popup-content { background: rgba(255, 255, 255, 0.95) !important; border-radius: 6px !important; color: #333 !important; font-size: 13px !important; }
            .leaflet-popup-tip { background: rgba(255, 255, 255, 0.95) !important; }
            .leaflet-tooltip { background: rgba(0, 0, 0, 0.7) !important; border: none !important; color: white !important; font-size: 10px !important; font-weight: bold !important; padding: 2px 5px !important; border-radius: 3px !important; box-shadow: 0 1px 3px rgba(0,0,0,0.4) !important; }
            .leaflet-tooltip-top:before, .leaflet-tooltip-bottom:before, .leaflet-tooltip-left:before, .leaflet-tooltip-right:before { border: none !important; }
            .info.legend { background: rgba(255,255,255,0.9); padding: 8px 10px; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.2); line-height: 1.4em; font: 12px/1.4 'Segoe UI', Arial, sans-serif; }
            .legend .item { display: flex; align-items: center; margin: 4px 0; }
            .legend .swatch { width: 14px; height: 14px; margin-right: 6px; border-radius: 2px; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.2); }
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
        
            var separationLines = [];
            var isSeparationMode = false;

            window.setSeparationMode = function(enabled) {
                isSeparationMode = enabled;
                if (!enabled) {
                    separationLines.forEach(l => map.removeLayer(l));
                    separationLines = [];
                    Object.values(aircraftMarkers).forEach(m => m.setOpacity(1.0));
                }
            };

            window.drawSeparationLines = function(lines) {
                separationLines.forEach(l => map.removeLayer(l));
                separationLines = [];

                if (!isSeparationMode) return;

                lines.forEach(l => {
                    var poly = L.polyline([[l.from_lat, l.from_lon], [l.to_lat, l.to_lon]], {
                        color: 'red', dashArray: '5, 10', weight: 2, opacity: 0.8
                    }).addTo(map);

                    var midLat = (l.from_lat + l.to_lat) / 2;
                    var midLon = (l.from_lon + l.to_lon) / 2;
                    var label = L.marker([midLat, midLon], {
                        icon: L.divIcon({
                            className: 'sep-label',
                            html: '<div style="background:white; border:1px solid red; padding:2px; font-size:10px; font-weight:bold;">' + l.dist + '</div>',
                            iconSize: [50, 20]
                        })
                    }).addTo(map);

                    separationLines.push(poly);
                    separationLines.push(label);
                });

                Object.values(aircraftMarkers).forEach(m => m.setOpacity(0.4));
            };

            var map = L.map('map', {
                zoomControl: true,
                attributionControl: false,
                closePopupOnClick: false
            }).setView([41.2972, 2.0833], 11);

            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
                maxZoom: 19, attribution: '', opacity: 0.95
            }).addTo(map);

            var radarIcon = L.divIcon({
                html: '<div style="font-size: 18px; font-weight: bold; color: #8B4513; text-shadow: 0 0 4px rgba(0,0,0,0.8);">📡</div>',
                className: 'aircraft-marker',
                iconSize: [24, 24],
                iconAnchor: [12, 12]
            });
            L.marker([41.300702, 2.102058], {icon: radarIcon, zIndexOffset: 1000}).bindPopup('<b>Barcelona Radar</b><br>SAC: 20, SIC: 129').addTo(map);

            var legend = L.control({position: 'topright'});
            legend.onAdd = function () {
                var div = L.DomUtil.create('div', 'info legend');
                div.innerHTML = '<strong>Detection Source</strong><br>' +
                    '<div class="item"><span class="swatch" style="background:#FFA500"></span>ADS-B (CAT021)</div>' +
                    '<div class="item"><span class="swatch" style="background:#FF4D4D"></span>Radar (CAT048)</div>';
                return div;
            };
            
            legend.addTo(map);

            var aircraftMarkers = {};
            var aircraftTrails = {};
            var aircraftColors = {};
            var openPopups = {};
            window.heatLayer = null;
            window.showLabels = false;

            function getAircraftColor(address) {
                if (aircraftColors[address]) return aircraftColors[address];
                var hash = 0;
                for (var i = 0; i < address.length; i++) { hash = address.charCodeAt(i) + ((hash << 5) - hash); }
                var hue = Math.abs(hash % 360);
                var saturation = 70 + (Math.abs(hash >> 8) % 20);
                var lightness = 50 + (Math.abs(hash >> 16) % 15);
                var color = 'hsl(' + hue + ', ' + saturation + '%, ' + lightness + '%)';
                aircraftColors[address] = color;
                return color;
            }

            function getBearing(lat1, lon1, lat2, lon2) {
                var dLon = (lon2 - lon1);
                var y = Math.sin(dLon * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180);
                var x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) - Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos(dLon * Math.PI / 180);
                var bearing = Math.atan2(y, x) * 180 / Math.PI;
                return (bearing + 360) % 360;
            }

            window.addHeatmap = function(data) {
                if (window.heatLayer) {
                    map.removeLayer(window.heatLayer);
                }
                
                window.heatLayer = L.heatLayer(data, {
                    radius: 20,
                    blur: 15,
                    maxZoom: 13,
                    max: 1.0,
                    gradient: {0.0: 'blue', 0.5: 'lime', 0.7: 'yellow', 1.0: 'red'}
                }).addTo(map);
            };

            window.cleanFutureTrails = function(currentTime) {
                Object.keys(aircraftTrails).forEach(function(trailKey) {
                    if (aircraftTrails[trailKey]) {
                        aircraftTrails[trailKey] = aircraftTrails[trailKey].filter(function(point) {
                            return point.time <= currentTime;
                        });
                    }
                });
            };

            window.updateAircraft = function(data, showLabels) {
                window.showLabels = showLabels;
            
                // Track which markers should remain open
                var currentOpenPopups = {};
                Object.keys(aircraftMarkers).forEach(function(markerId) {
                    var marker = aircraftMarkers[markerId];
                    if (marker.isPopupOpen()) {
                        currentOpenPopups[markerId] = true;
                    }
                });
            
                // ✅ Update existing markers instead of removing all
                var seenMarkers = {};
                
                data.forEach(function(aircraft) {
                    var markerId = aircraft.address + '_' + aircraft.cat;
                    seenMarkers[markerId] = true;
                    
                    var badgeColor = (aircraft.cat === 21 ? '#FFA500' : '#FF4D4D');
                    var srcText = (aircraft.cat === 21 ? 'ADS-B (CAT021)' : 'Radar (CAT048)');
                    
                    var rotation = aircraft.heading || 0;
                    var trailKey = aircraft.address + '_' + aircraft.cat;
            
                    // Calculate rotation from trail
                    if (aircraftTrails[trailKey] && aircraftTrails[trailKey].length >= 2) {
                        var trail = aircraftTrails[trailKey];
                        var prevPos = trail[trail.length - 2];
                        var currPos = trail[trail.length - 1];
                        var latDiff = Math.abs(currPos.lat - prevPos.lat);
                        var lonDiff = Math.abs(currPos.lon - prevPos.lon);
                        
                        if (latDiff > 0.0001 || lonDiff > 0.0001) {
                            rotation = getBearing(prevPos.lat, prevPos.lon, currPos.lat, currPos.lon);
                            aircraft.lastRotation = rotation;
                        } else if (aircraft.lastRotation !== undefined) {
                            rotation = aircraft.lastRotation;
                        }
                    } else if (aircraft.lastRotation !== undefined) {
                        rotation = aircraft.lastRotation;
                    }
            
                    var altitudeStr = aircraft.altitude_display || 'N/A';
                    var mode3aStr = aircraft.mode3a || 'N/A';
                    
                    var popupContent = '<b>' + (aircraft.callsign || aircraft.address) + '</b><br>' +
                                       '<strong>Source:</strong> ' + srcText + '<br>' +
                                       '<strong>Mode3/A:</strong> ' + mode3aStr + '<br>' +
                                       '<strong>Altitude:</strong> ' + altitudeStr + '<br>' +
                                       '<strong>Speed:</strong> ' + (aircraft.speed !== null ? Math.round(aircraft.speed) : 'N/A') + ' kt<br>' +
                                       '<strong>Heading:</strong> ' + Math.round(rotation) + '°';
            
                    // ✅ If marker exists, UPDATE it instead of recreating
                    if (aircraftMarkers[markerId]) {
                        var existingMarker = aircraftMarkers[markerId];
                        
                        // Update position
                        existingMarker.setLatLng([aircraft.lat, aircraft.lon]);
                        
                        // Update icon rotation
                        var icon = L.divIcon({
                            html: '<div style="transform: rotate(' + (rotation - 90) + 'deg); display: inline-block; font-size: 26px; text-shadow: 0 0 3px rgba(0,0,0,0.5); color:' + badgeColor + ';">✈</div>',
                            className: 'aircraft-marker',
                            iconSize: [26, 26],
                            iconAnchor: [13, 13]
                        });
                        existingMarker.setIcon(icon);
                        
                        // ✅ Update popup content WITHOUT closing it
                        if (existingMarker.getPopup()) {
                            existingMarker.getPopup().setContent(popupContent);
                        }
                        
                        // Update label if needed
                        if (showLabels && aircraft.callsign) {
                            if (!existingMarker.getTooltip()) {
                                existingMarker.bindTooltip(aircraft.callsign, {
                                    permanent: true,
                                    direction: 'top',
                                    offset: [0, -10],
                                    opacity: 0.9,
                                    className: 'aircraft-label'
                                });
                            }
                        } else {
                            existingMarker.unbindTooltip();
                        }
                        
                        // Update trail
                        if (existingMarker.trailLine) {
                            map.removeLayer(existingMarker.trailLine);
                        }
                        
                    } else {
                        // ✅ Create NEW marker only if it doesn't exist
                        var icon = L.divIcon({
                            html: '<div style="transform: rotate(' + (rotation - 90) + 'deg); display: inline-block; font-size: 26px; text-shadow: 0 0 3px rgba(0,0,0,0.5); color:' + badgeColor + ';">✈</div>',
                            className: 'aircraft-marker',
                            iconSize: [26, 26],
                            iconAnchor: [13, 13]
                        });
            
                        var marker = L.marker([aircraft.lat, aircraft.lon], {icon: icon, zIndexOffset: 500});
                        
                        var popup = L.popup({
                            autoClose: false,
                            closeOnClick: false
                        }).setContent(popupContent);
                        
                        marker.bindPopup(popup);
                        
                        marker.on('popupopen', function() {
                            currentOpenPopups[markerId] = true;
                        });
                        
                        marker.on('popupclose', function() {
                            delete currentOpenPopups[markerId];
                        });
            
                        if (showLabels && aircraft.callsign) {
                            marker.bindTooltip(aircraft.callsign, {
                                permanent: true,
                                direction: 'top',
                                offset: [0, -10],
                                opacity: 0.9,
                                className: 'aircraft-label'
                            });
                        }
            
                        marker.addTo(map);
                        marker.lastRotation = rotation;
                        aircraftMarkers[markerId] = marker;
                    }
                    
                    // ✅ Reopen popup if it was open before
                    if (currentOpenPopups[markerId]) {
                        aircraftMarkers[markerId].openPopup();
                    }
            
                    // Update trail
                    if (!aircraftTrails[trailKey]) {
                        aircraftTrails[trailKey] = [];
                    }
            
                    var newPoint = {lat: aircraft.lat, lon: aircraft.lon, time: aircraft.time_sec || 0};
                    var trail = aircraftTrails[trailKey];
            
                    if (trail.length === 0 ||
                        Math.abs(newPoint.lat - trail[trail.length-1].lat) > 0.0001 ||
                        Math.abs(newPoint.lon - trail[trail.length-1].lon) > 0.0001) {
                        trail.push(newPoint);
                    }
            
                    if (trail.length > 1) {
                        var trailColor = getAircraftColor(aircraft.address);
                        var trailCoords = trail.map(function(p) { return [p.lat, p.lon]; });
                        aircraftMarkers[markerId].trailLine = L.polyline(trailCoords, {
                            color: trailColor,
                            weight: 2,
                            opacity: 0.7,
                            lineCap: 'round',
                            lineJoin: 'round',
                            smoothFactor: 1.0
                        }).addTo(map);
                    }
                });
            
                // ✅ Remove markers for aircraft that are no longer visible
                Object.keys(aircraftMarkers).forEach(function(markerId) {
                    if (!seenMarkers[markerId]) {
                        var marker = aircraftMarkers[markerId];
                        if (marker.trailLine) {
                            map.removeLayer(marker.trailLine);
                        }
                        map.removeLayer(marker);
                        delete aircraftMarkers[markerId];
                        delete aircraftTrails[markerId];
                    }
                });
            };

            window.resetTrails = function() {
                Object.values(aircraftMarkers).forEach(marker => {
                    if (marker.trailLine) {
                        map.removeLayer(marker.trailLine);
                    }
                    map.removeLayer(marker);
                });
                
                aircraftMarkers = {};
                aircraftTrails = {};
                aircraftColors = {};
                openPopups = {};
                if (window.heatLayer) {
                    map.removeLayer(window.heatLayer);
                    window.heatLayer = null;
                }
            };
        </script>
    </body>
    </html>
        """

        self.web_view.setHtml(html)

    def load_3d_map(self):

        html = """
        
        
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <title>Vista 3D - deck.gl</title>
        <script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>
        <script src="https://unpkg.com/maplibre-gl@3.0.0/dist/maplibre-gl.js"></script>
        <link href="https://unpkg.com/maplibre-gl@3.0.0/dist/maplibre-gl.css" rel="stylesheet" />
        <style>
            body, html { margin: 0; padding: 0; height: 100vh; width: 100%; overflow: hidden; }
            #map { width: 100%; height: 100%; }

            .legend {
                position: absolute;
                top: 10px;
                right: 10px;
                background: rgba(255, 255, 255, 0.95);
                padding: 12px 15px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                line-height: 1.6;
                z-index: 1000;
            }
            
            .legend-title {
                font-weight: bold;
                margin-bottom: 8px;
                font-size: 14px;
            }
            
            .legend-item {
                display: flex;
                align-items: center;
                margin: 5px 0;
            }
            
            .legend-swatch {
                width: 16px;
                height: 16px;
                margin-right: 8px;
                border-radius: 50%;
                box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.2);
            }

            .controls-hint {
                position: absolute;
                bottom: 10px;
                left: 10px;
                background: rgba(255, 255, 255, 0.9);
                padding: 10px 12px;
                border-radius: 6px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                color: #666;
                z-index: 999;
                line-height: 1.4;
            }
            
            .controls-hint strong {
                color: #333;
            }

            .popup {
                position: absolute;
                background: rgba(255, 255, 255, 0.98);
                padding: 12px 15px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                z-index: 999;
                max-width: 250px;
                border-left: 4px solid #007bff;
                pointer-events: none;
            }
            
            .popup-title {
                font-weight: bold;
                font-size: 14px;
                margin-bottom: 6px;
                color: #333;
            }
            
            .popup-content {
                line-height: 1.5;
                color: #555;
            }
            
            .popup-close {
                position: absolute;
                top: 5px;
                right: 8px;
                cursor: pointer;
                font-size: 18px;
                color: #999;
                pointer-events: auto;
            }
            
            .popup-close:hover {
                color: #333;
            }
            
        </style>
    </head>
    <body>
        <div id="map"></div>

        <div class="legend">
            <div class="legend-title">Detection Source</div>
            <div class="legend-item">
                <span class="legend-swatch" style="background:#FFD700"></span>
                <span>ADS-B (CAT021)</span>
            </div>
            <div class="legend-item">
                <span class="legend-swatch" style="background:#FF4D4D"></span>
                <span>Radar (CAT048)</span>
            </div>
        </div>

        <div class="controls-hint">
            <strong>3D Controls:</strong><br>
            <strong>Drag:</strong> Rotate view<br>
            <strong>Scroll:</strong> Zoom<br>
            <strong>Shift + Drag:</strong> Incline
        </div>

        <div id="popup" class="popup" style="display:none;">
            <span class="popup-close" onclick="closePopup()">✕</span>
            <div class="popup-title" id="popup-title"></div>
            <div class="popup-content" id="popup-content"></div>
        </div>

        <script>
            const {DeckGL, ScatterplotLayer, PathLayer, ColumnLayer, TextLayer, LineLayer} = deck;
            let aircraftData = [];
            let trailsData = {};
            let radarPosition = {lon: 2.102058, lat: 41.300702};
            let showLabels = false;

            const deckgl = new DeckGL({
                container: 'map',
                mapStyle: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
                initialViewState: { longitude: 2.0833, latitude: 41.2972, zoom: 10, pitch: 65, bearing: -15 },
                controller: {
                    doubleClickZoom: true,
                    scrollZoom: true,
                    dragPan: true,
                    dragRotate: true,
                    touchRotate: true,
                    keyboard: true
                },
                
                layers: [],
                onClick: handleClick
            });

            function getColor(cat) {
                return cat === 48 ? [255, 77, 77, 255] : [255, 215, 0, 255];
            }

            function hashColor(str) {
                let hash = 0;
                for (let i = 0; i < str.length; i++) { hash = str.charCodeAt(i) + ((hash << 5) - hash); }
                const hue = Math.abs(hash % 360);
                const sat = 70 + (Math.abs(hash >> 8) % 20);
                const light = 50 + (Math.abs(hash >> 16) % 15);
                const c = (1 - Math.abs(2 * light/100 - 1)) * sat/100;
                const x = c * (1 - Math.abs((hue / 60) % 2 - 1));
                const m = light/100 - c/2;
                let r, g, b;
                if (hue < 60) { r = c; g = x; b = 0; }
                else if (hue < 120) { r = x; g = c; b = 0; }
                else if (hue < 180) { r = 0; g = c; b = x; }
                else if (hue < 240) { r = 0; g = x; b = c; }
                else if (hue < 300) { r = x; g = 0; b = c; }
                else { r = c; g = 0; b = x; }
                return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255), 120];
            }

            function handleClick(info) {
                if (info.layer && info.layer.id === 'aircraft-layer' && info.object) {
                    const aircraft = info.object;
                    const catText = aircraft.cat === 21 ? 'ADS-B (CAT021)' : (aircraft.cat === 48 ? 'Radar (CAT048)' : 'Unknown');
                    const altitudeStr = aircraft.altitude_display || 'N/A';
                    const mode3aStr = aircraft.mode3a || 'N/A';

                    const html = `
                        <b>${aircraft.callsign || aircraft.address}</b><br>
                        <strong>Address:</strong> ${aircraft.address}<br>
                        <strong>CAT:</strong> ${catText}<br>
                        <strong>Mode3/A:</strong> ${mode3aStr}<br>
                        <strong>Altitude:</strong> ${altitudeStr}<br>
                        <strong>Speed:</strong> ${aircraft.speed !== null ? Math.round(aircraft.speed) : 'N/A'} kt
                    `;

                    showPopup(info.x, info.y, aircraft.callsign || aircraft.address, html);
                } else {
                    closePopup();
                }
            }

            function showPopup(x, y, title, content) {
                const popup = document.getElementById('popup');
                document.getElementById('popup-title').textContent = title;
                document.getElementById('popup-content').innerHTML = content;
                popup.style.left = (x + 10) + 'px';
                popup.style.top = (y + 10) + 'px';
                popup.style.display = 'block';
            }

            function closePopup() {
                document.getElementById('popup').style.display = 'none';
            }

            function updateLayers() {
                const radarLayer = new ColumnLayer({
                    id: 'radar-layer',
                    data: [radarPosition],
                    diskResolution: 4,
                    radius: 120,
                    extruded: true,
                    wireframe: false,
                    filled: true,
                    stroked: true,
                    getPosition: d => [d.lon, d.lat],
                    getElevation: d => 400,
                    getFillColor: [128, 0, 128, 255],
                    getLineColor: [255, 255, 255, 255],
                    lineWidthMinPixels: 2,
                    pickable: true
                });

                const aircraftLayer = new ScatterplotLayer({
                    id: 'aircraft-layer',
                    data: aircraftData,
                    pickable: true,
                    opacity: 0.9,
                    stroked: true,
                    filled: true,
                    radiusScale: 60,
                    radiusMinPixels: 4,
                    radiusMaxPixels: 8,
                    lineWidthMinPixels: 0.5,
                    getPosition: d => [d.lon, d.lat, (d.fl || 0) * 30.48],
                    getRadius: 50,
                    getFillColor: d => getColor(d.cat),
                    getLineColor: [255, 255, 255, 200]
                });

                const pathData = Object.entries(trailsData).map(([key, trail]) => ({
                    path: trail.path.map(p => [p[0], p[1], p[2]]),
                    color: trail.color
                }));

                const pathLayer = new PathLayer({
                    id: 'trails-layer',
                    data: pathData,
                    pickable: false,
                    widthScale: 8,
                    widthMinPixels: 1,
                    jointRounded: true,
                    capRounded: true,
                    billboard: false,
                    getPath: d => d.path,
                    getColor: d => d.color,
                    getWidth: 1.5
                });

                const layers = [pathLayer, radarLayer, aircraftLayer];

                if (showLabels) {
                    const labelData = aircraftData.filter(d => d.callsign);

                    const textLayer = new TextLayer({
                        id: 'text-layer',
                        data: labelData,
                        pickable: false,
                        getPosition: d => [d.lon, d.lat, (d.fl || 0) * 30.48 + 200],
                        getText: d => d.callsign,
                        getSize: 14,
                        getColor: [255, 255, 255],
                        getAngle: 0,
                        getTextAnchor: 'middle',
                        getAlignmentBaseline: 'center',
                        billboard: true,
                        backgroundColor: [0, 0, 0, 180],
                        fontFamily: 'Arial, sans-serif',
                        fontWeight: 'bold',
                        outlineWidth: 2,
                        outlineColor: [0, 0, 0, 255],
                        pickable: false
                    });

                    layers.push(textLayer);
                }

                deckgl.setProps({ layers: layers });
            }

            window.cleanFutureTrails = function(currentTime) {
                Object.keys(trailsData).forEach(function(trailKey) {
                    if (trailsData[trailKey] && trailsData[trailKey].path) {
                        trailsData[trailKey].path = trailsData[trailKey].path.filter(function(point) {
                            return point[3] <= currentTime;
                        });
                    }
                });
                updateLayers();
            };

            window.updateAircraft = function(data, enableLabels) {
                aircraftData = data;
                showLabels = enableLabels;

                data.forEach(function(aircraft) {
                    var trailKey = aircraft.address + '_' + aircraft.cat;

                    if (!trailsData[trailKey]) {
                        trailsData[trailKey] = {
                            path: [],
                            color: hashColor(aircraft.address)
                        };
                    }

                    var newPoint = [
                        aircraft.lon,
                        aircraft.lat,
                        (aircraft.fl || 0) * 30.48,
                        aircraft.time_sec || 0
                    ];

                    var trail = trailsData[trailKey].path;

                    if (trail.length === 0 ||
                        Math.abs(newPoint[0] - trail[trail.length-1][0]) > 0.0001 ||
                        Math.abs(newPoint[1] - trail[trail.length-1][1]) > 0.0001) {
                        trail.push(newPoint);
                    }
                });

                updateLayers();
            };

            window.resetTrails = function() {
                trailsData = {};
                aircraftData = [];
                updateLayers();
                closePopup();
            };

            window.setSeparationMode = function(enabled) {
                if (!enabled) {
                    const currentLayers = deckgl.props.layers.filter(l => 
                        l.id !== 'separation-line' && l.id !== 'separation-label'
                    );
                    deckgl.setProps({ layers: currentLayers });
                }
            };

            window.drawSeparationLines = function(lines) {
                if (!lines || lines.length === 0) {
                    window.setSeparationMode(false);
                    return;
                }

                const line = lines[0];

                const sepLineLayer = new LineLayer({
                    id: 'separation-line',
                    data: [{
                        from: [line.from_lon, line.from_lat, line.from_alt],
                        to: [line.to_lon, line.to_lat, line.to_alt]
                    }],
                    getSourcePosition: d => d.from,
                    getTargetPosition: d => d.to,
                    getColor: [255, 0, 0, 200],
                    getWidth: 2,
                    widthMinPixels: 1,
                    pickable: false
                });

                const midLon = (line.from_lon + line.to_lon) / 2;
                const midLat = (line.from_lat + line.to_lat) / 2;
                const midAlt = (line.from_alt + line.to_alt) / 2;

                const textLayer = new TextLayer({
                    id: 'separation-label',
                    data: [{
                        position: [midLon, midLat, midAlt + 200],
                        text: line.dist
                    }],
                    getPosition: d => d.position,
                    getText: d => d.text,
                    getSize: 12,
                    getColor: [255, 0, 0, 255],
                    getAngle: 0,
                    getTextAnchor: 'middle',
                    getAlignmentBaseline: 'center',
                    billboard: true,
                    backgroundColor: [255, 255, 255, 200],
                    fontFamily: 'Arial, sans-serif',
                    fontWeight: 'normal',
                    outlineWidth: 1,
                    outlineColor: [255, 0, 0, 200],
                    pickable: false
                });

                const currentLayers = deckgl.props.layers.filter(l => 
                    l.id !== 'separation-line' && l.id !== 'separation-label'
                );

                deckgl.setProps({
                    layers: [...currentLayers, sepLineLayer, textLayer]
                });
            };

            updateLayers();
        </script>
    </body>
    </html>
        """

        self.web_view.setHtml(html)

    def load_data(self, df: pd.DataFrame):
        """Load and prepare ASTERIX data for visualization."""

        if df is None or df.empty:
            self.play_btn.setEnabled(False)
            self.reset_btn.setEnabled(False)
            self.time_slider.setEnabled(False)
            return

        needed = [c for c in ['LAT', 'LON', 'TI', 'TA', 'Time_sec', 'CAT', 'FL', 'H(ft)',
                              'Mode3/A', 'GS(kt)', 'GS_TVP(kt)', 'GS_BDS(kt)'] if c in df.columns]
        self.df = df[needed].dropna(subset=['LAT', 'LON', 'Time_sec']).sort_values('Time_sec')

        if 'CAT' in self.df.columns:
            self.df = self.df[self.df['CAT'].isin([21, 48])]

        self._last_radar_by_ta = {}

        self.min_time = float(self.df['Time_sec'].min())
        self.max_time = float(self.df['Time_sec'].max())
        self.current_time = self.min_time

        self.play_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.time_slider.setEnabled(True)

        duration = self.max_time - self.min_time

        if duration > 3600:
            self.time_slider.setSingleStep(10)
            self.time_slider.setPageStep(60)

        else:
            self.time_slider.setSingleStep(1)
            self.time_slider.setPageStep(10)

        self.time_slider.setRange(int(self.min_time), int(self.max_time))
        self.time_slider.setValue(int(self.current_time))

        self.time_start_label.setText(self._format_hms(self.min_time))
        self.time_end_label.setText(self._format_hms(self.max_time))
        self.update_time_label()

        self.web_view.page().runJavaScript("resetTrails();")
        self.update_aircraft_positions()

    def toggle_play(self):
        """Toggle play/pause state."""

        self.is_playing = not self.is_playing

        if self.is_playing:
            self.play_btn.setText("⏸ Pause")
            interval_ms = self._calculate_timer_interval()
            self.timer.start(interval_ms)
        else:
            self.play_btn.setText("▶ Play")
            self.timer.stop()

    def _calculate_timer_interval(self) -> int:
        """Calculate timer interval in milliseconds based on speed multiplier.

        At 1x speed: 1000ms (1 plot per second)
        At 10x speed: 100ms (10 plots per second)
        At 60x speed: 17ms (60 plots per second, ~60fps)
        """
        # Base: 1000ms for 1x speed
        # Formula: interval = 1000 / speed_multiplier
        interval_ms = int(1000.0 / self.speed_multiplier)

        # Clamp to reasonable bounds
        # Min: 16ms (~60fps max)
        # Max: 1000ms (1fps)
        return max(16, min(1000, interval_ms))

    def reset_simulation(self):
        """Reset simulation to start time."""

        self.current_time = self.min_time
        self.is_playing = False
        self.play_btn.setText("▶ Play")
        self.timer.stop()
        self._last_valid_rotation = {}
        self.update_time_label()

        self.web_view.page().runJavaScript("resetTrails();")

        if self.show_separation:
            self.web_view.page().runJavaScript("if(window.setSeparationMode) setSeparationMode(false);")

        self.update_aircraft_positions()

    def skip_time(self, seconds: float):
        """Skip forward or backward in time."""

        if self.df is None:
            return
        self.current_time = max(self.min_time, min(self.max_time, self.current_time + seconds))
        self.update_time_label()
        self.update_aircraft_positions()

    def on_speed_changed(self, value):
        """Update playback speed multiplier and restart timer if playing."""
        self.speed_multiplier = value
        self.speed_label.setText(f"{value}x")

        if self.is_playing:
            interval_ms = self._calculate_timer_interval()
            self.timer.start(interval_ms)

    def _on_time_slider_pressed(self):
        """Handle time slider press - pause if playing."""

        self._user_scrubbing = True
        self._was_playing = self.is_playing
        if self.is_playing:
            self.is_playing = False
            self.timer.stop()
            self.play_btn.setText("▶ Play")

    def _on_time_slider_released(self):
        """Handle time slider release - resume if was playing."""

        self._user_scrubbing = False
        if self._was_playing:
            self.is_playing = True
            self.play_btn.setText("⏸ Pause")
            self.timer.start(1000)

    def _on_time_slider_changed(self, value: int):
        """Handle manual time slider changes."""

        if self._user_scrubbing or not hasattr(self, 'min_time'):
            v = max(self.time_slider.minimum(), min(self.time_slider.maximum(), value))
            self.current_time = float(v)
            self.update_time_label()
            self.update_aircraft_positions()

    def update_simulation(self):
        """Advance simulation by one time step (always 1 second)."""
        self.current_time += self.base_time_increment

        if self.current_time >= self.max_time:
            self.reset_simulation()
            return

        self.update_time_label()
        self.update_aircraft_positions()


    def update_time_label(self):
        """Update time display label."""

        self.time_label.setText(f"Now: {self._format_hms(self.current_time)}")
        if not self._user_scrubbing and self.time_slider.isEnabled():
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(int(self.current_time))
            self.time_slider.blockSignals(False)

    def _format_altitude_display(self, fl, alt_ft):
        """Format altitude display string."""

        if pd.notna(alt_ft):
            return f"{int(round(alt_ft))} ft"
        if pd.notna(fl):
            return f"FL{int(round(fl))}"
        return "N/A"

    def _get_callsign(self, adsb_row, radar_row):
        """Safely get callsign from either source."""

        if adsb_row is not None and pd.notna(adsb_row.get('TI')):
            return str(adsb_row['TI'])

        if radar_row is not None and pd.notna(radar_row.get('TI')):
            return str(radar_row['TI'])
        return ''

    def _get_mode3a(self, adsb_row, radar_row):
        """Safely get Mode3/A from either source."""

        if adsb_row is not None and pd.notna(adsb_row.get('Mode3/A')):
            return str(adsb_row['Mode3/A'])

        if radar_row is not None and pd.notna(radar_row.get('Mode3/A')):
            return str(radar_row['Mode3/A'])
        return None

    def update_aircraft_positions(self):
        """Update aircraft markers and trajectories based on current time."""


        if self.df is None or self.df.empty:
            return

        if not hasattr(self, '_last_update_time'):
            self._last_update_time = self.current_time

        going_backwards = self.current_time < self._last_update_time

        if going_backwards:
            js_code = f"cleanFutureTrails({self.current_time});"
            self.web_view.page().runJavaScript(js_code)

        self._last_update_time = self.current_time

        time_window = 5
        mask = (self.df['Time_sec'] >= self.current_time - time_window) & (
                    self.df['Time_sec'] <= self.current_time + time_window)
        current_aircraft = self.df[mask]

        if 'CAT' in current_aircraft.columns:
            current_aircraft = current_aircraft[current_aircraft['CAT'].isin([21, 48])]

        if 'TA' not in current_aircraft.columns or current_aircraft.empty:
            self.aircraft_label.setText("Aircraft: 0")

            return

        current_sorted = current_aircraft.sort_values('Time_sec')
        latest_by_ta_cat = {}

        for _, row in current_sorted.iterrows():
            ta = str(row.get('TA')) if pd.notna(row.get('TA')) else None
            cat = int(row.get('CAT')) if pd.notna(row.get('CAT')) else None

            if ta is None or cat not in [21, 48]:

                continue

            latest_by_ta_cat[(ta, cat)] = row

        aircraft_data = []
        tas_seen = set([str(x) for x in current_sorted['TA'].dropna().unique()])

        def pick_speed(r):

            if r is None:
                return None

            for col in ['GS_TVP(kt)', 'GS(kt)', 'GS_BDS(kt)']:
                v = r.get(col)

                if pd.notna(v):
                    try:
                        return float(v)
                    except Exception:
                        continue
            return None

        for ta in tas_seen:
            adsb_row = latest_by_ta_cat.get((ta, 21))
            radar_row = latest_by_ta_cat.get((ta, 48))
            callsign = self._get_callsign(adsb_row, radar_row)
            mode3a = self._get_mode3a(adsb_row, radar_row)

            if self.source_filter in ['both', 'adsb']:

                if adsb_row is not None and pd.notna(adsb_row.get('LAT')) and pd.notna(adsb_row.get('LON')):
                    aircraft_data.append({
                        'address': ta,
                        'callsign': callsign,
                        'lat': float(adsb_row['LAT']),
                        'lon': float(adsb_row['LON']),
                        'fl': float(adsb_row['FL']) if pd.notna(adsb_row.get('FL')) else None,
                        'altitude_display': self._format_altitude_display(adsb_row.get('FL'), adsb_row.get('H(ft)')),
                        'speed': pick_speed(adsb_row),
                        'mode3a': mode3a,
                        'cat': 21,
                        'time_sec': float(adsb_row['Time_sec'])
                    })

            if self.source_filter in ['both', 'radar']:

                if radar_row is not None and pd.notna(radar_row.get('LAT')) and pd.notna(radar_row.get('LON')):
                    aircraft_data.append({
                        'address': ta,
                        'callsign': callsign,
                        'lat': float(radar_row['LAT']),
                        'lon': float(radar_row['LON']),
                        'fl': float(radar_row['FL']) if pd.notna(radar_row.get('FL')) else None,
                        'altitude_display': self._format_altitude_display(radar_row.get('FL'), radar_row.get('H(ft)')),
                        'speed': pick_speed(radar_row),
                        'mode3a': mode3a,
                        'cat': 48,
                        'time_sec': float(radar_row['Time_sec'])
                    })

        for aircraft in aircraft_data:
            key = f"{aircraft['address']}_{aircraft['cat']}"

            if key in self._last_valid_rotation:
                aircraft['heading'] = self._last_valid_rotation[key]
                aircraft['lastRotation'] = self._last_valid_rotation[key]

            else:
                aircraft['heading'] = 0
                aircraft['lastRotation'] = 0

        if aircraft_data:
            unique_tas = set([a['address'] for a in aircraft_data])
            adsb_count = len([a for a in aircraft_data if a['cat'] == 21])
            radar_count = len([a for a in aircraft_data if a['cat'] == 48])
            self.aircraft_label.setText(f"Aircraft: {len(unique_tas)} (ADS-B: {adsb_count}, Radar: {radar_count})")

            js_code = f"updateAircraft({json.dumps(aircraft_data)}, {json.dumps(self.show_labels)});"
            self.web_view.page().runJavaScript(js_code)

            if self.show_separation and self.departure_schedule:
                sep_lines = self.calculate_separation_lines(aircraft_data)

                if sep_lines:
                    js_code = f"if(window.drawSeparationLines) drawSeparationLines({json.dumps(sep_lines)});"
                    self.web_view.page().runJavaScript(js_code)

        else:
            self.aircraft_label.setText("Aircraft: 0")
