"""
Parse a voice transcription into a story length (word count) and theme string.

Length keywords:
  "short" / "quick"         → STORY_LENGTH_SHORT  (500 words)
  "long" / "longer"         → STORY_LENGTH_LONG   (1500 words)
  default                   → STORY_LENGTH_MEDIUM (1000 words)

Everything remaining after stripping length words is treated as the theme.
"""
import re
from dataclasses import dataclass

import config


@dataclass
class StoryIntent:
    word_count: int
    themes: str


_SHORT_PATTERNS = re.compile(r"\b(short|quick|brief)\b", re.IGNORECASE)
_LONG_PATTERNS  = re.compile(r"\b(long|longer|epic|extended)\b", re.IGNORECASE)

# Strip wake word prefix — Whisper may transcribe it as "hey storyteller",
# "hey story teller", "storyteller", etc.
_WAKE_WORD = re.compile(
    r"^(hey\s+story[\s\-]?teller|hey\s+storyteller|storyteller)[,\s]*",
    re.IGNORECASE,
)

# Filler phrases to strip from the transcription before extracting themes
_FILLER = re.compile(
    r"\b(tell me|give me|i want|i'd like|please|a story about|make it|"
    r"something about|something|a story|story)\b",
    re.IGNORECASE,
)

# Strip residual leading "about" / "a about" left after filler removal
_LEADING_ABOUT = re.compile(r"^\s*(a\s+)?about\s*", re.IGNORECASE)


def parse(transcription: str) -> StoryIntent:
    """
    Parse a raw transcription string into word count + theme description.

    Examples:
        "a short story about a betrayed king"
            → StoryIntent(word_count=500, themes="a betrayed king")

        "something long about two noble houses at war"
            → StoryIntent(word_count=1500, themes="two noble houses at war")

        "dragons and political intrigue in a dying empire"
            → StoryIntent(word_count=1000, themes="dragons and political intrigue in a dying empire")
    """
    text = transcription.strip()

    # Strip wake word prefix before any other processing
    text = _WAKE_WORD.sub("", text).strip()

    # Determine length
    if _SHORT_PATTERNS.search(text):
        word_count = config.STORY_LENGTH_SHORT
    elif _LONG_PATTERNS.search(text):
        word_count = config.STORY_LENGTH_LONG
    else:
        word_count = config.STORY_LENGTH_MEDIUM

    # Strip length keywords
    text = _SHORT_PATTERNS.sub("", text)
    text = _LONG_PATTERNS.sub("", text)

    # Strip filler phrases
    text = _FILLER.sub("", text)

    # Strip residual leading "about" / "a about" left after filler removal
    text = _LEADING_ABOUT.sub("", text)

    # Clean up extra spaces / punctuation
    text = re.sub(r"\s{2,}", " ", text).strip(" ,.")

    # Fall back to a generic theme if nothing meaningful remains
    if len(text) < 3:
        text = "a hero's journey through a dangerous and corrupt kingdom"

    return StoryIntent(word_count=word_count, themes=text)
