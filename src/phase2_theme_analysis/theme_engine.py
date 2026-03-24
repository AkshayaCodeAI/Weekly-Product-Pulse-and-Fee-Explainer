from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

from src.config import MAX_THEMES, TOP_THEMES
from src.phase2_theme_analysis.groq_client import chat_completion
from src.phase1_data_ingestion.csv_loader import ReviewRecord

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100

THEME_SYSTEM_PROMPT = (
    "You are a product analyst. Analyze the provided app reviews and group them "
    "into at most {max_themes} distinct themes. Rank each theme by frequency and "
    "sentiment impact. Return JSON only."
)

THEME_USER_PROMPT = """\
Here are {n} recent user reviews for the Groww app (a stock trading and \
mutual fund platform):

{reviews_block}

Return a JSON object with this exact structure:
{{
  "themes": [
    {{
      "rank": 1,
      "name": "<short theme name>",
      "description": "<1-sentence summary>",
      "sentiment": "positive|negative|mixed",
      "review_count": <number>,
      "sample_review_ids": ["id1", "id2"]
    }}
  ]
}}

Rules:
- Maximum {max_themes} themes.
- Rank by combined frequency and negative-sentiment weight.
- Do not include any personally identifiable information."""

MERGE_SYSTEM_PROMPT = (
    "You are a product analyst. Merge the following theme lists from multiple "
    "batches of reviews into a single consolidated list of at most {max_themes} "
    "themes, ranked by frequency and sentiment impact. Return JSON only."
)

MERGE_USER_PROMPT = """\
Below are theme analyses from {batch_count} batches of Groww app reviews. \
Merge them into a single list of at most {max_themes} ranked themes.

{batch_themes_block}

Return a JSON object with this exact structure:
{{
  "themes": [
    {{
      "rank": 1,
      "name": "<short theme name>",
      "description": "<1-sentence summary>",
      "sentiment": "positive|negative|mixed",
      "review_count": <number>,
      "sample_review_ids": ["id1", "id2"]
    }}
  ]
}}"""


class Theme(BaseModel):
    rank: int
    name: str
    description: str
    sentiment: str
    review_count: int
    sample_review_ids: list[str] = []


def _format_reviews_block(reviews: list[ReviewRecord]) -> str:
    """Format reviews into a numbered text block for the prompt."""
    lines = []
    for i, r in enumerate(reviews, 1):
        lines.append(f"[{r.review_id}] (score={r.score}) {r.content}")
    return "\n".join(lines)


def _parse_themes(data: dict[str, Any]) -> list[Theme]:
    """Parse and validate the themes list from LLM JSON output."""
    raw_themes = data.get("themes", [])
    themes: list[Theme] = []
    for t in raw_themes:
        themes.append(Theme(**t))

    themes.sort(key=lambda t: t.rank)

    if len(themes) > MAX_THEMES:
        themes = themes[:MAX_THEMES]

    return themes


def _analyze_batch(reviews: list[ReviewRecord]) -> list[Theme]:
    """Run theme analysis on a single batch of reviews."""
    reviews_block = _format_reviews_block(reviews)

    system_prompt = THEME_SYSTEM_PROMPT.format(max_themes=MAX_THEMES)
    user_prompt = THEME_USER_PROMPT.format(
        n=len(reviews),
        reviews_block=reviews_block,
        max_themes=MAX_THEMES,
    )

    result = chat_completion(system_prompt, user_prompt, temperature=0.3)
    return _parse_themes(result)


def _merge_theme_batches(batch_results: list[list[Theme]]) -> list[Theme]:
    """Merge multiple batch theme lists into one via a second LLM call."""
    blocks = []
    for i, themes in enumerate(batch_results, 1):
        theme_dicts = [t.model_dump() for t in themes]
        blocks.append(f"Batch {i}:\n{json.dumps(theme_dicts, indent=2)}")

    batch_themes_block = "\n\n".join(blocks)

    system_prompt = MERGE_SYSTEM_PROMPT.format(max_themes=MAX_THEMES)
    user_prompt = MERGE_USER_PROMPT.format(
        batch_count=len(batch_results),
        max_themes=MAX_THEMES,
        batch_themes_block=batch_themes_block,
    )

    result = chat_completion(system_prompt, user_prompt, temperature=0.3)
    return _parse_themes(result)


def analyze_themes(reviews: list[ReviewRecord]) -> list[Theme]:
    """
    Group reviews into ranked themes (max MAX_THEMES).

    If the review set exceeds _BATCH_SIZE, chunks into batches
    and merges the per-batch themes with a second LLM call.

    Returns the full list of themes sorted by rank.
    """
    if not reviews:
        return []

    if len(reviews) <= _BATCH_SIZE:
        return _analyze_batch(reviews)

    batches = [
        reviews[i : i + _BATCH_SIZE]
        for i in range(0, len(reviews), _BATCH_SIZE)
    ]

    logger.info("Splitting %d reviews into %d batches", len(reviews), len(batches))

    batch_results = [_analyze_batch(batch) for batch in batches]
    return _merge_theme_batches(batch_results)


def get_top_themes(themes: list[Theme], n: int | None = None) -> list[Theme]:
    """Return the top N themes from a ranked list."""
    n = n or TOP_THEMES
    return themes[:n]
