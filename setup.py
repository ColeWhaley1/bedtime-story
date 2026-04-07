"""
One-time setup wizard for Bedtime Story.

Run this before the first launch to:
  1. Discover nearby Bluetooth devices and save your speaker's MAC address
  2. Select a Kokoro TTS voice
  3. Generate sounds/chime.wav

All selections are written to .env.
"""
import os
import re
import subprocess
import sys
import time


ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------

def _read_env() -> dict:
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    return env


def _write_env(data: dict):
    """Merge `data` into .env, creating it from .env.example if needed."""
    example = os.path.join(os.path.dirname(__file__), ".env.example")
    if not os.path.exists(ENV_PATH) and os.path.exists(example):
        with open(example) as f:
            content = f.read()
    elif os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            content = f.read()
    else:
        content = ""

    for key, value in data.items():
        pattern = re.compile(rf"^{re.escape(key)}=.*", re.MULTILINE)
        replacement = f"{key}={value}"
        if pattern.search(content):
            content = pattern.sub(replacement, content)
        else:
            content += f"\n{replacement}"

    with open(ENV_PATH, "w") as f:
        f.write(content)

    print(f"  Saved to {ENV_PATH}")


# ---------------------------------------------------------------------------
# Step 1: Bluetooth
# ---------------------------------------------------------------------------

def _setup_bluetooth():
    print("\n━━━ Step 1: Bluetooth Speaker ━━━")
    print("Make sure your speaker is in pairing mode and powered on.")
    input("Press Enter to scan for Bluetooth devices (10 seconds) …")

    try:
        proc = subprocess.Popen(
            ["bluetoothctl"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        proc.stdin.write("power on\nscan on\n")
        proc.stdin.flush()
        print("Scanning …", end="", flush=True)
        for _ in range(10):
            time.sleep(1)
            print(".", end="", flush=True)
        proc.stdin.write("scan off\ndevices\nquit\n")
        proc.stdin.flush()
        out, _ = proc.communicate(timeout=5)
        print()
        devices = re.findall(r"Device\s+([0-9A-F:]{17})\s+(.+)", out, re.IGNORECASE)
        if devices:
            print("\nFound devices:")
            for i, (mac, name) in enumerate(devices, 1):
                print(f"  [{i}] {mac}  {name}")
        else:
            print("No devices found. You may enter the MAC address manually.")
    except Exception as exc:
        print(f"  (Scan failed: {exc})")

    mac = input("\nEnter Bluetooth speaker MAC (XX:XX:XX:XX:XX:XX): ").strip().upper()
    if not re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", mac):
        print("  Invalid MAC format — skipping.")
        return

    print(f"\nPairing and trusting {mac} …")
    try:
        subprocess.run(
            ["bluetoothctl", "pair", mac], timeout=15, capture_output=True
        )
        subprocess.run(
            ["bluetoothctl", "trust", mac], timeout=5, capture_output=True
        )
        subprocess.run(
            ["bluetoothctl", "connect", mac], timeout=15, capture_output=True
        )
        print("  Done.")
    except Exception as exc:
        print(f"  (bluetoothctl error: {exc} — you may need to pair manually)")

    _write_env({"BLUETOOTH_SPEAKER_MAC": mac})


# ---------------------------------------------------------------------------
# Step 2: Kokoro voice
# ---------------------------------------------------------------------------

_KOKORO_VOICES = {
    "bm_george": "British male — deep, dramatic (recommended for fantasy)",
    "am_michael": "American male — deep",
    "am_adam":   "American male",
    "af_heart":  "American female — warm (default)",
    "af_bella":  "American female — expressive",
    "bf_emma":   "British female",
}

def _setup_kokoro_voice():
    print("\n━━━ Step 2: Kokoro Voice ━━━")
    print("\nAvailable voices:")
    for name, desc in _KOKORO_VOICES.items():
        print(f"  {name:<12} {desc}")

    voice = input(
        "\nEnter voice to use (or press Enter for 'bm_george'): "
    ).strip()
    if not voice:
        voice = "bm_george"
        print(f"  Using: {voice}")

    _write_env({"KOKORO_VOICE": voice})


# ---------------------------------------------------------------------------
# Step 3: Generate chime.wav
# ---------------------------------------------------------------------------

def _generate_chime():
    print("\n━━━ Step 3: Generate chime.wav ━━━")
    chime_path = os.path.join(os.path.dirname(__file__), "sounds", "chime.wav")
    if os.path.exists(chime_path):
        overwrite = input("chime.wav already exists. Regenerate? [y/N]: ").strip().lower()
        if overwrite != "y":
            print("  Keeping existing chime.wav.")
            return

    script = os.path.join(os.path.dirname(__file__), "sounds", "generate_chime.py")
    if os.path.exists(script):
        os.system(f"{sys.executable} {script}")
    else:
        print("  sounds/generate_chime.py not found — skipping.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("╔══════════════════════════════════════╗")
    print("║      Bedtime Story — First-Time Setup ║")
    print("╚══════════════════════════════════════╝")

    # Load existing .env so we can display current values
    env = _read_env()
    if env.get("ANTHROPIC_API_KEY", "").startswith("your_"):
        print("\n⚠  ANTHROPIC_API_KEY looks like a placeholder.")
        print("   Edit .env and set it before running main.py.\n")

    _setup_bluetooth()
    _setup_kokoro_voice()
    _generate_chime()

    print("\n✓ Setup complete. Run the app with:")
    print("    python main.py\n")


if __name__ == "__main__":
    main()
