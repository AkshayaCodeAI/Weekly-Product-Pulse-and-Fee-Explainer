from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.config import PULSE_WORD_LIMIT
from src.phase2_theme_analysis.groq_client import chat_completion
from src.phase2_theme_analysis.theme_engine import Theme
from src.phase2_theme_analysis.quote_extractor import Quote
from src.phase1_data_ingestion.pii_scrubber import scrub_output

NOTE_SYSTEM_PROMPT = (
    "You are a product communications writer. Write a concise weekly pulse note "
    "for the Groww product team. Tone: professional, data-informed, constructive."
)

NOTE_USER_PROMPT = """\
Week ending: {week_end_date}
Review count analyzed: {total_reviews}

Top themes:
{themes_summary}

Representative quotes:
{quotes_block}

Write a weekly note (MAXIMUM {word_limit} words) that:
1. Opens with the overall sentiment trend.
2. Highlights the top 3 themes with brief context.
3. Includes the 3 user quotes inline.
4. Ends with exactly 3 specific, actionable ideas for the product team.

Return JSON:
{{
  "weekly_note": "<the {word_limit}-word note>",
  "action_ideas": [
    "<action 1>",
    "<action 2>",
    "<action 3>"
  ],
  "word_count": <number>
}}"""


class PulseResult(BaseModel):
    weekly_note: str
    action_ideas: list[str]
    word_count: int
    week_ending: str
    total_reviews: int
    themes: list[dict]
    quotes: list[dict]
    avg_rating: float


def _build_themes_summary(themes: list[Theme]) -> str:
    """Format themes into a readable summary for the prompt."""
    lines = []
    for t in themes:
        lines.append(
            f"{t.rank}. {t.name} ({t.sentiment}) — {t.description} "
            f"[{t.review_count} reviews]"
        )
    return "\n".join(lines)


def _build_quotes_block(quotes: list[Quote]) -> str:
    """Format quotes into a readable block for the prompt."""
    lines = []
    for i, q in enumerate(quotes, 1):
        lines.append(f'{i}. "{q.text}" (Rating: {q.star_rating}/5, Theme: {q.theme})')
    return "\n".join(lines)


def _parse_pulse_response(data: dict[str, Any]) -> tuple[str, list[str], int]:
    """Extract the weekly note, action ideas, and word count from LLM JSON."""
    weekly_note = data.get("weekly_note", "")
    action_ideas = data.get("action_ideas", [])
    word_count = data.get("word_count", len(weekly_note.split()))

    weekly_note = scrub_output(weekly_note)
    action_ideas = [scrub_output(idea) for idea in action_ideas]

    return weekly_note, action_ideas, word_count


def generate_weekly_pulse(
    themes: list[Theme],
    quotes: list[Quote],
    total_reviews: int,
    week_end_date: str | None = None,
    avg_rating: float = 0.0,
) -> PulseResult:
    """
    Generate the weekly pulse note and action ideas from themes and quotes.

    Uses a Groq LLM call with the weekly note prompt template.
    Post-scrubs the output through the PII scrubber.
    """
    if not week_end_date:
        week_end_date = datetime.now().strftime("%Y-%m-%d")

    themes_summary = _build_themes_summary(themes)
    quotes_block = _build_quotes_block(quotes)

    user_prompt = NOTE_USER_PROMPT.format(
        week_end_date=week_end_date,
        total_reviews=total_reviews,
        themes_summary=themes_summary,
        quotes_block=quotes_block,
        word_limit=PULSE_WORD_LIMIT,
    )

    result = chat_completion(
        NOTE_SYSTEM_PROMPT, user_prompt, temperature=0.5, max_tokens=2048
    )

    weekly_note, action_ideas, word_count = _parse_pulse_response(result)

    return PulseResult(
        weekly_note=weekly_note,
        action_ideas=action_ideas,
        word_count=word_count,
        week_ending=week_end_date,
        total_reviews=total_reviews,
        themes=[t.model_dump() for t in themes],
        quotes=[q.model_dump() for q in quotes],
        avg_rating=avg_rating,
    )
