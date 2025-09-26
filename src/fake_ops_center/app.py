"""Application entry point for Fake Ops Center."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from qasync import QEventLoop

from .core.bus import EventBus
from .core.config import ConfigError, load_config
from .core.feeds import FeedsController
from .core.theme import ThemeError, load_theme
from .ui.main_window import MainWindow


def _default_config_path() -> Path:
    """Return the config file bundled with the application."""

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent.parent.parent
    return base_path / "config.yaml"


async def _launch(app: QApplication, config_path: Path) -> int:
    loop = asyncio.get_running_loop()

    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"Failed to load config: {exc}")
        app.quit()
        return 1

    theme_path = config.resolve_theme_path(config_path.parent)
    try:
        theme = load_theme(theme_path)
    except ThemeError as exc:
        print(f"Failed to load theme: {exc}")
        app.quit()
        return 1

    feeds = FeedsController(config.feeds, config.buffers, config.map)
    bus = EventBus(loop)
    window = MainWindow(app, config, theme, feeds, bus)
    window.show()

    quit_future: asyncio.Future[None] = loop.create_future()

    def _on_about_to_quit() -> None:
        if not quit_future.done():
            quit_future.set_result(None)

    app.aboutToQuit.connect(_on_about_to_quit)

    loop.create_task(window.start_simulation())
    await quit_future
    await feeds.wait()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Fake Ops Center")
    parser.add_argument(
        "--config",
        type=Path,
        default=_default_config_path(),
        help="Path to config.yaml",
    )
    args = parser.parse_args()

    config_path = args.config.expanduser().resolve(strict=False)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    try:
        exit_code = loop.run_until_complete(_launch(app, config_path))
    finally:
        loop.close()
        app.quit()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
