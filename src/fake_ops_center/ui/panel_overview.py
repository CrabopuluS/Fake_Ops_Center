"""Incident overview dashboard panel."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Dict

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QVBoxLayout, QWidget

from ..core.models import Incident, IncidentSeverity, IncidentStatus


class OverviewPanel(QDockWidget):
    """Interactive dashboard with incident summaries."""

    _SEVERITY_ORDER: tuple[IncidentSeverity, ...] = (
        IncidentSeverity.LOW,
        IncidentSeverity.MEDIUM,
        IncidentSeverity.HIGH,
        IncidentSeverity.CRITICAL,
    )
    _STATUS_ORDER: tuple[IncidentStatus, ...] = (
        IncidentStatus.NEW,
        IncidentStatus.ACKNOWLEDGED,
        IncidentStatus.IN_PROGRESS,
        IncidentStatus.RESOLVED,
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Incident Overview", parent)
        self.setObjectName("overviewPanel")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._incidents: Dict[str, Incident] = {}
        self._severity_counts: Counter[IncidentSeverity] = Counter()
        self._status_counts: Counter[IncidentStatus] = Counter()
        self._resolution_times: list[float] = []
        self._start_time: datetime | None = None
        self._severity_colors: dict[IncidentSeverity, str] = {}
        self._status_colors: dict[IncidentStatus, str] = {}

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._graphics = pg.GraphicsLayoutWidget()
        self._graphics.ci.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._graphics)

        self._severity_plot = self._graphics.addPlot(row=0, col=0, title="By Severity")
        self._severity_plot.showGrid(x=True, y=True, alpha=0.15)
        self._severity_plot.setMouseEnabled(x=False, y=True)
        self._severity_plot.setMenuEnabled(True)
        self._severity_plot.getAxis("bottom").setTicks(
            [
                [
                    (idx, severity.name.title().replace("_", " "))
                    for idx, severity in enumerate(self._SEVERITY_ORDER)
                ]
            ]
        )
        self._severity_bars: list[pg.BarGraphItem] = []

        self._status_plot = self._graphics.addPlot(row=1, col=0, title="By Status")
        self._status_plot.showGrid(x=True, y=True, alpha=0.15)
        self._status_plot.setMouseEnabled(x=False, y=True)
        self._status_plot.setMenuEnabled(True)
        self._status_plot.getAxis("bottom").setTicks(
            [
                [
                    (idx, status.name.title().replace("_", " "))
                    for idx, status in enumerate(self._STATUS_ORDER)
                ]
            ]
        )
        self._status_bars: list[pg.BarGraphItem] = []

        self._trend_plot = self._graphics.addPlot(row=0, col=1, rowspan=2, title="Resolution Trend")
        self._trend_plot.showGrid(x=True, y=True, alpha=0.2)
        self._trend_plot.setLabel("bottom", "Time", units="s")
        self._trend_plot.setLabel("left", "Resolved Incidents", units="count")
        self._trend_curve = self._trend_plot.plot(pen=pg.mkPen("#8be9fd", width=2))

        self.setWidget(container)

    def set_theme_colors(
        self,
        severity_colors: dict[str, str],
        status_colors: dict[str, str],
    ) -> None:
        """Configure palette for bar charts."""

        self._severity_colors = {
            severity: severity_colors.get(severity.name.lower(), "#8be9fd")
            for severity in self._SEVERITY_ORDER
        }
        self._status_colors = {
            status: status_colors.get(status.name.lower(), "#6272a4")
            for status in self._STATUS_ORDER
        }
        self._refresh_severity_chart()
        self._refresh_status_chart()

    def update_incident(self, incident: Incident) -> None:
        """Update dashboards with latest *incident* details."""

        previous = self._incidents.get(incident.identifier)
        if previous is None:
            self._severity_counts[incident.severity] += 1
        elif previous.severity is not incident.severity:
            self._severity_counts[previous.severity] -= 1
            self._severity_counts[incident.severity] += 1

        if previous is None:
            self._status_counts[incident.status] += 1
        elif previous.status is not incident.status:
            self._status_counts[previous.status] -= 1
            if self._status_counts[previous.status] < 0:
                self._status_counts[previous.status] = 0
            self._status_counts[incident.status] += 1
            if incident.status is IncidentStatus.RESOLVED:
                self._record_resolution_time(incident)

        if previous is None and incident.status is IncidentStatus.RESOLVED:
            self._record_resolution_time(incident)

        self._incidents[incident.identifier] = incident

        self._refresh_severity_chart()
        self._refresh_status_chart()
        self._refresh_trend_chart()

    def clear(self) -> None:
        """Reset accumulated state."""

        self._incidents.clear()
        self._severity_counts.clear()
        self._status_counts.clear()
        self._resolution_times.clear()
        self._start_time = None
        self._refresh_severity_chart()
        self._refresh_status_chart()
        self._refresh_trend_chart()

    def _record_resolution_time(self, incident: Incident) -> None:
        timestamp = incident.last_update or incident.timestamp
        if self._start_time is None:
            self._start_time = timestamp
        if timestamp is None or self._start_time is None:
            return
        delta = (timestamp - self._start_time).total_seconds()
        if delta < 0:
            delta = 0.0
        self._resolution_times.append(delta)

    def _refresh_severity_chart(self) -> None:
        heights = [self._severity_counts.get(severity, 0) for severity in self._SEVERITY_ORDER]
        brushes = [
            pg.mkBrush(self._severity_colors.get(severity, "#8be9fd"))
            for severity in self._SEVERITY_ORDER
        ]
        for bar in self._severity_bars:
            self._severity_plot.removeItem(bar)
        self._severity_bars.clear()
        for idx, (height, brush) in enumerate(zip(heights, brushes, strict=False)):
            bar = pg.BarGraphItem(x=[idx], height=[height], width=0.6, brush=brush)
            self._severity_plot.addItem(bar)
            self._severity_bars.append(bar)
        self._severity_plot.setYRange(0, max(5, max(heights, default=0) + 1), padding=0.05)

    def _refresh_status_chart(self) -> None:
        heights = [self._status_counts.get(status, 0) for status in self._STATUS_ORDER]
        brushes = [
            pg.mkBrush(self._status_colors.get(status, "#6272a4"))
            for status in self._STATUS_ORDER
        ]
        for bar in self._status_bars:
            self._status_plot.removeItem(bar)
        self._status_bars.clear()
        for idx, (height, brush) in enumerate(zip(heights, brushes, strict=False)):
            bar = pg.BarGraphItem(x=[idx], height=[height], width=0.6, brush=brush)
            self._status_plot.addItem(bar)
            self._status_bars.append(bar)
        self._status_plot.setYRange(0, max(5, max(heights, default=0) + 1), padding=0.05)

    def _refresh_trend_chart(self) -> None:
        if not self._resolution_times:
            self._trend_curve.setData([], [])
            return
        sorted_pairs = sorted(self._resolution_times)
        counts = list(range(1, len(sorted_pairs) + 1))
        self._trend_curve.setData(sorted_pairs, counts)
        self._trend_plot.setXRange(0, max(sorted_pairs) + 10, padding=0.05)
        self._trend_plot.setYRange(0, counts[-1] + 1, padding=0.05)


__all__ = ["OverviewPanel"]
