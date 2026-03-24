"""
UI-agnostic pipeline orchestrator.

Connects phases 1-4 into a single callable that the Streamlit app
(or any other interface) can invoke.
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.phase1_data_ingestion.csv_loader import ReviewRecord, load_reviews_from_bytes
from src.phase1_data_ingestion.pii_scrubber import scrub_reviews
from src.phase2_theme_analysis.theme_engine import Theme, analyze_themes, get_top_themes
from src.phase2_theme_analysis.quote_extractor import Quote, extract_quotes
from src.phase3_weekly_pulse.generator import PulseResult, generate_weekly_pulse
from src.phase4_fee_explainer.explainer import FeeExplanation, explain_fee_scenario

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when a pipeline stage fails."""


def run_pipeline(
    csv_bytes: bytes,
    weeks: int = 8,
    fee_scenario: str = "Mutual Fund Exit Load",
) -> tuple[PulseResult, FeeExplanation]:
    """
    Execute the full analysis pipeline end-to-end.

    Steps:
      1. Load and validate CSV reviews
      2. Scrub PII from review content
      3. Analyze themes via Groq LLM
      4. Extract representative quotes via Groq LLM
      5. Generate the weekly pulse note via Groq LLM
      6. Generate the fee explanation via Groq LLM

    Returns a (PulseResult, FeeExplanation) tuple.
    Raises PipelineError with context if any stage fails.
    """
    current_date = datetime.now().strftime("%Y-%m-%d")

    # --- Stage 1: Data Ingestion ---
    logger.info("Stage 1: Loading and validating CSV")
    reviews = load_reviews_from_bytes(csv_bytes, weeks=weeks)
    if not reviews:
        raise PipelineError(
            "No reviews found in the selected date range. "
            "Try increasing the week window or uploading a different CSV."
        )
    logger.info("Loaded %d reviews", len(reviews))

    # --- Stage 2: PII Scrubbing ---
    logger.info("Stage 2: Scrubbing PII")
    cleaned_reviews = scrub_reviews(reviews)

    # --- Stage 3: Theme Analysis ---
    logger.info("Stage 3: Analyzing themes")
    all_themes = analyze_themes(cleaned_reviews)
    top_themes = get_top_themes(all_themes)
    if not top_themes:
        raise PipelineError("Theme analysis returned no themes.")
    logger.info("Found %d themes, top %d selected", len(all_themes), len(top_themes))

    # --- Stage 4: Quote Extraction ---
    logger.info("Stage 4: Extracting quotes")
    quotes = extract_quotes(top_themes, cleaned_reviews)

    # --- Stage 5: Weekly Pulse Generation ---
    logger.info("Stage 5: Generating weekly pulse")
    avg_rating = sum(r.score for r in reviews) / len(reviews)
    pulse = generate_weekly_pulse(
        themes=top_themes,
        quotes=quotes,
        total_reviews=len(reviews),
        week_end_date=current_date,
        avg_rating=round(avg_rating, 2),
    )

    # --- Stage 6: Fee Explanation ---
    logger.info("Stage 6: Generating fee explanation")
    fee = explain_fee_scenario(fee_scenario, current_date=current_date)

    logger.info("Pipeline complete")
    return pulse, fee
