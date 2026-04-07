"""
Text-to-speech synthesis via locally installed Kokoro, with gTTS fallback.

Kokoro runs fully offline on the Pi — no API key required.
Synthesizes in sentence-sized chunks and logs progress so long stories don't
appear frozen. Saves synthesized audio to a temp WAV file under /tmp/.
The caller is responsible for deleting the file after playback.
"""
import logging
import re
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


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs for incremental synthesis and logging."""
    parts = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    return parts if parts else [text]


def _output_path() -> str:
    return f"/tmp/story_{int(time.time())}.wav"


def synthesize(text: str) -> str:
    """
    Convert text to speech and save to a temp WAV file.
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


def synthesize_iter(text: str):
    """
    Synthesize paragraph by paragraph, yielding each WAV path as soon as it's
    ready. Allows the caller to start playing audio before the full story is
    synthesized. Falls back to yielding a single gTTS file on error.
    """
    try:
        pipeline = _get_pipeline()
        paragraphs = _split_paragraphs(text)
        total = len(paragraphs)

        for i, paragraph in enumerate(paragraphs, 1):
            logger.info(
                "Kokoro: synthesizing paragraph %d / %d …", i, total
            )
            audio_chunks = []
            for _, _, audio in pipeline(
                paragraph, voice=config.KOKORO_VOICE, speed=config.KOKORO_SPEED
            ):
                if audio is not None and len(audio) > 0:
                    audio_chunks.append(audio)

            if not audio_chunks:
                continue

            path = _output_path()
            sf.write(path, np.concatenate(audio_chunks), samplerate=24000)
            yield path

    except Exception as exc:
        logger.error("Kokoro streaming error: %s — falling back to gTTS.", exc)
        yield _synthesize_gtts(text, _output_path())


def warmup():
    """Pre-load the Kokoro pipeline so the first story has no cold-start delay."""
    try:
        _get_pipeline()
    except Exception as exc:
        logger.warning("Kokoro warmup failed: %s", exc)


def _synthesize_kokoro(text: str, path: str) -> str:
    pipeline = _get_pipeline()

    total_words = len(text.split())
    logger.info(
        "Synthesizing via Kokoro | voice=%s | speed=%.1f | ~%d words",
        config.KOKORO_VOICE,
        config.KOKORO_SPEED,
        total_words,
    )

    paragraphs = _split_paragraphs(text)
    audio_chunks = []

    for i, paragraph in enumerate(paragraphs, 1):
        logger.info("Kokoro: synthesizing paragraph %d / %d …", i, len(paragraphs))
        for _, _, audio in pipeline(
            paragraph, voice=config.KOKORO_VOICE, speed=config.KOKORO_SPEED
        ):
            if audio is not None and len(audio) > 0:
                audio_chunks.append(audio)

    if not audio_chunks:
        raise RuntimeError("Kokoro returned no audio.")

    logger.info("Kokoro: concatenating %d audio chunks …", len(audio_chunks))
    full_audio = np.concatenate(audio_chunks)
    sf.write(path, full_audio, samplerate=24000)

    duration = len(full_audio) / 24000
    logger.info("Kokoro audio saved: %s (%.1f s)", path, duration)
    return path


def _synthesize_gtts(text: str, path: str) -> str:
    try:
        from gtts import gTTS  # type: ignore
    except ImportError:
        raise RuntimeError("Neither Kokoro nor gTTS is available.")

    mp3_path = path.replace(".wav", ".mp3")

    logger.info("Synthesizing via gTTS (fallback) | ~%d words", len(text.split()))
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(mp3_path)

    logger.info("gTTS audio saved: %s", mp3_path)
    return mp3_path
