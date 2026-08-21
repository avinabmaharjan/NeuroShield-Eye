"""
generate_assets.py - Generates placeholder assets for NeuroShield Eye.

Run this once before first launch if you don't have real assets:
    python generate_assets.py

Generates:
  - assets/tray_icon.ico   (32x32 eye icon)
  - assets/sounds/break_alert.wav  (simple sine-wave beep)

These are functional placeholders. Replace with professional assets for
production release.
"""

import math
import struct
import sys
import wave
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ASSETS_DIR = Path(__file__).parent / "assets"
SOUNDS_DIR = ASSETS_DIR / "sounds"
ICON_PATH = ASSETS_DIR / "tray_icon.ico"
SOUND_PATH = SOUNDS_DIR / "break_alert.wav"
ASSETS_DIR.mkdir(exist_ok=True)
SOUNDS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# WAV generator — 440 Hz sine wave beep (0.6 seconds)
# ---------------------------------------------------------------------------
def generate_beep_wav(path: Path, frequency: float = 440.0, duration: float = 0.6,
                      sample_rate: int = 44100, amplitude: float = 0.4) -> None:
    n_samples = int(sample_rate * duration)
    # Fade in/out over 5ms to avoid clicks
    fade_samples = int(sample_rate * 0.005)

    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        value = math.sin(2 * math.pi * frequency * t)

        # Apply fade in
        if i < fade_samples:
            value *= i / fade_samples
        # Apply fade out
        elif i > n_samples - fade_samples:
            value *= (n_samples - i) / fade_samples

        # Convert to 16-bit integer
        sample = int(value * amplitude * 32767)
        samples.append(max(-32768, min(32767, sample)))

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)       # Mono
        wav.setsampwidth(2)       # 16-bit
        wav.setframerate(sample_rate)
        data = struct.pack(f"<{n_samples}h", *samples)
        wav.writeframes(data)

    print(f"  ✓ Created: {path}")


# ---------------------------------------------------------------------------
# ICO generator — simple programmatic icon using Pillow
# ---------------------------------------------------------------------------
def generate_icon(path: Path) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  ⚠ Pillow not installed. Skipping icon generation.")
        print("    Install with: pip install Pillow")
        print("    Or place your own tray_icon.ico in assets/")
        return

    sizes = [16, 32, 48, 64]
    images = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Background circle
        margin = max(1, size // 8)
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=(13, 17, 23, 255),
            outline=(88, 166, 255, 255),
            width=max(1, size // 16),
        )

        # Eye outline (ellipse)
        ex = size // 4
        ey = size * 3 // 8
        ew = size // 2
        eh = size // 4
        draw.ellipse([ex, ey, ex + ew, ey + eh], outline=(88, 166, 255, 255),
                     width=max(1, size // 16))

        # Pupil
        px = size * 7 // 16
        py = size * 7 // 16
        pr = max(1, size // 8)
        draw.ellipse([px, py, px + pr, py + pr], fill=(88, 166, 255, 255))

        images.append(img)

    images[1].save(
        str(path),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[2:],
    )
    print(f"  ✓ Created: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("NeuroShield Eye — Asset Generator")
    print("=" * 40)

    print("\nGenerating break alert sound...")
    generate_beep_wav(SOUND_PATH)

    print("\nGenerating tray icon...")
    generate_icon(ICON_PATH)

    print("\n✅ Asset generation complete.")
    print("   You can replace these with professional assets at any time.")
