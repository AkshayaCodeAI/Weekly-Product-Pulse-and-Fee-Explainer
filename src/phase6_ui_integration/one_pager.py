"""
One-pager visual renderer.

Takes pipeline output (PulseResult + FeeExplanation) and renders
the complete one-page report in the Streamlit main area.
"""

from __future__ import annotations

import streamlit as st

from src.phase3_weekly_pulse.generator import PulseResult
from src.phase4_fee_explainer.explainer import FeeExplanation
from src.phase6_ui_integration.components import (
    render_action_ideas,
    render_fee_bullets,
    render_metric_cards,
    render_quote,
    render_source_links,
    render_theme_card,
)


def render_one_pager(pulse: PulseResult, fee: FeeExplanation) -> None:
    """Render the full one-pager report in the Streamlit main area."""

    # --- Header ---
    st.title(f"Weekly Pulse — Week of {pulse.week_ending}")
    st.caption(f"{pulse.total_reviews:,} reviews analyzed")

    # --- Metric Cards ---
    top_theme_name = pulse.themes[0]["name"] if pulse.themes else "N/A"
    render_metric_cards(pulse.total_reviews, top_theme_name, pulse.avg_rating)

    st.divider()

    # --- Theme Breakdown ---
    st.header("Theme Breakdown")
    for i, theme in enumerate(pulse.themes):
        highlighted = i < 3
        render_theme_card(theme, highlighted=highlighted)

    st.divider()

    # --- User Quotes ---
    st.header("User Quotes")
    for i, quote in enumerate(pulse.quotes, 1):
        render_quote(quote, i)

    st.divider()

    # --- Weekly Note ---
    st.header("Weekly Note")
    st.markdown(pulse.weekly_note)
    st.caption(f"Word count: {pulse.word_count}")

    st.divider()

    # --- Action Ideas ---
    st.header("Action Ideas")
    render_action_ideas(pulse.action_ideas)

    st.divider()

    # --- Fee Explainer ---
    st.header("Fee Explainer")
    st.subheader(f"Scenario: {fee.scenario}")
    render_fee_bullets(fee.bullets)

    st.markdown("**Sources:**")
    source_links = [{"title": sl.title, "url": sl.url} for sl in fee.source_links]
    render_source_links(source_links, fee.last_checked)
