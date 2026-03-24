from __future__ import annotations

import re

from src.phase1_data_ingestion.csv_loader import ReviewRecord

# Ordered so more-specific patterns match first and avoid false positives.
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Email addresses
    (re.compile(r"[\w.-]+@[\w.-]+\.\w+"), "[EMAIL]"),
    # Indian PAN (e.g. ABCDE1234F) — before phone to avoid partial matches
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[ID]"),
    # Indian phone: +91 prefix or starting with 6-9, exactly 10 digits
    (re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b"), "[PHONE]"),
    # International phone numbers (broad catch-all, run after IN-specific)
    (re.compile(r"\+?\d{1,3}[\s-]?\d{6,14}\b"), "[PHONE]"),
    # Aadhaar-style 12-digit numbers (XXXX XXXX XXXX or XXXX-XXXX-XXXX)
    (re.compile(r"\b\d{4}[\s-]\d{4}[\s-]\d{4}\b"), "[ID]"),
]


def scrub_text(text: str) -> str:
    """Remove PII from a single text string using regex patterns."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def scrub_reviews(reviews: list[ReviewRecord]) -> list[ReviewRecord]:
    """
    Pre-LLM pass: return new ReviewRecord list with PII removed from content.
    Original objects are not mutated.
    """
    return [
        review.model_copy(update={"content": scrub_text(review.content)})
        for review in reviews
    ]


def scrub_output(text: str) -> str:
    """
    Post-LLM pass: scrub any PII that may have leaked into generated output.
    Same regex set as pre-LLM pass.
    """
    return scrub_text(text)
