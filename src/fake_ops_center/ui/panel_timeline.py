"""Interactive timeline panel visualising incident lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import hypot
from typing import Dict, List

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QDockWidget, QVBoxLayout, QWidget

from ..core.models import Incident, IncidentSeverity, IncidentStatus


@dataclass(frozen=True)
class TimelineEvent:
    """Represents a point on the incident timeline."""

    identifier: str
    timestamp: datetime
    severity: IncidentSeverity
    status: IncidentStatus
    description: str


def ensure_timestamp(timestamp: datetime | None) -> datetime:
    """Return a non-null, timezone aware timestamp.

    Parameters
    ----------
    timestamp:
        Candidate timestamp that may be ``None``.

    Returns
    -------
    datetime
        ``timestamp`` when provided, otherwise the current UTC time.

    Examples
    --------
    >>> isinstance(ensure_timestamp(None), datetime)
    True
    """

    if timestamp is None:
        return datetime.now(UTC)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp


class TimelinePanel(QDockWidget):
    """Dockable widget displaying an interactive incident timeline."""

    _SEVERITY_ORDER: tuple[IncidentSeverity, ...] = (
        IncidentSeverity.LOW,
        IncidentSeverity.MEDIUM,
        IncidentSeverity.HIGH,
        IncidentSeverity.CRITICAL,
    )

    _STATUS_SYMBOLS: dict[IncidentStatus, str] = {
        IncidentStatus.NEW: "o",
        IncidentStatus.ACKNOWLEDGED: "s",
        IncidentStatus.IN_PROGRESS: "t",
        IncidentStatus.RESOLVED: "star",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Incident Timeline", parent)
        self.setObjectName("timelinePanel")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._plot = pg.PlotWidget(title="Lifecycle Events")
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.setMouseEnabled(x=True, y=False)
        self._plot.getPlotItem().hideButtons()
        self._plot.setLabel("bottom", "Elapsed", units="s")
        self._plot.setLabel("left", "Severity")
        self._plot.setYRange(-0.5, len(self._SEVERITY_ORDER) - 0.5)
        self._plot.getAxis("left").setTicks(
            [[(idx, sev.name.title()) for idx, sev in enumerate(self._SEVERITY_ORDER)]]
        )

        self._scatter = pg.ScatterPlotItem(size=10, pxMode=True)
        self._plot.addItem(self._scatter)

        self._info_label = QLabel("Наведите курсор на событие для подробностей")
        self._info_label.setObjectName("timelineInfoLabel")

        layout.addWidget(self._plot)
        layout.addWidget(self._info_label)
        self.setWidget(container)

        self._events: List[TimelineEvent] = []
        self._last_status: Dict[str, IncidentStatus] = {}
        self._spots: list[dict[str, object]] = []
        self._severity_colors: dict[IncidentSeverity, str] = {}
        self._max_events = 480

        self._mouse_proxy = pg.SignalProxy(
            self._plot.scene().sigMouseMoved, rateLimit=45, slot=self._on_mouse_moved
        )

    # ------------------------------------------------------------------
    # Theme configuration
    # ------------------------------------------------------------------
    def set_theme_colors(self, severity_colors: dict[str, str]) -> None:
        """Update palette using *severity_colors* mapping."""

        self._severity_colors = {
            severity: severity_colors.get(severity.name.lower(), "#8be9fd")
            for severity in self._SEVERITY_ORDER
        }
        self._refresh_plot()

    # ------------------------------------------------------------------
    # Incident updates
    # ------------------------------------------------------------------
    def update_incident(self, incident: Incident) -> None:
        """Append lifecycle event for *incident* when status changes."""

        identifier = incident.identifier
        latest_status = incident.status
        previous_status = self._last_status.get(identifier)
        if previous_status is latest_status:
            return

        timestamp = ensure_timestamp(incident.last_update or incident.timestamp)
        description = incident.description.strip() if incident.description else ""
        safe_description = description[:160] if description else ""

        event = TimelineEvent(
            identifier=identifier,
            timestamp=timestamp,
            severity=incident.severity,
            status=latest_status,
            description=safe_description,
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]

        self._last_status[identifier] = latest_status
        if latest_status is IncidentStatus.RESOLVED:
            self._last_status.pop(identifier, None)

        self._refresh_plot()

    def clear(self) -> None:
        """Reset accumulated events and UI state."""

        self._events.clear()
        self._last_status.clear()
        self._spots.clear()
        self._scatter.clear()
        self._info_label.setText("Наведите курсор на событие для подробностей")

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _refresh_plot(self) -> None:
        if not self._events:
            self._scatter.clear()
            self._spots.clear()
            return

        times = [event.timestamp for event in self._events]
        t0 = min(times)
        x_values = [max((evt.timestamp - t0).total_seconds(), 0.0) for evt in self._events]
        severity_index = {
            severity: idx for idx, severity in enumerate(self._SEVERITY_ORDER)
        }

        self._spots = []
        for event, x in zip(self._events, x_values, strict=False):
            severity_idx = severity_index.get(event.severity, 0)
            color = self._severity_colors.get(event.severity, "#8be9fd")
            symbol = self._STATUS_SYMBOLS.get(event.status, "o")
            self._spots.append(
                {
                    "pos": (x, severity_idx),
                    "data": event,
                    "brush": pg.mkBrush(color),
                    "symbol": symbol,
                    "pen": pg.mkPen(color, width=1),
                    "size": 12 if event.status is IncidentStatus.RESOLVED else 10,
                }
            )

        self._scatter.setData(self._spots)
        if x_values:
            max_x = max(x_values)
            self._plot.setXRange(0, max(60.0, max_x * 1.05), padding=0.02)

    def _on_mouse_moved(self, event: tuple[object, ...]) -> None:
        if not self._spots:
            return
        if not event:
            return
        view_box = self._plot.getViewBox()
        if view_box is None:
            return
        position = event[0]
        if position is None:
            return
        point = view_box.mapSceneToView(position)
        closest_event = self._find_closest_event(point.x(), point.y())
        if closest_event is None:
            self._info_label.setText("Наведите курсор на событие для подробностей")
            return
        timestamp = closest_event.timestamp.strftime("%H:%M:%S")
        message = (
            f"#{closest_event.identifier} · {closest_event.status.name.title()} · "
            f"{closest_event.severity.name.title()} · {timestamp}"
        )
        if closest_event.description:
            message += f" · {closest_event.description}"
        self._info_label.setText(message)

    def _find_closest_event(self, x: float, y: float) -> TimelineEvent | None:
        minimum_distance = float("inf")
        closest: TimelineEvent | None = None
        for spot in self._spots:
            pos_x, pos_y = spot["pos"]  # type: ignore[misc]
            distance = hypot(pos_x - x, pos_y - y)
            if distance < minimum_distance and distance < 6.0:
                minimum_distance = distance
                closest = spot["data"]  # type: ignore[assignment]
        return closest


__all__ = ["TimelinePanel", "TimelineEvent", "ensure_timestamp"]

