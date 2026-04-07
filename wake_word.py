"""
Offline wake-word detection using openWakeWord.

Runs on a background thread, continuously reading 80 ms chunks from the USB
mic and feeding them to the openWakeWord model. When the score exceeds
WAKEWORD_THRESHOLD, it fires a callback on the main thread.

Detection is paused during recording/playback to avoid false triggers.
"""
import audioop
import logging
import threading
import time
from typing import Callable, Optional

import numpy as np
import pyaudio

import config
import voice_input

logger = logging.getLogger(__name__)

CHUNK_MS = 80
CHUNK_SAMPLES = int(config.RECORD_SAMPLE_RATE * CHUNK_MS / 1000)  # 1280 @ 16kHz


class WakeWordDetector:
    def __init__(self, on_detected: Callable[[], None]):
        self._callback = on_detected
        self._paused = threading.Event()   # set = detection paused
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._model = None

    # -----------------------------------------------------------------------
    # Model loading
    # -----------------------------------------------------------------------

    def _load_model(self):
        """Lazily load the openWakeWord model."""
        try:
            from openwakeword.model import Model as OWWModel
        except ImportError:
            logger.error(
                "openwakeword not installed — run: pip install openwakeword"
            )
            return None

        model_spec = config.WAKEWORD_MODEL
        logger.info("Loading wake-word model: %s …", model_spec)
        try:
            model = OWWModel(wakeword_models=[model_spec], inference_framework="tflite")
            logger.info("Wake-word model loaded.")
            return model
        except Exception as exc:
            logger.error("Failed to load wake-word model %r: %s", model_spec, exc)
            return None

    # -----------------------------------------------------------------------
    # Audio loop
    # -----------------------------------------------------------------------

    def _run(self):
        self._model = self._load_model()
        if self._model is None:
            logger.error("Wake-word detection disabled (model unavailable).")
            return

        pa = voice_input.get_pyaudio()
        device_index = voice_input.get_usb_device_index()

        stream_kwargs = dict(
            format=pyaudio.paInt16,
            channels=1,
            rate=config.RECORD_SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SAMPLES,
        )
        if device_index is not None:
            stream_kwargs["input_device_index"] = device_index

        logger.info("Wake-word detection active. Say '%s' to trigger.", config.WAKEWORD_MODEL)

        stream = None
        try:
            while not self._stop.is_set():
                if self._paused.is_set():
                    if stream is not None:
                        stream.stop_stream()
                        stream.close()
                        stream = None
                    time.sleep(0.1)
                    continue

                if stream is None:
                    try:
                        stream = pa.open(**stream_kwargs)
                    except OSError as exc:
                        logger.error("Wake-word: could not open mic: %s", exc)
                        time.sleep(1)
                        continue

                try:
                    raw = stream.read(CHUNK_SAMPLES, exception_on_overflow=False)
                except OSError as exc:
                    logger.warning("Mic read error: %s", exc)
                    stream.stop_stream()
                    stream.close()
                    stream = None
                    time.sleep(0.05)
                    continue

                # Resample from mic rate (44100) down to 16000 Hz that
                # openWakeWord requires, then convert to int16 numpy array
                resampled, _ = audioop.ratecv(
                    raw, 2, 1, config.RECORD_SAMPLE_RATE, 16000, None
                )
                audio_chunk = np.frombuffer(resampled, dtype=np.int16)

                try:
                    predictions = self._model.predict(audio_chunk)
                except Exception as exc:
                    logger.debug("WW predict error: %s", exc)
                    continue

                for model_name, score in predictions.items():
                    if score >= config.WAKEWORD_THRESHOLD:
                        logger.info(
                            "Wake word detected! model=%r score=%.3f", model_name, score
                        )
                        # Reset model scores to avoid repeated triggers
                        try:
                            self._model.reset()
                        except Exception:
                            pass
                        self._callback()
                        break
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()

    # -----------------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------------

    def start(self):
        """Start the detection loop in a daemon thread."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="WakeWord")
        self._thread.start()

    def pause(self):
        """Pause detection (during recording / playback)."""
        self._paused.set()
        logger.debug("Wake-word detection paused.")

    def resume(self):
        """Resume detection."""
        self._paused.clear()
        logger.debug("Wake-word detection resumed.")

    def stop(self):
        """Stop the detection thread."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
