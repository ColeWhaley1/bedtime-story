"""
USB microphone detection, audio recording, and Whisper transcription.

At startup, scans PyAudio device list for the DUNGZDUZ USB mic by name.
Records up to RECORD_MAX_SECONDS of audio, stopping early on silence.
Saves to RECORDING_PATH and transcribes with Whisper.
"""
import audioop
import logging
import math
import struct
import threading
import wave
from typing import Optional

import numpy as np
import pyaudio

import config

logger = logging.getLogger(__name__)

_pa: Optional[pyaudio.PyAudio] = None
_usb_device_index: Optional[int] = None
_whisper_model = None
_init_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------

def _find_usb_mic(pa: pyaudio.PyAudio) -> Optional[int]:
    """
    Scan PyAudio devices for the USB microphone.
    Matches on 'USB' or 'DUNGZDUZ' in the device name (case-insensitive).
    Returns the device index, or None if not found.
    """
    count = pa.get_device_count()
    for i in range(count):
        info = pa.get_device_info_by_index(i)
        name = info.get("name", "").upper()
        max_input = info.get("maxInputChannels", 0)
        if max_input > 0 and ("USB" in name or "DUNGZDUZ" in name):
            logger.info("Found USB mic: index=%d name=%r", i, info["name"])
            return i
    return None


def get_usb_device_index() -> Optional[int]:
    """Return the cached USB mic device index (initialised on first call)."""
    global _pa, _usb_device_index
    with _init_lock:
        if _pa is None:
            _pa = pyaudio.PyAudio()
        if _usb_device_index is None:
            _usb_device_index = _find_usb_mic(_pa)
            if _usb_device_index is None:
                logger.warning(
                    "USB mic not found — falling back to system default input."
                )
    return _usb_device_index


def get_pyaudio() -> pyaudio.PyAudio:
    """Return (and lazily initialise) the shared PyAudio instance."""
    global _pa
    with _init_lock:
        if _pa is None:
            _pa = pyaudio.PyAudio()
    return _pa


# ---------------------------------------------------------------------------
# Whisper
# ---------------------------------------------------------------------------

def _load_whisper():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        logger.info("Loading Whisper model: %s …", config.WHISPER_MODEL)
        _whisper_model = whisper.load_model(config.WHISPER_MODEL)
        logger.info("Whisper model loaded.")
    return _whisper_model


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def _rms(chunk_bytes: bytes) -> float:
    """Compute root-mean-square amplitude of a raw int16 PCM chunk."""
    if not chunk_bytes:
        return 0.0
    count = len(chunk_bytes) // 2
    shorts = struct.unpack(f"<{count}h", chunk_bytes)
    mean_sq = sum(s * s for s in shorts) / count
    return math.sqrt(mean_sq)


def _do_record() -> Optional[str]:
    """Blocking record implementation — run via record() in a thread."""
    pa = get_pyaudio()
    device_index = get_usb_device_index()

    frames_per_chunk = config.RECORD_CHUNK_SIZE
    sample_rate = config.RECORD_SAMPLE_RATE
    max_chunks = int(sample_rate / frames_per_chunk * config.RECORD_MAX_SECONDS)
    silence_chunks = int(
        sample_rate / frames_per_chunk * config.RECORD_SILENCE_DURATION
    )

    stream_kwargs = dict(
        format=pyaudio.paInt16,
        channels=config.RECORD_CHANNELS,
        rate=sample_rate,
        input=True,
        frames_per_buffer=frames_per_chunk,
    )
    if device_index is not None:
        stream_kwargs["input_device_index"] = device_index

    try:
        stream = pa.open(**stream_kwargs)
    except OSError as exc:
        logger.error("Could not open microphone: %s", exc)
        return None

    logger.info("Recording … (speak now)")
    frames = []
    silent_chunks = 0

    try:
        for _ in range(max_chunks):
            data = stream.read(frames_per_chunk, exception_on_overflow=False)
            frames.append(data)
            if _rms(data) < config.RECORD_SILENCE_THRESHOLD:
                silent_chunks += 1
                if silent_chunks >= silence_chunks:
                    logger.debug("Silence detected — stopping early.")
                    break
            else:
                silent_chunks = 0
    finally:
        stream.stop_stream()
        stream.close()

    if not frames:
        logger.warning("No audio captured.")
        return None

    # Save WAV
    path = config.RECORDING_PATH
    with wave.open(path, "wb") as wf:
        wf.setnchannels(config.RECORD_CHANNELS)
        wf.setsampwidth(pa.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))

    logger.info("Saved recording: %s (%d chunks)", path, len(frames))
    return path


def record() -> Optional[str]:
    """
    Record up to RECORD_MAX_SECONDS from the USB mic.
    Runs the blocking PyAudio loop in a daemon thread so the main thread
    remains responsive to signals (Ctrl+C) during recording.
    Returns the saved WAV path, or None on error.
    """
    result: list[Optional[str]] = [None]

    def _target():
        result[0] = _do_record()

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    while t.is_alive():
        t.join(timeout=0.1)
    return result[0]


def warmup():
    """Pre-load the Whisper model so the first transcription has no cold-start delay."""
    try:
        _load_whisper()
    except Exception as exc:
        logger.warning("Whisper warmup failed: %s", exc)


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def transcribe(wav_path: str) -> str:
    """Transcribe a WAV file with Whisper. Returns the transcribed text."""
    model = _load_whisper()
    logger.info("Transcribing …")
    result = model.transcribe(wav_path, fp16=False)
    text = result.get("text", "").strip()
    logger.info("Transcription: %r", text)
    return text
