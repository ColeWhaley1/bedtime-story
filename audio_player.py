"""
Bluetooth speaker connection and audio playback via mpv.

On startup, attempts to connect to the configured Bluetooth speaker MAC.
Retries once on failure; falls back to aplay on the 3.5mm jack if Bluetooth
is unavailable so the user always hears something (even an error tone).
"""
import logging
import os
import subprocess
import tempfile
import threading
import time

import config

logger = logging.getLogger(__name__)

_mpv_process: subprocess.Popen | None = None
_mpv_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Bluetooth connection
# ---------------------------------------------------------------------------

def _run_bt_connect(mac: str) -> bool:
    """Send a bluetoothctl connect command. Returns True if 'Connected' appears."""
    try:
        result = subprocess.run(
            ["bluetoothctl", "connect", mac],
            capture_output=True, text=True,
            timeout=config.BT_CONNECT_TIMEOUT + 2,
        )
        output = result.stdout + result.stderr
        return "Connected" in output or "already connected" in output.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def connect_bluetooth() -> bool:
    """
    Attempt to connect to BLUETOOTH_SPEAKER_MAC.
    Retries once if the first attempt fails.
    Logs an error and plays a fallback error tone on total failure.
    Returns True if connected.
    """
    mac = config.BLUETOOTH_SPEAKER_MAC
    if not mac:
        logger.warning("BLUETOOTH_SPEAKER_MAC not set — skipping BT connect.")
        return False

    logger.info("Connecting to Bluetooth speaker %s …", mac)

    for attempt in range(1, config.BT_RETRY_COUNT + 2):  # +2: original + retries
        if _run_bt_connect(mac):
            logger.info("Bluetooth speaker connected.")
            return True
        if attempt <= config.BT_RETRY_COUNT:
            logger.warning("BT connect attempt %d failed, retrying in 3 s …", attempt)
            time.sleep(3)

    logger.error("Could not connect to Bluetooth speaker after %d attempt(s).", config.BT_RETRY_COUNT + 1)
    _play_error_tone()
    return False


def _play_error_tone():
    """Play the chime through the 3.5mm jack via aplay as an error signal."""
    if os.path.exists(config.CHIME_PATH):
        try:
            subprocess.run(
                ["aplay", "-D", "default", config.CHIME_PATH],
                timeout=5,
            )
        except Exception:
            pass  # Best-effort only


# ---------------------------------------------------------------------------
# Playback
# ---------------------------------------------------------------------------

def play(path: str):
    """
    Play an audio file through the Bluetooth speaker via mpv + BlueALSA.
    Blocks until playback finishes or stop() is called.
    Deletes the file after playback.
    """
    global _mpv_process

    if not os.path.exists(path):
        logger.error("Audio file not found: %s", path)
        return

    cmd = [
        "mpv",
        "--no-video",
        "--audio-device=alsa/bluealsa",
        "--really-quiet",
        path,
    ]

    logger.info("Playing: %s", path)
    with _mpv_lock:
        try:
            _mpv_process = subprocess.Popen(cmd)
        except FileNotFoundError:
            logger.error("mpv not found — install with: sudo apt install mpv")
            return

    try:
        _mpv_process.wait()
    except Exception as exc:
        logger.warning("mpv wait interrupted: %s", exc)
    finally:
        with _mpv_lock:
            _mpv_process = None
        try:
            os.remove(path)
            logger.debug("Deleted temp file: %s", path)
        except OSError:
            pass


def play_chime():
    """Play the notification chime through the Bluetooth speaker."""
    if not os.path.exists(config.CHIME_PATH):
        logger.warning("chime.wav not found — run: python sounds/generate_chime.py")
        return

    cmd = [
        "mpv",
        "--no-video",
        "--audio-device=alsa/bluealsa",
        "--really-quiet",
        config.CHIME_PATH,
    ]
    try:
        subprocess.run(cmd, timeout=10)
    except Exception as exc:
        logger.warning("Chime playback failed: %s", exc)


def stop():
    """Kill the current mpv process to stop playback."""
    with _mpv_lock:
        if _mpv_process and _mpv_process.poll() is None:
            logger.info("Stopping playback.")
            _mpv_process.terminate()
            try:
                _mpv_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                _mpv_process.kill()
