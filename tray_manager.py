"""
tray_manager.py - System tray icon and context menu for NeuroShield Eye.

Manages the QSystemTrayIcon lifecycle and exposes a signals interface
so the AppController can respond to menu actions without coupling
tray logic to business logic.

Signals:
    action_blue_light_toggled()
    action_break_now()
    action_focus_toggled()
    action_open_dashboard()
    action_open_settings()
    action_exit()
"""

import os
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QColor, QPixmap, QPainter
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from utils.logger import get_logger

log = get_logger("tray_manager")


def _make_fallback_icon(size: int = 32) -> QIcon:
    """
    Generate a simple colored circle icon programmatically.
    Used when the .ico file is missing (development mode, CI, etc.).
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#58a6ff"))
    painter.setPen(QColor("#1f6feb"))
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.setBrush(QColor("#e6edf3"))
    painter.setPen(QColor("#e6edf3"))
    # Draw a simple eye shape
    eye_w = size // 3
    eye_h = size // 5
    cx = size // 2
    cy = size // 2
    painter.drawEllipse(cx - eye_w // 2, cy - eye_h // 2, eye_w, eye_h)
    painter.end()
    return QIcon(pixmap)


def _load_icon() -> QIcon:
    """Load tray_icon.ico from assets/, falling back to generated icon."""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent.parent / "assets" / "tray_icon.ico",
        Path(os.environ.get("_MEIPASS", "")) / "assets" / "tray_icon.ico",
    ]
    for path in candidates:
        if path.exists():
            return QIcon(str(path))
    log.warning("tray_icon.ico not found, using generated fallback icon.")
    return _make_fallback_icon()


class TrayManager(QObject):
    """
    System tray icon manager.

    Instantiate once and call setup() after QApplication is created.
    """

    # Signals emitted by menu actions
    action_blue_light_toggled = pyqtSignal()
    action_break_now = pyqtSignal()
    action_focus_toggled = pyqtSignal()
    action_open_dashboard = pyqtSignal()
    action_open_settings = pyqtSignal()
    action_exit = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._tray: Optional[QSystemTrayIcon] = None
        self._blue_light_enabled: bool = True
        self._focus_enabled: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Create and show the tray icon. Must be called after QApplication."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.error("System tray not available on this system.")
            return

        self._tray = QSystemTrayIcon(_load_icon())
        self._tray.setToolTip("NeuroShield Eye — Eye Protection Active")
        self._tray.setContextMenu(self._build_menu())
        self._tray.activated.connect(self._on_activated)
        self._tray.show()
        log.info("System tray icon shown.")

    def show_notification(self, title: str, message: str, duration_ms: int = 3000) -> None:
        """Show a tray balloon/notification message."""
        if self._tray and self._tray.isVisible():
            self._tray.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                duration_ms,
            )

    def update_blue_light_state(self, enabled: bool) -> None:
        """Update the menu item label to reflect current filter state."""
        self._blue_light_enabled = enabled
        self._rebuild_menu()

    def update_focus_state(self, enabled: bool) -> None:
        self._focus_enabled = enabled
        self._rebuild_menu()

    def hide(self) -> None:
        if self._tray:
            self._tray.hide()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _build_menu(self) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px 0;
                font-family: 'Segoe UI';
                font-size: 11px;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background-color: #21262d; }
            QMenu::separator { height: 1px; background: #30363d; margin: 4px 8px; }
        """)

        bl_text = "✅ Blue Light Filter ON" if self._blue_light_enabled else "⬜ Blue Light Filter OFF"
        bl_action = menu.addAction(bl_text)
        bl_action.triggered.connect(self.action_blue_light_toggled.emit)

        focus_text = "🎯 Focus Mode: ON" if self._focus_enabled else "🎯 Focus Mode: OFF"
        focus_action = menu.addAction(focus_text)
        focus_action.triggered.connect(self.action_focus_toggled.emit)

        menu.addSeparator()

        break_action = menu.addAction("⏱ Start Break Now")
        break_action.triggered.connect(self.action_break_now.emit)

        menu.addSeparator()

        dashboard_action = menu.addAction("📊 Open Dashboard")
        dashboard_action.triggered.connect(self.action_open_dashboard.emit)

        settings_action = menu.addAction("⚙ Settings")
        settings_action.triggered.connect(self.action_open_settings.emit)

        menu.addSeparator()

        exit_action = menu.addAction("✕  Exit")
        exit_action.triggered.connect(self.action_exit.emit)

        return menu

    def _rebuild_menu(self) -> None:
        """Recreate and reassign context menu (required to update action labels)."""
        if self._tray:
            old_menu = self._tray.contextMenu()
            new_menu = self._build_menu()
            self._tray.setContextMenu(new_menu)
            if old_menu:
                old_menu.deleteLater()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon click/double-click."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.action_open_dashboard.emit()
