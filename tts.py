"""
Text-to-speech synthesis via ElevenLabs, with gTTS fallback on quota errors.

Saves synthesized audio to a temp file under /tmp/ and returns the path.
The caller is responsible for deleting the file after playback.
"""
import logging
import tempfile
import time

import config

logger = logging.getLogger(__name__)

_ELEVENLABS_MODEL = "eleven_monolingual_v1"


def _output_path() -> str:
    """Return a unique temp path for the story MP3."""
    return f"/tmp/story_{int(time.time())}.mp3"


def synthesize(text: str) -> str:
    """
    Convert text to speech and save to a temp file.
    Returns the file path.

    Primary:  ElevenLabs API  → high-quality, dramatic voice
    Fallback: gTTS            → free, lower quality, but always works
    """
    path = _output_path()

    # --- Try ElevenLabs first ---
    if config.ELEVENLABS_API_KEY and config.DEFAULT_VOICE_ID:
        try:
            return _synthesize_elevenlabs(text, path)
        except Exception as exc:
            msg = str(exc).lower()
            if any(kw in msg for kw in ("quota", "limit", "402", "429", "billing")):
                logger.warning(
                    "ElevenLabs quota/billing error — falling back to gTTS. (%s)", exc
                )
            else:
                logger.error("ElevenLabs error: %s — falling back to gTTS.", exc)
    else:
        logger.warning(
            "ElevenLabs API key or voice ID not configured — using gTTS fallback."
        )

    # --- gTTS fallback ---
    return _synthesize_gtts(text, path)


def _synthesize_elevenlabs(text: str, path: str) -> str:
    """Synthesize using the ElevenLabs SDK (v1.x client)."""
    from elevenlabs.client import ElevenLabs  # type: ignore

    client = ElevenLabs(api_key=config.ELEVENLABS_API_KEY)

    logger.info(
        "Synthesizing via ElevenLabs | voice=%s | model=%s | ~%d words",
        config.DEFAULT_VOICE_ID,
        _ELEVENLABS_MODEL,
        len(text.split()),
    )

    audio_stream = client.text_to_speech.convert(
        text=text,
        voice_id=config.DEFAULT_VOICE_ID,
        model_id=_ELEVENLABS_MODEL,
    )

    with open(path, "wb") as f:
        for chunk in audio_stream:
            if chunk:
                f.write(chunk)

    logger.info("ElevenLabs audio saved: %s", path)
    return path


def _synthesize_gtts(text: str, path: str) -> str:
    """Synthesize using gTTS (Google Text-to-Speech, free tier)."""
    try:
        from gtts import gTTS  # type: ignore
    except ImportError:
        raise RuntimeError(
            "Neither ElevenLabs nor gTTS is available. "
            "Install gTTS: pip install gTTS"
        )

    logger.info(
        "Synthesizing via gTTS (fallback) | ~%d words", len(text.split())
    )

    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(path)

    logger.info("gTTS audio saved: %s", path)
    return path
