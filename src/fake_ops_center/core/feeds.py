"""Synthetic data feeds used by the application."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np

from .bus import EventBus
from .config import BufferConfig, FeedConfig, MapConfig
from .models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    LogRecord,
    MetricSample,
    utc_timestamp,
)

METRICS_TOPIC = "metrics"
LOG_TOPIC = "log"
INCIDENT_TOPIC = "incident"

_REGIONS = [
    "us-east",
    "us-west",
    "eu-central",
    "ap-south",
    "sa-east",
]
_INCIDENT_TYPES = [
    "network",
    "database",
    "compute",
    "storage",
    "security",
]
_LOG_MESSAGES = [
    "Scaling up worker pool",
    "Replica lag detected",
    "Background job completed",
    "Checkpoint successful",
    "Connection timeout",
    "Retrying failed task",
    "Service dependency degraded",
    "Configuration reloaded",
    "Leader election triggered",
]


@dataclass
class FeedState:
    """State shared across feeds, mainly for reproducibility."""

    seed: int
    rng: np.random.Generator = field(init=False)

    def __post_init__(self) -> None:
        self.rng = np.random.default_rng(self.seed)

    def reset(self, seed: int | None = None) -> None:
        """Reset the RNG with *seed* if provided."""

        self.rng = np.random.default_rng(self.seed if seed is None else seed)
        if seed is not None:
            self.seed = seed


class BaseFeed:
    """Base class providing lifecycle helpers for feeds."""

    topic: str

    def __init__(
        self, config: FeedConfig, buffers: BufferConfig, state: FeedState
    ) -> None:
        self.config = config
        self.buffers = buffers
        self.state = state
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self, bus: EventBus) -> None:
        """Start streaming data to *bus*."""

        if self._task and not self._task.done():
            return
        self._running = True
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run(bus))

    async def _run(self, bus: EventBus) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        """Stop the feed."""

        self._running = False
        if self._task:
            self._task.cancel()

    async def wait(self) -> None:
        """Wait for the background task to finish."""

        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def reset(self) -> None:
        """Reset feed state."""

        self.stop()


class MetricsFeed(BaseFeed):
    """Feed generating CPU and memory utilisation samples."""

    topic = METRICS_TOPIC

    def __init__(
        self, config: FeedConfig, buffers: BufferConfig, state: FeedState
    ) -> None:
        super().__init__(config, buffers, state)
        self._cpu = 55.0
        self._mem = 48.0

    def sample(self) -> MetricSample:
        """Return a new metric sample."""

        drift = self.state.rng.normal(0, 2, size=2)
        spike = self.state.rng.exponential(scale=2)
        if spike > 5:
            drift += self.state.rng.normal(10, 5, size=2)
        self._cpu = float(np.clip(self._cpu + drift[0], 1, 98))
        self._mem = float(np.clip(self._mem + drift[1], 5, 95))
        return MetricSample(
            timestamp=utc_timestamp(), cpu_percent=self._cpu, memory_percent=self._mem
        )

    async def _run(self, bus: EventBus) -> None:
        interval = 1.0 / float(self.config.metrics_hz)
        while self._running:
            sample = self.sample()
            bus.publish(self.topic, sample)
            await asyncio.sleep(interval)

    def reset(self) -> None:
        super().reset()
        self._cpu = 55.0
        self._mem = 48.0


class LogsFeed(BaseFeed):
    """Feed producing synthetic log records."""

    topic = LOG_TOPIC

    def __init__(
        self, config: FeedConfig, buffers: BufferConfig, state: FeedState
    ) -> None:
        super().__init__(config, buffers, state)
        self._levels = np.array([0.7, 0.2, 0.1])

    def sample(self) -> LogRecord:
        """Return a synthetic log record."""

        level = self.state.rng.choice(["INFO", "WARN", "ERROR"], p=self._levels)
        message = str(self.state.rng.choice(_LOG_MESSAGES))
        incident_id = None
        if level != "INFO" and self.state.rng.random() < 0.5:
            incident_id = f"I{self.state.rng.integers(100, 999)}"
        return LogRecord(
            timestamp=utc_timestamp(),
            level=level,
            message=message,
            incident_id=incident_id,
        )

    async def _run(self, bus: EventBus) -> None:
        interval = 1.0 / float(self.config.logs_per_sec)
        while self._running:
            record = self.sample()
            bus.publish(self.topic, record)
            await asyncio.sleep(interval)


class IncidentTracker:
    """Manage active incidents and their lifecycle."""

    def __init__(self) -> None:
        self.active: dict[str, Incident] = {}
        self.counter = 0

    def new_identifier(self) -> str:
        self.counter += 1
        return f"A{self.counter:04d}"

    def add(self, incident: Incident) -> None:
        self.active[incident.identifier] = incident

    def iter_active(self) -> Iterable[Incident]:
        return list(self.active.values())

    def purge(self) -> None:
        resolved = [
            key
            for key, inc in self.active.items()
            if inc.status is IncidentStatus.RESOLVED
        ]
        for key in resolved:
            self.active.pop(key, None)


class IncidentsFeed(BaseFeed):
    """Feed that generates operational incidents."""

    topic = INCIDENT_TOPIC

    def __init__(
        self,
        config: FeedConfig,
        buffers: BufferConfig,
        state: FeedState,
        map_config: MapConfig,
    ) -> None:
        super().__init__(config, buffers, state)
        self.tracker = IncidentTracker()
        self._grid_width, self._grid_height = map_config.grid

    def _make_incident(self) -> Incident:
        identifier = self.tracker.new_identifier()
        severities = list(IncidentSeverity)
        severity = severities[int(self.state.rng.integers(0, len(severities)))]
        category = str(self.state.rng.choice(_INCIDENT_TYPES))
        region = str(self.state.rng.choice(_REGIONS))
        autoresolve = float(
            self.state.rng.uniform(
                self.config.incident_autoresolve_sec[0],
                self.config.incident_autoresolve_sec[1],
            )
        )
        location = (
            int(self.state.rng.integers(0, self._grid_width)),
            int(self.state.rng.integers(0, self._grid_height)),
        )
        incident = Incident(
            identifier=identifier,
            timestamp=datetime.now(UTC),
            category=category,
            severity=severity,
            status=IncidentStatus.NEW,
            region=region,
            description=f"{category.title()} anomaly detected",
            autoresolve_after=autoresolve,
            location=location,
        )
        self.tracker.add(incident)
        return incident

    def step(self) -> list[Incident]:
        """Advance the simulation and return emitted incidents."""

        emitted: list[Incident] = []
        mean_rate = self.config.incidents_per_min / 60.0
        events = self.state.rng.poisson(mean_rate)
        for _ in range(events):
            emitted.append(self._make_incident())
        now = datetime.now(UTC)
        for incident in list(self.tracker.iter_active()):
            if incident.status is IncidentStatus.RESOLVED:
                continue
            if incident.can_autoresolve():
                incident.status = IncidentStatus.RESOLVED
                incident.last_update = now
                emitted.append(incident)
            else:
                progress_roll = self.state.rng.random()
                if (
                    incident.status in {IncidentStatus.NEW, IncidentStatus.ACKNOWLEDGED}
                    and progress_roll < 0.3
                ):
                    incident.advance_status()
                    incident.last_update = now
                    emitted.append(incident)
                elif (
                    incident.status is IncidentStatus.IN_PROGRESS and progress_roll < 0.15
                ):
                    incident.advance_status()
                    incident.last_update = now
                    emitted.append(incident)
        self.tracker.purge()
        return emitted

    async def _run(self, bus: EventBus) -> None:
        interval = 1.0
        while self._running:
            for incident in self.step():
                bus.publish(self.topic, incident)
            await asyncio.sleep(interval)

    def reset(self) -> None:
        super().reset()
        self.tracker = IncidentTracker()


class FeedsController:
    """Manage lifecycle of all feeds together."""

    def __init__(
        self,
        config: FeedConfig,
        buffers: BufferConfig,
        map_config: MapConfig,
        seed: int = 1337,
    ) -> None:
        self.state = FeedState(seed=seed)
        self.metrics = MetricsFeed(config, buffers, self.state)
        self.logs = LogsFeed(config, buffers, self.state)
        self.incidents = IncidentsFeed(config, buffers, self.state, map_config)
        self._feeds = [self.metrics, self.logs, self.incidents]

    async def start(self, bus: EventBus) -> None:
        for feed in self._feeds:
            await feed.start(bus)

    def stop(self) -> None:
        for feed in self._feeds:
            feed.stop()

    async def wait(self) -> None:
        for feed in self._feeds:
            await feed.wait()

    def reset(self, seed: int | None = None) -> None:
        self.state.reset(seed)
        for feed in self._feeds:
            feed.reset()


__all__ = [
    "FeedsController",
    "MetricsFeed",
    "LogsFeed",
    "IncidentsFeed",
    "METRICS_TOPIC",
    "LOG_TOPIC",
    "INCIDENT_TOPIC",
]
