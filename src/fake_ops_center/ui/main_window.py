"""Main window and UI composition for Fake Ops Center."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from ..core.bus import EventBus
from ..core.config import Config
from ..core.feeds import INCIDENT_TOPIC, LOG_TOPIC, METRICS_TOPIC, FeedsController
from ..core.models import Incident, IncidentStatus, LogRecord, MetricSample
from ..core.theme import Theme, apply_theme
from .alerts import AlertsOverlay
from .panel_incidents import IncidentsPanel
from .panel_logs import LogsPanel
from .panel_map import MapPanel
from .panel_overview import OverviewPanel
from .panel_metrics import MetricsPanel
from .panel_risk import RiskMatrixPanel
from .panel_timeline import TimelinePanel


def _post_to_ui(callback: Callable[[], None]) -> None:
    """Schedule *callback* to run on the Qt event queue."""

    QTimer.singleShot(0, callback)


class MainWindow(QMainWindow):
    """Application main window with dockable panels."""

    def __init__(
        self,
        app: QApplication,
        config: Config,
        theme: Theme,
        feeds: FeedsController,
        bus: EventBus,
    ) -> None:
        super().__init__()
        self.app = app
        self.config = config
        self.theme = theme
        self.feeds = feeds
        self.bus = bus
        self._paused = False
        self._loop = asyncio.get_event_loop()

        self.setWindowTitle("Fake Ops Center")
        if config.window.fullscreen:
            self.showFullScreen()
        else:
            width, height = config.window.size
            self.resize(width, height)

        self.metrics_panel = MetricsPanel(config.buffers.metrics_seconds, self)
        self.overview_panel = OverviewPanel(self)
        self.incidents_panel = IncidentsPanel(self)
        self.logs_panel = LogsPanel(config.buffers.max_logs, {}, self)
        self.map_panel = MapPanel(config.map.grid, {}, self)
        self.risk_panel = RiskMatrixPanel(self)
        self.timeline_panel = TimelinePanel(self)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.metrics_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.overview_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.incidents_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.logs_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.map_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.risk_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.timeline_panel)

        self.alerts = AlertsOverlay(self)
        self.alerts.setGeometry(self.rect())

        self._create_menus()
        self._register_bus_subscribers()
        self.statusBar()

        self._apply_theme_to_widgets(theme)

        shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_search.activated.connect(self.logs_panel.focus_search)

    def _schedule(self, awaitable: Awaitable[object]) -> None:
        """Schedule *awaitable* on the application event loop."""

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = self._loop
        loop.create_task(awaitable)

    def _create_menus(self) -> None:
        menu_file = self.menuBar().addMenu("&File")
        action_screenshot = QAction("Screenshot", self, shortcut="Ctrl+S")
        action_quit = QAction("Exit", self, shortcut="Ctrl+Q")
        action_screenshot.triggered.connect(self.capture_screenshot)
        action_quit.triggered.connect(self.close)
        menu_file.addAction(action_screenshot)
        menu_file.addAction(action_quit)

        menu_view = self.menuBar().addMenu("&View")
        action_fullscreen = QAction(
            "Toggle Fullscreen", self, shortcut="F11", checkable=True
        )
        action_fullscreen.toggled.connect(self._toggle_fullscreen)
        menu_view.addAction(action_fullscreen)
        menu_view.addSeparator()
        for dock in [
            self.metrics_panel,
            self.overview_panel,
            self.incidents_panel,
            self.logs_panel,
            self.map_panel,
            self.risk_panel,
            self.timeline_panel,
        ]:
            action = dock.toggleViewAction()
            menu_view.addAction(action)

        menu_sim = self.menuBar().addMenu("&Simulation")
        self.action_pause = QAction("Pause", self, shortcut="Ctrl+P")
        self.action_reset = QAction("Reset", self, shortcut="Ctrl+R")
        self.action_pause.triggered.connect(self.toggle_pause)
        self.action_reset.triggered.connect(self.reset_simulation)
        menu_sim.addAction(self.action_pause)
        menu_sim.addAction(self.action_reset)

        menu_theme = self.menuBar().addMenu("&Theme")
        self.action_theme_dark = QAction("Dark", self, checkable=True)
        self.action_theme_light = QAction("Light", self, checkable=True)
        self.action_theme_dark.triggered.connect(
            lambda: self.change_theme("themes/dark.yaml")
        )
        self.action_theme_light.triggered.connect(
            lambda: self.change_theme("themes/light.yaml")
        )
        menu_theme.addAction(self.action_theme_dark)
        menu_theme.addAction(self.action_theme_light)
        self.action_theme_dark.setChecked(True)

    def _register_bus_subscribers(self) -> None:
        self.bus.subscribe(METRICS_TOPIC, self._on_metrics)
        self.bus.subscribe(LOG_TOPIC, self._on_log)
        self.bus.subscribe(INCIDENT_TOPIC, self._on_incident)

    def _on_metrics(self, sample: MetricSample) -> None:
        _post_to_ui(lambda: self.metrics_panel.update_metrics(sample))

    def _on_log(self, record: LogRecord) -> None:
        _post_to_ui(lambda: self.logs_panel.append_log(record))

    def _on_incident(self, incident: Incident) -> None:
        def _update() -> None:
            self.incidents_panel.add_incident(incident)
            self.overview_panel.update_incident(incident)
            self.map_panel.update_incident(incident)
            self.risk_panel.update_incident(incident)
            self.timeline_panel.update_incident(incident)
            if incident.status is IncidentStatus.RESOLVED:
                self.alerts.queue(f"Incident #{incident.identifier} resolved")

        _post_to_ui(_update)

    async def start_simulation(self) -> None:
        await self.feeds.start(self.bus)

    def toggle_pause(self) -> None:
        if self._paused:
            self.action_pause.setText("Pause")
            self._schedule(self.feeds.start(self.bus))
        else:
            self.action_pause.setText("Resume")
            self.feeds.stop()
        self._paused = not self._paused

    def reset_simulation(self) -> None:
        self.feeds.stop()
        self.feeds.reset()
        self.metrics_panel.buffer.samples.clear()
        self.logs_panel.view.clear()
        self.incidents_panel.clear()
        self.overview_panel.clear()
        self.risk_panel.clear()
        self.timeline_panel.clear()
        self.alerts.queue("Simulation reset", duration=2.0)
        if not self._paused:
            self._schedule(self.feeds.start(self.bus))

    def change_theme(self, path: str) -> None:
        from ..core.theme import load_theme

        try:
            theme = load_theme(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Theme Error", str(exc))
            return
        self.theme = theme
        self._apply_theme_to_widgets(theme)
        if "dark" in path:
            self.action_theme_dark.setChecked(True)
            self.action_theme_light.setChecked(False)
        else:
            self.action_theme_dark.setChecked(False)
            self.action_theme_light.setChecked(True)

    def capture_screenshot(self) -> None:
        directory = Path("screens")
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = directory / f"fake-ops-center-{timestamp}.png"
        image = self.grab()
        image.save(str(filename))
        self.statusBar().showMessage(f"Saved screenshot to {filename}", 5000)

    def _apply_theme_to_widgets(self, theme: Theme) -> None:
        apply_theme(self.app, theme)
        level_colors = theme.colors.get("log_levels", {})
        if isinstance(level_colors, dict):
            self.logs_panel.set_theme(level_colors)
        map_colors = {
            "grid": theme.colors.get("grid", "#444"),
            "marker_ok": theme.colors.get("marker_ok", "#50fa7b"),
            "marker_warn": theme.colors.get("marker_warn", "#f1fa8c"),
            "marker_err": theme.colors.get("marker_err", "#ff5555"),
            "bg": theme.colors.get("bg", "#0b0f1a"),
            "surface": theme.colors.get("panel_bg", "#111a32"),
            "surface_alt": theme.colors.get("control_bg", "#16223f"),
            "text": theme.colors.get("fg", "#e9ecff"),
            "muted": theme.colors.get("muted", "#7c8db5"),
            "accent": theme.colors.get("accent", "#7dd3fc"),
        }
        self.map_panel.set_colors(map_colors)
        severity_colors = {
            "low": map_colors["marker_ok"],
            "medium": map_colors["marker_warn"],
            "high": map_colors["marker_err"],
            "critical": map_colors["marker_err"],
        }
        status_colors = {
            "new": theme.colors.get("accent", "#8be9fd"),
            "acknowledged": theme.colors.get("warn", "#f1fa8c"),
            "in_progress": theme.colors.get("err", "#ff5555"),
            "resolved": map_colors["marker_ok"],
        }
        self.overview_panel.set_theme_colors(severity_colors, status_colors)
        self.timeline_panel.set_theme_colors(severity_colors)
        self.risk_panel.set_theme_colors(severity_colors, map_colors["accent"])

    def _toggle_fullscreen(self, enabled: bool) -> None:
        if enabled:
            self.showFullScreen()
        else:
            self.showNormal()

    def event(self, event: QEvent) -> bool:  # noqa: D401
        if event.type() == QEvent.Type.Resize:
            self.alerts.setGeometry(self.rect())
        return super().event(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.feeds.stop()
        event.accept()


__all__ = ["MainWindow"]
