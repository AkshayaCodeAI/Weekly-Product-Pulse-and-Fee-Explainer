"""Reusable Streamlit UI widgets for the Weekly Pulse application."""

from __future__ import annotations

import streamlit as st


SENTIMENT_COLORS = {
    "negative": "#FF4B4B",
    "positive": "#21C354",
    "mixed": "#FACA2B",
}

SENTIMENT_ICONS = {
    "negative": "\U0001f534",
    "positive": "\U0001f7e2",
    "mixed": "\U0001f7e1",
}


def render_metric_cards(total_reviews: int, top_theme_name: str, avg_rating: float) -> None:
    """Display three metric cards in a row: reviews, top theme, avg rating."""
    c1, c2, c3 = st.columns(3)
    c1.metric("Reviews Analyzed", f"{total_reviews:,}")
    c2.metric("Top Theme", top_theme_name)
    c3.metric("Avg Rating", f"{avg_rating:.1f} / 5")


def render_theme_card(theme: dict, highlighted: bool = False) -> None:
    """Render a single theme as an expandable card."""
    icon = SENTIMENT_ICONS.get(theme.get("sentiment", ""), "\u26aa")
    label = f"{theme['rank']}. {theme['name']} {icon}"
    color = SENTIMENT_COLORS.get(theme.get("sentiment", ""), "#888")

    if highlighted:
        st.markdown(
            f'<div style="border-left: 4px solid {color}; padding: 2px 12px; '
            f'margin-bottom: 4px;">'
            f'<strong>{label}</strong></div>',
            unsafe_allow_html=True,
        )
    with st.expander(label if not highlighted else f"Details: {theme['name']}", expanded=highlighted):
        st.write(theme.get("description", ""))
        st.caption(f"{theme.get('review_count', 0)} reviews | Sentiment: {theme.get('sentiment', 'N/A')}")


def render_quote(quote: dict, index: int) -> None:
    """Render a single user quote with star rating badge."""
    stars = "\u2605" * quote.get("star_rating", 0) + "\u2606" * (5 - quote.get("star_rating", 0))
    st.info(f'**Quote {index}:** "{quote["text"]}"\n\n{stars} | Theme: {quote["theme"]}')


def render_action_ideas(ideas: list[str]) -> None:
    """Render action ideas as numbered success blocks."""
    for i, idea in enumerate(ideas, 1):
        st.success(f"**{i}.** {idea}")


def render_fee_bullets(bullets: list[str]) -> None:
    """Render fee explanation bullets in a styled container."""
    md = "\n".join(f"- {b}" for b in bullets)
    st.markdown(md)


def render_source_links(links: list[dict], last_checked: str) -> None:
    """Render source links and the last-checked timestamp."""
    for link in links:
        title = link.get("title", link.get("url", ""))
        url = link.get("url", "")
        st.markdown(f"- [{title}]({url})")
    st.caption(f"Last checked: {last_checked}")
