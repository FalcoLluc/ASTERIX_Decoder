from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QTimer, Signal, Slot, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel
from PySide6.QtGui import QShortcut, QKeySequence
import pandas as pd
import json
import hashlib


class MapWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.df = None
        self.current_time = 0
        self.min_time = 0
        self.max_time = 0
        self.is_playing = False
        self.speed_multiplier = 1.0
        self._user_scrubbing = False
        self._was_playing = False

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Web view for map
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # Control panel
        control_layout = QHBoxLayout()

        # Play/Pause button
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self.toggle_play)
        self.play_btn.setEnabled(False)
        control_layout.addWidget(self.play_btn)

        # Reset button
        self.reset_btn = QPushButton("🔄 Reset")
        self.reset_btn.clicked.connect(self.reset_simulation)
        self.reset_btn.setEnabled(False)
        control_layout.addWidget(self.reset_btn)

        # Speed control
        control_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider()
        self.speed_slider.setOrientation(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(60)
        self.speed_slider.setValue(1)
        self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        control_layout.addWidget(self.speed_slider)

        self.speed_label = QLabel("1x")
        control_layout.addWidget(self.speed_label)

        # Time selector (legend)
        control_layout.addWidget(QLabel("Time:"))
        self.time_start_label = QLabel("--:--:--")
        control_layout.addWidget(self.time_start_label)

        self.time_slider = QSlider()
        self.time_slider.setOrientation(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setEnabled(False)
        self.time_slider.sliderPressed.connect(self._on_time_slider_pressed)
        self.time_slider.sliderReleased.connect(self._on_time_slider_released)
        self.time_slider.valueChanged.connect(self._on_time_slider_changed)
        control_layout.addWidget(self.time_slider, stretch=1)

        self.time_end_label = QLabel("--:--:--")
        control_layout.addWidget(self.time_end_label)

        # Current time display
        self.time_label = QLabel("Now: --:--:--")
        control_layout.addWidget(self.time_label)

        # Aircraft count
        self.aircraft_label = QLabel("Aircraft: 0")
        control_layout.addWidget(self.aircraft_label)

        control_layout.addStretch()

        layout.addLayout(control_layout)
        self.setLayout(layout)

        # Timer for simulation
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)

        # ✅ Keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.skip_time(-10))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.skip_time(10))

        # Load initial empty map
        self.load_base_map()

    def _format_hms(self, seconds: float) -> str:
        try:
            s = int(max(0, seconds))
            h = s // 3600
            m = (s % 3600) // 60
            sec = s % 60
            return f"{h:02d}:{m:02d}:{sec:02d}"
        except Exception:
            return "--:--:--"

    def load_base_map(self):
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>ASTERIX Radar View</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body { margin: 0; padding: 0; }
        #map { width: 100%; height: 100vh; }

        .aircraft-marker {
            background: transparent;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 26px;
            text-shadow: 0 0 3px rgba(0,0,0,0.5);
        }

        .leaflet-popup-content {
            background: rgba(255, 255, 255, 0.95) !important;
            border-radius: 6px !important;
            color: #333 !important;
            font-size: 13px !important;
        }

        .leaflet-popup-tip {
            background: rgba(255, 255, 255, 0.95) !important;
        }

        /* Legend styling */
        .info.legend {
            background: rgba(255,255,255,0.9);
            padding: 8px 10px;
            border-radius: 6px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
            line-height: 1.4em;
            font: 12px/1.4 'Segoe UI', Arial, sans-serif;
        }
        .legend .item { display: flex; align-items: center; margin: 4px 0; }
        .legend .swatch {
            width: 14px; height: 14px; margin-right: 6px; border-radius: 2px;
            box-shadow: inset 0 0 0 1px rgba(0,0,0,0.2);
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        // Initialize map centered on Barcelona radar
        var map = L.map('map', {
            zoomControl: true,
            attributionControl: false
        }).setView([41.2972, 2.0833], 11);

        // Esri World Topo Map for ATC-style appearance
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: 19,
            attribution: '',
            opacity: 0.95
        }).addTo(map);

        // Add Barcelona radar position
        var radarIcon = L.divIcon({
            html: '<div style="font-size: 32px; text-shadow: 0 0 4px rgba(0,0,0,0.5);">𖦏</div>',
            className: 'aircraft-marker',
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });

        var radarMarker = L.marker([41.300702, 2.102058], {icon: radarIcon, zIndexOffset: 1000})
            .bindPopup('<b>Barcelona Radar</b><br>SAC: 20, SIC: 129')
            .addTo(map);

        // Add legend
        var legend = L.control({position: 'topright'});
        legend.onAdd = function () {
            var div = L.DomUtil.create('div', 'info legend');
            div.innerHTML = '<strong>Detection Source</strong><br>' +
                '<div class="item"><span class="swatch" style="background:#FFD700"></span>ADS-B (CAT021)</div>' +
                '<div class="item"><span class="swatch" style="background:#FF4D4D"></span>Radar (CAT048)</div>' +
                '<div class="item"><span class="swatch" style="background:#00E5FF"></span>Both Systems</div>';
            return div;
        };
        legend.addTo(map);

        // Storage for aircraft markers and PERMANENT trails
        var aircraftMarkers = {};
        var aircraftTrails = {};
        var permanentTrails = [];
        var trailSegmentCount = {};
        var previousPositions = {};
        var aircraftColors = {};  // ✅ Store consistent colors per aircraft

        // ✅ Generate deterministic color from aircraft address
        function getAircraftColor(address) {
            if (aircraftColors[address]) {
                return aircraftColors[address];
            }

            // Use hash of address to generate consistent color
            var hash = 0;
            for (var i = 0; i < address.length; i++) {
                hash = address.charCodeAt(i) + ((hash << 5) - hash);
            }

            // Generate vibrant HSL color
            var hue = Math.abs(hash % 360);
            var saturation = 70 + (Math.abs(hash >> 8) % 20);  // 70-90%
            var lightness = 50 + (Math.abs(hash >> 16) % 15);  // 50-65%

            var color = 'hsl(' + hue + ', ' + saturation + '%, ' + lightness + '%)';
            aircraftColors[address] = color;
            return color;
        }

        // Function to calculate bearing between two points
        function getBearing(lat1, lon1, lat2, lon2) {
            var dLon = (lon2 - lon1);
            var y = Math.sin(dLon * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180);
            var x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
                    Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos(dLon * Math.PI / 180);
            var bearing = Math.atan2(y, x) * 180 / Math.PI;
            return (bearing + 360) % 360;
        }

        // Function to calculate opacity based on segment age
        function calculateOpacity(segmentIndex, totalSegments) {
            var maxSegments = 50;
            var relativeAge = (totalSegments - segmentIndex) / maxSegments;

            if (relativeAge > 1) relativeAge = 1;
            if (relativeAge < 0) relativeAge = 0;

            var opacity = 0.85 * relativeAge;
            if (opacity < 0.15) opacity = 0.15;
            return opacity;
        }

        // Function to update aircraft positions (called from Python)
        function updateAircraft(data) {
            // Clear existing markers (but NOT the trails)
            Object.values(aircraftMarkers).forEach(marker => map.removeLayer(marker));
            aircraftMarkers = {};

            // Add aircraft
            data.forEach(function(aircraft) {
                var rotation = 0;

                // Calculate rotation from previous position
                if (previousPositions[aircraft.address]) {
                    var prevPos = previousPositions[aircraft.address];
                    rotation = getBearing(prevPos.lat, prevPos.lon, aircraft.lat, aircraft.lon);
                } else if (aircraftTrails[aircraft.address] && aircraftTrails[aircraft.address].length >= 2) {
                    var prevPos = aircraftTrails[aircraft.address][aircraftTrails[aircraft.address].length - 2];
                    rotation = getBearing(prevPos[0], prevPos[1], aircraft.lat, aircraft.lon);
                }

                // Store previous position for next iteration
                previousPositions[aircraft.address] = {lat: aircraft.lat, lon: aircraft.lon};

                // ✅ Use unique color for each aircraft's trail
                var trailColor = getAircraftColor(aircraft.address);

                // Marker uses detection type badge color
                var badgeColor = aircraft.both ? '#00E5FF' : (aircraft.cat === 48 ? '#FF4D4D' : '#FFD700');

                // AIRPLANE ROTATED TOWARD DIRECTION with badge color
                var icon = L.divIcon({
                    html: '<div style="transform: rotate(' + (rotation - 90) + 'deg); display: inline-block; font-size: 26px; text-shadow: 0 0 3px rgba(0,0,0,0.5); color:' + badgeColor + ';">✈</div>',
                    className: 'aircraft-marker',
                    iconSize: [26, 26],
                    iconAnchor: [13, 13]
                });

                var marker = L.marker([aircraft.lat, aircraft.lon], {
                    icon: icon, 
                    zIndexOffset: 500
                }).bindPopup(
                    '<b>' + (aircraft.callsign || aircraft.address) + '</b><br>' +
                    '<strong>CAT:</strong> ' + aircraft.cat + (aircraft.both ? ' (Both)' : '') + '<br>' +
                    '<strong>FL:</strong> ' + (aircraft.fl !== null ? Math.round(aircraft.fl) : 'N/A') + '<br>' +
                    '<strong>Speed:</strong> ' + (aircraft.speed !== null ? Math.round(aircraft.speed) : 'N/A') + ' kt<br>' +
                    '<strong>Heading:</strong> ' + Math.round(rotation) + '°'
                );

                marker.addTo(map);
                aircraftMarkers[aircraft.address] = marker;

                // Add to trail
                if (!aircraftTrails[aircraft.address]) {
                    aircraftTrails[aircraft.address] = [];
                    trailSegmentCount[aircraft.address] = 0;
                }
                aircraftTrails[aircraft.address].push([aircraft.lat, aircraft.lon]);

                // Add new trail segment (only if there's a previous point)
                if (aircraftTrails[aircraft.address].length > 1) {
                    var trail = aircraftTrails[aircraft.address];
                    var lastPoint = trail[trail.length - 1];
                    var prevPoint = trail[trail.length - 2];

                    var segmentIndex = trailSegmentCount[aircraft.address];
                    var opacity = calculateOpacity(segmentIndex, trailSegmentCount[aircraft.address]);

                    // ✅ Use unique aircraft color for trail
                    var segment = L.polyline([prevPoint, lastPoint], {
                        color: trailColor,
                        weight: 2.5,
                        opacity: opacity,
                        lineCap: 'round'
                    }).addTo(map);

                    permanentTrails.push(segment);
                    trailSegmentCount[aircraft.address]++;
                }
            });
        }

        // Function to reset trails
        function resetTrails() {
            permanentTrails.forEach(trail => map.removeLayer(trail));
            permanentTrails = [];
            aircraftTrails = {};
            trailSegmentCount = {};
            previousPositions = {};
            aircraftColors = {};  // ✅ Reset colors on trail reset
        }

        // Expose functions to Python
        window.updateAircraft = updateAircraft;
        window.resetTrails = resetTrails;
    </script>
</body>
</html>
        """
        self.web_view.setHtml(html)

    def load_data(self, df: pd.DataFrame):
        """Load data into map widget for playback"""
        if df is None or df.empty:
            print("⚠️ MapWidget: Received empty DataFrame")
            self.play_btn.setEnabled(False)
            self.reset_btn.setEnabled(False)
            self.time_slider.setEnabled(False)
            self.time_start_label.setText("--:--:--")
            self.time_end_label.setText("--:--:--")
            self.time_label.setText("Now: --:--:--")
            return

        required_cols = ['LAT', 'LON', 'Time_sec']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"⚠️ MapWidget: Missing required columns: {missing_cols}")
            self.play_btn.setEnabled(False)
            self.reset_btn.setEnabled(False)
            self.time_slider.setEnabled(False)
            return

        # Select only needed columns
        needed = [c for c in ['LAT', 'LON', 'TI', 'TA', 'Time_sec', 'CAT', 'FL', 'GS(kt)'] if c in df.columns]
        self.df = df[needed]

        # Filter valid positions
        self.df = self.df.dropna(subset=['LAT', 'LON', 'Time_sec'])

        if self.df.empty:
            print("⚠️ MapWidget: No valid position data after filtering")
            self.play_btn.setEnabled(False)
            self.reset_btn.setEnabled(False)
            self.time_slider.setEnabled(False)
            return

        # Sort by time
        self.df = self.df.sort_values('Time_sec')

        # Compute detection system presence per aircraft
        try:
            tas_series = self.df['TA'] if 'TA' in self.df.columns else None
            cat_series = self.df['CAT'] if 'CAT' in self.df.columns else None
            if tas_series is not None and cat_series is not None:
                self.tas_adsb = set(tas_series[cat_series == 21].dropna().astype(str).unique())
                self.tas_radar = set(tas_series[cat_series == 48].dropna().astype(str).unique())
                self.tas_both = self.tas_adsb.intersection(self.tas_radar)
            else:
                self.tas_adsb = set()
                self.tas_radar = set()
                self.tas_both = set()
        except Exception:
            self.tas_adsb = set()
            self.tas_radar = set()
            self.tas_both = set()

        # Set time range
        self.min_time = float(self.df['Time_sec'].min())
        self.max_time = float(self.df['Time_sec'].max())
        self.current_time = self.min_time

        # Enable controls
        self.play_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)

        # ✅ Initialize time slider with adaptive resolution
        duration = self.max_time - self.min_time
        if duration > 3600:  # > 1 hour
            self.time_slider.setSingleStep(10)
            self.time_slider.setPageStep(60)
        else:
            self.time_slider.setSingleStep(1)
            self.time_slider.setPageStep(10)

        min_int = int(self.min_time)
        max_int = int(self.max_time) if self.max_time >= self.min_time else int(self.min_time)
        self.time_slider.setRange(min_int, max_int)
        self.time_slider.setValue(int(self.current_time))
        self.time_slider.setEnabled(True)

        self.time_start_label.setText(self._format_hms(self.min_time))
        self.time_end_label.setText(self._format_hms(self.max_time))

        # Update display
        self.update_time_label()
        self.web_view.page().runJavaScript("resetTrails();")
        self.update_aircraft_positions()

    def toggle_play(self):
        self.is_playing = not self.is_playing

        if self.is_playing:
            self.play_btn.setText("⏸ Pause")
            self.timer.start(1000)
        else:
            self.play_btn.setText("▶ Play")
            self.timer.stop()

    def reset_simulation(self):
        self.current_time = self.min_time
        self.is_playing = False
        self.play_btn.setText("▶ Play")
        self.timer.stop()
        self.update_time_label()

        # Reset trails on map
        self.web_view.page().runJavaScript("resetTrails();")
        self.update_aircraft_positions()

    def skip_time(self, seconds: float):
        """Skip forward/backward by specified seconds (keyboard shortcut)"""
        if self.df is None:
            return

        self.current_time = max(self.min_time, min(self.max_time, self.current_time + seconds))
        self.update_time_label()
        self.update_aircraft_positions()

    def on_speed_changed(self, value):
        self.speed_multiplier = value
        self.speed_label.setText(f"{value}x")

    # ===== Time slider handlers =====
    def _on_time_slider_pressed(self):
        self._user_scrubbing = True
        self._was_playing = self.is_playing
        if self.is_playing:
            self.is_playing = False
            self.timer.stop()
            self.play_btn.setText("▶ Play")

    def _on_time_slider_released(self):
        self._user_scrubbing = False
        if self._was_playing:
            self.is_playing = True
            self.play_btn.setText("⏸ Pause")
            self.timer.start(1000)

    def _on_time_slider_changed(self, value: int):
        if self._user_scrubbing or not hasattr(self, 'min_time'):
            try:
                min_v = self.time_slider.minimum()
                max_v = self.time_slider.maximum()
                v = max(min_v, min(max_v, int(value)))
                self.current_time = float(v)
                self.update_time_label()
                self.update_aircraft_positions()
            except Exception as e:
                print(f"⚠️ Time slider change error: {e}")

    def update_simulation(self):
        self.current_time += self.speed_multiplier

        if self.current_time >= self.max_time:
            self.reset_simulation()
            return

        self.update_time_label()
        self.update_aircraft_positions()

    def update_time_label(self):
        self.time_label.setText(f"Now: {self._format_hms(self.current_time)}")

        # ✅ IMPROVED: Use blockSignals to prevent recursion
        if hasattr(self, 'time_slider') and self.time_slider.isEnabled() and not self._user_scrubbing:
            self.time_slider.blockSignals(True)
            try:
                self.time_slider.setValue(int(self.current_time))
            finally:
                self.time_slider.blockSignals(False)

    def update_aircraft_positions(self):
        """Update aircraft positions on map"""
        if self.df is None or self.df.empty:
            return

        try:
            time_window = 5
            mask = (self.df['Time_sec'] >= self.current_time - time_window) & \
                   (self.df['Time_sec'] <= self.current_time + time_window)

            current_aircraft = self.df[mask]

            if 'TA' not in current_aircraft.columns or current_aircraft.empty:
                self.aircraft_label.setText("Aircraft: 0")
                return

            latest_positions = current_aircraft.sort_values('Time_sec').groupby('TA', observed=True).last()

            aircraft_data = []
            both_set = getattr(self, 'tas_both', set())

            for address, row in latest_positions.iterrows():
                if pd.notna(row['LAT']) and pd.notna(row['LON']):
                    addr_str = str(address)
                    aircraft_data.append({
                        'address': addr_str,
                        'callsign': str(row.get('TI', '')) if pd.notna(row.get('TI')) else '',
                        'lat': float(row['LAT']),
                        'lon': float(row['LON']),
                        'fl': float(row['FL']) if pd.notna(row.get('FL')) else None,
                        'speed': float(row['GS(kt)']) if pd.notna(row.get('GS(kt)')) else None,
                        'cat': int(row['CAT']) if pd.notna(row.get('CAT')) else 0,
                        'both': addr_str in both_set
                    })

            # ✅ IMPROVED: Show breakdown
            if aircraft_data:
                adsb_count = sum(1 for a in aircraft_data if a['cat'] == 21)
                radar_count = sum(1 for a in aircraft_data if a['cat'] == 48)
                both_count = sum(1 for a in aircraft_data if a['both'])

                self.aircraft_label.setText(
                    f"Aircraft: {len(aircraft_data)} "
                    f"(ADS-B: {adsb_count}, Radar: {radar_count}, Both: {both_count})"
                )

                js_code = f"updateAircraft({json.dumps(aircraft_data)});"
                self.web_view.page().runJavaScript(js_code)
            else:
                self.aircraft_label.setText("Aircraft: 0")

        except Exception as e:
            print(f"❌ MapWidget.update_aircraft_positions() error: {str(e)}")
            import traceback
            traceback.print_exc()
            self.aircraft_label.setText("Aircraft: Error")
