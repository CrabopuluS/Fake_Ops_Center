"""Metrics panel rendering CPU and memory timeseries."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QWidget

from ..core.models import MetricSample, MetricsBuffer


class MetricsPanel(QDockWidget):
    """Dockable panel displaying metrics graphs."""

    def __init__(self, buffer_seconds: int, parent: QWidget | None = None) -> None:
        super().__init__("CPU / Memory", parent)
        self.setObjectName("metricsPanel")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.buffer = MetricsBuffer(max_age=float(buffer_seconds))
        self._plot = pg.PlotWidget(title="CPU & Memory Utilisation")
        self._plot.showGrid(x=True, y=True, alpha=0.2)
        self._plot.setYRange(0, 100)
        self._plot.setLabel("bottom", "Time", units="s")
        self._plot.setLabel("left", "Percent", units="%")
        self._cpu_curve = self._plot.plot(pen=pg.mkPen("#8be9fd", width=2), name="CPU")
        self._mem_curve = self._plot.plot(
            pen=pg.mkPen("#ff79c6", width=2), name="Memory"
        )
        self.setWidget(self._plot)

    def update_metrics(self, sample: MetricSample) -> None:
        """Add *sample* to the buffer and redraw the graph."""

        self.buffer.add(sample)
        times, cpu, mem = self.buffer.as_series()
        if not times:
            return
        t0 = times[0]
        shifted = [t - t0 for t in times]
        self._cpu_curve.setData(shifted, cpu)
        self._mem_curve.setData(shifted, mem)


__all__ = ["MetricsPanel"]
