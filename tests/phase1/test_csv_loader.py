import io
from datetime import datetime

import pytest

from src.phase1_data_ingestion.csv_loader import (
    CSVValidationError,
    ReviewRecord,
    load_reviews_from_bytes,
)

VALID_HEADER = "reviewId,userName,content,score,thumbsUpCount,reviewCreatedVersion,at,replyContent,repliedAt"


def _make_csv(*rows: str) -> bytes:
    """Build a CSV from header + data rows."""
    lines = [VALID_HEADER] + list(rows)
    return "\n".join(lines).encode("utf-8")


class TestColumnValidation:
    def test_valid_columns_accepted(self):
        csv = _make_csv(
            "r1,User,Great app,5,2,1.0,2026-03-01 10:00:00,,"
        )
        records = load_reviews_from_bytes(csv, weeks=52)
        assert len(records) == 1

    def test_missing_column_raises(self):
        bad_csv = b"reviewId,content,score\nr1,Good,5"
        with pytest.raises(CSVValidationError, match="missing required columns"):
            load_reviews_from_bytes(bad_csv)


class TestDateFiltering:
    def test_old_reviews_filtered_out(self):
        csv = _make_csv(
            "r1,User,Old review,3,0,1.0,2020-01-01 10:00:00,,",
            "r2,User,Recent review,4,1,1.0,2026-03-10 10:00:00,,",
        )
        ref = datetime(2026, 3, 15)
        records = load_reviews_from_bytes(csv, weeks=8, reference_date=ref)
        assert len(records) == 1
        assert records[0].review_id == "r2"

    def test_all_within_window_kept(self):
        csv = _make_csv(
            "r1,User,Review A,5,0,1.0,2026-03-01 10:00:00,,",
            "r2,User,Review B,4,0,1.0,2026-03-10 10:00:00,,",
        )
        ref = datetime(2026, 3, 15)
        records = load_reviews_from_bytes(csv, weeks=8, reference_date=ref)
        assert len(records) == 2

    def test_12_week_window(self):
        csv = _make_csv(
            "r1,User,Older review,3,0,1.0,2025-12-28 10:00:00,,",
            "r2,User,Recent review,4,0,1.0,2026-03-10 10:00:00,,",
        )
        ref = datetime(2026, 3, 15)
        records_8w = load_reviews_from_bytes(csv, weeks=8, reference_date=ref)
        records_12w = load_reviews_from_bytes(csv, weeks=12, reference_date=ref)
        assert len(records_8w) == 1
        assert len(records_12w) == 2


class TestEmptyContentDrop:
    def test_empty_content_dropped(self):
        csv = _make_csv(
            "r1,User,,5,0,1.0,2026-03-10 10:00:00,,",
            "r2,User,Valid content,4,0,1.0,2026-03-10 10:00:00,,",
        )
        ref = datetime(2026, 3, 15)
        records = load_reviews_from_bytes(csv, weeks=8, reference_date=ref)
        assert len(records) == 1
        assert records[0].review_id == "r2"

    def test_whitespace_only_content_dropped(self):
        csv = _make_csv(
            "r1,User,   ,5,0,1.0,2026-03-10 10:00:00,,",
        )
        ref = datetime(2026, 3, 15)
        records = load_reviews_from_bytes(csv, weeks=8, reference_date=ref)
        assert len(records) == 0


class TestReviewRecord:
    def test_valid_record(self):
        r = ReviewRecord(
            review_id="r1",
            content="Good app",
            score=5,
            date=datetime(2026, 3, 1),
            thumbs_up=10,
        )
        assert r.score == 5

    def test_invalid_score_rejected(self):
        with pytest.raises(ValueError, match="score must be between"):
            ReviewRecord(
                review_id="r1",
                content="Bad score",
                score=6,
                date=datetime(2026, 3, 1),
            )

    def test_zero_score_rejected(self):
        with pytest.raises(ValueError, match="score must be between"):
            ReviewRecord(
                review_id="r1",
                content="Zero score",
                score=0,
                date=datetime(2026, 3, 1),
            )


class TestEmptyResults:
    def test_no_reviews_in_range(self):
        csv = _make_csv(
            "r1,User,Ancient review,3,0,1.0,2020-01-01 10:00:00,,",
        )
        ref = datetime(2026, 3, 15)
        records = load_reviews_from_bytes(csv, weeks=8, reference_date=ref)
        assert records == []


class TestSampleCSV:
    def test_sample_csv_loads(self):
        with open("data/sample_reviews.csv", "rb") as f:
            csv_bytes = f.read()
        ref = datetime(2026, 3, 21)
        records = load_reviews_from_bytes(csv_bytes, weeks=12, reference_date=ref)
        assert len(records) > 0
        for r in records:
            assert r.content.strip() != ""
            assert 1 <= r.score <= 5
