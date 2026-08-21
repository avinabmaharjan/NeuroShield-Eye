"""
focus_mode.py - ADHD visual-anchor focus mode.

Dims the entire desktop except a hole cut around the foreground window,
so only the active task stays bright. Click-through overlay, 250ms poll.

On Windows this uses GetForegroundWindow + GetWindowRect.
Elsewhere it falls back to dimming non-primary screens.
"""

from __future__ import annotations

import ctypes
from typing import Optional

from PyQt6.QtCore import QObject, QRect, QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent, QRegion
from PyQt6.QtWidgets import QApplication, QWidget

from logger import get_logger

log = get_logger("focus_mode")

try:
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    _HAS_WIN32 = True
except (AttributeError, OSError):
    user32 = None
    _HAS_WIN32 = False


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _foreground_rect() -> Optional[tuple[int, int, int, int]]:
    """Screen-coordinate rect of the foreground window, or None."""
    if not _HAS_WIN32 or user32 is None:
        return None
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    if rect.right - rect.left < 40 or rect.bottom - rect.top < 40:
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)


class _FocusDimWidget(QWidget):
    """Full-monitor dimmer with an optional hole for the active window."""

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
            color = QColor(128, 128, 128, int(self._opacity * 200))
        else:
            color = QColor(0, 0, 0, int(self._opacity * 255))
        painter.fillRect(self.rect(), color)
        painter.end()

    def set_params(self, opacity: float, grayscale: bool) -> None:
        self._opacity = opacity
        self._grayscale = grayscale
        self.update()

    def set_hole(self, screen_rect: Optional[tuple[int, int, int, int]]) -> None:
        full = QRegion(self.rect())
        if not screen_rect:
            self.clearMask()
            return
        geo = self.geometry()
        left, top, right, bottom = screen_rect
        pad = 6
        hole = QRect(
            left - geo.x() - pad,
            top - geo.y() - pad,
            (right - left) + pad * 2,
            (bottom - top) + pad * 2,
        )
        local = QRegion(self.rect())
        cut = local.intersected(QRegion(hole))
        if cut.isEmpty():
            self.clearMask()
            return
        self.setMask(full.subtracted(QRegion(hole)))


class FocusMode(QObject):
    """Visual-anchor manager. Dims everything except the active window."""

    def __init__(self, settings) -> None:
        super().__init__()
        self._settings = settings
        self._enabled: bool = False
        self._widgets: list[_FocusDimWidget] = []
        self._last_rect: Optional[tuple[int, int, int, int]] = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(250)
        self._poll_timer.timeout.connect(self._poll)
        log.info("FocusMode initialized (win32=%s).", _HAS_WIN32)

    def enable(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        self._ensure_widgets()
        self._last_rect = None
        self._poll_timer.start()
        self._poll()
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

    def update_params(self, opacity: float, grayscale: bool) -> None:
        for w in self._widgets:
            w.set_params(opacity, grayscale)

    def refresh_monitors(self) -> None:
        was_enabled = self._enabled
        self.disable()
        self._destroy_widgets()
        if was_enabled:
            self.enable()

    def _poll(self) -> None:
        if not self._enabled:
            return
        opacity = self._settings.get("focus_mode", "dim_opacity", 0.6)
        grayscale = self._settings.get("focus_mode", "grayscale", False)
        rect = _foreground_rect()

        if not _HAS_WIN32:
            # Fallback: dim every screen except the primary.
            app = QApplication.instance()
            primary = app.primaryScreen() if app else None
            for widget in self._widgets:
                widget.set_params(opacity, grayscale)
                if primary and widget.geometry() == primary.geometry():
                    widget.hide()
                else:
                    widget.show()
                    widget.raise_()
            return

        if rect == self._last_rect:
            return
        self._last_rect = rect

        for widget in self._widgets:
            widget.set_params(opacity, grayscale)
            widget.set_hole(rect)
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
            w.clearMask()
        self._last_rect = None

    def _destroy_widgets(self) -> None:
        for w in self._widgets:
            w.hide()
            w.deleteLater()
        self._widgets.clear()
