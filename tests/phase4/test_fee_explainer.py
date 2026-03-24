from unittest.mock import patch, call

from src.phase4_fee_explainer.explainer import (
    FeeExplanation,
    SourceLink,
    _check_tone,
    _has_tone_violations,
    _parse_fee_response,
    explain_fee_scenario,
)


# --- Fixtures ---

_CLEAN_RESPONSE = {
    "scenario": "Mutual Fund Exit Load",
    "bullets": [
        "Exit load is a fee charged when an investor redeems mutual fund units before a specified period.",
        "Most equity mutual funds charge an exit load of 1% if redeemed within 1 year of purchase.",
        "Liquid funds typically have a graded exit load structure for redemptions within 7 days.",
        "Exit load is deducted from the redemption amount and is not charged separately.",
        "The exit load percentage and applicable period are disclosed in the scheme information document.",
        "SEBI regulations require all mutual funds to clearly disclose exit load terms to investors.",
    ],
    "source_links": [
        {
            "title": "What is Exit Load in Mutual Funds - Groww",
            "url": "https://groww.in/blog/what-is-exit-load-in-mutual-funds",
        },
        {
            "title": "Exit Load - AMFI India",
            "url": "https://www.amfiindia.com/investor-corner/knowledge-center/exit-load.html",
        },
    ],
    "last_checked": "2026-03-21",
}

_TAINTED_RESPONSE = {
    "scenario": "Mutual Fund Exit Load",
    "bullets": [
        "Exit load is a fee charged on early redemption.",
        "You should check the exit load before investing.",
        "This fund is better than others in terms of exit load.",
    ],
    "source_links": [
        {
            "title": "Groww Blog",
            "url": "https://groww.in/blog/what-is-exit-load-in-mutual-funds",
        },
        {
            "title": "AMFI",
            "url": "https://www.amfiindia.com/investor-corner/knowledge-center/exit-load.html",
        },
    ],
    "last_checked": "2026-03-21",
}


# ---------------------------------------------------------------------------
# Tone check tests
# ---------------------------------------------------------------------------

class TestToneCheck:
    def test_clean_text(self):
        assert _check_tone("Exit load is charged at 1% for redemptions within 1 year.") == []

    def test_recommendation_detected(self):
        violations = _check_tone("You should invest in this fund.")
        assert len(violations) > 0
        assert "you should" in violations[0].lower()

    def test_comparison_detected(self):
        violations = _check_tone("This is better than other funds.")
        assert len(violations) > 0

    def test_superlative_detected(self):
        violations = _check_tone("This is the best option available.")
        assert len(violations) > 0

    def test_multiple_violations(self):
        text = "You should consider this, it is the best and better than others."
        violations = _check_tone(text)
        assert len(violations) >= 3

    def test_case_insensitive(self):
        assert len(_check_tone("YOU SHOULD check this")) > 0
        assert len(_check_tone("BETTER THAN competitors")) > 0


class TestHasToneViolations:
    def test_clean_result(self):
        result = _parse_fee_response(_CLEAN_RESPONSE, "2026-03-21")
        assert not _has_tone_violations(result)

    def test_tainted_result(self):
        result = _parse_fee_response(_TAINTED_RESPONSE, "2026-03-21")
        assert _has_tone_violations(result)


# ---------------------------------------------------------------------------
# Response parsing tests
# ---------------------------------------------------------------------------

class TestParseFeeResponse:
    def test_basic_parsing(self):
        result = _parse_fee_response(_CLEAN_RESPONSE, "2026-03-21")
        assert isinstance(result, FeeExplanation)
        assert result.scenario == "Mutual Fund Exit Load"
        assert len(result.bullets) == 6
        assert len(result.source_links) == 2
        assert result.last_checked == "2026-03-21"

    def test_bullets_capped_at_limit(self):
        data = {
            "scenario": "Test",
            "bullets": [f"Bullet {i}" for i in range(10)],
            "source_links": [],
            "last_checked": "2026-03-21",
        }
        result = _parse_fee_response(data, "2026-03-21")
        assert len(result.bullets) <= 6

    def test_source_links_capped_at_two(self):
        data = {
            "scenario": "Test",
            "bullets": ["B1"],
            "source_links": [
                {"title": f"Link {i}", "url": f"https://example.com/{i}"}
                for i in range(5)
            ],
            "last_checked": "2026-03-21",
        }
        result = _parse_fee_response(data, "2026-03-21")
        assert len(result.source_links) <= 2

    def test_missing_fields(self):
        result = _parse_fee_response({}, "2026-03-21")
        assert result.scenario == ""
        assert result.bullets == []
        assert result.source_links == []
        assert result.last_checked == "2026-03-21"

    def test_last_checked_fallback(self):
        data = {"scenario": "Test", "bullets": [], "source_links": []}
        result = _parse_fee_response(data, "2026-03-21")
        assert result.last_checked == "2026-03-21"

    def test_source_link_model(self):
        result = _parse_fee_response(_CLEAN_RESPONSE, "2026-03-21")
        link = result.source_links[0]
        assert isinstance(link, SourceLink)
        assert link.title == "What is Exit Load in Mutual Funds - Groww"
        assert "groww.in" in link.url


# ---------------------------------------------------------------------------
# Full explainer with mocked LLM
# ---------------------------------------------------------------------------

class TestExplainFeeScenario:
    @patch(
        "src.phase4_fee_explainer.explainer.chat_completion",
        return_value=_CLEAN_RESPONSE,
    )
    def test_clean_response_single_call(self, mock_chat):
        result = explain_fee_scenario(
            "Mutual Fund Exit Load", current_date="2026-03-21"
        )
        assert isinstance(result, FeeExplanation)
        assert result.scenario == "Mutual Fund Exit Load"
        assert len(result.bullets) == 6
        assert len(result.source_links) == 2
        assert result.last_checked == "2026-03-21"
        mock_chat.assert_called_once()

    @patch("src.phase4_fee_explainer.explainer.chat_completion")
    def test_tainted_response_triggers_retry(self, mock_chat):
        mock_chat.side_effect = [_TAINTED_RESPONSE, _CLEAN_RESPONSE]
        result = explain_fee_scenario(
            "Mutual Fund Exit Load", current_date="2026-03-21"
        )
        assert mock_chat.call_count == 2
        assert len(result.bullets) == 6
        assert not _has_tone_violations(result)

    @patch(
        "src.phase4_fee_explainer.explainer.chat_completion",
        return_value=_CLEAN_RESPONSE,
    )
    def test_default_date(self, mock_chat):
        result = explain_fee_scenario("Exit Load")
        assert result.last_checked  # should be today's date

    @patch(
        "src.phase4_fee_explainer.explainer.chat_completion",
        return_value=_CLEAN_RESPONSE,
    )
    def test_source_links_are_official(self, mock_chat):
        result = explain_fee_scenario(
            "Mutual Fund Exit Load", current_date="2026-03-21"
        )
        urls = [link.url for link in result.source_links]
        assert any("groww.in" in u for u in urls)
        assert any("amfiindia.com" in u for u in urls)
