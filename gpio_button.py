"""
Physical GPIO button monitor (fallback trigger).

Short press (< 2 s): trigger the story pipeline.
Long press (>= 2 s): stop current playback.

Uses gpiozero with 50 ms debounce. Runs in the main thread via gpiozero's
background callback threads — no extra thread needed here.
"""
import logging
import threading
from typing import Callable, Optional

import config

logger = logging.getLogger(__name__)


class GPIOButton:
    def __init__(
        self,
        on_short_press: Callable[[], None],
        on_long_press: Callable[[], None],
    ):
        self._on_short = on_short_press
        self._on_long = on_long_press
        self._button = None
        self._press_time: float = 0.0

    def start(self):
        """Initialise the GPIO button. Silently skips if gpiozero is unavailable."""
        try:
            from gpiozero import Button
            import time as _time

            btn = Button(
                config.GPIO_BUTTON_PIN,
                hold_time=2,
                bounce_time=0.05,
                pull_up=True,
            )

            def _pressed():
                import time as t
                self._press_time = t.monotonic()

            def _released():
                import time as t
                held = t.monotonic() - self._press_time
                if held < 2.0:
                    logger.info("Button: short press (%.2f s) — triggering story.", held)
                    self._on_short()

            def _held():
                logger.info("Button: long press — stopping playback.")
                self._on_long()

            btn.when_pressed = _pressed
            btn.when_released = _released
            btn.when_held = _held

            self._button = btn
            logger.info(
                "GPIO button active on pin %d (short=story, long=stop).",
                config.GPIO_BUTTON_PIN,
            )

        except ImportError:
            logger.warning(
                "gpiozero not available — GPIO button disabled. "
                "(Install: pip install gpiozero)"
            )
        except Exception as exc:
            logger.warning("GPIO button init failed: %s", exc)

    def stop(self):
        """Release GPIO resources."""
        if self._button is not None:
            try:
                self._button.close()
            except Exception:
                pass
