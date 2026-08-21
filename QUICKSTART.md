# NeuroShield Eye — Quick Start Guide

## First-Time Setup (3 minutes)

### 1. Install dependencies
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Generate placeholder assets
```bash
python generate_assets.py
```
This creates:
- `assets/tray_icon.ico` — system tray icon
- `assets/sounds/break_alert.wav` — break notification sound

> Replace these with your own professional assets at any time.

### 3. Run the app
```bash
python src/main.py
```

NeuroShield Eye will appear in your **system tray** (bottom-right).
Right-click the eye icon to access all features.

---

## Troubleshooting

**"No module named 'PyQt6'"**
→ Run: `pip install -r requirements.txt`

**"System tray not available"**
→ Ensure Windows 11 task bar is enabled and not hidden.

**Tray icon is generic/missing**
→ Run `python generate_assets.py` then restart.

**Break sound doesn't play**
→ The app falls back to `winsound.MessageBeep()`. Check your audio is on.

---

## Build Executable

```bash
pip install pyinstaller
python generate_assets.py   # Ensure assets exist
pyinstaller NeuroShieldEye.spec
# Output: dist/NeuroShieldEye.exe
```

---

## File Locations (Runtime)

| File | Location |
|------|----------|
| Database | `%APPDATA%\NeuroShieldEye\data.db` |
| User config | `%APPDATA%\NeuroShieldEye\user_config.json` |
| Log files | `%APPDATA%\NeuroShieldEye\logs\neuroshield.log` |
