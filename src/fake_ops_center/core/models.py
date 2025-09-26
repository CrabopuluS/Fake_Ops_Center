"""Domain models for Fake Ops Center."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


class IncidentStatus(str, enum.Enum):
    """Lifecycle states for incidents."""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class IncidentSeverity(str, enum.Enum):
    """Supported severity levels."""

    LOW = "low"
    MEDIUM = "med"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class Incident:
    """Representation of an operational incident."""

    identifier: str
    timestamp: datetime
    category: str
    severity: IncidentSeverity
    status: IncidentStatus
    region: str
    acknowledged: bool = False
    description: str | None = None
    last_update: datetime = field(default_factory=lambda: datetime.now(UTC))
    autoresolve_after: float | None = None
    location: tuple[int, int] | None = None

    def advance_status(self) -> None:
        """Advance the incident status along the lifecycle."""

        if self.status is IncidentStatus.NEW:
            self.status = IncidentStatus.ACKNOWLEDGED
            self.acknowledged = True
        elif self.status is IncidentStatus.ACKNOWLEDGED:
            self.status = IncidentStatus.IN_PROGRESS
        elif self.status is IncidentStatus.IN_PROGRESS:
            self.status = IncidentStatus.RESOLVED
        self.last_update = datetime.now(UTC)

    def can_autoresolve(self) -> bool:
        """Return whether the incident should auto-resolve."""

        if self.autoresolve_after is None:
            return False
        elapsed = (datetime.now(UTC) - self.last_update).total_seconds()
        return elapsed >= self.autoresolve_after


LogLevel = Literal["INFO", "WARN", "ERROR"]


@dataclass(slots=True)
class LogRecord:
    """Structured log message."""

    timestamp: float
    level: LogLevel
    message: str
    incident_id: str | None = None

    def iso_time(self) -> str:
        """Return an ISO formatted timestamp string."""

        return datetime.utcfromtimestamp(self.timestamp).isoformat(timespec="seconds")


@dataclass(slots=True)
class MetricSample:
    """CPU and memory utilisation snapshot."""

    timestamp: float
    cpu_percent: float
    memory_percent: float


@dataclass(slots=True)
class MetricsBuffer:
    """Time-series storage for metric samples."""

    max_age: float
    samples: list[MetricSample] = field(default_factory=list)

    def add(self, sample: MetricSample) -> None:
        """Add a new sample and prune anything older than the window."""

        self.samples.append(sample)
        cutoff = sample.timestamp - self.max_age
        self.samples = [s for s in self.samples if s.timestamp >= cutoff]

    def as_series(self) -> tuple[list[float], list[float], list[float]]:
        """Return times and series for cpu/memory usage."""

        times = [s.timestamp for s in self.samples]
        cpu = [s.cpu_percent for s in self.samples]
        mem = [s.memory_percent for s in self.samples]
        return times, cpu, mem


def utc_timestamp() -> float:
    """Return the current UTC timestamp."""

    return time.time()
