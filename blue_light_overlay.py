"""
blue_light_overlay.py - Fullscreen blue light filter overlay.

Creates one transparent, click-through, always-on-top QWidget per monitor.
The overlay renders a warm amber tint using QPainter with configurable
color temperature and opacity. Supports multi-monitor via QScreen enumeration.

Color temperature mapping (Kelvin → RGB tint):
  2000K → very warm amber (255, 100, 0)
  3400K → warm white  (255, 180, 80)
  5000K → neutral      (255, 230, 180)
  6500K → daylight     (255, 255, 255) — effectively transparent
"""

import math
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QApplication, QWidget

from utils.logger import get_logger

log = get_logger("blue_light_overlay")


# ---------------------------------------------------------------------------
# Color temperature → RGB conversion
# ---------------------------------------------------------------------------

def kelvin_to_rgb(kelvin: int) -> tuple[int, int, int]:
    """
    Approximate conversion from color temperature (K) to an RGB tint color.
    Uses a simplified Planckian locus approximation suitable for overlay tinting.

    Returns (R, G, B) where all values are in 0–255.
    """
    kelvin = max(1000, min(kelvin, 6500))
    # Normalize to [0, 1] where 0 = warmest (2000K), 1 = coolest (6500K)
    t = (kelvin - 2000) / 4500.0

    # Red stays at 255
    r = 255
    # Green rises from ~80 at 2000K to ~255 at 6500K
    g = int(80 + t * 175)
    # Blue rises from 0 at 2000K to ~220 at 6500K
    b = int(t * 220)

    return (r, min(g, 255), min(b, 255))


# ---------------------------------------------------------------------------
# Per-monitor overlay widget
# ---------------------------------------------------------------------------

class _OverlayWidget(QWidget):
    """
    A single fullscreen overlay window for one monitor.
    Painted with a semi-transparent warm tint color.
    WA_TransparentForMouseEvents ensures clicks pass through.
    """

    def __init__(self, geometry, color: QColor) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._color = color
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setGeometry(geometry)
        # Prevent the overlay from appearing in the taskbar
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()  # Schedule repaint

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.fillRect(self.rect(), self._color)
        painter.end()


# ---------------------------------------------------------------------------
# Public manager
# ---------------------------------------------------------------------------

class BlueLightOverlay:
    """
    Manages one _OverlayWidget per connected monitor.

    Usage:
        overlay = BlueLightOverlay()
        overlay.set_temperature(3400)
        overlay.set_opacity(0.35)
        overlay.show()
        overlay.hide()
    """

    def __init__(self) -> None:
        self._overlays: list[_OverlayWidget] = []
        self._temperature: int = 3400
        self._opacity: float = 0.35
        self._visible: bool = False
        log.info("BlueLightOverlay initialized (temperature=%dK, opacity=%.2f)",
                 self._temperature, self._opacity)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Create overlays if needed and show them on all monitors."""
        self._ensure_overlays()
        for widget in self._overlays:
            widget.show()
            widget.raise_()
        self._visible = True
        log.debug("Blue light overlays shown (%d monitors).", len(self._overlays))

    def hide(self) -> None:
        """Hide all overlay windows."""
        for widget in self._overlays:
            widget.hide()
        self._visible = False
        log.debug("Blue light overlays hidden.")

    def toggle(self) -> bool:
        """Toggle visibility. Returns True if now visible."""
        if self._visible:
            self.hide()
        else:
            self.show()
        return self._visible

    def is_visible(self) -> bool:
        return self._visible

    def set_temperature(self, kelvin: int) -> None:
        """Set color temperature (2000K–6500K) and refresh overlays."""
        self._temperature = max(2000, min(kelvin, 6500))
        self._apply_color()
        log.debug("Color temperature set to %dK", self._temperature)

    def set_opacity(self, opacity: float) -> None:
        """Set overlay opacity (0.0–0.80) and refresh overlays."""
        self._opacity = max(0.0, min(opacity, 0.80))
        self._apply_color()
        log.debug("Overlay opacity set to %.2f", self._opacity)

    def apply_settings(self, temperature: int, opacity: float) -> None:
        """Convenience method to update both settings at once."""
        self._temperature = max(2000, min(temperature, 6500))
        self._opacity = max(0.0, min(opacity, 0.80))
        self._apply_color()

    def refresh_monitors(self) -> None:
        """
        Destroy and recreate overlays to pick up monitor configuration changes.
        Should be called on QGuiApplication.screenAdded / screenRemoved signals.
        """
        was_visible = self._visible
        self._destroy_overlays()
        if was_visible:
            self.show()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_color(self) -> QColor:
        r, g, b = kelvin_to_rgb(self._temperature)
        alpha = int(self._opacity * 255)
        return QColor(r, g, b, alpha)

    def _ensure_overlays(self) -> None:
        """Create overlays if the list is empty."""
        if self._overlays:
            return
        color = self._build_color()
        app = QApplication.instance()
        if app is None:
            log.error("No QApplication instance found.")
            return
        for screen in app.screens():
            geom = screen.geometry()
            widget = _OverlayWidget(geom, color)
            self._overlays.append(widget)
            log.debug(
                "Created overlay for screen '%s' at %s",
                screen.name(), geom
            )

    def _apply_color(self) -> None:
        """Recompute the tint color and push it to all existing overlays."""
        if not self._overlays:
            return
        color = self._build_color()
        for widget in self._overlays:
            widget.set_color(color)

    def _destroy_overlays(self) -> None:
        for widget in self._overlays:
            widget.hide()
            widget.deleteLater()
        self._overlays.clear()
        self._visible = False
