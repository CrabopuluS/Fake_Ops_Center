"""Theme loading utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass
class Theme:
    """Representation of a UI theme."""

    name: str
    colors: dict[str, str]

    def color(self, key: str, fallback: str = "#ffffff") -> QColor:
        """Return a QColor for *key* with fallback."""

        return QColor(self.colors.get(key, fallback))

    def palette(self) -> QPalette:
        """Return a palette configured for the theme."""

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, self.color("bg"))
        palette.setColor(QPalette.ColorRole.WindowText, self.color("fg"))
        palette.setColor(QPalette.ColorRole.Base, self.color("panel_bg"))
        palette.setColor(QPalette.ColorRole.AlternateBase, self.color("bg"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, self.color("panel_bg"))
        palette.setColor(QPalette.ColorRole.ToolTipText, self.color("fg"))
        palette.setColor(QPalette.ColorRole.Text, self.color("fg"))
        palette.setColor(QPalette.ColorRole.Button, self.color("panel_bg"))
        palette.setColor(QPalette.ColorRole.ButtonText, self.color("fg"))
        palette.setColor(QPalette.ColorRole.Highlight, self.color("accent"))
        palette.setColor(QPalette.ColorRole.HighlightedText, self.color("bg"))
        return palette


class ThemeError(RuntimeError):
    """Raised when theme parsing fails."""


def load_theme(path: str | Path) -> Theme:
    """Load a theme description from YAML."""

    theme_path = Path(path)
    try:
        with theme_path.open("r", encoding="utf8") as handle:
            data = yaml.safe_load(handle) or {}
    except FileNotFoundError as exc:
        raise ThemeError(f"theme file not found: {theme_path}") from exc
    except yaml.YAMLError as exc:
        raise ThemeError(f"failed to parse theme: {exc}") from exc
    if not isinstance(data, dict):
        raise ThemeError("theme file must contain a mapping")
    name = data.get("name", theme_path.stem.title())
    colors = {
        key: str(value) for key, value in data.items() if isinstance(value, str | int)
    }
    return Theme(name=name, colors=colors)


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Apply *theme* palette and style to *app*."""

    app.setPalette(theme.palette())
    colors = theme.colors
    bg = colors.get("bg", "#0f111a")
    fg = colors.get("fg", "#f5f7ff")
    panel_bg = colors.get("panel_bg", "#161c2e")
    panel_border = colors.get("panel_border", "#1f2d4d")
    panel_shadow = colors.get("panel_shadow", "#020409")
    control_bg = colors.get("control_bg", "#1a253f")
    control_hover = colors.get("control_hover", "#24345a")
    accent = colors.get("accent", "#7dd3fc")
    accent_alt = colors.get("accent_alt", accent)
    accent_soft = colors.get("accent_soft", "#203b5f")
    muted = colors.get("muted", "#7c8db5")
    header_bg = colors.get("header_bg", control_bg)
    highlight = colors.get("highlight", accent)

    app.setStyleSheet(
        f"""
        QWidget {{
            background-color: {bg};
            color: {fg};
            font-family: 'Inter', 'Segoe UI', sans-serif;
            font-size: 13px;
        }}
        QMainWindow {{
            background-color: {bg};
        }}
        QDockWidget {{
            background-color: transparent;
            border: none;
        }}
        QDockWidget > QWidget {{
            background-color: {panel_bg};
            border: 1px solid {panel_border};
            border-radius: 14px;
        }}
        QDockWidget::title {{
            padding: 10px 14px;
            margin: 0px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {panel_bg}, stop:1 {control_bg});
            color: {fg};
            font-weight: 600;
            border-top-left-radius: 14px;
            border-top-right-radius: 14px;
            border: 1px solid {panel_border};
            border-bottom: 1px solid {panel_border};
        }}
        QDockWidget::close-button, QDockWidget::float-button {{
            border: none;
            background: transparent;
            padding: 0px;
            icon-size: 16px;
        }}
        QToolBar {{
            background: transparent;
            border: none;
            padding: 6px;
            spacing: 8px;
        }}
        QToolBar QToolButton {{
            background-color: {control_bg};
            border: 1px solid {panel_border};
            border-radius: 8px;
            padding: 6px 12px;
            color: {fg};
        }}
        QToolBar QToolButton:hover {{
            background-color: {accent_soft};
            border-color: {accent_alt};
            color: {fg};
        }}
        QPushButton {{
            background-color: {control_bg};
            border: 1px solid {panel_border};
            border-radius: 10px;
            padding: 6px 14px;
            color: {fg};
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {accent_soft};
            border-color: {accent_alt};
        }}
        QPushButton:pressed {{
            background-color: {accent_alt};
            color: {bg};
        }}
        QComboBox, QLineEdit, QSpinBox {{
            background-color: {control_bg};
            border: 1px solid {panel_border};
            border-radius: 10px;
            padding: 4px 10px;
            selection-background-color: {accent};
            selection-color: {bg};
        }}
        QComboBox:hover, QLineEdit:hover, QSpinBox:hover {{
            border-color: {accent_alt};
        }}
        QComboBox:focus, QLineEdit:focus, QSpinBox:focus {{
            background-color: {control_hover};
            border-color: {accent_alt};
        }}
        QComboBox::drop-down {{
            background: transparent;
            border: none;
            width: 22px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {panel_bg};
            border: 1px solid {panel_border};
            selection-background-color: {accent};
            selection-color: {bg};
        }}
        QTableView {{
            background-color: {panel_bg};
            alternate-background-color: {control_bg};
            gridline-color: {panel_border};
            border: none;
            selection-background-color: {highlight};
            selection-color: {bg};
        }}
        QHeaderView::section {{
            background-color: {header_bg};
            color: {fg};
            border: none;
            padding: 8px 12px;
            font-weight: 600;
            border-radius: 8px;
        }}
        QTableCornerButton::section {{
            background-color: {header_bg};
            border: none;
        }}
        QTreeView {{
            selection-background-color: {highlight};
            alternate-background-color: {control_bg};
        }}
        QStatusBar {{
            background-color: {panel_bg};
            border-top: 1px solid {panel_border};
        }}
        QMenuBar {{
            background: {panel_bg};
            border-bottom: 1px solid {panel_border};
        }}
        QMenuBar::item {{
            padding: 6px 12px;
            background: transparent;
        }}
        QMenuBar::item:selected {{
            background: {accent_soft};
            border-radius: 6px;
        }}
        QMenu {{
            background-color: {panel_bg};
            border: 1px solid {panel_border};
            padding: 6px;
            border-radius: 10px;
        }}
        QMenu::item {{
            padding: 6px 12px;
            border-radius: 6px;
        }}
        QMenu::item:selected {{
            background-color: {accent};
            color: {bg};
        }}
        QToolTip {{
            background-color: {panel_bg};
            border: 1px solid {accent_alt};
            color: {fg};
            padding: 6px 8px;
            border-radius: 8px;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: 10px 0px 10px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {accent_soft};
            border-radius: 6px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {accent};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 12px;
            margin: 0px 10px 0px 10px;
        }}
        QScrollBar::handle:horizontal {{
            background: {accent_soft};
            border-radius: 6px;
            min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {accent};
        }}
        QLabel[objectName="muted"] {{
            color: {muted};
        }}
        """
    )


__all__ = ["Theme", "ThemeError", "load_theme", "apply_theme"]
