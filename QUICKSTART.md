# NeuroShield Eye Pro — Quick Start

## First-time setup (3 minutes)

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
Creates:
- `assets/tray_icon.ico`
- `assets/sounds/break_alert.wav`

### 3. Run
```bash
python main.py
```

Create a local name + PIN. The sidebar dashboard is the home screen; the tray icon keeps the overlays alive if you close the window.

---

## What to click first

1. **Dashboard** — 20-20-20 bar and today’s numbers (a demo week is seeded so charts are not empty).
2. **Eye Protection** — drag temperature / dim sliders (overlay reacts immediately). Apply **Late Night Coding** or **Gaming Mode**.
3. **Focus Mode** — turn on the visual anchor; other windows dim.
4. **Lock** in the sidebar when you step away.

---

## Troubleshooting

**"No module named 'PyQt6'"**  
→ `pip install -r requirements.txt`

**System tray missing**  
→ Windows taskbar must be available. The dashboard still runs.

**Focus Mode does nothing on one monitor**  
→ It punches a hole around the *foreground* window. Click the app you want to keep bright.

**Forgot PIN**  
→ Data is local. Delete `%APPDATA%\NeuroShieldEye\neuroshield.db` to re-run first-time setup (this also clears analytics/profiles).

---

## File locations

| File | Location |
|------|----------|
| Database | `%APPDATA%\NeuroShieldEye\neuroshield.db` |
| User config | `%APPDATA%\NeuroShieldEye\user_config.json` |
| Logs | `%APPDATA%\NeuroShieldEye\logs\neuroshield.log` |
