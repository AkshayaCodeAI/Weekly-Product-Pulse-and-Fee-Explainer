from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.config import FEE_BULLET_LIMIT, FEE_SOURCE_LINKS
from src.phase2_theme_analysis.groq_client import chat_completion

logger = logging.getLogger(__name__)

FEE_SYSTEM_PROMPT = (
    "You are a neutral financial information assistant. Explain fee structures "
    "using only verified facts. Never make recommendations. Never compare "
    "products. Maintain a strictly informational tone."
)

FEE_USER_PROMPT = """\
Scenario: {scenario_description}

Generate a structured explanation with these rules:
1. Maximum {bullet_limit} bullet points.
2. Each bullet must be a factual statement about the fee/charge.
3. Include exactly 2 official source links from: {source_links_list}
4. Add a "Last checked: {current_date}" line at the end.
5. No recommendations, no comparisons, no opinions.

Return JSON:
{{
  "scenario": "<scenario name>",
  "bullets": [
    "<bullet 1>",
    "<bullet 2>"
  ],
  "source_links": [
    {{"title": "<display text>", "url": "<url>"}}
  ],
  "last_checked": "YYYY-MM-DD"
}}"""

STRICTER_ADDENDUM = (
    "\n\nIMPORTANT: Your previous response contained recommendation or "
    "comparative language. Rewrite using ONLY neutral, factual statements. "
    "Do NOT use words like: should, recommend, consider, best, worst, "
    "better, cheaper, prefer, suggest, ideal."
)

_TONE_VIOLATIONS: list[re.Pattern[str]] = [
    re.compile(r"\byou should\b", re.IGNORECASE),
    re.compile(r"\bwe recommend\b", re.IGNORECASE),
    re.compile(r"\bconsider\b", re.IGNORECASE),
    re.compile(r"\bbetter than\b", re.IGNORECASE),
    re.compile(r"\bcheaper than\b", re.IGNORECASE),
    re.compile(r"\bworst\b", re.IGNORECASE),
    re.compile(r"\bbest\b", re.IGNORECASE),
    re.compile(r"\bprefer\b", re.IGNORECASE),
    re.compile(r"\bsuggest\b", re.IGNORECASE),
    re.compile(r"\bideal\b", re.IGNORECASE),
]


class SourceLink(BaseModel):
    title: str
    url: str


class FeeExplanation(BaseModel):
    scenario: str
    bullets: list[str]
    source_links: list[SourceLink]
    last_checked: str


def _format_source_links_list() -> str:
    """Format available source links for prompt injection."""
    return "\n".join(
        f"- {link['title']}: {link['url']}" for link in FEE_SOURCE_LINKS
    )


def _check_tone(text: str) -> list[str]:
    """Return list of tone-violation phrases found in text."""
    violations = []
    for pattern in _TONE_VIOLATIONS:
        match = pattern.search(text)
        if match:
            violations.append(match.group())
    return violations


def _has_tone_violations(result: FeeExplanation) -> bool:
    """Check if any bullet or the scenario text has tone violations."""
    all_text = " ".join(result.bullets) + " " + result.scenario
    return len(_check_tone(all_text)) > 0


def _parse_fee_response(data: dict[str, Any], current_date: str) -> FeeExplanation:
    """Parse and validate the fee explanation from LLM JSON output."""
    scenario = data.get("scenario", "")
    bullets = data.get("bullets", [])[:FEE_BULLET_LIMIT]
    raw_links = data.get("source_links", [])[:2]
    last_checked = data.get("last_checked", current_date)

    source_links = [SourceLink(**link) for link in raw_links]

    return FeeExplanation(
        scenario=scenario,
        bullets=bullets,
        source_links=source_links,
        last_checked=last_checked,
    )


def explain_fee_scenario(
    scenario_description: str,
    current_date: str | None = None,
) -> FeeExplanation:
    """
    Generate a neutral fee explanation for the given scenario.

    Uses Groq LLM with tone guardrails:
    - First pass generates the explanation.
    - If tone violations are detected, retries once with a stricter prompt.
    - Bullets capped at FEE_BULLET_LIMIT (6).
    - Exactly 2 official source links included.
    - "Last checked" timestamp auto-injected.
    """
    if not current_date:
        current_date = datetime.now().strftime("%Y-%m-%d")

    source_links_list = _format_source_links_list()

    user_prompt = FEE_USER_PROMPT.format(
        scenario_description=scenario_description,
        bullet_limit=FEE_BULLET_LIMIT,
        source_links_list=source_links_list,
        current_date=current_date,
    )

    data = chat_completion(FEE_SYSTEM_PROMPT, user_prompt, temperature=0.5)
    result = _parse_fee_response(data, current_date)

    if _has_tone_violations(result):
        logger.warning("Tone violations detected, retrying with stricter prompt")
        stricter_prompt = user_prompt + STRICTER_ADDENDUM
        data = chat_completion(FEE_SYSTEM_PROMPT, stricter_prompt, temperature=0.3)
        result = _parse_fee_response(data, current_date)

    return result
