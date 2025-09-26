"""Risk matrix heatmap panel for region and severity analysis."""

from __future__ import annotations

from collections import Counter
from typing import Dict

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QLabel, QDockWidget, QVBoxLayout, QWidget

from ..core.models import Incident, IncidentSeverity, IncidentStatus


def sanitize_region_name(raw_region: str | None) -> str:
    """Return a safe, human-friendly region label.

    Non-alphanumeric characters (except ``-`` and ``_``) are stripped to guard against
    UI injection. Empty strings are normalised to ``"unknown"``.

    Examples
    --------
    >>> sanitize_region_name("us-east")
    'us-east'
    >>> sanitize_region_name("  ../etc/passwd  ")
    'unknown'
    """

    if not raw_region:
        return "unknown"
    filtered = "".join(
        ch for ch in raw_region.strip() if ch.isalnum() or ch in {"-", "_"}
    )
    if not filtered:
        return "unknown"
    return filtered[:32].lower()


class RiskMatrixPanel(QDockWidget):
    """Dockable heatmap showing active incidents per region and severity."""

    _SEVERITY_ORDER: tuple[IncidentSeverity, ...] = (
        IncidentSeverity.LOW,
        IncidentSeverity.MEDIUM,
        IncidentSeverity.HIGH,
        IncidentSeverity.CRITICAL,
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Risk Matrix", parent)
        self.setObjectName("riskMatrixPanel")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._plot = pg.PlotWidget(title="Active Incidents by Region")
        self._plot.invertY(True)
        self._plot.showGrid(x=False, y=False)
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.getPlotItem().hideButtons()
        self._plot.setLabel("bottom", "Region")
        self._plot.setLabel("left", "Severity")

        self._image = pg.ImageItem(axisOrder="row-major")
        self._image.setAutoDownsample(True)
        self._plot.addItem(self._image)

        self._info_label = QLabel("Наведите курсор на матрицу для деталей")
        self._info_label.setObjectName("riskMatrixInfoLabel")

        layout.addWidget(self._plot)
        layout.addWidget(self._info_label)
        self.setWidget(container)

        self._active_incidents: Dict[str, Incident] = {}
        self._regions: list[str] = []
        self._severity_colors: dict[IncidentSeverity, str] = {}
        self._lut = pg.ColorMap([0.0, 1.0], [(30, 30, 60), (125, 211, 252)]).getLookupTable(
            nPts=256
        )
        self._mouse_proxy = pg.SignalProxy(
            self._plot.scene().sigMouseMoved, rateLimit=45, slot=self._on_mouse_moved
        )

    # ------------------------------------------------------------------
    # Theme configuration
    # ------------------------------------------------------------------
    def set_theme_colors(self, severity_colors: dict[str, str], accent_color: str) -> None:
        """Update gradient and axis palette."""

        self._severity_colors = {
            severity: severity_colors.get(severity.name.lower(), "#8be9fd")
            for severity in self._SEVERITY_ORDER
        }
        gradient_positions = np.linspace(0.0, 1.0, len(self._SEVERITY_ORDER))
        gradient_colors = [
            pg.mkColor(self._severity_colors[severity]).getRgb()[:3]
            for severity in self._SEVERITY_ORDER
        ]
        gradient_colors[0] = pg.mkColor(accent_color).getRgb()[:3]
        color_map = pg.ColorMap(gradient_positions, gradient_colors)
        self._lut = color_map.getLookupTable(nPts=512)
        self._image.setLookupTable(self._lut)
        self._refresh_axes()
        self._refresh_heatmap()

    # ------------------------------------------------------------------
    # Incident updates
    # ------------------------------------------------------------------
    def update_incident(self, incident: Incident) -> None:
        """Track *incident* and rebuild heatmap based on active items."""

        region = sanitize_region_name(incident.region)
        if region not in self._regions:
            self._regions.append(region)
            self._regions = sorted(self._regions)
            self._refresh_axes()

        if incident.status is IncidentStatus.RESOLVED:
            self._active_incidents.pop(incident.identifier, None)
        else:
            self._active_incidents[incident.identifier] = incident

        self._refresh_heatmap()

    def clear(self) -> None:
        """Remove all cached incidents and visuals."""

        self._active_incidents.clear()
        self._regions.clear()
        self._image.clear()
        self._info_label.setText("Наведите курсор на матрицу для деталей")
        self._plot.getAxis("bottom").setTicks([[]])
        self._plot.getAxis("left").setTicks([[]])

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _refresh_axes(self) -> None:
        if not self._regions:
            return
        bottom_ticks = [(idx, label.upper()) for idx, label in enumerate(self._regions)]
        left_ticks = [
            (idx, severity.name.title())
            for idx, severity in enumerate(self._SEVERITY_ORDER)
        ]
        self._plot.getAxis("bottom").setTicks([bottom_ticks])
        self._plot.getAxis("left").setTicks([left_ticks])
        self._plot.setLimits(
            xMin=-0.5,
            xMax=len(self._regions) - 0.5,
            yMin=-0.5,
            yMax=len(self._SEVERITY_ORDER) - 0.5,
        )

    def _refresh_heatmap(self) -> None:
        if not self._regions:
            self._image.clear()
            return
        data = np.zeros((len(self._SEVERITY_ORDER), len(self._regions)), dtype=float)
        region_index = {region: idx for idx, region in enumerate(self._regions)}
        for incident in self._active_incidents.values():
            idx_region = region_index.get(sanitize_region_name(incident.region))
            if idx_region is None:
                continue
            idx_severity = self._SEVERITY_ORDER.index(incident.severity)
            data[idx_severity, idx_region] += 1.0

        if float(np.max(data)) > 0:
            normalised = data / float(np.max(data))
        else:
            normalised = data
        self._image.setLookupTable(self._lut)
        self._image.setImage(normalised, levels=(0.0, 1.0))
        rect = QRectF(
            -0.5, -0.5, float(len(self._regions)), float(len(self._SEVERITY_ORDER))
        )
        self._image.setRect(rect)

    def _on_mouse_moved(self, event: tuple[object, ...]) -> None:
        if not event or not self._regions:
            return
        view_box = self._plot.getViewBox()
        if view_box is None:
            return
        position = event[0]
        if position is None:
            return
        point = view_box.mapSceneToView(position)
        region_idx = int(round(point.x()))
        severity_idx = int(round(point.y()))
        if not (0 <= region_idx < len(self._regions)):
            return
        if not (0 <= severity_idx < len(self._SEVERITY_ORDER)):
            return
        region = self._regions[region_idx]
        severity = self._SEVERITY_ORDER[severity_idx]
        count = self._count_incidents(region, severity)
        message = (
            f"Регион {region.upper()} · {severity.name.title()} · активных: {count}"
        )
        self._info_label.setText(message)

    def _count_incidents(self, region: str, severity: IncidentSeverity) -> int:
        counter = Counter()
        for incident in self._active_incidents.values():
            incident_region = sanitize_region_name(incident.region)
            if incident_region != region:
                continue
            counter[incident.severity] += 1
        return counter.get(severity, 0)


__all__ = ["RiskMatrixPanel", "sanitize_region_name"]

