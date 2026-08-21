"""
auth_window.py - Minimalist local profile / PIN gate for NeuroShield-Eye Pro.

First launch: create a display name + 4–6 digit PIN (stored as PBKDF2 in SQLite).
Later launches: unlock with PIN. Nothing leaves the machine.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from logger import get_logger

log = get_logger("auth_window")

_STYLE = """
QDialog, QWidget {
    background-color: #121212;
    color: #E6E1E5;
    font-family: 'Segoe UI';
}
QLabel#brand {
    color: #82B1FF;
    letter-spacing: 2px;
}
QLabel#title {
    color: #E6E1E5;
}
QLabel#subtitle {
    color: #9E9E9E;
}
QLabel#error {
    color: #EF5350;
}
QLineEdit {
    background-color: #1E1E1E;
    border: 1px solid #2C2C2C;
    border-radius: 10px;
    padding: 10px 14px;
    color: #E6E1E5;
    font-size: 14px;
    selection-background-color: #1A237E;
}
QLineEdit:focus {
    border: 1px solid #82B1FF;
}
QLineEdit#pin {
    font-size: 22px;
    letter-spacing: 10px;
    qproperty-alignment: AlignCenter;
}
QPushButton#primary {
    background-color: #82B1FF;
    color: #0D1117;
    border: none;
    border-radius: 10px;
    padding: 12px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#primary:hover { background-color: #A7C8FF; }
QPushButton#primary:disabled { background-color: #2C2C2C; color: #6E6E6E; }
QPushButton#ghost {
    background: transparent;
    color: #9E9E9E;
    border: none;
    padding: 8px;
}
QPushButton#ghost:hover { color: #E6E1E5; }
QPushButton#pad {
    background-color: #1E1E1E;
    color: #E6E1E5;
    border: 1px solid #2C2C2C;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
}
QPushButton#pad:hover { background-color: #2A2A2A; border-color: #82B1FF; }
QPushButton#pad:pressed { background-color: #1565C0; }
QFrame#card {
    background-color: #1A1A1A;
    border: 1px solid #2C2C2C;
    border-radius: 16px;
}
"""


class AuthWindow(QDialog):
    """Local login / first-run setup dialog. Accepted = authenticated."""

    authenticated = pyqtSignal(str)

    def __init__(self, db) -> None:
        super().__init__(None)
        self._db = db
        self._is_setup = not db.has_user()
        self._pin_buffer = ""
        self._attempts = 0

        self.setWindowTitle("NeuroShield Eye Pro")
        self.setModal(True)
        self.setFixedSize(440, 640 if not self._is_setup else 560)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        if self._is_setup:
            self._build_setup()
        else:
            self._build_unlock()

    # ------------------------------------------------------------------
    # Setup (first run)
    # ------------------------------------------------------------------

    def _build_setup(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 28)
        root.setSpacing(0)

        brand = QLabel("NEUROSHIELD EYE PRO")
        brand.setObjectName("brand")
        brand.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(brand)
        root.addSpacing(18)

        title = QLabel("Create your local profile")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        root.addWidget(title)
        root.addSpacing(8)

        sub = QLabel(
            "A 4–6 digit PIN keeps your protection profiles private.\n"
            "Nothing is sent anywhere — this stays on this PC."
        )
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        root.addWidget(sub)
        root.addSpacing(28)

        card = QFrame()
        card.setObjectName("card")
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(20, 20, 20, 20)
        card_l.setSpacing(12)

        card_l.addWidget(self._field_label("Display name"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Alex")
        self._name.setMaxLength(32)
        card_l.addWidget(self._name)

        card_l.addWidget(self._field_label("PIN (4–6 digits)"))
        self._pin = QLineEdit()
        self._pin.setObjectName("pin")
        self._pin.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin.setMaxLength(6)
        self._pin.setPlaceholderText("••••")
        card_l.addWidget(self._pin)

        card_l.addWidget(self._field_label("Confirm PIN"))
        self._pin2 = QLineEdit()
        self._pin2.setObjectName("pin")
        self._pin2.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin2.setMaxLength(6)
        self._pin2.setPlaceholderText("••••")
        card_l.addWidget(self._pin2)

        root.addWidget(card)
        root.addSpacing(14)

        self._error = QLabel("")
        self._error.setObjectName("error")
        self._error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error.setWordWrap(True)
        root.addWidget(self._error)
        root.addStretch()

        create = QPushButton("Create profile")
        create.setObjectName("primary")
        create.setCursor(Qt.CursorShape.PointingHandCursor)
        create.setFixedHeight(46)
        create.clicked.connect(self._on_create)
        root.addWidget(create)

        self._pin2.returnPressed.connect(self._on_create)
        self._name.setFocus()

    def _on_create(self) -> None:
        name = self._name.text().strip()
        pin = self._pin.text().strip()
        pin2 = self._pin2.text().strip()
        if len(name) < 1:
            return self._set_error("Give yourself a name — even a short one.")
        if not (pin.isdigit() and 4 <= len(pin) <= 6):
            return self._set_error("PIN must be 4 to 6 digits.")
        if pin != pin2:
            return self._set_error("PINs don’t match. Try again.")
        if not self._db.create_user(name, pin):
            return self._set_error("Could not create the local profile.")
        log.info("Setup complete for '%s'.", name)
        self.authenticated.emit(name)
        self.accept()

    # ------------------------------------------------------------------
    # Unlock
    # ------------------------------------------------------------------

    def _build_unlock(self) -> None:
        user = self._db.get_user() or {}
        name = user.get("display_name", "there")

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 24)
        root.setSpacing(0)

        brand = QLabel("NEUROSHIELD EYE PRO")
        brand.setObjectName("brand")
        brand.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(brand)
        root.addSpacing(20)

        title = QLabel(f"Welcome back, {name}")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        root.addWidget(title)
        root.addSpacing(6)

        sub = QLabel("Enter your PIN to unlock your profiles.")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(sub)
        root.addSpacing(18)

        self._dots = QLabel("○  ○  ○  ○")
        self._dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dots.setFont(QFont("Segoe UI", 18))
        self._dots.setStyleSheet("color: #82B1FF;")
        root.addWidget(self._dots)
        root.addSpacing(16)

        pad = QWidget()
        grid = QVBoxLayout(pad)
        grid.setSpacing(8)
        keys = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["⌫", "0", "OK"]]
        for row_keys in keys:
            row = QHBoxLayout()
            row.setSpacing(8)
            for key in row_keys:
                btn = QPushButton(key)
                btn.setObjectName("pad")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(52)
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                btn.clicked.connect(lambda _=False, k=key: self._on_pad(k))
                row.addWidget(btn)
            grid.addLayout(row)
        root.addWidget(pad)
        root.addSpacing(10)

        self._error = QLabel("")
        self._error.setObjectName("error")
        self._error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._error)

    def _on_pad(self, key: str) -> None:
        if key == "⌫":
            self._pin_buffer = self._pin_buffer[:-1]
        elif key == "OK":
            self._try_unlock()
            return
        elif key.isdigit() and len(self._pin_buffer) < 6:
            self._pin_buffer += key
        self._refresh_dots()
        if len(self._pin_buffer) == 6:
            QTimer.singleShot(80, self._try_unlock)

    def _refresh_dots(self) -> None:
        filled = len(self._pin_buffer)
        shown = max(4, filled)
        parts = ["●" if i < filled else "○" for i in range(shown)]
        self._dots.setText("  ".join(parts))

    def _try_unlock(self) -> None:
        pin = self._pin_buffer
        if not (pin.isdigit() and 4 <= len(pin) <= 6):
            return self._set_error("PIN is 4 to 6 digits.")
        if self._db.verify_pin(pin):
            user = self._db.get_user() or {}
            name = user.get("display_name", "")
            log.info("PIN accepted.")
            self.authenticated.emit(name)
            self.accept()
            return
        self._attempts += 1
        self._pin_buffer = ""
        self._refresh_dots()
        if self._attempts >= 5:
            self._set_error("Too many attempts. Slow down and try again.")
            QTimer.singleShot(1500, lambda: self._set_error(""))
        else:
            self._set_error("That PIN doesn’t match.")

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if self._is_setup:
            return super().keyPressEvent(event)
        key = event.key()
        if key == Qt.Key.Key_Backspace:
            self._on_pad("⌫")
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_pad("OK")
            return
        text = event.text()
        if text.isdigit():
            self._on_pad(text)
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Shared
    # ------------------------------------------------------------------

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("subtitle")
        lbl.setFont(QFont("Segoe UI", 9))
        return lbl

    def _set_error(self, text: str) -> None:
        self._error.setText(text)
