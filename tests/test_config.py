"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from fake_ops_center.core.config import ConfigError, load_config


def test_load_valid_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
        theme: themes/dark.yaml
        window:
          fullscreen: false
          size: [800, 600]
        """,
        encoding="utf8",
    )
    config = load_config(config_path)
    assert config.window.size == (800, 600)
    assert config.theme == "themes/dark.yaml"


def test_invalid_window_size(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
        window:
          size: [320, 200]
        """,
        encoding="utf8",
    )
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "missing.yaml")
