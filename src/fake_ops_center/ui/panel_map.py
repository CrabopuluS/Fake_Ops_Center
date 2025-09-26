"""Interactive map panel powered by a Leaflet map."""

from __future__ import annotations

import json
from dataclasses import dataclass

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QDockWidget, QWidget

from ..core.models import Incident, IncidentSeverity, IncidentStatus


@dataclass(frozen=True)
class _Bounds:
    """Geographical bounding box."""

    south: float
    west: float
    north: float
    east: float


class MapPanel(QDockWidget):
    """Dockable widget showing an interactive Leaflet map of Moscow."""

    _MOSCOW_CENTER = (55.751244, 37.618423)
    _MOSCOW_BOUNDS = _Bounds(south=55.55, west=37.35, north=55.95, east=37.85)

    def __init__(
        self,
        grid_size: tuple[int, int],
        colors: dict[str, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Map", parent)
        self.setObjectName("mapPanel")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.grid_size = self._validated_grid_size(grid_size)
        self.colors = dict(colors)
        self._incidents: dict[str, Incident] = {}
        self._pending_scripts: list[str] = []
        self._page_ready = False

        self.view = QWebEngineView(self)
        self.setWidget(self.view)
        self.view.loadFinished.connect(self._on_load_finished)
        self._load_initial_map()

    @staticmethod
    def _validated_grid_size(grid_size: tuple[int, int]) -> tuple[int, int]:
        width, height = grid_size
        if width <= 0 or height <= 0:
            raise ValueError("grid_size dimensions must be positive integers")
        return width, height

    def _load_initial_map(self) -> None:
        self._page_ready = False
        self._pending_scripts.clear()
        html = self._build_initial_html()
        self.view.setHtml(html, QUrl("https://local.fake-ops/"))

    def _build_initial_html(self) -> str:
        marker_ok = self.colors.get("marker_ok", "#50fa7b")
        marker_warn = self.colors.get("marker_warn", "#ffb86c")
        marker_err = self.colors.get("marker_err", "#ff5555")
        surface = self.colors.get("surface", "#111a32")
        surface_alt = self.colors.get("surface_alt", "#16223f")
        text = self.colors.get("text", "#f5f7ff")
        muted = self.colors.get("muted", "#7c8db5")
        accent = self.colors.get("accent", marker_ok)
        bg = self.colors.get("bg", "#080b1a")
        grid = self.colors.get("grid", "#233353")
        tile_layer = (
            "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/"
            "{z}/{x}/{y}{r}.png"
        )
        return f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet" />
    <style>
      :root {{
        color-scheme: dark;
        --color-bg: {bg};
        --color-surface: {surface};
        --color-surface-alt: {surface_alt};
        --color-text: {text};
        --color-muted: {muted};
        --color-accent: {accent};
        --marker-ok: {marker_ok};
        --marker-warn: {marker_warn};
        --marker-err: {marker_err};
      }}
      * {{
        box-sizing: border-box;
      }}
      html, body {{ height: 100%; margin: 0; }}
      body {{
        background: radial-gradient(circle at top left, rgba(45, 94, 181, 0.25), transparent 55%),
                    radial-gradient(circle at bottom right, rgba(34, 197, 94, 0.2), transparent 50%),
                    var(--color-bg);
        font-family: 'Inter', 'Segoe UI', sans-serif;
        color: var(--color-text);
        overflow: hidden;
      }}
      #map {{
        position: absolute;
        inset: 0;
        border-radius: 18px;
        overflow: hidden;
        box-shadow: inset 0 0 0 1px rgba(94, 234, 212, 0.08);
      }}
      .leaflet-container {{
        background: radial-gradient(circle at 20% 20%, rgba(59, 130, 246, 0.25), transparent 50%),
                    radial-gradient(circle at 80% 30%, rgba(16, 185, 129, 0.22), transparent 55%),
                    var(--color-bg);
        font-family: 'Inter', 'Segoe UI', sans-serif;
      }}
      .leaflet-tile-pane {{
        filter: saturate(1.1) brightness(0.96) contrast(1.12);
      }}
      .leaflet-control-container .leaflet-top.leaflet-right {{
        margin-top: 24px;
        margin-right: 24px;
      }}
      .leaflet-control-zoom a {{
        background: rgba(12, 22, 44, 0.88);
        border: 1px solid rgba(59, 130, 246, 0.45);
        color: var(--color-text);
        transition: background 0.2s ease, color 0.2s ease;
      }}
      .leaflet-control-zoom a:hover {{
        background: rgba(37, 99, 235, 0.65);
        color: #fff;
      }}
      .map-overlay {{
        position: absolute;
        inset: 24px 24px auto 24px;
        display: flex;
        align-items: flex-start;
        gap: 16px;
        pointer-events: none;
        z-index: 1200;
      }}
      .map-card {{
        background: rgba(10, 18, 36, 0.88);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(125, 211, 252, 0.25);
        border-radius: 18px;
        padding: 18px 22px;
        box-shadow: 0 18px 45px rgba(5, 10, 24, 0.55);
        pointer-events: auto;
      }}
      .map-card h1 {{
        font-size: 18px;
        font-weight: 700;
        margin: 0 0 4px 0;
        color: var(--color-text);
        letter-spacing: 0.4px;
      }}
      .map-card p {{
        margin: 0;
        color: var(--color-muted);
        font-size: 13px;
      }}
      .legend {{
        display: grid;
        grid-template-columns: repeat(3, auto);
        gap: 12px 16px;
        margin-top: 12px;
      }}
      .legend-item {{
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 12px;
        border-radius: 12px;
        background: rgba(17, 34, 60, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.05);
      }}
      .legend-item span {{
        display: inline-flex;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        box-shadow: 0 0 12px currentColor;
      }}
      .legend-item strong {{
        font-size: 12px;
        letter-spacing: 0.3px;
      }}
      .grid-card {{
        position: absolute;
        right: 24px;
        bottom: 24px;
        background: rgba(10, 18, 36, 0.78);
        border: 1px solid {grid};
        border-radius: 16px;
        padding: 14px 18px;
        font-size: 12px;
        color: var(--color-muted);
        pointer-events: none;
        backdrop-filter: blur(14px);
      }}
      .grid-card span {{
        color: var(--color-text);
        font-weight: 600;
      }}
      .foc-marker-wrapper {{
        width: 36px;
        height: 36px;
        transform: translate(-50%, -50%);
      }}
      .foc-marker {{
        position: relative;
        width: 36px;
        height: 36px;
        transform: translate(-50%, -50%);
      }}
      .foc-marker__core {{
        position: absolute;
        inset: 8px;
        border-radius: 50%;
        background: var(--marker-color);
        box-shadow: 0 0 22px rgba(125, 211, 252, 0.45);
        border: 3px solid rgba(255, 255, 255, 0.7);
      }}
      .foc-marker__pulse {{
        position: absolute;
        inset: 0;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255, 255, 255, 0.65) 0%, rgba(255, 255, 255, 0.0) 65%);
        opacity: 0.85;
        animation: focPulse 2.8s ease-out infinite;
      }}
      .foc-marker__dot {{
        position: absolute;
        inset: 13px;
        border-radius: 50%;
        background: rgba(10, 18, 36, 0.85);
        border: 2px solid rgba(255, 255, 255, 0.65);
      }}
      .foc-marker--ok .foc-marker__core {{
        box-shadow: 0 0 18px rgba(52, 211, 153, 0.45);
      }}
      .foc-marker--warn .foc-marker__core {{
        box-shadow: 0 0 18px rgba(249, 115, 22, 0.55);
      }}
      .foc-marker--err .foc-marker__core {{
        box-shadow: 0 0 22px rgba(244, 63, 94, 0.6);
      }}
      .foc-marker--resolved .foc-marker__pulse {{
        animation-duration: 4s;
        opacity: 0.45;
      }}
      .foc-marker--resolved .foc-marker__core {{
        border-color: rgba(255, 255, 255, 0.35);
        box-shadow: 0 0 14px rgba(52, 211, 153, 0.45);
      }}
      .fallback-tooltip {{
        position: absolute;
        bottom: 38px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(15, 23, 42, 0.92);
        padding: 8px 12px;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.35);
        color: var(--color-text);
        font-size: 11px;
        white-space: nowrap;
        pointer-events: none;
        letter-spacing: 0.25px;
      }}
      @keyframes focPulse {{
        0% {{ transform: scale(0.45); opacity: 0.9; }}
        70% {{ transform: scale(1); opacity: 0; }}
        100% {{ transform: scale(1); opacity: 0; }}
      }}
      @media (max-width: 768px) {{
        .map-overlay {{
          flex-direction: column;
          inset: 16px;
        }}
        .legend {{
          grid-template-columns: repeat(2, auto);
        }}
        .grid-card {{
          right: 16px;
          bottom: 16px;
        }}
      }}
    </style>
  </head>
  <body>
    <div id="map"></div>
    <div class="map-overlay">
      <div class="map-card">
        <h1>Operational Landscape</h1>
        <p>Live telemetry of ongoing incidents across the region.</p>
        <div class="legend">
          <div class="legend-item" style="color: var(--marker-err);">
            <span style="background: var(--marker-err);"></span>
            <strong>Critical / High</strong>
          </div>
          <div class="legend-item" style="color: var(--marker-warn);">
            <span style="background: var(--marker-warn);"></span>
            <strong>Medium Severity</strong>
          </div>
          <div class="legend-item" style="color: var(--marker-ok);">
            <span style="background: var(--marker-ok);"></span>
            <strong>Normal / Resolved</strong>
          </div>
        </div>
      </div>
    </div>
    <div class="grid-card">Grid resolution <span>{self.grid_size[0]} × {self.grid_size[1]}</span></div>
    <link
      rel="stylesheet"
      href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
      crossorigin=""
    />
    <script
      src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
      integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
      crossorigin=""
    ></script>
    <script>
      const MOSCOW_CENTER = [{self._MOSCOW_CENTER[0]}, {self._MOSCOW_CENTER[1]}];
      const MOSCOW_BOUNDS = [
        [{self._MOSCOW_BOUNDS.south}, {self._MOSCOW_BOUNDS.west}],
        [{self._MOSCOW_BOUNDS.north}, {self._MOSCOW_BOUNDS.east}]
      ];
      const markers = {{}};
      const pendingUpdates = [];
      const fallbackMarkers = {{}};
      const fallbackLayerId = 'fallback-layer';
      const mapElement = document.getElementById('map');
      let map;
      let mapReady = false;
      let usingFallback = false;
      let tileLayer;

      function mapBounds() {{
        return {{
          south: MOSCOW_BOUNDS[0][0],
          west: MOSCOW_BOUNDS[0][1],
          north: MOSCOW_BOUNDS[1][0],
          east: MOSCOW_BOUNDS[1][1],
        }};
      }}

      function percentFromBounds(lat, lng) {{
        const bounds = mapBounds();
        const latSpan = bounds.north - bounds.south || 1;
        const lngSpan = bounds.east - bounds.west || 1;
        const x = ((lng - bounds.west) / lngSpan) * 100;
        const y = (1 - (lat - bounds.south) / latSpan) * 100;
        return {{ x: Math.max(0, Math.min(100, x)), y: Math.max(0, Math.min(100, y)) }};
      }}

      function removeFallbackLayer() {{
        const layer = document.getElementById(fallbackLayerId);
        if (layer) {{
          layer.remove();
        }}
      }}

      function ensureFallbackLayer() {{
        let layer = document.getElementById(fallbackLayerId);
        if (!layer) {{
          layer = document.createElement('div');
          layer.id = fallbackLayerId;
          layer.style.position = 'absolute';
          layer.style.inset = '0';
          layer.style.background = 'linear-gradient(135deg, rgba(30, 64, 175, 0.3), rgba(15, 23, 42, 0.88))';
          layer.style.border = '1px solid rgba(148, 163, 184, 0.3)';
          layer.style.borderRadius = '16px';
          layer.style.margin = '18px';
          layer.style.overflow = 'hidden';
          layer.style.boxShadow = '0 18px 45px rgba(8, 11, 26, 0.65)';
          const gridLayer = document.createElement('div');
          gridLayer.style.position = 'absolute';
          gridLayer.style.inset = '0';
          gridLayer.style.backgroundImage = 'linear-gradient(rgba(148, 163, 184, 0.18) 1px, transparent 1px), linear-gradient(90deg, rgba(148, 163, 184, 0.18) 1px, transparent 1px)';
          gridLayer.style.backgroundSize = '40px 40px';
          layer.appendChild(gridLayer);
          const emptyState = document.createElement('div');
          emptyState.textContent = 'Карта недоступна — показано упрощённое представление.';
          emptyState.style.position = 'absolute';
          emptyState.style.top = '16px';
          emptyState.style.left = '50%';
          emptyState.style.transform = 'translateX(-50%)';
          emptyState.style.padding = '10px 18px';
          emptyState.style.borderRadius = '999px';
          emptyState.style.background = 'rgba(15, 23, 42, 0.85)';
          emptyState.style.color = 'var(--color-text)';
          emptyState.style.fontSize = '12px';
          emptyState.style.letterSpacing = '0.3px';
          emptyState.style.pointerEvents = 'none';
          layer.appendChild(emptyState);
          mapElement.appendChild(layer);
        }}
        return layer;
      }}

      function markerState(data) {{
        if (data.resolved) {{
          return 'foc-marker--resolved';
        }}
        if (data.severity === 'warn') {{
          return 'foc-marker--warn';
        }}
        if (data.severity === 'err') {{
          return 'foc-marker--err';
        }}
        return 'foc-marker--ok';
      }}

      function createFallbackMarker(data) {{
        const layer = ensureFallbackLayer();
        let marker = fallbackMarkers[data.id];
        if (!marker) {{
          marker = document.createElement('div');
          marker.className = 'foc-marker ' + markerState(data);
          marker.style.position = 'absolute';
          marker.innerHTML = '<div class="foc-marker__pulse"></div><div class="foc-marker__core"></div><div class="foc-marker__dot"></div>';
          marker.style.setProperty('--marker-color', data.color);
          layer.appendChild(marker);
          fallbackMarkers[data.id] = marker;
          const tooltip = document.createElement('div');
          tooltip.className = 'fallback-tooltip';
          tooltip.textContent = data.id + ' — ' + data.status;
          marker.appendChild(tooltip);
        }}
        return marker;
      }}

      function updateFallbackMarker(marker, data, position) {{
        marker.style.left = position.x + '%';
        marker.style.top = position.y + '%';
        marker.style.setProperty('--marker-color', data.color);
        marker.className = 'foc-marker ' + markerState(data);
        const tooltip = marker.querySelector('.fallback-tooltip');
        if (tooltip) {{
          tooltip.textContent = data.id + ' — ' + data.status;
        }}
      }}

      function applyPendingUpdates() {{
        if (!pendingUpdates.length) {{
          return;
        }}
        const updates = pendingUpdates.splice(0, pendingUpdates.length);
        updates.forEach(handleIncidentUpdate);
      }}

      function markerHtml(data) {{
        return (
          '<div class="foc-marker-wrapper">' +
          '<div class="foc-marker ' + markerState(data) + '" style="--marker-color: ' + data.color + ';">' +
          '<span class="foc-marker__pulse"></span>' +
          '<span class="foc-marker__core"></span>' +
          '<span class="foc-marker__dot"></span>' +
          '</div>' +
          '</div>'
        );
      }}

      function createMarker(data) {{
        const icon = L.divIcon({{
          className: 'foc-marker-wrapper',
          html: markerHtml(data),
          iconSize: [36, 36],
          iconAnchor: [18, 18],
          popupAnchor: [0, -22],
        }});
        const marker = L.marker([data.lat, data.lng], {{ icon, zIndexOffset: data.resolved ? 200 : 400 }});
        marker.bindPopup('<strong>' + data.id + '</strong><br />' + data.category + '<br />' + data.status);
        marker.bindTooltip(data.id, {{ direction: 'top', offset: [0, -14] }});
        marker.addTo(map);
        markers[data.id] = marker;
        return marker;
      }}

      function updateMarker(marker, data) {{
        const icon = L.divIcon({{
          className: 'foc-marker-wrapper',
          html: markerHtml(data),
          iconSize: [36, 36],
          iconAnchor: [18, 18],
          popupAnchor: [0, -22],
        }});
        marker.setLatLng([data.lat, data.lng]);
        marker.setIcon(icon);
        marker.setZIndexOffset(data.resolved ? 200 : 400);
        marker.setPopupContent('<strong>' + data.id + '</strong><br />' + data.category + '<br />' + data.status);
      }}

      function handleIncidentUpdate(data) {{
        const position = [data.lat, data.lng];
        if (usingFallback) {{
          const projected = percentFromBounds(data.lat, data.lng);
          const marker = createFallbackMarker(data);
          updateFallbackMarker(marker, data, projected);
          return;
        }}
        let marker = markers[data.id];
        if (!marker) {{
          marker = createMarker(data);
        }} else {{
          updateMarker(marker, data);
        }}
        if (map && map.getBounds && !map.getBounds().contains(position)) {{
          map.flyTo(position, map.getZoom(), {{ duration: 0.8 }});
        }}
      }}

      function initializeFallback() {{
        usingFallback = true;
        mapReady = true;
        applyPendingUpdates();
      }}

      function initializeMap() {{
        usingFallback = false;
        removeFallbackLayer();
        if (!window.L) {{
          initializeFallback();
          return;
        }}
        const bounds = L.latLngBounds(
          [MOSCOW_BOUNDS[0][0], MOSCOW_BOUNDS[0][1]],
          [MOSCOW_BOUNDS[1][0], MOSCOW_BOUNDS[1][1]]
        );
        map = L.map('map', {{
          center: MOSCOW_CENTER,
          zoom: 11,
          minZoom: 9,
          maxZoom: 16,
          maxBounds: bounds.pad(0.2),
          zoomControl: false,
        }});
        L.control.zoom({{ position: 'topright' }}).addTo(map);
        mapReady = true;
        applyPendingUpdates();
        let tileLoaded = false;
        tileLayer = L.tileLayer('{tile_layer}', {{
          maxZoom: 18,
          subdomains: 'abcd',
          crossOrigin: true,
          className: 'foc-tile-layer',
        }});
        tileLayer.on('load', () => {{
          if (!tileLoaded) {{
            tileLoaded = true;
            usingFallback = false;
            removeFallbackLayer();
            mapReady = true;
            applyPendingUpdates();
          }}
        }});
        tileLayer.on('tileerror', () => {{
          if (!tileLoaded && !usingFallback) {{
            initializeFallback();
          }}
        }});
        tileLayer.addTo(map);
        map.fitBounds(bounds, {{ padding: [32, 32] }});
        map.on('zoomend moveend', () => {{
          mapReady = true;
          applyPendingUpdates();
        }});
        setTimeout(() => {{
          if (!tileLoaded && !usingFallback) {{
            initializeFallback();
          }}
        }}, 2200);
      }}

      window.updateIncident = function(payload) {{
        const data = JSON.parse(payload);
        if (!mapReady) {{
          pendingUpdates.push(data);
          return;
        }}
        handleIncidentUpdate(data);
      }};

      document.addEventListener('DOMContentLoaded', () => {{
        initializeMap();
        if (!mapReady) {{
          setTimeout(() => {{
            if (!mapReady && !usingFallback) {{
              initializeFallback();
            }}
          }}, 2500);
        }}
      }});
    </script>
  </body>
</html>

"""
    def _on_load_finished(self, ok: bool) -> None:
        self._page_ready = ok
        if ok and self._pending_scripts:
            for script in self._pending_scripts:
                self.view.page().runJavaScript(script)
            self._pending_scripts.clear()

    def _enqueue_script(self, script: str) -> None:
        if self._page_ready:
            self.view.page().runJavaScript(script)
        else:
            self._pending_scripts.append(script)

    def _marker_color(self, incident: Incident) -> str:
        if incident.status is IncidentStatus.RESOLVED:
            return self.colors.get("marker_ok", "#50fa7b")
        if incident.severity in (IncidentSeverity.HIGH, IncidentSeverity.CRITICAL):
            return self.colors.get("marker_err", "#ff5555")
        if incident.severity is IncidentSeverity.MEDIUM:
            return self.colors.get("marker_warn", "#ffb86c")
        return self.colors.get("marker_ok", "#50fa7b")

    def _location_to_latlon(self, location: tuple[int, int] | None) -> tuple[float, float]:
        if location is None:
            return self._MOSCOW_CENTER
        x, y = location
        width, height = self.grid_size
        x = max(0, min(width - 1, x))
        y = max(0, min(height - 1, y))
        lon_span = self._MOSCOW_BOUNDS.east - self._MOSCOW_BOUNDS.west
        lat_span = self._MOSCOW_BOUNDS.north - self._MOSCOW_BOUNDS.south
        lon = self._MOSCOW_BOUNDS.west + (x / max(1, width - 1)) * lon_span
        lat = self._MOSCOW_BOUNDS.north - (y / max(1, height - 1)) * lat_span
        return lat, lon

    def update_incident(self, incident: Incident) -> None:
        """Create or update a map marker for *incident*."""

        self._incidents[incident.identifier] = incident
        lat, lon = self._location_to_latlon(incident.location)
        severity_tag = "ok"
        if incident.status is IncidentStatus.RESOLVED:
            severity_tag = "resolved"
        elif incident.severity in (IncidentSeverity.HIGH, IncidentSeverity.CRITICAL):
            severity_tag = "err"
        elif incident.severity is IncidentSeverity.MEDIUM:
            severity_tag = "warn"

        payload = {
            "id": incident.identifier,
            "lat": lat,
            "lng": lon,
            "color": self._marker_color(incident),
            "status": incident.status.name.replace("_", " ").title(),
            "category": incident.category.title(),
            "resolved": incident.status is IncidentStatus.RESOLVED,
            "severity": severity_tag,
        }
        script = f"window.updateIncident({json.dumps(json.dumps(payload))});"
        self._enqueue_script(script)

    def set_colors(self, colors: dict[str, str]) -> None:
        self.colors = dict(colors)
        self._load_initial_map()
        if self._incidents:
            for incident in self._incidents.values():
                self.update_incident(incident)


__all__ = ["MapPanel"]
