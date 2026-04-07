"""
Story generation via the Google Gemini API.

Generates an original adult epic fantasy story using Gemini, streamed to
handle long outputs without HTTP timeouts.
"""
import logging

import google.generativeai as genai

import config
from intent_parser import StoryIntent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a master storyteller in the tradition of George R.R. Martin and "
    "Andrzej Sapkowski. Write original adult epic fantasy stories with morally "
    "complex characters, political intrigue, vivid world-building, and rich "
    "atmospheric prose. Stories should feel cinematic and immersive. End each "
    "story at a natural resolution point — not a cliffhanger — that feels "
    "satisfying and complete, like the closing scene of a great episode. "
    "Avoid explicit sexual content."
)

USER_PROMPT_TEMPLATE = (
    "Write a {word_count}-word epic fantasy story featuring: {themes}. "
    "End at a natural, satisfying resolution."
)


def generate(intent: StoryIntent) -> str:
    """
    Call the Gemini API and return the complete story text.
    Uses streaming so long stories don't hit HTTP timeouts.
    Raises on API errors.
    """
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=config.GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        word_count=intent.word_count,
        themes=intent.themes,
    )

    logger.info(
        "Generating %d-word story | themes: %r | model: %s",
        intent.word_count,
        intent.themes,
        config.GEMINI_MODEL,
    )

    story_text = ""

    try:
        for chunk in model.generate_content(user_prompt, stream=True):
            if chunk.text:
                story_text += chunk.text

    except Exception as exc:
        logger.error("Gemini API error: %s", exc)
        raise

    word_count = len(story_text.split())
    logger.info("Story generated: ~%d words.", word_count)
    return story_text.strip()
