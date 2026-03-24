from datetime import datetime
from unittest.mock import patch

from src.phase2_theme_analysis.theme_engine import (
    Theme,
    _format_reviews_block,
    _parse_themes,
    analyze_themes,
    get_top_themes,
)
from src.phase2_theme_analysis.quote_extractor import Quote, _parse_quotes, extract_quotes
from src.phase1_data_ingestion.csv_loader import ReviewRecord


def _make_review(rid: str, content: str, score: int = 4) -> ReviewRecord:
    return ReviewRecord(
        review_id=rid,
        content=content,
        score=score,
        date=datetime(2026, 3, 1),
        thumbs_up=0,
    )


# ---------------------------------------------------------------------------
# Theme parsing tests (no LLM calls)
# ---------------------------------------------------------------------------

class TestParseThemes:
    def test_basic_parsing(self):
        data = {
            "themes": [
                {
                    "rank": 1,
                    "name": "App Crashes",
                    "description": "App crashes during trading",
                    "sentiment": "negative",
                    "review_count": 10,
                    "sample_review_ids": ["r1", "r2"],
                },
                {
                    "rank": 2,
                    "name": "Good UI",
                    "description": "Users love the clean interface",
                    "sentiment": "positive",
                    "review_count": 8,
                    "sample_review_ids": ["r3"],
                },
            ]
        }
        themes = _parse_themes(data)
        assert len(themes) == 2
        assert themes[0].name == "App Crashes"
        assert themes[1].name == "Good UI"

    def test_themes_capped_at_max(self):
        data = {
            "themes": [
                {
                    "rank": i,
                    "name": f"Theme {i}",
                    "description": f"Description {i}",
                    "sentiment": "mixed",
                    "review_count": 10 - i,
                    "sample_review_ids": [],
                }
                for i in range(1, 9)  # 8 themes, exceeds MAX_THEMES=5
            ]
        }
        themes = _parse_themes(data)
        assert len(themes) <= 5

    def test_sorted_by_rank(self):
        data = {
            "themes": [
                {
                    "rank": 3,
                    "name": "Third",
                    "description": "d3",
                    "sentiment": "mixed",
                    "review_count": 2,
                    "sample_review_ids": [],
                },
                {
                    "rank": 1,
                    "name": "First",
                    "description": "d1",
                    "sentiment": "negative",
                    "review_count": 10,
                    "sample_review_ids": [],
                },
                {
                    "rank": 2,
                    "name": "Second",
                    "description": "d2",
                    "sentiment": "positive",
                    "review_count": 5,
                    "sample_review_ids": [],
                },
            ]
        }
        themes = _parse_themes(data)
        assert themes[0].rank == 1
        assert themes[1].rank == 2
        assert themes[2].rank == 3

    def test_empty_themes(self):
        assert _parse_themes({"themes": []}) == []
        assert _parse_themes({}) == []


class TestGetTopThemes:
    def test_returns_top_n(self):
        themes = [
            Theme(rank=i, name=f"T{i}", description="d", sentiment="mixed", review_count=1)
            for i in range(1, 6)
        ]
        top = get_top_themes(themes, n=3)
        assert len(top) == 3
        assert [t.rank for t in top] == [1, 2, 3]

    def test_fewer_themes_than_n(self):
        themes = [
            Theme(rank=1, name="Only", description="d", sentiment="positive", review_count=5)
        ]
        top = get_top_themes(themes, n=3)
        assert len(top) == 1


class TestFormatReviewsBlock:
    def test_format_output(self):
        reviews = [
            _make_review("r1", "Great app", 5),
            _make_review("r2", "Terrible crashes", 1),
        ]
        block = _format_reviews_block(reviews)
        assert "[r1]" in block
        assert "(score=5)" in block
        assert "Great app" in block
        assert "[r2]" in block
        assert "Terrible crashes" in block


# ---------------------------------------------------------------------------
# Theme analysis with mocked LLM
# ---------------------------------------------------------------------------

class TestAnalyzeThemes:
    _mock_response = {
        "themes": [
            {
                "rank": 1,
                "name": "App Stability",
                "description": "App crashes and freezes during trading",
                "sentiment": "negative",
                "review_count": 8,
                "sample_review_ids": ["r1", "r8"],
            },
            {
                "rank": 2,
                "name": "Customer Support",
                "description": "Slow response times from support",
                "sentiment": "negative",
                "review_count": 5,
                "sample_review_ids": ["r5"],
            },
            {
                "rank": 3,
                "name": "Clean Interface",
                "description": "Users appreciate the UI design",
                "sentiment": "positive",
                "review_count": 6,
                "sample_review_ids": ["r2"],
            },
        ]
    }

    @patch("src.phase2_theme_analysis.theme_engine.chat_completion", return_value=_mock_response)
    def test_single_batch(self, mock_chat):
        reviews = [_make_review(f"r{i}", f"Review {i}") for i in range(10)]
        themes = analyze_themes(reviews)
        assert len(themes) == 3
        assert themes[0].name == "App Stability"
        mock_chat.assert_called_once()

    @patch("src.phase2_theme_analysis.theme_engine.chat_completion", return_value=_mock_response)
    def test_multi_batch_triggers_merge(self, mock_chat):
        reviews = [_make_review(f"r{i}", f"Review {i}") for i in range(150)]
        themes = analyze_themes(reviews)
        assert len(themes) <= 5
        # 2 batch calls + 1 merge call = 3 total
        assert mock_chat.call_count == 3

    def test_empty_reviews(self):
        assert analyze_themes([]) == []


# ---------------------------------------------------------------------------
# Quote parsing tests (no LLM calls)
# ---------------------------------------------------------------------------

class TestParseQuotes:
    def test_basic_parsing(self):
        data = {
            "quotes": [
                {"text": "App crashed during trading", "theme": "App Stability", "star_rating": 1},
                {"text": "Love the clean UI", "theme": "Clean Interface", "star_rating": 5},
                {"text": "Support took 45 min", "theme": "Customer Support", "star_rating": 2},
            ]
        }
        quotes = _parse_quotes(data)
        assert len(quotes) == 3
        assert quotes[0].text == "App crashed during trading"

    def test_quotes_capped_at_max(self):
        data = {
            "quotes": [
                {"text": f"Quote {i}", "theme": f"Theme {i}", "star_rating": 3}
                for i in range(10)
            ]
        }
        quotes = _parse_quotes(data)
        assert len(quotes) <= 3

    def test_pii_scrubbed_in_quotes(self):
        data = {
            "quotes": [
                {
                    "text": "Contact me at user@example.com for help",
                    "theme": "Support",
                    "star_rating": 2,
                },
            ]
        }
        quotes = _parse_quotes(data)
        assert "user@example.com" not in quotes[0].text
        assert "[EMAIL]" in quotes[0].text

    def test_empty_quotes(self):
        assert _parse_quotes({"quotes": []}) == []
        assert _parse_quotes({}) == []


class TestExtractQuotes:
    _mock_response = {
        "quotes": [
            {"text": "App froze during market hours", "theme": "App Stability", "star_rating": 1},
            {"text": "Beautiful and intuitive design", "theme": "Clean UI", "star_rating": 5},
            {"text": "Waited 30 mins for support", "theme": "Support Issues", "star_rating": 2},
        ]
    }

    @patch("src.phase2_theme_analysis.quote_extractor.chat_completion", return_value=_mock_response)
    def test_extract_with_mock(self, mock_chat):
        themes = [
            Theme(rank=1, name="App Stability", description="crashes", sentiment="negative", review_count=5),
            Theme(rank=2, name="Clean UI", description="good design", sentiment="positive", review_count=4),
        ]
        reviews = [_make_review(f"r{i}", f"Review {i}") for i in range(10)]
        quotes = extract_quotes(themes, reviews)
        assert len(quotes) == 3
        assert quotes[0].theme == "App Stability"
        mock_chat.assert_called_once()

    def test_empty_inputs(self):
        assert extract_quotes([], []) == []
        themes = [
            Theme(rank=1, name="T", description="d", sentiment="mixed", review_count=1)
        ]
        assert extract_quotes(themes, []) == []
        reviews = [_make_review("r1", "text")]
        assert extract_quotes([], reviews) == []
