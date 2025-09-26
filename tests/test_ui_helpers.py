"""Unit tests for lightweight UI helper utilities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from importlib import util
from pathlib import Path
from types import ModuleType

import pytest

pytest.importorskip("PySide6", reason="PySide6 is required for UI helper tests")
pytest.importorskip(
    "pyqtgraph",
    reason="pyqtgraph is required for UI helper tests",
    exc_type=ImportError,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = PROJECT_ROOT / "src" / "fake_ops_center" / "ui"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to import module {name} from {path}")
    module = util.module_from_spec(spec)
    loader = spec.loader
    loader.exec_module(module)  # type: ignore[call-arg]
    return module


panel_risk = _load_module("panel_risk", UI_DIR / "panel_risk.py")
panel_timeline = _load_module("panel_timeline", UI_DIR / "panel_timeline.py")

sanitize_region_name = getattr(panel_risk, "sanitize_region_name")
ensure_timestamp = getattr(panel_timeline, "ensure_timestamp")


def test_sanitize_region_name_filters_invalid_characters() -> None:
    assert sanitize_region_name("us-east") == "us-east"
    assert sanitize_region_name("  ../etc/passwd  ") == "unknown"


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, "unknown"),
        ("", "unknown"),
        ("   ", "unknown"),
        ("EU-Central", "eu-central"),
    ],
)
def test_sanitize_region_name_variants(value: str | None, expected: str) -> None:
    assert sanitize_region_name(value) == expected


def test_ensure_timestamp_generates_timezone_aware_value() -> None:
    now = ensure_timestamp(None)
    assert now.tzinfo is UTC


def test_ensure_timestamp_preserves_timezone() -> None:
    aware = datetime.now(timezone(timedelta(hours=3)))
    ensured = ensure_timestamp(aware)
    assert ensured.tzinfo == aware.tzinfo


def test_ensure_timestamp_promotes_naive_datetime() -> None:
    naive = datetime(2024, 4, 5, 12, 30, 0)
    ensured = ensure_timestamp(naive)
    assert ensured.tzinfo is UTC
