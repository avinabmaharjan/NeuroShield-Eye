"""
break_timer.py - Smart break timer engine for NeuroShield Eye.

Supports two modes:
  - 20-20-20: 20 min work → 20 sec break
  - Custom:   N min work → M min break

The engine runs on a QTimer (main thread) to stay Qt-native and avoid
thread synchronization complexity. Break screens are fullscreen overlays
with animated countdown. Sound notification uses winsound (stdlib).

Signals emitted:
  break_started     → show break overlay
  break_ended       → hide break overlay
  tick              → (seconds_remaining: int) for countdown UI
"""

import winsound
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt, QSize

from utils.logger import get_logger

log = get_logger("break_timer")


# ---------------------------------------------------------------------------
# Break screen overlay widget
# ---------------------------------------------------------------------------

class BreakScreen(QWidget):
    """
    Fullscreen break overlay with countdown display.
    Dismissible unless forced_break=True.
    """

    dismissed = pyqtSignal()

    def __init__(self, duration_seconds: int, forced: bool = False) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._duration = duration_seconds
        self._remaining = duration_seconds
        self._forced = forced

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._build_ui()
        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setStyleSheet("background-color: #0d1117;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)

        icon_label = QLabel("👁️", self)
        icon_label.setFont(QFont("Segoe UI Emoji", 64))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("color: #58a6ff;")
        layout.addWidget(icon_label)

        title = QLabel("Time for a Break", self)
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #e6edf3;")
        layout.addWidget(title)

        instruction = QLabel(
            "Look at something 20 feet away\nRelax your eyes and breathe.", self
        )
        instruction.setFont(QFont("Segoe UI", 14))
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction.setStyleSheet("color: #8b949e; line-height: 1.6;")
        layout.addWidget(instruction)

        self._countdown_label = QLabel(self._format_time(self._remaining), self)
        self._countdown_label.setFont(QFont("Segoe UI", 56, QFont.Weight.Bold))
        self._countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_label.setStyleSheet("color: #58a6ff;")
        layout.addWidget(self._countdown_label)

        if not self._forced:
            skip_btn = QPushButton("Skip Break", self)
            skip_btn.setFixedSize(QSize(160, 44))
            skip_btn.setFont(QFont("Segoe UI", 11))
            skip_btn.setStyleSheet("""
                QPushButton {
                    background-color: #21262d;
                    color: #8b949e;
                    border: 1px solid #30363d;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #30363d;
                    color: #e6edf3;
                }
            """)
            skip_btn.clicked.connect(self._skip)
            layout.addWidget(skip_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    # ------------------------------------------------------------------
    # Timer logic
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Show the overlay and begin countdown."""
        app = QApplication.instance()
        if app:
            # Cover primary screen
            screen = app.primaryScreen()
            if screen:
                self.setGeometry(screen.geometry())
        self.showFullScreen()
        self._ticker.start()

    def _tick(self) -> None:
        self._remaining -= 1
        self._countdown_label.setText(self._format_time(self._remaining))
        if self._remaining <= 0:
            self._ticker.stop()
            self.dismissed.emit()
            self.hide()

    def _skip(self) -> None:
        self._ticker.stop()
        self.dismissed.emit()
        self.hide()

    @staticmethod
    def _format_time(seconds: int) -> str:
        m, s = divmod(max(seconds, 0), 60)
        return f"{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Break timer engine
# ---------------------------------------------------------------------------

class BreakTimer(QObject):
    """
    Manages the work/break cycle. Emits Qt signals for UI integration.

    Signals:
        break_started()   – A break is beginning (show break screen)
        break_ended(completed: bool) – A break finished
        work_tick(seconds_remaining: int) – Seconds until next break
    """

    break_started = pyqtSignal()
    break_ended = pyqtSignal(bool)  # True = completed, False = skipped
    work_tick = pyqtSignal(int)

    def __init__(self, settings, db) -> None:
        super().__init__()
        self._settings = settings
        self._db = db

        self._work_timer = QTimer(self)
        self._work_timer.setInterval(1000)
        self._work_timer.timeout.connect(self._on_work_tick)

        self._work_seconds_remaining: int = 0
        self._current_break_screen: Optional[BreakScreen] = None
        self._current_break_id: int = 0
        self._running: bool = False

        log.info("BreakTimer initialized.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin the work countdown."""
        if self._running:
            return
        self._running = True
        self._reset_work_timer()
        self._work_timer.start()
        log.info("Break timer started (mode=%s).", self._get_mode())

    def stop(self) -> None:
        """Stop all timers and dismiss any active break screen."""
        self._running = False
        self._work_timer.stop()
        if self._current_break_screen:
            self._current_break_screen.hide()
            self._current_break_screen = None
        log.info("Break timer stopped.")

    def trigger_break_now(self) -> None:
        """Immediately start a break, resetting the work cycle."""
        if not self._running:
            self.start()
        self._work_timer.stop()
        self._start_break()

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_mode(self) -> str:
        return self._settings.get("break_timer", "mode", "20-20-20")

    def _get_work_seconds(self) -> int:
        mode = self._get_mode()
        if mode == "20-20-20":
            return self._settings.get("break_timer", "work_interval_minutes", 20) * 60
        else:
            return self._settings.get("break_timer", "custom_work_minutes", 45) * 60

    def _get_break_seconds(self) -> int:
        mode = self._get_mode()
        if mode == "20-20-20":
            return self._settings.get("break_timer", "break_duration_seconds", 20)
        else:
            return self._settings.get("break_timer", "custom_break_minutes", 5) * 60

    def _reset_work_timer(self) -> None:
        self._work_seconds_remaining = self._get_work_seconds()

    def _on_work_tick(self) -> None:
        self._work_seconds_remaining -= 1
        self.work_tick.emit(self._work_seconds_remaining)

        if self._work_seconds_remaining <= 0:
            self._work_timer.stop()
            self._start_break()

    def _start_break(self) -> None:
        forced = self._settings.get("break_timer", "forced_break", False)
        duration = self._get_break_seconds()
        break_type = self._get_mode()

        # Play sound notification
        if self._settings.get("break_timer", "sound_enabled", True):
            self._play_alert()

        # Record break start in DB
        self._current_break_id = self._db.record_break_start(break_type)

        # Show break screen
        self._current_break_screen = BreakScreen(duration, forced=forced)
        self._current_break_screen.dismissed.connect(self._on_break_dismissed)
        self._current_break_screen.start()

        self.break_started.emit()
        log.info("Break started (type=%s, duration=%ds, forced=%s)",
                 break_type, duration, forced)

    def _on_break_dismissed(self) -> None:
        """Called when BreakScreen emits dismissed (timer complete OR skipped)."""
        # Determine if completed: check remaining time in screen
        screen = self._current_break_screen
        completed = screen is not None and screen._remaining <= 0
        self._db.record_break_end(self._current_break_id, completed)
        self._current_break_screen = None
        self.break_ended.emit(completed)

        # Resume work cycle
        if self._running:
            self._reset_work_timer()
            self._work_timer.start()

        log.info("Break ended (completed=%s).", completed)

    def _play_alert(self) -> None:
        """Play the break alert sound asynchronously."""
        sound_path = self._find_sound_file()
        if sound_path and sound_path.exists():
            try:
                winsound.PlaySound(
                    str(sound_path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC,
                )
                return
            except Exception as e:
                log.warning("Could not play sound file: %s", e)
        # Fallback: system beep
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    @staticmethod
    def _find_sound_file() -> Optional[Path]:
        """Locate break_alert.wav relative to project or PyInstaller bundle."""
        import os
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "assets" / "sounds" / "break_alert.wav",
            Path(os.environ.get("_MEIPASS", "")) / "assets" / "sounds" / "break_alert.wav",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None
