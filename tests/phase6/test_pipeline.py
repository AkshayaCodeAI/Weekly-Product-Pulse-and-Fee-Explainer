"""Tests for the pipeline orchestrator and Phase 6 integration modules."""

from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

from src.phase2_theme_analysis.theme_engine import Theme
from src.phase2_theme_analysis.quote_extractor import Quote
from src.phase3_weekly_pulse.generator import PulseResult
from src.phase4_fee_explainer.explainer import FeeExplanation, SourceLink
from src.pipeline import run_pipeline, PipelineError
from src.phase6_ui_integration.components import (
    SENTIMENT_COLORS,
    SENTIMENT_ICONS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_THEMES = [
    Theme(rank=1, name="App Crashes", description="Frequent crashes reported",
          sentiment="negative", review_count=45),
    Theme(rank=2, name="Ease of Use", description="Users find the app intuitive",
          sentiment="positive", review_count=30),
    Theme(rank=3, name="Slow Withdrawals", description="Withdrawal processing delays",
          sentiment="negative", review_count=20),
]

_SAMPLE_QUOTES = [
    Quote(text="The app keeps crashing every time I try to trade", theme="App Crashes", star_rating=1),
    Quote(text="Very simple and clean UI, love it!", theme="Ease of Use", star_rating=5),
    Quote(text="My withdrawal has been pending for 3 days", theme="Slow Withdrawals", star_rating=2),
]

_SAMPLE_PULSE = PulseResult(
    weekly_note="Overall sentiment trends mixed this week. Key concerns include app stability.",
    action_ideas=["Prioritize crash fixes", "Improve withdrawal SLA", "Enhance onboarding"],
    word_count=120,
    week_ending="2026-03-21",
    total_reviews=347,
    themes=[t.model_dump() for t in _SAMPLE_THEMES],
    quotes=[q.model_dump() for q in _SAMPLE_QUOTES],
    avg_rating=3.8,
)

_SAMPLE_FEE = FeeExplanation(
    scenario="Mutual Fund Exit Load",
    bullets=[
        "Exit load is a fee charged when units are redeemed early.",
        "Most equity funds charge 1% for redemptions within 1 year.",
    ],
    source_links=[
        SourceLink(title="Groww Blog", url="https://groww.in/blog/what-is-exit-load-in-mutual-funds"),
        SourceLink(title="AMFI India", url="https://www.amfiindia.com/investor-corner/knowledge-center/exit-load.html"),
    ],
    last_checked="2026-03-21",
)


# ---------------------------------------------------------------------------
# Pipeline orchestrator tests
# ---------------------------------------------------------------------------

class TestRunPipeline:
    @patch("src.pipeline.explain_fee_scenario", return_value=_SAMPLE_FEE)
    @patch("src.pipeline.generate_weekly_pulse", return_value=_SAMPLE_PULSE)
    @patch("src.pipeline.extract_quotes", return_value=_SAMPLE_QUOTES)
    @patch("src.pipeline.get_top_themes", return_value=_SAMPLE_THEMES)
    @patch("src.pipeline.analyze_themes", return_value=_SAMPLE_THEMES)
    @patch("src.pipeline.scrub_reviews", side_effect=lambda r: r)
    @patch("src.pipeline.load_reviews_from_bytes")
    def test_full_pipeline(self, mock_load, mock_scrub, mock_analyze,
                           mock_top, mock_quotes, mock_pulse, mock_fee):
        from src.phase1_data_ingestion.csv_loader import ReviewRecord
        mock_load.return_value = [
            ReviewRecord(
                review_id="r1", content="Great app", score=5,
                date=datetime(2026, 3, 15), thumbs_up=10,
            )
        ]

        pulse, fee = run_pipeline(b"fake csv bytes", weeks=8, fee_scenario="Mutual Fund Exit Load")

        assert isinstance(pulse, PulseResult)
        assert isinstance(fee, FeeExplanation)
        assert pulse.total_reviews == 347
        assert fee.scenario == "Mutual Fund Exit Load"

        mock_load.assert_called_once()
        mock_scrub.assert_called_once()
        mock_analyze.assert_called_once()
        mock_top.assert_called_once()
        mock_quotes.assert_called_once()
        mock_pulse.assert_called_once()
        mock_fee.assert_called_once()

    @patch("src.pipeline.load_reviews_from_bytes", return_value=[])
    def test_empty_reviews_raises(self, mock_load):
        with pytest.raises(PipelineError, match="No reviews found"):
            run_pipeline(b"fake csv", weeks=8)

    @patch("src.pipeline.analyze_themes", return_value=[])
    @patch("src.pipeline.scrub_reviews", side_effect=lambda r: r)
    @patch("src.pipeline.load_reviews_from_bytes")
    def test_no_themes_raises(self, mock_load, mock_scrub, mock_analyze):
        from src.phase1_data_ingestion.csv_loader import ReviewRecord
        mock_load.return_value = [
            ReviewRecord(
                review_id="r1", content="Test", score=4,
                date=datetime(2026, 3, 15), thumbs_up=0,
            )
        ]
        with pytest.raises(PipelineError, match="no themes"):
            run_pipeline(b"fake csv", weeks=8)


# ---------------------------------------------------------------------------
# Component utility tests (non-Streamlit logic)
# ---------------------------------------------------------------------------

class TestComponentConstants:
    def test_sentiment_colors_has_keys(self):
        assert "negative" in SENTIMENT_COLORS
        assert "positive" in SENTIMENT_COLORS
        assert "mixed" in SENTIMENT_COLORS

    def test_sentiment_icons_has_keys(self):
        assert "negative" in SENTIMENT_ICONS
        assert "positive" in SENTIMENT_ICONS
        assert "mixed" in SENTIMENT_ICONS

    def test_colors_are_hex(self):
        for color in SENTIMENT_COLORS.values():
            assert color.startswith("#")
            assert len(color) == 7


# ---------------------------------------------------------------------------
# PulseResult / FeeExplanation integration tests
# ---------------------------------------------------------------------------

class TestDataModelIntegration:
    def test_pulse_to_dict_roundtrip(self):
        d = _SAMPLE_PULSE.model_dump()
        assert d["week_ending"] == "2026-03-21"
        assert d["total_reviews"] == 347
        assert len(d["themes"]) == 3
        assert len(d["quotes"]) == 3

    def test_fee_to_dict_roundtrip(self):
        d = _SAMPLE_FEE.model_dump()
        assert d["scenario"] == "Mutual Fund Exit Load"
        assert len(d["bullets"]) == 2
        assert len(d["source_links"]) == 2

    def test_pulse_themes_are_dicts(self):
        for theme in _SAMPLE_PULSE.themes:
            assert isinstance(theme, dict)
            assert "name" in theme
            assert "rank" in theme

    def test_fee_source_links_have_fields(self):
        for link in _SAMPLE_FEE.source_links:
            assert link.title
            assert link.url.startswith("https://")


# ---------------------------------------------------------------------------
# One-pager renderer smoke test (verify no import errors)
# ---------------------------------------------------------------------------

class TestOnePagerImport:
    def test_render_function_exists(self):
        from src.phase6_ui_integration.one_pager import render_one_pager
        assert callable(render_one_pager)

    def test_components_module_exports(self):
        from src.phase6_ui_integration import components
        assert callable(components.render_metric_cards)
        assert callable(components.render_theme_card)
        assert callable(components.render_quote)
        assert callable(components.render_action_ideas)
        assert callable(components.render_fee_bullets)
        assert callable(components.render_source_links)
