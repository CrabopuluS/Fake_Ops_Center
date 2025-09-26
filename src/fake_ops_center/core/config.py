"""Configuration loading and validation for Fake Ops Center."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class WindowConfig(BaseModel):
    """Window placement and sizing options."""

    fullscreen: bool = False
    size: tuple[int, int] = Field(default=(1600, 900), min_length=2, max_length=2)

    @field_validator("size")
    @classmethod
    def _validate_size(cls, value: tuple[int, int]) -> tuple[int, int]:
        width, height = value
        if width < 640 or height < 480:
            raise ValueError("window size must be at least 640x480")
        return value


class FeedConfig(BaseModel):
    """Timing parameters for synthetic data feeds."""

    metrics_hz: float = Field(default=10.0, gt=0)
    logs_per_sec: float = Field(default=6.0, gt=0)
    incidents_per_min: float = Field(default=8.0, gt=0)
    incident_autoresolve_sec: tuple[int, int] = Field(
        default=(30, 120), min_length=2, max_length=2
    )

    @field_validator("incident_autoresolve_sec")
    @classmethod
    def _validate_autoresolve(cls, value: tuple[int, int]) -> tuple[int, int]:
        low, high = value
        if low <= 0 or high <= 0:
            raise ValueError("autoresolve bounds must be positive")
        if low >= high:
            raise ValueError("autoresolve lower bound must be less than upper bound")
        return value


class BufferConfig(BaseModel):
    """Buffer limits for rolling datasets."""

    metrics_seconds: int = Field(default=120, gt=0)
    max_logs: int = Field(default=1000, gt=0)
    max_incidents: int = Field(default=200, gt=0)


class MapConfig(BaseModel):
    """Synthetic map configuration parameters."""

    grid: tuple[int, int] = Field(default=(20, 12), min_length=2, max_length=2)
    hotspot_prob: float = Field(default=0.15, ge=0, le=1)
    max_markers: int = Field(default=40, gt=0)

    @field_validator("grid")
    @classmethod
    def _validate_grid(cls, value: tuple[int, int]) -> tuple[int, int]:
        width, height = value
        if width <= 1 or height <= 1:
            raise ValueError("map grid must be at least 2x2")
        return value


class Config(BaseModel):
    """Top-level application configuration."""

    theme: str = "themes/dark.yaml"
    window: WindowConfig = Field(default_factory=WindowConfig)
    feeds: FeedConfig = Field(default_factory=FeedConfig)
    buffers: BufferConfig = Field(default_factory=BufferConfig)
    map: MapConfig = Field(default_factory=MapConfig)

    def resolve_theme_path(self, base_dir: Path) -> Path:
        """Return the absolute path to the configured theme file."""

        theme_path = Path(self.theme)
        if not theme_path.is_absolute():
            theme_path = base_dir / theme_path
        return theme_path


class ConfigError(RuntimeError):
    """Raised when configuration loading fails."""


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file into a dictionary."""

    try:
        with path.open("r", encoding="utf8") as handle:
            data = yaml.safe_load(handle) or {}
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"failed to parse YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("configuration root must be a mapping")
    return data


def load_config(path: str | Path) -> Config:
    """Load and validate the configuration at *path*."""

    config_path = Path(path)
    data = _load_yaml(config_path)
    try:
        config = Config.model_validate(data)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    return config


__all__ = ["Config", "ConfigError", "load_config"]
