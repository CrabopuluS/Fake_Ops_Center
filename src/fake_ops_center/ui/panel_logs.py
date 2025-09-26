"""Logs panel providing streaming log output with search."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.models import LogRecord


class LogsPanel(QDockWidget):
    """Dockable log viewer with search support."""

    def __init__(
        self, max_logs: int, level_colors: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__("Logs", parent)
        self.setObjectName("logsPanel")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.max_logs = max_logs
        self.level_colors = {key: QColor(value) for key, value in level_colors.items()}
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 4, 8, 4)
        controls_layout.addWidget(QLabel("Search:"))
        self.input_search = QLineEdit()
        self.button_next = QPushButton("Next")
        controls_layout.addWidget(self.input_search)
        controls_layout.addWidget(self.button_next)
        layout.addWidget(controls)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self.view)

        container.setLayout(layout)
        self.setWidget(container)

        self._records: list[LogRecord] = []
        self._last_search: str | None = None

        self.input_search.returnPressed.connect(self._perform_search)
        self.button_next.clicked.connect(self._search_next)

    def append_log(self, record: LogRecord) -> None:
        """Append a log record to the view."""

        self._records.append(record)
        if len(self._records) > self.max_logs:
            self._records = self._records[-self.max_logs :]
            self.view.clear()
            for existing in self._records:
                self._append_to_widget(existing)
        else:
            self._append_to_widget(record)
        self.view.moveCursor(QTextCursor.MoveOperation.End)

    def _append_to_widget(self, record: LogRecord) -> None:
        color = self.level_colors.get(record.level, QColor("#ffffff"))
        html = (
            f'<span style="color:{color.name()};">'
            f"[{record.iso_time()}] {record.level:<5} {record.message}"
            "</span>"
        )
        if record.incident_id:
            highlight = color.lighter().name()
            html += (
                f" <span style='color:{highlight};'>"
                f"({record.incident_id})"
                "</span>"
            )
        self.view.appendHtml(html)

    def _perform_search(self) -> None:
        text = self.input_search.text().strip()
        if not text:
            return
        self._last_search = text
        self._search_from(0)

    def _search_next(self) -> None:
        if not self._last_search:
            self._perform_search()
            return
        position = self.view.textCursor().position()
        self._search_from(position)

    def _search_from(self, position: int) -> None:
        if not self._last_search:
            return
        doc = self.view.document()
        cursor = self.view.textCursor()
        cursor.setPosition(position)
        cursor = doc.find(self._last_search, cursor, Qt.CaseSensitivity.CaseInsensitive)
        if cursor.isNull():
            cursor = doc.find(
                self._last_search,
                0,
                Qt.CaseSensitivity.CaseInsensitive,
            )
        if not cursor.isNull():
            self.view.setTextCursor(cursor)

    def focus_search(self) -> None:
        self.input_search.setFocus()

    def set_theme(self, level_colors: dict[str, str]) -> None:
        self.level_colors = {key: QColor(value) for key, value in level_colors.items()}


__all__ = ["LogsPanel"]
