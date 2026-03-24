from datetime import datetime

from src.phase1_data_ingestion.csv_loader import ReviewRecord
from src.phase1_data_ingestion.pii_scrubber import scrub_output, scrub_reviews, scrub_text


def _make_review(content: str) -> ReviewRecord:
    return ReviewRecord(
        review_id="test-1",
        content=content,
        score=3,
        date=datetime(2026, 3, 1),
        thumbs_up=0,
    )


class TestScrubText:
    def test_email_redacted(self):
        assert scrub_text("Contact me at user@example.com for details") == (
            "Contact me at [EMAIL] for details"
        )

    def test_indian_phone_redacted(self):
        assert "[PHONE]" in scrub_text("Call me at 9876543210")
        assert "[PHONE]" in scrub_text("My number is +91 9876543210")
        assert "[PHONE]" in scrub_text("Reach me at +91-9876543210")

    def test_international_phone_redacted(self):
        assert "[PHONE]" in scrub_text("Call +1 2025551234")

    def test_aadhaar_redacted(self):
        assert scrub_text("Aadhaar 1234 5678 9012") == "Aadhaar [ID]"
        assert scrub_text("Aadhaar 1234-5678-9012") == "Aadhaar [ID]"

    def test_pan_redacted(self):
        assert scrub_text("PAN is ABCDE1234F") == "PAN is [ID]"

    def test_clean_text_unchanged(self):
        clean = "App is great for trading stocks"
        assert scrub_text(clean) == clean

    def test_multiple_pii_types(self):
        text = "Email user@test.com or call 9876543210. PAN: ABCDE1234F"
        result = scrub_text(text)
        assert "user@test.com" not in result
        assert "9876543210" not in result
        assert "ABCDE1234F" not in result
        assert "[EMAIL]" in result
        assert "[PHONE]" in result
        assert "[ID]" in result


class TestScrubReviews:
    def test_returns_new_objects(self):
        original = _make_review("Contact support@groww.in")
        scrubbed = scrub_reviews([original])
        assert len(scrubbed) == 1
        assert scrubbed[0].content == "Contact [EMAIL]"
        assert original.content == "Contact support@groww.in"

    def test_preserves_other_fields(self):
        original = _make_review("Call 9876543210 for help")
        scrubbed = scrub_reviews([original])[0]
        assert scrubbed.review_id == original.review_id
        assert scrubbed.score == original.score
        assert scrubbed.date == original.date
        assert scrubbed.thumbs_up == original.thumbs_up

    def test_empty_list(self):
        assert scrub_reviews([]) == []


class TestScrubOutput:
    def test_post_llm_scrub(self):
        text = 'The user mentioned email test@domain.com and phone 8765432109'
        result = scrub_output(text)
        assert "test@domain.com" not in result
        assert "8765432109" not in result

    def test_clean_output_unchanged(self):
        text = "Theme: App crashes during trading hours"
        assert scrub_output(text) == text
