"""
settings_panel.py - Settings UI for NeuroShield Eye.

Dark-themed, tabbed settings window. All changes are applied live via
callbacks and persisted to config on 'Apply' or 'Save'. 'Reset Defaults'
restores factory settings and refreshes the UI.

Tab layout:
  1. Blue Light Filter
  2. Break Timer
  3. Dimming & Focus
  4. Posture
  5. General
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QFrame,
    QSizePolicy,
    QLineEdit,
)

from utils.logger import get_logger

log = get_logger("settings_panel")

_DARK_STYLE = """
QMainWindow, QDialog, QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: 'Segoe UI';
    font-size: 11px;
}
QTabWidget::pane {
    border: 1px solid #30363d;
    border-radius: 6px;
    background-color: #161b22;
}
QTabBar::tab {
    background-color: #21262d;
    color: #8b949e;
    padding: 8px 18px;
    border: 1px solid #30363d;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #161b22;
    color: #e6edf3;
    border-bottom: 2px solid #58a6ff;
}
QGroupBox {
    border: 1px solid #30363d;
    border-radius: 6px;
    margin-top: 12px;
    padding: 8px;
    background-color: #0d1117;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #8b949e;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QLabel { color: #c9d1d9; }
QCheckBox { color: #c9d1d9; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #30363d;
    border-radius: 3px;
    background: #21262d;
}
QCheckBox::indicator:checked {
    background: #58a6ff;
    border-color: #58a6ff;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #30363d;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #58a6ff;
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal { background: #58a6ff; border-radius: 2px; }
QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 5px;
    padding: 4px 8px;
    color: #e6edf3;
}
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {
    border-color: #58a6ff;
}
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 18px;
}
QPushButton:hover { background-color: #30363d; color: #e6edf3; }
QPushButton#save_btn {
    background-color: #1f6feb;
    color: white;
    border: none;
}
QPushButton#save_btn:hover { background-color: #388bfd; }
QPushButton#reset_btn { color: #f85149; border-color: #f85149; }
QPushButton#reset_btn:hover { background-color: #21262d; }
"""


def _section(title: str) -> QGroupBox:
    g = QGroupBox(title)
    return g


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    return lbl


def _row(left_widget, right_widget) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.addWidget(left_widget)
    layout.addStretch()
    layout.addWidget(right_widget)
    return layout


class SettingsWindow(QMainWindow):
    """
    Tabbed settings window. Emits settings_changed when the user applies.
    The AppController connects to this signal to propagate changes live.
    """

    settings_changed = pyqtSignal()

    def __init__(self, settings) -> None:
        super().__init__()
        self._settings = settings
        self._setup_window()
        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle("NeuroShield Eye — Settings")
        self.setMinimumSize(580, 520)
        self.setStyleSheet(_DARK_STYLE)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(16)

        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #e6edf3;")
        root.addWidget(title)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self._build_blue_light_tab(), "🔵 Blue Light")
        tabs.addTab(self._build_break_tab(), "⏱ Breaks")
        tabs.addTab(self._build_dim_focus_tab(), "🔆 Dim & Focus")
        tabs.addTab(self._build_posture_tab(), "🪑 Posture")
        tabs.addTab(self._build_general_tab(), "⚙ General")
        root.addWidget(tabs)

        # Buttons row
        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset Defaults")
        reset_btn.setObjectName("reset_btn")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        save_btn = QPushButton("Save & Apply")
        save_btn.setObjectName("save_btn")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Tab: Blue Light
    # ------------------------------------------------------------------

    def _build_blue_light_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        g = _section("Blue Light Filter")
        g_layout = QVBoxLayout(g)
        g_layout.setSpacing(12)

        self._bl_enabled = QCheckBox("Enable blue light filter")
        g_layout.addWidget(self._bl_enabled)

        temp_label = _label("Color Temperature (K)")
        self._bl_temp = QSlider(Qt.Orientation.Horizontal)
        self._bl_temp.setRange(2000, 6500)
        self._bl_temp.setTickInterval(500)
        self._bl_temp_display = QLabel("3400K")
        self._bl_temp.valueChanged.connect(
            lambda v: self._bl_temp_display.setText(f"{v}K")
        )
        g_layout.addWidget(temp_label)
        temp_row = QHBoxLayout()
        temp_row.addWidget(QLabel("Warm (2000K)"))
        temp_row.addWidget(self._bl_temp)
        temp_row.addWidget(QLabel("Cool (6500K)"))
        temp_row.addWidget(self._bl_temp_display)
        g_layout.addLayout(temp_row)

        opacity_label = _label("Filter Opacity (%)")
        self._bl_opacity = QSlider(Qt.Orientation.Horizontal)
        self._bl_opacity.setRange(0, 80)
        self._bl_opacity_display = QLabel("35%")
        self._bl_opacity.valueChanged.connect(
            lambda v: self._bl_opacity_display.setText(f"{v}%")
        )
        g_layout.addWidget(opacity_label)
        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("0%"))
        op_row.addWidget(self._bl_opacity)
        op_row.addWidget(QLabel("80%"))
        op_row.addWidget(self._bl_opacity_display)
        g_layout.addLayout(op_row)

        layout.addWidget(g)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Tab: Break Timer
    # ------------------------------------------------------------------

    def _build_break_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        g = _section("Break Timer Mode")
        g_layout = QVBoxLayout(g)
        g_layout.setSpacing(12)

        mode_row = QHBoxLayout()
        mode_row.addWidget(_label("Mode:"))
        self._break_mode = QComboBox()
        self._break_mode.addItems(["20-20-20", "Custom"])
        mode_row.addStretch()
        mode_row.addWidget(self._break_mode)
        g_layout.addLayout(mode_row)

        work_row = QHBoxLayout()
        work_row.addWidget(_label("Work interval (minutes):"))
        self._work_interval = QSpinBox()
        self._work_interval.setRange(5, 120)
        self._work_interval.setValue(20)
        work_row.addStretch()
        work_row.addWidget(self._work_interval)
        g_layout.addLayout(work_row)

        break_row = QHBoxLayout()
        break_row.addWidget(_label("Break duration (seconds for 20-20-20, minutes for Custom):"))
        self._break_duration = QSpinBox()
        self._break_duration.setRange(5, 3600)
        self._break_duration.setValue(20)
        break_row.addStretch()
        break_row.addWidget(self._break_duration)
        g_layout.addLayout(break_row)

        self._forced_break = QCheckBox("Force break (cannot be skipped)")
        g_layout.addWidget(self._forced_break)

        self._sound_enabled = QCheckBox("Play sound notification")
        g_layout.addWidget(self._sound_enabled)

        layout.addWidget(g)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Tab: Dim & Focus
    # ------------------------------------------------------------------

    def _build_dim_focus_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        dim_g = _section("Dim Engine")
        dim_layout = QVBoxLayout(dim_g)
        self._dim_enabled = QCheckBox("Enable software dimming")
        dim_layout.addWidget(self._dim_enabled)

        dim_op_row = QHBoxLayout()
        dim_op_row.addWidget(_label("Dim level:"))
        self._dim_opacity = QSlider(Qt.Orientation.Horizontal)
        self._dim_opacity.setRange(0, 90)
        self._dim_opacity_display = QLabel("0%")
        self._dim_opacity.valueChanged.connect(
            lambda v: self._dim_opacity_display.setText(f"{v}%")
        )
        dim_op_row.addWidget(self._dim_opacity)
        dim_op_row.addWidget(self._dim_opacity_display)
        dim_layout.addLayout(dim_op_row)
        layout.addWidget(dim_g)

        focus_g = _section("Focus Mode")
        focus_layout = QVBoxLayout(focus_g)
        self._focus_enabled = QCheckBox("Enable focus mode (dims non-active monitors)")
        focus_layout.addWidget(self._focus_enabled)

        focus_op_row = QHBoxLayout()
        focus_op_row.addWidget(_label("Dim opacity for inactive monitors:"))
        self._focus_opacity = QSlider(Qt.Orientation.Horizontal)
        self._focus_opacity.setRange(0, 90)
        self._focus_opacity_display = QLabel("60%")
        self._focus_opacity.valueChanged.connect(
            lambda v: self._focus_opacity_display.setText(f"{v}%")
        )
        focus_op_row.addWidget(self._focus_opacity)
        focus_op_row.addWidget(self._focus_opacity_display)
        focus_layout.addLayout(focus_op_row)

        self._focus_grayscale = QCheckBox("Grayscale inactive monitors")
        focus_layout.addWidget(self._focus_grayscale)
        layout.addWidget(focus_g)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Tab: Posture
    # ------------------------------------------------------------------

    def _build_posture_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        g = _section("Posture Reminder")
        g_layout = QVBoxLayout(g)
        g_layout.setSpacing(12)

        self._posture_enabled = QCheckBox("Enable posture reminders")
        g_layout.addWidget(self._posture_enabled)

        interval_row = QHBoxLayout()
        interval_row.addWidget(_label("Reminder interval (minutes):"))
        self._posture_interval = QSpinBox()
        self._posture_interval.setRange(5, 120)
        self._posture_interval.setValue(30)
        interval_row.addStretch()
        interval_row.addWidget(self._posture_interval)
        g_layout.addLayout(interval_row)

        g_layout.addWidget(_label("Reminder message:"))
        self._posture_message = QLineEdit()
        self._posture_message.setMinimumWidth(320)
        g_layout.addWidget(self._posture_message)

        layout.addWidget(g)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Tab: General
    # ------------------------------------------------------------------

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        g = _section("Application")
        g_layout = QVBoxLayout(g)

        self._start_with_windows = QCheckBox("Start with Windows (registry)")
        g_layout.addWidget(self._start_with_windows)

        self._show_notifications = QCheckBox("Show system tray notifications")
        g_layout.addWidget(self._show_notifications)

        self._track_screen_time = QCheckBox("Track screen time")
        g_layout.addWidget(self._track_screen_time)

        goal_row = QHBoxLayout()
        goal_row.addWidget(_label("Daily screen time goal (hours):"))
        self._daily_goal = QSpinBox()
        self._daily_goal.setRange(1, 24)
        self._daily_goal.setValue(8)
        goal_row.addStretch()
        goal_row.addWidget(self._daily_goal)
        g_layout.addLayout(goal_row)

        layout.addWidget(g)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Load / Save / Reset
    # ------------------------------------------------------------------

    def _load_values(self) -> None:
        """Populate all widgets from the current settings."""
        s = self._settings

        # Blue light
        self._bl_enabled.setChecked(s.get("blue_light", "enabled", True))
        self._bl_temp.setValue(s.get("blue_light", "color_temperature", 3400))
        self._bl_opacity.setValue(int(s.get("blue_light", "opacity", 0.35) * 100))

        # Break
        mode = s.get("break_timer", "mode", "20-20-20")
        self._break_mode.setCurrentText(mode)
        self._work_interval.setValue(s.get("break_timer", "work_interval_minutes", 20))
        self._break_duration.setValue(s.get("break_timer", "break_duration_seconds", 20))
        self._forced_break.setChecked(s.get("break_timer", "forced_break", False))
        self._sound_enabled.setChecked(s.get("break_timer", "sound_enabled", True))

        # Dim
        self._dim_enabled.setChecked(s.get("dim_engine", "enabled", False))
        self._dim_opacity.setValue(int(s.get("dim_engine", "opacity", 0.0) * 100))

        # Focus
        self._focus_enabled.setChecked(s.get("focus_mode", "enabled", False))
        self._focus_opacity.setValue(int(s.get("focus_mode", "dim_opacity", 0.6) * 100))
        self._focus_grayscale.setChecked(s.get("focus_mode", "grayscale", False))

        # Posture
        self._posture_enabled.setChecked(s.get("posture", "enabled", True))
        self._posture_interval.setValue(s.get("posture", "interval_minutes", 30))
        self._posture_message.setText(
            s.get("posture", "message",
                  "Check your posture! Sit up straight and relax your shoulders.")
        )

        # General
        self._start_with_windows.setChecked(s.get("app", "start_with_windows", False))
        self._show_notifications.setChecked(s.get("app", "show_notifications", True))
        self._track_screen_time.setChecked(s.get("analytics", "track_screen_time", True))
        self._daily_goal.setValue(s.get("analytics", "daily_goal_hours", 8))

    def _save(self) -> None:
        """Write widget values back to settings and emit settings_changed."""
        s = self._settings

        s.set("blue_light", "enabled", self._bl_enabled.isChecked())
        s.set("blue_light", "color_temperature", self._bl_temp.value())
        s.set("blue_light", "opacity", self._bl_opacity.value() / 100.0)

        mode = self._break_mode.currentText()
        s.set("break_timer", "mode", mode)
        s.set("break_timer", "work_interval_minutes", self._work_interval.value())
        s.set("break_timer", "break_duration_seconds", self._break_duration.value())
        s.set("break_timer", "custom_work_minutes", self._work_interval.value())
        s.set("break_timer", "custom_break_minutes", self._break_duration.value() // 60 or 5)
        s.set("break_timer", "forced_break", self._forced_break.isChecked())
        s.set("break_timer", "sound_enabled", self._sound_enabled.isChecked())

        s.set("dim_engine", "enabled", self._dim_enabled.isChecked())
        s.set("dim_engine", "opacity", self._dim_opacity.value() / 100.0)

        s.set("focus_mode", "enabled", self._focus_enabled.isChecked())
        s.set("focus_mode", "dim_opacity", self._focus_opacity.value() / 100.0)
        s.set("focus_mode", "grayscale", self._focus_grayscale.isChecked())

        s.set("posture", "enabled", self._posture_enabled.isChecked())
        s.set("posture", "interval_minutes", self._posture_interval.value())
        s.set("posture", "message", self._posture_message.text())

        s.set("app", "start_with_windows", self._start_with_windows.isChecked())
        s.set("app", "show_notifications", self._show_notifications.isChecked())
        s.set("analytics", "track_screen_time", self._track_screen_time.isChecked())
        s.set("analytics", "daily_goal_hours", self._daily_goal.value())

        s.save()
        self.settings_changed.emit()
        log.info("Settings saved and applied.")

    def _reset_defaults(self) -> None:
        self._settings.reset_to_defaults()
        self._load_values()
        self.settings_changed.emit()
        log.info("Settings reset to defaults.")

    def closeEvent(self, event) -> None:  # noqa: N802
        self.hide()
        event.ignore()
