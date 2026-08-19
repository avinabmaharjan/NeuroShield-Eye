"""
main.py - Entry point and AppController for NeuroShield Eye.

The AppController is the central orchestrator that:
  1. Owns all module instances (single source of truth for state)
  2. Wires Qt signals between modules
  3. Manages Windows startup registry entry
  4. Handles graceful shutdown

Architecture principle: All inter-module communication happens through
Qt signals, keeping modules decoupled and independently testable.

Usage:
    python src/main.py
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: add src/ to sys.path so all relative imports resolve correctly
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# ---------------------------------------------------------------------------
# Qt application must be created before any Qt classes are instantiated
# ---------------------------------------------------------------------------
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

app = QApplication(sys.argv)
app.setApplicationName("NeuroShieldEye")
app.setOrganizationName("NeuroShield")
# Prevent the app from quitting when the last window closes (tray-only app)
app.setQuitOnLastWindowClosed(False)

# ---------------------------------------------------------------------------
# Now import project modules (QApplication is already alive)
# ---------------------------------------------------------------------------
from logger import setup_logging, get_logger
from settings_manager import SettingsManager
from settings_panel import SettingsWindow
from database_manager import DatabaseManager
from tray_manager import TrayManager
from blue_light_overlay import BlueLightOverlay
from break_timer import BreakTimer
from dim_engine import DimEngine
from focus_mode import FocusMode
from posture_reminder import PostureReminder
from dashboard_window import DashboardWindow

import winreg  # Windows registry access (pywin32 not needed; winreg is stdlib on Windows)

setup_logging()
log = get_logger("main")

_STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "NeuroShieldEye"


def _set_startup_registry(enable: bool) -> None:
    """Add or remove the app from Windows startup via registry."""
    try:
        exe_path = sys.executable if getattr(sys, "frozen", False) else (
            f'"{sys.executable}" "{Path(__file__).resolve()}"'
        )
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enable:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, exe_path)
                log.info("Added to startup registry.")
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                    log.info("Removed from startup registry.")
                except FileNotFoundError:
                    pass  # Already removed
    except OSError as e:
        log.error("Registry operation failed: %s", e)


# ---------------------------------------------------------------------------
# AppController
# ---------------------------------------------------------------------------

class AppController:
    """
    Central controller for NeuroShield Eye.

    Initializes all subsystems and wires their signals together.
    This class owns the lifecycle of every module.
    """

    def __init__(self) -> None:
        log.info("NeuroShield Eye starting up...")

        # --- Core services ---
        self._settings = SettingsManager()
        self._db = DatabaseManager()

        # --- Feature modules ---
        self._tray = TrayManager()
        self._blue_light = BlueLightOverlay()
        self._break_timer = BreakTimer(self._settings, self._db)
        self._dim_engine = DimEngine()
        self._focus_mode = FocusMode(self._settings)
        self._posture = PostureReminder(self._settings, self._db)

        # --- UI windows (lazy-shown, never destroyed) ---
        self._dashboard: DashboardWindow | None = None
        self._settings_window: SettingsWindow | None = None

        # --- Screen-time tracking timer (updates every minute) ---
        self._screen_time_timer = QTimer()
        self._screen_time_timer.setInterval(60_000)
        self._screen_time_timer.timeout.connect(self._track_screen_minute)

        # Wire everything up
        self._connect_signals()

        # Apply initial config
        self._apply_initial_settings()

        log.info("AppController initialized.")

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Connect tray menu signals to controller handlers."""
        t = self._tray
        t.action_blue_light_toggled.connect(self._toggle_blue_light)
        t.action_break_now.connect(self._break_timer.trigger_break_now)
        t.action_focus_toggled.connect(self._toggle_focus)
        t.action_open_dashboard.connect(self._open_dashboard)
        t.action_open_settings.connect(self._open_settings)
        t.action_exit.connect(self._exit)

        # Break timer feedback
        self._break_timer.break_started.connect(self._on_break_started)
        self._break_timer.break_ended.connect(self._on_break_ended)

        # Monitor plug/unplug — refresh overlays
        app = QApplication.instance()
        if app:
            app.screenAdded.connect(self._on_screens_changed)
            app.screenRemoved.connect(self._on_screens_changed)

    # ------------------------------------------------------------------
    # Initial configuration
    # ------------------------------------------------------------------

    def _apply_initial_settings(self) -> None:
        """Apply saved settings to all modules at startup."""
        # Blue light
        if self._settings.get("blue_light", "enabled", True):
            self._blue_light.apply_settings(
                temperature=self._settings.get("blue_light", "color_temperature", 3400),
                opacity=self._settings.get("blue_light", "opacity", 0.35),
            )
            self._blue_light.show()
            self._tray.update_blue_light_state(True)

        # Dim engine
        if self._settings.get("dim_engine", "enabled", False):
            self._dim_engine.set_opacity(self._settings.get("dim_engine", "opacity", 0.0))
            self._dim_engine.show()

        # Focus mode
        if self._settings.get("focus_mode", "enabled", False):
            self._focus_mode.enable()
            self._tray.update_focus_state(True)

        # Posture
        if self._settings.get("posture", "enabled", True):
            self._posture.start()

        # Startup registry
        _set_startup_registry(self._settings.get("app", "start_with_windows", False))

        # Break timer
        self._break_timer.start()

        # Screen time tracking
        if self._settings.get("analytics", "track_screen_time", True):
            self._screen_time_timer.start()

    def _apply_settings_changes(self) -> None:
        """Called when the settings window emits settings_changed."""
        log.info("Applying settings changes...")

        # Blue light
        bl_enabled = self._settings.get("blue_light", "enabled", True)
        self._blue_light.apply_settings(
            temperature=self._settings.get("blue_light", "color_temperature", 3400),
            opacity=self._settings.get("blue_light", "opacity", 0.35),
        )
        if bl_enabled and not self._blue_light.is_visible():
            self._blue_light.show()
        elif not bl_enabled and self._blue_light.is_visible():
            self._blue_light.hide()
        self._tray.update_blue_light_state(bl_enabled)

        # Dim
        dim_enabled = self._settings.get("dim_engine", "enabled", False)
        self._dim_engine.set_opacity(self._settings.get("dim_engine", "opacity", 0.0))
        if dim_enabled and not self._dim_engine.is_visible():
            self._dim_engine.show()
        elif not dim_enabled and self._dim_engine.is_visible():
            self._dim_engine.hide()

        # Focus
        focus_enabled = self._settings.get("focus_mode", "enabled", False)
        if focus_enabled and not self._focus_mode.is_enabled():
            self._focus_mode.enable()
        elif not focus_enabled and self._focus_mode.is_enabled():
            self._focus_mode.disable()
        self._tray.update_focus_state(self._focus_mode.is_enabled())

        # Posture
        posture_enabled = self._settings.get("posture", "enabled", True)
        if posture_enabled and not self._posture.is_enabled():
            self._posture.start()
        elif not posture_enabled and self._posture.is_enabled():
            self._posture.stop()
        else:
            self._posture.update_interval()

        # Startup
        _set_startup_registry(self._settings.get("app", "start_with_windows", False))

        # Break timer — restart with new settings
        self._break_timer.stop()
        self._break_timer.start()

        # Screen time
        if self._settings.get("analytics", "track_screen_time", True):
            if not self._screen_time_timer.isActive():
                self._screen_time_timer.start()
        else:
            self._screen_time_timer.stop()

    # ------------------------------------------------------------------
    # Tray action handlers
    # ------------------------------------------------------------------

    def _toggle_blue_light(self) -> None:
        visible = self._blue_light.toggle()
        self._settings.set("blue_light", "enabled", visible)
        self._tray.update_blue_light_state(visible)
        state = "enabled" if visible else "disabled"
        if self._settings.get("app", "show_notifications", True):
            self._tray.show_notification("Blue Light Filter", f"Filter {state}.")
        log.info("Blue light filter toggled → %s", state)

    def _toggle_focus(self) -> None:
        enabled = self._focus_mode.toggle()
        self._settings.set("focus_mode", "enabled", enabled)
        self._tray.update_focus_state(enabled)
        log.info("Focus mode toggled → %s", "ON" if enabled else "OFF")

    def _open_dashboard(self) -> None:
        if self._dashboard is None:
            self._dashboard = DashboardWindow(self._db)
        self._dashboard.show()
        self._dashboard.raise_()
        self._dashboard.activateWindow()

    def _open_settings(self) -> None:
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self._settings)
            self._settings_window.settings_changed.connect(self._apply_settings_changes)
        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _exit(self) -> None:
        log.info("Shutting down NeuroShield Eye...")
        self._break_timer.stop()
        self._posture.stop()
        self._focus_mode.disable()
        self._blue_light.hide()
        self._dim_engine.hide()
        self._tray.hide()
        self._screen_time_timer.stop()
        QApplication.quit()

    # ------------------------------------------------------------------
    # Break event handlers
    # ------------------------------------------------------------------

    def _on_break_started(self) -> None:
        if self._settings.get("app", "show_notifications", True):
            self._tray.show_notification("Time for a Break!", "Look 20 feet away for 20 seconds.")

    def _on_break_ended(self, completed: bool) -> None:
        if completed and self._settings.get("app", "show_notifications", True):
            self._tray.show_notification("Break Complete", "Great job! Back to work.")

    # ------------------------------------------------------------------
    # Screen time tracking
    # ------------------------------------------------------------------

    def _track_screen_minute(self) -> None:
        """Called every minute to log 1 minute of screen time."""
        self._db.add_screen_minutes(1)

    # ------------------------------------------------------------------
    # Monitor change handler
    # ------------------------------------------------------------------

    def _on_screens_changed(self) -> None:
        """Refresh all overlays when monitors are added or removed."""
        log.info("Screen configuration changed — refreshing overlays.")
        self._blue_light.refresh_monitors()
        self._dim_engine.refresh_monitors()
        self._focus_mode.refresh_monitors()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Prevent multiple instances (simple lock file approach)
    import tempfile
    lock_path = Path(tempfile.gettempdir()) / "neuroshield_eye.lock"
    try:
        lock_file = open(lock_path, "w")
        import msvcrt
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        # Another instance is running
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle("NeuroShield Eye")
        msg.setText("NeuroShield Eye is already running.\nCheck your system tray.")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
        sys.exit(0)

    controller = AppController()
    controller._tray.setup()

    log.info("NeuroShield Eye running. Check the system tray.")
    exit_code = app.exec()
    log.info("Application exited with code %d.", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
