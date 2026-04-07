"""
Text-to-speech synthesis via locally installed Kokoro, with gTTS fallback.

Kokoro runs fully offline on the Pi — no API key required.
Saves synthesized audio to a temp WAV file under /tmp/ and returns the path.
The caller is responsible for deleting the file after playback.
"""
import logging
import tempfile
import time

import numpy as np
import soundfile as sf

import config

logger = logging.getLogger(__name__)

_kokoro_pipeline = None


def _get_pipeline():
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        from kokoro import KPipeline  # type: ignore
        logger.info("Loading Kokoro TTS pipeline (lang=%s) …", config.KOKORO_LANG)
        _kokoro_pipeline = KPipeline(lang_code=config.KOKORO_LANG)
        logger.info("Kokoro pipeline ready.")
    return _kokoro_pipeline


def _output_path() -> str:
    return f"/tmp/story_{int(time.time())}.wav"


def synthesize(text: str) -> str:
    """
    Convert text to speech and save to a temp file.
    Returns the file path.

    Primary:  Kokoro (local, offline)
    Fallback: gTTS (requires internet)
    """
    path = _output_path()

    try:
        return _synthesize_kokoro(text, path)
    except Exception as exc:
        logger.error("Kokoro TTS error: %s — falling back to gTTS.", exc)

    return _synthesize_gtts(text, path)


def _synthesize_kokoro(text: str, path: str) -> str:
    pipeline = _get_pipeline()

    logger.info(
        "Synthesizing via Kokoro | voice=%s | speed=%.1f | ~%d words",
        config.KOKORO_VOICE,
        config.KOKORO_SPEED,
        len(text.split()),
    )

    audio_chunks = []
    for _, _, audio in pipeline(text, voice=config.KOKORO_VOICE, speed=config.KOKORO_SPEED):
        if audio is not None and len(audio) > 0:
            audio_chunks.append(audio)

    if not audio_chunks:
        raise RuntimeError("Kokoro returned no audio.")

    full_audio = np.concatenate(audio_chunks)
    sf.write(path, full_audio, samplerate=24000)

    logger.info("Kokoro audio saved: %s", path)
    return path


def _synthesize_gtts(text: str, path: str) -> str:
    try:
        from gtts import gTTS  # type: ignore
    except ImportError:
        raise RuntimeError("Neither Kokoro nor gTTS is available.")

    # gTTS saves MP3, so adjust path extension
    mp3_path = path.replace(".wav", ".mp3")

    logger.info("Synthesizing via gTTS (fallback) | ~%d words", len(text.split()))
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(mp3_path)

    logger.info("gTTS audio saved: %s", mp3_path)
    return mp3_path
