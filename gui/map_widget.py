from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel
from PySide6.QtGui import QShortcut, QKeySequence
import pandas as pd
import json


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
        self.is_3d_mode = False

        self.init_ui()

    def _format_hms(self, seconds: float) -> str:
        try:
            s = int(max(0, seconds))
            h = s // 3600
            m = (s % 3600) // 60
            sec = s % 60
            return f"{h:02d}:{m:02d}:{sec:02d}"
        except Exception:
            return "--:--:--"

    def init_ui(self):
        layout = QVBoxLayout()
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        control_layout = QHBoxLayout()

        # Botón para cambiar entre 2D y 3D
        self.view_mode_btn = QPushButton("🌐 Vista 3D")
        self.view_mode_btn.clicked.connect(self.toggle_view_mode)
        control_layout.addWidget(self.view_mode_btn)

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self.toggle_play)
        self.play_btn.setEnabled(False)
        control_layout.addWidget(self.play_btn)

        self.reset_btn = QPushButton("🔄 Reset")
        self.reset_btn.clicked.connect(self.reset_simulation)
        self.reset_btn.setEnabled(False)
        control_layout.addWidget(self.reset_btn)

        control_layout.addWidget(QLabel("Speed:"))
        self.speed_slider = QSlider()
        self.speed_slider.setOrientation(Qt.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(60)
        self.speed_slider.setValue(1)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        control_layout.addWidget(self.speed_slider)

        self.speed_label = QLabel("1x")
        control_layout.addWidget(self.speed_label)

        control_layout.addWidget(QLabel("Time:"))
        self.time_start_label = QLabel("--:--:--")
        control_layout.addWidget(self.time_start_label)

        self.time_slider = QSlider()
        self.time_slider.setOrientation(Qt.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(0)
        self.time_slider.setEnabled(False)
        self.time_slider.sliderPressed.connect(self._on_time_slider_pressed)
        self.time_slider.sliderReleased.connect(self._on_time_slider_released)
        self.time_slider.valueChanged.connect(self._on_time_slider_changed)
        control_layout.addWidget(self.time_slider, stretch=1)

        self.time_end_label = QLabel("--:--:--")
        control_layout.addWidget(self.time_end_label)

        self.time_label = QLabel("Now: --:--:--")
        control_layout.addWidget(self.time_label)

        self.aircraft_label = QLabel("Aircraft: 0")
        control_layout.addWidget(self.aircraft_label)
        control_layout.addStretch()

        layout.addLayout(control_layout)
        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)

        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self.toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self.skip_time(-10))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self.skip_time(10))

        self.load_base_map()

    def toggle_view_mode(self):
        self.is_3d_mode = not self.is_3d_mode
        if self.is_3d_mode:
            self.view_mode_btn.setText("🗺️ Vista 2D")
            self.load_3d_map()
        else:
            self.view_mode_btn.setText("🌐 Vista 3D")
            self.load_base_map()

        # Actualizar posiciones después de cambiar el mapa
        if self.df is not None:
            self.update_aircraft_positions()

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
            .aircraft-marker { background: transparent; border: none; display: flex; align-items: center; justify-content: center; font-size: 26px; text-shadow: 0 0 3px rgba(0,0,0,0.5); }
            .leaflet-popup-content { background: rgba(255, 255, 255, 0.95) !important; border-radius: 6px !important; color: #333 !important; font-size: 13px !important; }
            .leaflet-popup-tip { background: rgba(255, 255, 255, 0.95) !important; }
            .info.legend { background: rgba(255,255,255,0.9); padding: 8px 10px; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.2); line-height: 1.4em; font: 12px/1.4 'Segoe UI', Arial, sans-serif; }
            .legend .item { display: flex; align-items: center; margin: 4px 0; }
            .legend .swatch { width: 14px; height: 14px; margin-right: 6px; border-radius: 2px; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.2); }
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            var map = L.map('map', { zoomControl: true, attributionControl: false }).setView([41.2972, 2.0833], 11);
            L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
                maxZoom: 19, attribution: '', opacity: 0.95
            }).addTo(map);

            var radarIcon = L.divIcon({ html: '<div style="font-size: 32px; text-shadow: 0 0 4px rgba(0,0,0,0.5);">𖦏</div>', className: 'aircraft-marker', iconSize: [32, 32], iconAnchor: [16, 16] });
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
            var permanentTrails = [];
            var trailSegmentCount = {};
            var previousPositions = {};
            var aircraftColors = {};

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

            function calculateOpacity(segmentIndex, totalSegments) {
                var maxSegments = 50;
                var relativeAge = (totalSegments - segmentIndex) / maxSegments;
                if (relativeAge > 1) relativeAge = 1;
                if (relativeAge < 0) relativeAge = 0;
                var opacity = 0.85 * relativeAge;
                if (opacity < 0.15) opacity = 0.15;
                return opacity;
            }

            window.updateAircraft = function(data) {
                Object.values(aircraftMarkers).forEach(marker => map.removeLayer(marker));
                aircraftMarkers = {};
                data.forEach(function(aircraft) {
                    var markerId = aircraft.address + '_' + (aircraft.cat === 48 ? '48' : '21');
                    var rotation = 0;
                    if (previousPositions[markerId]) {
                        var prevPos = previousPositions[markerId];
                        rotation = getBearing(prevPos.lat, prevPos.lon, aircraft.lat, aircraft.lon);
                    } else if (aircraftTrails[markerId] && aircraftTrails[markerId].length >= 2) {
                        var prevPos = aircraftTrails[markerId][aircraftTrails[markerId].length - 2];
                        rotation = getBearing(prevPos[0], prevPos[1], aircraft.lat, aircraft.lon);
                    }
                    previousPositions[markerId] = {lat: aircraft.lat, lon: aircraft.lon};
                    var trailColor = getAircraftColor(aircraft.address);
                    var badgeColor = (aircraft.cat === 48 ? '#FF4D4D' : '#FFA500');
                    var srcText = (aircraft.cat === 48 ? 'Radar (CAT048)' : 'ADS-B (CAT021)');
                    var icon = L.divIcon({ html: '<div style="transform: rotate(' + (rotation - 90) + 'deg); display: inline-block; font-size: 26px; text-shadow: 0 0 3px rgba(0,0,0,0.5); color:' + badgeColor + ';">✈</div>', className: 'aircraft-marker', iconSize: [26, 26], iconAnchor: [13, 13] });
                    var marker = L.marker([aircraft.lat, aircraft.lon], {icon: icon, zIndexOffset: 500}).bindPopup('<b>' + (aircraft.callsign || aircraft.address) + '</b><br><strong>Source:</strong> ' + srcText + '<br><strong>FL:</strong> ' + (aircraft.fl !== null ? Math.round(aircraft.fl) : 'N/A') + '<br><strong>Speed:</strong> ' + (aircraft.speed !== null ? Math.round(aircraft.speed) : 'N/A') + ' kt<br><strong>Heading:</strong> ' + Math.round(rotation) + '°');
                    marker.addTo(map);
                    aircraftMarkers[markerId] = marker;
                    if (!aircraftTrails[markerId]) { aircraftTrails[markerId] = []; trailSegmentCount[markerId] = 0; }
                    aircraftTrails[markerId].push([aircraft.lat, aircraft.lon]);
                    if (aircraftTrails[markerId].length > 1) {
                        var trail = aircraftTrails[markerId];
                        var lastPoint = trail[trail.length - 1];
                        var prevPoint = trail[trail.length - 2];
                        var segmentIndex = trailSegmentCount[markerId];
                        var opacity = calculateOpacity(segmentIndex, trailSegmentCount[markerId]);
                        var segment = L.polyline([prevPoint, lastPoint], { color: trailColor, weight: 2.5, opacity: opacity, lineCap: 'round' }).addTo(map);
                        permanentTrails.push(segment);
                        trailSegmentCount[markerId]++;
                    }
                });
            };

            window.resetTrails = function() {
                permanentTrails.forEach(trail => map.removeLayer(trail));
                permanentTrails = []; aircraftTrails = {}; trailSegmentCount = {}; previousPositions = {}; aircraftColors = {};
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
            <div class="legend-item">
                <span class="legend-swatch" style="background:#00E5FF"></span>
                <span>Both Systems</span>
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
            const {DeckGL, ScatterplotLayer, PathLayer, ColumnLayer} = deck;
            let aircraftData = [];
            let trailsData = {};
            let radarPosition = {lon: 2.102058, lat: 41.300702};

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

            function getColor(cat, both) {
                if (both) return [0, 229, 255, 255];
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

                    const html = `
                        <b>${aircraft.callsign || aircraft.address}</b><br>
                        <strong>Address:</strong> ${aircraft.address}<br>
                        <strong>CAT:</strong> ${catText}<br>
                        <strong>FL:</strong> ${aircraft.fl !== null ? Math.round(aircraft.fl) : 'N/A'}<br>
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
                //  Radar como cubo 
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

                // Aviones como esferas pequeñas (ScatterplotLayer)
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
                    getFillColor: d => getColor(d.cat, d.both),
                    getLineColor: [255, 255, 255, 200]
                });

                const pathData = Object.entries(trailsData).map(([address, trail]) => ({ 
                    path: trail.path, 
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

                deckgl.setProps({ layers: [pathLayer, radarLayer, aircraftLayer] });
            }

            window.updateAircraft = function(data) {
                aircraftData = data;
                data.forEach(aircraft => {
                    if (!trailsData[aircraft.address]) {
                        trailsData[aircraft.address] = { path: [], color: hashColor(aircraft.address) };
                    }
                    const newPoint = [aircraft.lon, aircraft.lat, (aircraft.fl || 0) * 30.48];
                    trailsData[aircraft.address].path.push(newPoint);
                    if (trailsData[aircraft.address].path.length > 200) {
                        trailsData[aircraft.address].path.shift();
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

            updateLayers();
        </script>
    </body>
    </html>
        """
        self.web_view.setHtml(html)

    def load_data(self, df: pd.DataFrame):
        if df is None or df.empty:
            self.play_btn.setEnabled(False)
            self.reset_btn.setEnabled(False)
            self.time_slider.setEnabled(False)
            return

        needed = [c for c in ['LAT', 'LON', 'TI', 'TA', 'Time_sec', 'CAT', 'FL', 'GS(kt)', 'GS_TVP(kt)', 'GS_BDS(kt)'] if c in df.columns]
        self.df = df[needed].dropna(subset=['LAT', 'LON', 'Time_sec']).sort_values('Time_sec')
        # Storage for last known radar positions (by TA as string)
        self._last_radar_by_ta = {}

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
        self.web_view.page().runJavaScript("resetTrails();")
        self.update_aircraft_positions()

    def skip_time(self, seconds: float):
        if self.df is None:
            return
        self.current_time = max(self.min_time, min(self.max_time, self.current_time + seconds))
        self.update_time_label()
        self.update_aircraft_positions()

    def on_speed_changed(self, value):
        self.speed_multiplier = value
        self.speed_label.setText(f"{value}x")

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
            v = max(self.time_slider.minimum(), min(self.time_slider.maximum(), value))
            self.current_time = float(v)
            self.update_time_label()
            self.update_aircraft_positions()

    def update_simulation(self):
        self.current_time += self.speed_multiplier
        if self.current_time >= self.max_time:
            self.reset_simulation()
            return
        self.update_time_label()
        self.update_aircraft_positions()

    def update_time_label(self):
        self.time_label.setText(f"Now: {self._format_hms(self.current_time)}")
        if not self._user_scrubbing and self.time_slider.isEnabled():
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(int(self.current_time))
            self.time_slider.blockSignals(False)

    def update_aircraft_positions(self):
        if self.df is None or self.df.empty:
            return

        time_window = 5
        mask = (self.df['Time_sec'] >= self.current_time - time_window) & (
                    self.df['Time_sec'] <= self.current_time + time_window)
        current_aircraft = self.df[mask]

        if 'TA' not in current_aircraft.columns or current_aircraft.empty:
            self.aircraft_label.setText("Aircraft: 0")
            return

        # Compute latest per TA per CAT
        current_sorted = current_aircraft.sort_values('Time_sec')
        latest_by_ta_cat = {}
        for _, row in current_sorted.iterrows():
            ta = str(row.get('TA')) if pd.notna(row.get('TA')) else None
            cat = int(row.get('CAT')) if pd.notna(row.get('CAT')) else None
            if ta is None or cat not in (21, 48):
                continue
            latest_by_ta_cat[(ta, cat)] = row

        # Build data allowing duplicates per TA (one per source)
        aircraft_data = []
        tas_seen = set([str(x) for x in current_sorted['TA'].dropna().unique()])
        both_set = getattr(self, 'tas_both', set())

        for ta in tas_seen:
            adsb_row = latest_by_ta_cat.get((ta, 21))
            radar_row = latest_by_ta_cat.get((ta, 48))

            # Update last known radar position if present
            if radar_row is not None and pd.notna(radar_row.get('LAT')) and pd.notna(radar_row.get('LON')):
                self._last_radar_by_ta[ta] = {
                    'lat': float(radar_row['LAT']),
                    'lon': float(radar_row['LON']),
                    'fl': float(radar_row['FL']) if pd.notna(radar_row.get('FL')) else None,
                    'time': float(radar_row['Time_sec'])
                }

            # Helper to choose speed with priority GS_TVP(kt) > GS(kt) > GS_BDS(kt)
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

            # ADS-B point
            if adsb_row is not None and pd.notna(adsb_row.get('LAT')) and pd.notna(adsb_row.get('LON')):
                aircraft_data.append({
                    'address': ta,
                    'callsign': str(adsb_row.get('TI', '')) if pd.notna(adsb_row.get('TI')) else '',
                    'lat': float(adsb_row['LAT']),
                    'lon': float(adsb_row['LON']),
                    'fl': float(adsb_row['FL']) if pd.notna(adsb_row.get('FL')) else None,
                    'speed': pick_speed(adsb_row),
                    'cat': 21,
                    'both': ta in both_set
                })

            # RADAR point: if missing in this window but known historically, keep last position
            if radar_row is not None and pd.notna(radar_row.get('LAT')) and pd.notna(radar_row.get('LON')):
                aircraft_data.append({
                    'address': ta,
                    'callsign': str(radar_row.get('TI', '')) if pd.notna(radar_row.get('TI')) else '',
                    'lat': float(radar_row['LAT']),
                    'lon': float(radar_row['LON']),
                    'fl': float(radar_row['FL']) if pd.notna(radar_row.get('FL')) else None,
                    'speed': pick_speed(radar_row),
                    'cat': 48,
                    'both': ta in both_set
                })
            else:
                last = self._last_radar_by_ta.get(ta)
                if last is not None:
                    aircraft_data.append({
                        'address': ta,
                        'callsign': str(adsb_row.get('TI', '')) if adsb_row is not None and pd.notna(adsb_row.get('TI')) else '',
                        'lat': last['lat'],
                        'lon': last['lon'],
                        'fl': last['fl'],
                        'speed': None,
                        'cat': 48,
                        'both': ta in both_set
                    })

        if aircraft_data:
            adsb_count = sum(1 for a in aircraft_data if a['cat'] == 21)
            radar_count = sum(1 for a in aircraft_data if a['cat'] == 48)
            both_count = len([ta for ta in tas_seen if ta in both_set])

            self.aircraft_label.setText(
                f"Aircraft: {len(aircraft_data)} (ADS-B: {adsb_count}, Radar: {radar_count}, Both: {both_count})")
            js_code = f"updateAircraft({json.dumps(aircraft_data)});"
            self.web_view.page().runJavaScript(js_code)
        else:
            self.aircraft_label.setText("Aircraft: 0")
