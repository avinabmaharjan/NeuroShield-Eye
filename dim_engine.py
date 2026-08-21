"""
dim_engine.py - Software screen dimming overlay for NeuroShield Eye.

Creates a black semi-transparent overlay per monitor to dim the screen
below the hardware minimum brightness. Independent of the blue light filter.
Click-through, always-on-top, zero interaction footprint.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPaintEvent
from PyQt6.QtWidgets import QApplication, QWidget

from utils.logger import get_logger

log = get_logger("dim_engine")


class _DimWidget(QWidget):
    """Single-monitor transparent black dimming overlay."""

    def __init__(self, geometry, opacity: float) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._opacity = opacity
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        self.setGeometry(geometry)

    def set_opacity(self, opacity: float) -> None:
        self._opacity = max(0.0, min(opacity, 0.9))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        alpha = int(self._opacity * 255)
        color = QColor(0, 0, 0, alpha)
        painter = QPainter(self)
        painter.fillRect(self.rect(), color)
        painter.end()


class DimEngine:
    """
    Manages software dimming overlays across all monitors.

    Usage:
        dim = DimEngine()
        dim.set_opacity(0.4)   # 0.0 = no dim, 0.9 = very dark
        dim.show()
        dim.hide()
    """

    def __init__(self) -> None:
        self._widgets: list[_DimWidget] = []
        self._opacity: float = 0.0
        self._visible: bool = False
        log.info("DimEngine initialized.")

    def show(self) -> None:
        self._ensure_widgets()
        for w in self._widgets:
            w.show()
            w.raise_()
        self._visible = True
        log.debug("Dim overlays shown (opacity=%.2f, monitors=%d).",
                  self._opacity, len(self._widgets))

    def hide(self) -> None:
        for w in self._widgets:
            w.hide()
        self._visible = False
        log.debug("Dim overlays hidden.")

    def toggle(self) -> bool:
        if self._visible:
            self.hide()
        else:
            self.show()
        return self._visible

    def is_visible(self) -> bool:
        return self._visible

    def set_opacity(self, opacity: float) -> None:
        """Adjust dim level (0.0 = transparent, 0.9 = near black)."""
        self._opacity = max(0.0, min(opacity, 0.9))
        for w in self._widgets:
            w.set_opacity(self._opacity)
        log.debug("Dim opacity → %.2f", self._opacity)

    def refresh_monitors(self) -> None:
        was_visible = self._visible
        self._destroy_widgets()
        if was_visible:
            self.show()

    def _ensure_widgets(self) -> None:
        if self._widgets:
            return
        app = QApplication.instance()
        if app is None:
            return
        for screen in app.screens():
            w = _DimWidget(screen.geometry(), self._opacity)
            self._widgets.append(w)
            log.debug("Dim widget created for screen '%s'.", screen.name())

    def _destroy_widgets(self) -> None:
        for w in self._widgets:
            w.hide()
            w.deleteLater()
        self._widgets.clear()
        self._visible = False
