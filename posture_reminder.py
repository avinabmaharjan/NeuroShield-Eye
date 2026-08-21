"""
posture_reminder.py - Non-intrusive posture reminder system.

Shows a toast-style popup in the bottom-right corner of the primary
monitor at configurable intervals. The popup auto-dismisses after 8 seconds
and never steals keyboard focus. Logs each reminder to the database.
"""

from PyQt6.QtCore import QObject, QPropertyAnimation, QTimer, Qt, QEasingCurve
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from utils.logger import get_logger

log = get_logger("posture_reminder")


class PosturePopup(QWidget):
    """
    Toast-style popup for posture reminders.
    Slides in from the bottom-right, auto-dismisses after `display_seconds`.
    """

    POPUP_WIDTH = 320
    POPUP_HEIGHT = 120

    def __init__(self, message: str, display_seconds: int = 8) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(self.POPUP_WIDTH, self.POPUP_HEIGHT)
        self._display_seconds = display_seconds
        self._build_ui(message)
        self._position_popup()
        self._auto_dismiss_timer = QTimer(self)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self.close)

    def _build_ui(self, message: str) -> None:
        self.setStyleSheet("""
            QWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header_row_widget = QWidget(self)
        header_row_widget.setStyleSheet("border: none; background: transparent;")
        from PyQt6.QtWidgets import QHBoxLayout
        header_layout = QHBoxLayout(header_row_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        icon = QLabel("🪑", header_row_widget)
        icon.setFont(QFont("Segoe UI Emoji", 16))
        icon.setStyleSheet("color: #f0883e; border: none;")
        header_layout.addWidget(icon)

        title = QLabel("Posture Check", header_row_widget)
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #e6edf3; border: none;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        close_btn = QPushButton("✕", header_row_widget)
        close_btn.setFixedSize(20, 20)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8b949e;
                border: none;
                font-size: 10px;
            }
            QPushButton:hover { color: #e6edf3; }
        """)
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)
        layout.addWidget(header_row_widget)

        msg_label = QLabel(message, self)
        msg_label.setFont(QFont("Segoe UI", 9))
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("color: #8b949e; border: none; background: transparent;")
        layout.addWidget(msg_label)

    def _position_popup(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        screen = app.primaryScreen()
        if screen is None:
            return
        geom = screen.availableGeometry()
        x = geom.right() - self.POPUP_WIDTH - 16
        y = geom.bottom() - self.POPUP_HEIGHT - 16
        self.move(x, y)

    def show_popup(self) -> None:
        self.show()
        self._auto_dismiss_timer.start(self._display_seconds * 1000)


class PostureReminder(QObject):
    """
    Schedules and shows posture reminder popups at configurable intervals.
    Reads settings on each trigger to always use the latest configuration.
    """

    def __init__(self, settings, db) -> None:
        super().__init__()
        self._settings = settings
        self._db = db
        self._enabled: bool = False
        self._popup: PosturePopup | None = None

        self._interval_timer = QTimer(self)
        self._interval_timer.timeout.connect(self._show_reminder)
        log.info("PostureReminder initialized.")

    def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        self._restart_timer()
        log.info("Posture reminder started (interval=%d min).",
                 self._settings.get("posture", "interval_minutes", 30))

    def stop(self) -> None:
        self._enabled = False
        self._interval_timer.stop()
        log.info("Posture reminder stopped.")

    def toggle(self) -> bool:
        if self._enabled:
            self.stop()
        else:
            self.start()
        return self._enabled

    def is_enabled(self) -> bool:
        return self._enabled

    def update_interval(self) -> None:
        """Call when settings change to restart timer with new interval."""
        if self._enabled:
            self._restart_timer()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _restart_timer(self) -> None:
        interval_min = self._settings.get("posture", "interval_minutes", 30)
        self._interval_timer.start(int(interval_min) * 60 * 1000)

    def _show_reminder(self) -> None:
        message = self._settings.get(
            "posture", "message",
            "Check your posture! Sit up straight and relax your shoulders."
        )
        # Close any existing popup
        if self._popup is not None:
            self._popup.close()
        self._popup = PosturePopup(message)
        self._popup.show_popup()
        self._db.record_posture_alert()
        log.debug("Posture reminder shown.")
