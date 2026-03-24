import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.phase2_theme_analysis.theme_engine import Theme
from src.phase2_theme_analysis.quote_extractor import Quote
from src.phase3_weekly_pulse.generator import (
    PulseResult,
    _build_themes_summary,
    _build_quotes_block,
    _parse_pulse_response,
    generate_weekly_pulse,
)
from src.phase3_weekly_pulse.formatter import (
    to_markdown,
    to_json,
    save_markdown,
    save_json,
    save_both,
)

# --- Fixtures ---

_THEMES = [
    Theme(rank=1, name="App Stability", description="Crashes during trading", sentiment="negative", review_count=8),
    Theme(rank=2, name="Customer Support", description="Slow response times", sentiment="negative", review_count=5),
    Theme(rank=3, name="Clean UI", description="Users love the interface", sentiment="positive", review_count=10),
]

_QUOTES = [
    Quote(text="App froze during a volatile session", theme="App Stability", star_rating=1),
    Quote(text="Support took 45 minutes to respond", theme="Customer Support", star_rating=2),
    Quote(text="Best trading app I have used so far", theme="Clean UI", star_rating=5),
]

_MOCK_LLM_RESPONSE = {
    "weekly_note": (
        "This week saw a mixed sentiment trend across 50 reviews. "
        "App stability remains the top concern, with users reporting crashes "
        "during market hours. Customer support response times continue to frustrate "
        "traders needing urgent help. On the positive side, the clean UI and "
        "intuitive navigation received strong praise from new investors."
    ),
    "action_ideas": [
        "Prioritize crash-fix sprint for intraday trading flow before next release",
        "Add live-chat fallback when phone queue exceeds 10 minutes",
        "Showcase UI testimonials in onboarding to reinforce positive perception",
    ],
    "word_count": 68,
}


def _make_pulse() -> PulseResult:
    return PulseResult(
        weekly_note=_MOCK_LLM_RESPONSE["weekly_note"],
        action_ideas=_MOCK_LLM_RESPONSE["action_ideas"],
        word_count=68,
        week_ending="2026-03-21",
        total_reviews=50,
        themes=[t.model_dump() for t in _THEMES],
        quotes=[q.model_dump() for q in _QUOTES],
        avg_rating=3.4,
    )


# ---------------------------------------------------------------------------
# Prompt building tests (no LLM)
# ---------------------------------------------------------------------------

class TestBuildThemesSummary:
    def test_format(self):
        summary = _build_themes_summary(_THEMES)
        assert "1. App Stability (negative)" in summary
        assert "[8 reviews]" in summary
        assert "2. Customer Support" in summary
        assert "3. Clean UI (positive)" in summary

    def test_empty_themes(self):
        assert _build_themes_summary([]) == ""


class TestBuildQuotesBlock:
    def test_format(self):
        block = _build_quotes_block(_QUOTES)
        assert '"App froze during a volatile session"' in block
        assert "Rating: 1/5" in block
        assert "Theme: App Stability" in block
        assert '"Best trading app I have used so far"' in block

    def test_empty_quotes(self):
        assert _build_quotes_block([]) == ""


# ---------------------------------------------------------------------------
# Response parsing tests (no LLM)
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_basic_parse(self):
        note, ideas, wc = _parse_pulse_response(_MOCK_LLM_RESPONSE)
        assert "mixed sentiment" in note
        assert len(ideas) == 3
        assert wc == 68

    def test_pii_scrubbed(self):
        data = {
            "weekly_note": "User test@example.com reported crashes",
            "action_ideas": ["Contact user at 9876543210"],
            "word_count": 10,
        }
        note, ideas, _ = _parse_pulse_response(data)
        assert "test@example.com" not in note
        assert "[EMAIL]" in note
        assert "9876543210" not in ideas[0]

    def test_missing_fields(self):
        note, ideas, wc = _parse_pulse_response({})
        assert note == ""
        assert ideas == []

    def test_word_count_fallback(self):
        data = {"weekly_note": "one two three four five", "action_ideas": []}
        _, _, wc = _parse_pulse_response(data)
        assert wc == 5


# ---------------------------------------------------------------------------
# Full generator with mocked LLM
# ---------------------------------------------------------------------------

class TestGenerateWeeklyPulse:
    @patch(
        "src.phase3_weekly_pulse.generator.chat_completion",
        return_value=_MOCK_LLM_RESPONSE,
    )
    def test_generate(self, mock_chat):
        result = generate_weekly_pulse(
            themes=_THEMES,
            quotes=_QUOTES,
            total_reviews=50,
            week_end_date="2026-03-21",
            avg_rating=3.4,
        )
        assert isinstance(result, PulseResult)
        assert "mixed sentiment" in result.weekly_note
        assert len(result.action_ideas) == 3
        assert result.total_reviews == 50
        assert result.week_ending == "2026-03-21"
        assert result.avg_rating == 3.4
        assert len(result.themes) == 3
        assert len(result.quotes) == 3
        mock_chat.assert_called_once()

    @patch(
        "src.phase3_weekly_pulse.generator.chat_completion",
        return_value=_MOCK_LLM_RESPONSE,
    )
    def test_default_date(self, mock_chat):
        result = generate_weekly_pulse(
            themes=_THEMES, quotes=_QUOTES, total_reviews=10
        )
        assert result.week_ending  # should be today's date string


# ---------------------------------------------------------------------------
# Formatter tests (no LLM)
# ---------------------------------------------------------------------------

class TestMarkdownFormatter:
    def test_contains_sections(self):
        pulse = _make_pulse()
        md = to_markdown(pulse)
        assert "# Weekly Pulse — Week of 2026-03-21" in md
        assert "## Top Themes" in md
        assert "**App Stability**" in md
        assert "## User Quotes" in md
        assert "App froze during a volatile session" in md
        assert "## Weekly Note" in md
        assert "## Action Ideas" in md
        assert "1." in md

    def test_ratings_shown(self):
        pulse = _make_pulse()
        md = to_markdown(pulse)
        assert "★" in md
        assert "Reviews analyzed:** 50" in md


class TestJsonFormatter:
    def test_valid_json(self):
        pulse = _make_pulse()
        raw = to_json(pulse)
        data = json.loads(raw)
        assert data["week_ending"] == "2026-03-21"
        assert data["total_reviews"] == 50
        assert len(data["themes"]) == 3
        assert len(data["quotes"]) == 3
        assert len(data["action_ideas"]) == 3
        assert "weekly_note" in data


class TestFileSave:
    def test_save_markdown(self):
        pulse = _make_pulse()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_markdown(pulse, Path(tmpdir))
            assert path.exists()
            assert path.name == "pulse_2026-03-21.md"
            content = path.read_text()
            assert "Weekly Pulse" in content

    def test_save_json(self):
        pulse = _make_pulse()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_json(pulse, Path(tmpdir))
            assert path.exists()
            assert path.name == "pulse_2026-03-21.json"
            data = json.loads(path.read_text())
            assert data["total_reviews"] == 50

    def test_save_both(self):
        pulse = _make_pulse()
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path, json_path = save_both(pulse, Path(tmpdir))
            assert md_path.exists()
            assert json_path.exists()
            assert md_path.suffix == ".md"
            assert json_path.suffix == ".json"
