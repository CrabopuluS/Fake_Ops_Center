"""Incidents table panel."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..core.models import Incident, IncidentSeverity, IncidentStatus


@dataclass
class IncidentRow:
    """Row representation for the table."""

    incident: Incident


_COLUMNS = ["ID", "Timestamp", "Type", "Severity", "Status", "Region"]


class IncidentTableModel(QAbstractTableModel):
    """Model exposing incidents to the view."""

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[IncidentRow] = []

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return len(_COLUMNS)

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ):  # noqa: N802
        if not index.isValid():
            return None
        row = self._rows[index.row()].incident
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if column == 0:
                return row.identifier
            if column == 1:
                return row.timestamp.strftime("%H:%M:%S")
            if column == 2:
                return row.category
            if column == 3:
                severity = row.severity
                if isinstance(severity, IncidentSeverity):
                    return severity.value
                return str(severity)
            if column == 4:
                status = row.status
                if isinstance(status, IncidentStatus):
                    return status.value
                return str(status)
            if column == 5:
                return row.region
        if role == Qt.ItemDataRole.UserRole:
            return row
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return _COLUMNS[section]
        return str(section)

    def upsert(self, incident: Incident) -> None:
        """Insert or update *incident*."""

        for idx, row in enumerate(self._rows):
            if row.incident.identifier == incident.identifier:
                self._rows[idx] = IncidentRow(incident)
                self.dataChanged.emit(
                    self.index(idx, 0), self.index(idx, self.columnCount() - 1)
                )
                return
        self.beginInsertRows(QModelIndex(), len(self._rows), len(self._rows))
        self._rows.append(IncidentRow(incident))
        self.endInsertRows()

    def incidents(self) -> Iterable[Incident]:
        return (row.incident for row in self._rows)

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()


class IncidentsPanel(QDockWidget):
    """Dockable incidents view with filters."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Incidents", parent)
        self.setObjectName("incidentsPanel")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.toolbar = QToolBar("Incidents")
        self.action_ack = QAction("Acknowledge", self)
        self.action_resolve = QAction("Resolve", self)
        self.toolbar.addAction(self.action_ack)
        self.toolbar.addAction(self.action_resolve)
        layout.addWidget(self.toolbar)

        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 0, 8, 0)
        controls_layout.addWidget(QLabel("Severity:"))
        self.filter_severity = QComboBox()
        self.filter_severity.addItem("All", None)
        for severity in IncidentSeverity:
            self.filter_severity.addItem(severity.value, severity)
        controls_layout.addWidget(self.filter_severity)
        controls_layout.addWidget(QLabel("Status:"))
        self.filter_status = QComboBox()
        self.filter_status.addItem("All", None)
        for status in IncidentStatus:
            self.filter_status.addItem(status.value, status)
        controls_layout.addWidget(self.filter_status)
        controls_layout.addStretch()
        layout.addWidget(controls)

        self.table = QTableView()
        self.model = IncidentTableModel()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.filter_severity.currentIndexChanged.connect(self._apply_filters)
        self.filter_status.currentIndexChanged.connect(self._apply_filters)
        self.action_ack.triggered.connect(self.acknowledge_selected)
        self.action_resolve.triggered.connect(self.resolve_selected)

        container.setLayout(layout)
        self.setWidget(container)

    def add_incident(self, incident: Incident) -> None:
        """Add or update an incident."""

        self.model.upsert(incident)
        self._apply_filters()

    def clear(self) -> None:
        self.model.clear()
        self.table.viewport().update()

    def _apply_filters(self) -> None:
        severity = self.filter_severity.currentData()
        status = self.filter_status.currentData()
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 0)
            incident_row = self.model.data(index, Qt.ItemDataRole.UserRole)
            visible = True
            if severity and incident_row.incident.severity != severity:
                visible = False
            if status and incident_row.incident.status != status:
                visible = False
            self.table.setRowHidden(row, not visible)

    def _selected_incident(self) -> Incident | None:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return None
        row = selection[0].row()
        index = self.model.index(row, 0)
        row_data: IncidentRow = self.model.data(index, Qt.ItemDataRole.UserRole)
        return row_data.incident

    def acknowledge_selected(self) -> None:
        incident = self._selected_incident()
        if incident:
            incident.acknowledged = True
            if incident.status is IncidentStatus.NEW:
                incident.status = IncidentStatus.ACKNOWLEDGED
            self.model.upsert(incident)

    def resolve_selected(self) -> None:
        incident = self._selected_incident()
        if incident:
            incident.status = IncidentStatus.RESOLVED
            self.model.upsert(incident)


__all__ = ["IncidentsPanel"]
