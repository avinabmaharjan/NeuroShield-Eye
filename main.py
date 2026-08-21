"""
main.py - Entry point for NeuroShield Eye.
Cleaned for Pylance and flat directory structure.
"""

import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Bootstrap: add current directory to sys.path
# ---------------------------------------------------------------------------
_CURRENT_DIR = Path(__file__).resolve().parent
if str(_CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(_CURRENT_DIR))

# ---------------------------------------------------------------------------
# Qt application setup
# ---------------------------------------------------------------------------
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer, QCoreApplication

app = QApplication(sys.argv)
app.setApplicationName("NeuroShieldEye")
app.setOrganizationName("NeuroShield")
app.setQuitOnLastWindowClosed(False)

# ---------------------------------------------------------------------------
# Project modules (Flat structure)
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

import winreg 

setup_logging()
log = get_logger("main")

_STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "NeuroShieldEye"

def _set_startup_registry(enable: bool) -> None:
    try:
        exe_path = sys.executable if getattr(sys, "frozen", False) else (
            f'"{sys.executable}" "{Path(__file__).resolve()}"'
        )
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enable:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                except FileNotFoundError:
                    pass 
    except OSError as e:
        log.error("Registry operation failed: %s", e)


class AppController:
    def __init__(self) -> None:
        log.info("NeuroShield Eye starting up...")

        self.settings = SettingsManager()
        self.db = DatabaseManager()

        self.tray = TrayManager()
        self.blue_light = BlueLightOverlay()
        self.break_timer = BreakTimer(self.settings, self.db)
        self.dim_engine = DimEngine()
        self.focus_mode = FocusMode(self.settings)
        self.posture = PostureReminder(self.settings, self.db)

        self.dashboard: Any = None
        self.settings_window: Any = None

        self.screen_time_timer = QTimer()
        self.screen_time_timer.setInterval(60_000)
        self.screen_time_timer.timeout.connect(self._track_screen_minute) # type: ignore

        self._connect_signals()
        self._apply_initial_settings()

    def _connect_signals(self) -> None:
        t = self.tray
        # Using type: ignore because Pylance struggles with PyQt signals
        t.action_blue_light_toggled.connect(self._toggle_blue_light) # type: ignore
        t.action_break_now.connect(self.break_timer.trigger_break_now) # type: ignore
        t.action_focus_toggled.connect(self._toggle_focus) # type: ignore
        t.action_open_dashboard.connect(self._open_dashboard) # type: ignore
        t.action_open_settings.connect(self._open_settings) # type: ignore
        t.action_exit.connect(self._exit) # type: ignore

        self.break_timer.break_started.connect(self._on_break_started) # type: ignore
        self.break_timer.break_ended.connect(self._on_break_ended) # type: ignore

        # Cast app to Any to avoid "screenAdded" attribute errors in Pylance
        app_inst: Any = QApplication.instance()
        if app_inst:
            app_inst.screenAdded.connect(self._on_screens_changed)
            app_inst.screenRemoved.connect(self._on_screens_changed)

    def _apply_initial_settings(self) -> None:
        if self.settings.get("blue_light", "enabled", True):
            self.blue_light.apply_settings(
                temperature=self.settings.get("blue_light", "color_temperature", 3400),
                opacity=self.settings.get("blue_light", "opacity", 0.35),
            )
            self.blue_light.show()
            self.tray.update_blue_light_state(True)

        if self.settings.get("dim_engine", "enabled", False):
            self.dim_engine.set_opacity(self.settings.get("dim_engine", "opacity", 0.0))
            self.dim_engine.show()

        if self.settings.get("focus_mode", "enabled", False):
            self.focus_mode.enable()
            self.tray.update_focus_state(True)

        if self.settings.get("posture", "enabled", True):
            self.posture.start()

        _set_startup_registry(self.settings.get("app", "start_with_windows", False))
        self.break_timer.start()

        if self.settings.get("analytics", "track_screen_time", True):
            self.screen_time_timer.start()

    def _apply_settings_changes(self) -> None:
        log.info("Applying settings changes...")
        bl_enabled = self.settings.get("blue_light", "enabled", True)
        
        # Cast to Any to prevent Pylance from complaining about missing methods
        bl: Any = self.blue_light
        dim: Any = self.dim_engine

        bl.apply_settings(
            temperature=self.settings.get("blue_light", "color_temperature", 3400),
            opacity=self.settings.get("blue_light", "opacity", 0.35),
        )
        
        if bl_enabled and not bl.isVisible():
            bl.show()
        elif not bl_enabled and bl.isVisible():
            bl.hide()
        self.tray.update_blue_light_state(bl_enabled)

        dim_enabled = self.settings.get("dim_engine", "enabled", False)
        dim.set_opacity(self.settings.get("dim_engine", "opacity", 0.0))
        if dim_enabled and not dim.isVisible():
            dim.show()
        elif not dim_enabled and dim.isVisible():
            dim.hide()

        focus_enabled = self.settings.get("focus_mode", "enabled", False)
        if focus_enabled and not self.focus_mode.is_enabled():
            self.focus_mode.enable()
        elif not focus_enabled and self.focus_mode.is_enabled():
            self.focus_mode.disable()
        self.tray.update_focus_state(self.focus_mode.is_enabled())

        posture_enabled = self.settings.get("posture", "enabled", True)
        if posture_enabled and not self.posture.is_enabled():
            self.posture.start()
        elif not posture_enabled and self.posture.is_enabled():
            self.posture.stop()
        else:
            self.posture.update_interval()

        _set_startup_registry(self.settings.get("app", "start_with_windows", False))
        self.break_timer.stop()
        self.break_timer.start()

    def _toggle_blue_light(self) -> None:
        bl: Any = self.blue_light
        visible = bl.toggle()
        self.settings.set("blue_light", "enabled", visible)
        self.tray.update_blue_light_state(visible)

    def _toggle_focus(self) -> None:
        enabled = self.focus_mode.toggle()
        self.settings.set("focus_mode", "enabled", enabled)
        self.tray.update_focus_state(enabled)

    def _open_dashboard(self) -> None:
        if self.dashboard is None:
            self.dashboard = DashboardWindow(self.db)
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def _open_settings(self) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.settings)
            self.settings_window.settings_changed.connect(self._apply_settings_changes) # type: ignore
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _exit(self) -> None:
        self.break_timer.stop()
        self.posture.stop()
        self.focus_mode.disable()
        self.blue_light.hide()
        self.dim_engine.hide()
        self.tray.hide()
        self.screen_time_timer.stop()
        QCoreApplication.quit()

    def _on_break_started(self) -> None:
        if self.settings.get("app", "show_notifications", True):
            self.tray.show_notification("Time for a Break!", "Look 20 feet away.")

    def _on_break_ended(self, completed: bool) -> None:
        if completed and self.settings.get("app", "show_notifications", True):
            self.tray.show_notification("Break Complete", "Back to work.")

    def _track_screen_minute(self) -> None:
        self.db.add_screen_minutes(1)

    def _on_screens_changed(self) -> None:
        self.blue_light.refresh_monitors()
        self.dim_engine.refresh_monitors()
        self.focus_mode.refresh_monitors()


def main() -> None:
    import tempfile
    lock_path = Path(tempfile.gettempdir()) / "neuroshield_eye.lock"
    try:
        lock_file = open(lock_path, "w")
        import msvcrt
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        msg = QMessageBox()
        msg.setText("NeuroShield Eye is already running.")
        msg.exec()
        sys.exit(0)

    controller = AppController()
    controller.tray.setup()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()