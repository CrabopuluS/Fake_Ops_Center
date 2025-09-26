"""Toast-style notifications for the Fake Ops Center."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


@dataclass
class Alert:
    """Description of a transient alert."""

    message: str
    created_at: datetime
    duration: float = 5.0


class AlertWidget(QWidget):
    """Widget implementing a toast notification."""

    def __init__(self, alert: Alert, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setWindowOpacity(0.0)
        self.setStyleSheet(
            """
            background-color: rgba(0, 0, 0, 190);
            color: #ffffff;
            border-radius: 6px;
            padding: 10px 18px;
            font-weight: 600;
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        label = QLabel(alert.message)
        font = QFont()
        font.setPointSize(10)
        label.setFont(font)
        label.setWordWrap(True)
        layout.addWidget(label)
        self._fade = QPropertyAnimation(self, b"windowOpacity", duration=250)
        self._fade.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def show_with_fade(self, timeout: float) -> None:
        """Show the toast with fade in/out."""

        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        super().show()
        loop = asyncio.get_event_loop()
        loop.create_task(self._auto_close(timeout))

    async def _auto_close(self, timeout: float) -> None:
        await asyncio.sleep(timeout)
        self._fade.stop()
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.start()
        await asyncio.sleep(self._fade.duration() / 1000)
        self.close()


class AlertsOverlay(QWidget):
    """Overlay widget that manages toast notifications."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._alerts: deque[Alert] = deque()
        self._active: list[AlertWidget] = []

    def queue(self, message: str, duration: float = 5.0) -> None:
        """Queue a new alert."""

        self._alerts.append(
            Alert(message=message, created_at=datetime.utcnow(), duration=duration)
        )
        asyncio.get_event_loop().create_task(self._dequeue())

    async def _dequeue(self) -> None:
        if not self._alerts:
            return
        alert = self._alerts.popleft()
        toast = AlertWidget(alert, parent=self.parentWidget())
        geometry = self._toast_geometry(len(self._active))
        toast.setGeometry(geometry)
        toast.show_with_fade(alert.duration)
        self._active.append(toast)
        await asyncio.sleep(alert.duration + 0.5)
        self._active.remove(toast)

    def _toast_geometry(self, index: int) -> QRect:
        parent = self.parentWidget()
        if parent is None:
            return QRect(0, 0, 320, 60)
        margin = 24
        width = 320
        height = 60
        x = parent.width() - width - margin
        y = parent.height() - (height + 12) * (index + 1) - margin
        return QRect(x, y, width, height)


__all__ = ["AlertsOverlay"]
