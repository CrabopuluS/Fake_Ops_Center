"""Tests for synthetic data feeds."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from fake_ops_center.core.config import BufferConfig, FeedConfig, MapConfig
from fake_ops_center.core.feeds import FeedState, IncidentsFeed, LogsFeed, MetricsFeed
from fake_ops_center.core.models import IncidentSeverity, IncidentStatus


@pytest.fixture()
def feed_config() -> FeedConfig:
    return FeedConfig(
        metrics_hz=5,
        logs_per_sec=5,
        incidents_per_min=12,
        incident_autoresolve_sec=(5, 10),
    )


@pytest.fixture()
def buffers() -> BufferConfig:
    return BufferConfig(metrics_seconds=60, max_logs=100, max_incidents=50)


@pytest.fixture()
def map_config() -> MapConfig:
    return MapConfig(grid=(12, 8), hotspot_prob=0.2, max_markers=30)


def test_metrics_deterministic(feed_config: FeedConfig, buffers: BufferConfig) -> None:
    state_a = FeedState(seed=123)
    state_b = FeedState(seed=123)
    feed_a = MetricsFeed(feed_config, buffers, state_a)
    feed_b = MetricsFeed(feed_config, buffers, state_b)
    samples_a = [feed_a.sample() for _ in range(5)]
    samples_b = [feed_b.sample() for _ in range(5)]
    assert [(s.cpu_percent, s.memory_percent) for s in samples_a] == [
        (s.cpu_percent, s.memory_percent) for s in samples_b
    ]


def test_logs_levels(feed_config: FeedConfig, buffers: BufferConfig) -> None:
    state = FeedState(seed=321)
    feed = LogsFeed(feed_config, buffers, state)
    for _ in range(10):
        record = feed.sample()
        assert record.level in {"INFO", "WARN", "ERROR"}


def test_incident_autoresolve(
    feed_config: FeedConfig, buffers: BufferConfig, map_config: MapConfig
) -> None:
    state = FeedState(seed=999)
    feed = IncidentsFeed(feed_config, buffers, state, map_config)
    incident = feed._make_incident()  # noqa: SLF001 - internal helper is deterministic
    assert (
        feed_config.incident_autoresolve_sec[0]
        <= incident.autoresolve_after
        <= feed_config.incident_autoresolve_sec[1]
    )
    incident.last_update = datetime.now(UTC) - timedelta(
        seconds=incident.autoresolve_after + 1
    )
    feed.tracker.add(incident)
    emitted = feed.step()
    assert any(
        item.identifier == incident.identifier
        and item.status is IncidentStatus.RESOLVED
        for item in emitted
    )


def test_incident_properties(
    feed_config: FeedConfig, buffers: BufferConfig, map_config: MapConfig
) -> None:
    state = FeedState(seed=111)
    feed = IncidentsFeed(feed_config, buffers, state, map_config)
    incidents = []
    for _ in range(5):
        incidents.extend(feed.step())
    for incident in incidents:
        assert incident.severity in IncidentSeverity
        assert incident.status in IncidentStatus
        if incident.location:
            x, y = incident.location
            assert 0 <= x < map_config.grid[0]
            assert 0 <= y < map_config.grid[1]
