from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from src.config import MAX_QUOTES
from src.phase2_theme_analysis.groq_client import chat_completion
from src.phase2_theme_analysis.theme_engine import Theme, _format_reviews_block
from src.phase1_data_ingestion.csv_loader import ReviewRecord
from src.phase1_data_ingestion.pii_scrubber import scrub_text

QUOTE_SYSTEM_PROMPT = (
    "You are a product analyst. From the provided reviews, extract exactly "
    "{max_quotes} real user quotes that best represent the top themes. Quotes "
    "must be verbatim excerpts (may be trimmed for length). No PII allowed."
)

QUOTE_USER_PROMPT = """\
Top themes:
{themes_json}

Reviews:
{reviews_block}

Return JSON:
{{
  "quotes": [
    {{
      "text": "<verbatim quote, max 50 words>",
      "theme": "<matching theme name>",
      "star_rating": <1-5>
    }}
  ]
}}

Rules:
- Exactly {max_quotes} quotes.
- Each quote must come from a different review.
- Each quote must map to one of the top themes listed above.
- Do not include any personally identifiable information."""


class Quote(BaseModel):
    text: str
    theme: str
    star_rating: int


def _parse_quotes(data: dict[str, Any]) -> list[Quote]:
    """Parse and validate quotes from LLM JSON output."""
    raw_quotes = data.get("quotes", [])
    quotes: list[Quote] = []
    for q in raw_quotes:
        quote = Quote(**q)
        quote = quote.model_copy(update={"text": scrub_text(quote.text)})
        quotes.append(quote)

    return quotes[:MAX_QUOTES]


def extract_quotes(
    themes: list[Theme],
    reviews: list[ReviewRecord],
) -> list[Quote]:
    """
    Extract real user quotes that represent the given themes.

    Uses a Groq LLM call with the top themes and full review list.
    Post-scrubs each quote through the PII scrubber.
    """
    if not themes or not reviews:
        return []

    themes_json = json.dumps(
        [{"name": t.name, "description": t.description, "sentiment": t.sentiment} for t in themes],
        indent=2,
    )

    reviews_block = _format_reviews_block(reviews)

    system_prompt = QUOTE_SYSTEM_PROMPT.format(max_quotes=MAX_QUOTES)
    user_prompt = QUOTE_USER_PROMPT.format(
        themes_json=themes_json,
        reviews_block=reviews_block,
        max_quotes=MAX_QUOTES,
    )

    result = chat_completion(system_prompt, user_prompt, temperature=0.3)
    return _parse_quotes(result)
