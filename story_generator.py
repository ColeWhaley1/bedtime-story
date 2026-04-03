"""
Story generation via the Anthropic API.

Generates an original adult epic fantasy story using Claude, streamed to
handle long outputs without HTTP timeouts.
"""
import logging

import anthropic

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

# Leave generous headroom: 1500 words ≈ 2000 tokens; 8192 is plenty
_MAX_OUTPUT_TOKENS = 8192


def generate(intent: StoryIntent) -> str:
    """
    Call the Anthropic API and return the complete story text.
    Uses streaming so long stories don't hit HTTP timeouts.
    Raises on API errors.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        word_count=intent.word_count,
        themes=intent.themes,
    )

    logger.info(
        "Generating %d-word story | themes: %r | model: %s",
        intent.word_count,
        intent.themes,
        config.CLAUDE_MODEL,
    )

    story_text = ""

    try:
        with client.messages.stream(
            model=config.CLAUDE_MODEL,
            max_tokens=_MAX_OUTPUT_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text_chunk in stream.text_stream:
                story_text += text_chunk

        # Verify the model finished naturally
        final = stream.get_final_message()
        if final.stop_reason not in ("end_turn", "stop_sequence"):
            logger.warning(
                "Unexpected stop_reason=%r — story may be truncated.", final.stop_reason
            )

    except anthropic.APIError as exc:
        logger.error("Anthropic API error: %s", exc)
        raise

    word_count = len(story_text.split())
    logger.info("Story generated: ~%d words.", word_count)
    return story_text.strip()
