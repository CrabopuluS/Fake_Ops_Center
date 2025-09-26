"""Core utilities for Fake Ops Center."""

from __future__ import annotations

from .bus import EventBus
from .config import Config, ConfigError, load_config
from .feeds import FeedsController

__all__ = ["Config", "ConfigError", "EventBus", "FeedsController", "load_config"]

try:  # pragma: no cover - optional dependency for headless tests
    from .theme import Theme, load_theme
except Exception:  # noqa: BLE001
    Theme = None  # type: ignore[assignment]
    load_theme = None  # type: ignore[assignment]
else:  # pragma: no cover
    __all__.extend(["Theme", "load_theme"])
