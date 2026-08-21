"""
focus_mode.py - Focus mode for NeuroShield Eye.

Uses Windows accessibility APIs (pywin32) to detect the currently focused
window and dims all other top-level windows by placing a per-monitor
semi-transparent overlay below them. Since overlaying individual windows
reliably requires hooking into WinEvent (which is complex), this module
uses a practical, stable approach:

  1. A polling QTimer samples the foreground window every 500ms.
  2. When a new foreground HWND is detected, a dim overlay covers all
     monitors EXCEPT the monitor containing the active window.
  3. Optional grayscale mode: applies a color matrix overlay to simulate
     desaturation (using a gray-tinted full-screen overlay at low opacity).

This approach is safe, low-CPU, and doesn't require admin privileges.
"""

import ctypes
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QApplication, QWidget

from utils.logger import get_logger

log = get_logger("focus_mode")

user32 = ctypes.windll.user32


def _get_foreground_monitor_index() -> int:
    """
    Return the QScreen index (into QApplication.screens()) that contains
    the current foreground window. Falls back to 0 if detection fails.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return 0

    # MONITORINFO struct
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

    MONITOR_DEFAULTTONEAREST = 0x00000002
    hmon = ctypes.windll.user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)

    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info))

    app = QApplication.instance()
    if app is None:
        return 0

    active_rect = info.rcMonitor
    for idx, screen in enumerate(app.screens()):
        sg = screen.geometry()
        if (sg.left() == active_rect.left and sg.top() == active_rect.top):
            return idx
    return 0


class _FocusDimWidget(QWidget):
    """Dim overlay covering one monitor."""

    def __init__(self, geometry, opacity: float, grayscale: bool) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._opacity = opacity
        self._grayscale = grayscale
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        self.setGeometry(geometry)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        if self._grayscale:
            # Semi-transparent gray to simulate desaturation
            color = QColor(128, 128, 128, int(self._opacity * 200))
        else:
            color = QColor(0, 0, 0, int(self._opacity * 255))
        painter.fillRect(self.rect(), color)
        painter.end()

    def set_params(self, opacity: float, grayscale: bool) -> None:
        self._opacity = opacity
        self._grayscale = grayscale
        self.update()


class FocusMode(QObject):
    """
    Focus mode manager. Dims non-active monitors when enabled.

    Polls the foreground window every 500ms (negligible CPU cost).
    """

    def __init__(self, settings) -> None:
        super().__init__()
        self._settings = settings
        self._enabled: bool = False
        self._widgets: list[_FocusDimWidget] = []
        self._last_active_idx: int = -1

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll)

        log.info("FocusMode initialized.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enable(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        self._ensure_widgets()
        self._poll_timer.start()
        log.info("Focus mode enabled.")

    def disable(self) -> None:
        self._enabled = False
        self._poll_timer.stop()
        self._hide_all()
        log.info("Focus mode disabled.")

    def toggle(self) -> bool:
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    def is_enabled(self) -> bool:
        return self._enabled

    def refresh_monitors(self) -> None:
        was_enabled = self._enabled
        self.disable()
        self._destroy_widgets()
        if was_enabled:
            self.enable()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        """Sample foreground window and update dim state."""
        try:
            active_idx = _get_foreground_monitor_index()
        except Exception as e:
            log.warning("Focus poll error: %s", e)
            return

        if active_idx == self._last_active_idx:
            return  # No change, skip repaint

        self._last_active_idx = active_idx
        opacity = self._settings.get("focus_mode", "dim_opacity", 0.6)
        grayscale = self._settings.get("focus_mode", "grayscale", False)

        for idx, widget in enumerate(self._widgets):
            if idx == active_idx:
                widget.hide()
            else:
                widget.set_params(opacity, grayscale)
                widget.show()
                widget.raise_()

    def _ensure_widgets(self) -> None:
        if self._widgets:
            return
        app = QApplication.instance()
        if app is None:
            return
        opacity = self._settings.get("focus_mode", "dim_opacity", 0.6)
        grayscale = self._settings.get("focus_mode", "grayscale", False)
        for screen in app.screens():
            w = _FocusDimWidget(screen.geometry(), opacity, grayscale)
            self._widgets.append(w)

    def _hide_all(self) -> None:
        for w in self._widgets:
            w.hide()
        self._last_active_idx = -1

    def _destroy_widgets(self) -> None:
        for w in self._widgets:
            w.hide()
            w.deleteLater()
        self._widgets.clear()
