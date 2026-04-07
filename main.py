"""
Bedtime Story — entry point.

Architecture
------------
Two daemon threads run in the background and share a single trigger Event:

  WakeWordDetector thread  — listens for "hey storyteller" (or configured model)
  GPIOButton callbacks     — fires on short button press

When either trigger fires the main loop runs the full pipeline:

  1. Pause wake-word detection
  2. Play chime to signal "listening"
  3. Record voice input from USB mic
  4. Transcribe with Whisper
  5. Parse intent (length + themes)
  6. Generate story via Anthropic API
  7. Synthesize speech via ElevenLabs (or gTTS)
  8. Play through Bluetooth speaker via mpv
  9. Clean up temp files
 10. Resume wake-word detection

A long button press at any point calls audio_player.stop().
All exceptions in the pipeline are caught — the app always returns to idle.
"""
import logging
import os
import signal
import threading
import time

# Configure logging before importing local modules
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

import audio_player
import config
import gpio_button
import intent_parser
import story_generator
import story_saver
import tts
import voice_input
import wake_word


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_trigger_event = threading.Event()   # set by wake word or button short press
_pipeline_active = threading.Event() # set while pipeline is running
_shutdown = threading.Event()        # set on SIGINT / SIGTERM


def _trigger_story():
    """Called from wake-word or button thread to fire the pipeline."""
    if not _pipeline_active.is_set():
        logger.info("Trigger received.")
        _trigger_event.set()
    else:
        logger.debug("Trigger ignored — pipeline already active.")


def _stop_playback():
    """Called from button long-press to stop current audio."""
    audio_player.stop()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _run_pipeline(ww_detector: wake_word.WakeWordDetector):
    """Execute one full story pipeline pass."""
    _pipeline_active.set()
    ww_detector.pause()
    time.sleep(0.4)  # Give ALSA time to fully release the mic stream

    audio_path: str | None = None

    try:
        # 1. Record voice — start immediately so we capture the full request
        #    ("Hey storyteller, tell me a story about …")
        logger.info("Pipeline: recording …")
        wav_path = voice_input.record()
        if not wav_path:
            logger.warning("Pipeline: no audio recorded — aborting.")
            return

        # 2. Transcribe
        transcription = voice_input.transcribe(wav_path)
        if not transcription:
            logger.warning("Pipeline: empty transcription — aborting.")
            return

        # 3. Parse intent
        intent = intent_parser.parse(transcription)
        logger.info(
            "Pipeline: intent → %d words | themes: %r",
            intent.word_count, intent.themes,
        )

        # 4. Chime confirms we understood the request and are now generating
        logger.info("Pipeline: playing chime …")
        audio_player.play_chime()

        # 5. Generate story
        logger.info("Pipeline: generating story …")
        story_text = story_generator.generate(intent)
        story_saver.save(story_text, intent)

        # 6. Synthesize
        logger.info("Pipeline: synthesizing audio …")
        audio_path = tts.synthesize(story_text)

        # 7. Play
        logger.info("Pipeline: playing story …")
        audio_player.play(audio_path)   # blocks until done (or stopped)
        audio_path = None               # play() deletes the file on completion

        logger.info("Pipeline: complete.")

    except Exception as exc:
        logger.exception("Pipeline error: %s", exc)

    finally:
        # Clean up temp file if play() was interrupted before it could delete it
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass

        _pipeline_active.clear()
        _trigger_event.clear()
        ww_detector.resume()
        logger.info("Idle — waiting for wake word or button press.")


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def _handle_signal(sig, _frame):
    logger.info("Received signal %s — shutting down …", sig)
    _shutdown.set()
    audio_player.stop()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info("=== Bedtime Story starting up ===")

    # Connect Bluetooth speaker
    audio_player.connect_bluetooth()

    # Verify required API keys
    if not config.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set in .env — story generation disabled.")
    if not config.ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not set — will use gTTS fallback.")

    # Warm up USB mic detection (logs device index at startup)
    voice_input.get_usb_device_index()

    # Set up wake-word detector
    ww_detector = wake_word.WakeWordDetector(on_detected=_trigger_story)
    ww_detector.start()

    # Set up GPIO button
    btn = gpio_button.GPIOButton(
        on_short_press=_trigger_story,
        on_long_press=_stop_playback,
    )
    btn.start()

    # Install signal handlers
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("Ready. Say the wake word or press the button.")

    # Main event loop
    while not _shutdown.is_set():
        triggered = _trigger_event.wait(timeout=0.5)
        if triggered and not _pipeline_active.is_set():
            _run_pipeline(ww_detector)

    # Graceful shutdown
    ww_detector.stop()
    btn.stop()
    logger.info("=== Bedtime Story stopped ===")


if __name__ == "__main__":
    main()
