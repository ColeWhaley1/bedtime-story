"""
Save generated stories as .txt files on disk.

Files land in config.STORIES_DIR (default: ~/Desktop/Bedtime Stories/).
Each file is named by timestamp and a slug of the story themes so they're
easy to browse without opening them.
"""
import logging
import os
import re
import time

import config
from intent_parser import StoryIntent

logger = logging.getLogger(__name__)


def _theme_slug(themes: str, max_chars: int = 40) -> str:
    """Turn a themes string into a safe, readable filename fragment."""
    slug = re.sub(r"[^\w\s-]", "", themes.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:max_chars]


def save(story_text: str, intent: StoryIntent) -> str | None:
    """
    Write *story_text* to a .txt file in config.STORIES_DIR.

    Returns the saved file path on success, or None if saving failed
    (never raises — saving is best-effort and shouldn't interrupt playback).
    """
    try:
        os.makedirs(config.STORIES_DIR, exist_ok=True)

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        slug = _theme_slug(intent.themes)
        filename = f"{timestamp}_{slug}.txt" if slug else f"{timestamp}.txt"
        filepath = os.path.join(config.STORIES_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(f"Themes: {intent.themes}\n")
            fh.write(f"Length: ~{intent.word_count} words\n")
            fh.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            fh.write("\n" + "-" * 60 + "\n\n")
            fh.write(story_text)

        logger.info("Story saved to %s", filepath)
        return filepath

    except Exception as exc:
        logger.warning("Could not save story: %s", exc)
        return None
