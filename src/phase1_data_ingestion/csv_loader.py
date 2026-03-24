from __future__ import annotations

import io
from datetime import datetime, timedelta

import pandas as pd
from pydantic import BaseModel, field_validator

from src.config import EXPECTED_CSV_COLUMNS, REVIEW_WINDOW_WEEKS


class ReviewRecord(BaseModel):
    review_id: str
    content: str
    score: int
    date: datetime
    thumbs_up: int = 0

    @field_validator("score")
    @classmethod
    def score_must_be_valid(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError(f"score must be between 1 and 5, got {v}")
        return v


class CSVValidationError(Exception):
    """Raised when the CSV does not match the expected schema."""


def _validate_columns(df: pd.DataFrame) -> None:
    """Check that all required columns exist in the dataframe."""
    missing = EXPECTED_CSV_COLUMNS - set(df.columns)
    if missing:
        raise CSVValidationError(
            f"CSV is missing required columns: {', '.join(sorted(missing))}. "
            f"Expected columns include: {', '.join(sorted(EXPECTED_CSV_COLUMNS))}"
        )


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the 'at' column to timezone-naive datetime."""
    df = df.copy()
    df["at"] = pd.to_datetime(df["at"], format="mixed", utc=True)
    df["at"] = df["at"].dt.tz_localize(None)
    return df


def _filter_by_date_window(
    df: pd.DataFrame, weeks: int | None = None, reference_date: datetime | None = None
) -> pd.DataFrame:
    """Keep only reviews within the last `weeks` weeks from reference_date."""
    weeks = weeks or REVIEW_WINDOW_WEEKS
    ref = reference_date or datetime.now()
    cutoff = ref - timedelta(weeks=weeks)
    return df[df["at"] >= cutoff].copy()


def _drop_empty_content(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows where review content is missing or blank."""
    df = df.copy()
    df["content"] = df["content"].astype(str).str.strip()
    return df[df["content"].ne("") & df["content"].ne("nan")].copy()


def _to_records(df: pd.DataFrame) -> list[ReviewRecord]:
    """Convert cleaned dataframe rows into ReviewRecord models."""
    records: list[ReviewRecord] = []
    for _, row in df.iterrows():
        records.append(
            ReviewRecord(
                review_id=str(row.get("reviewId", "")),
                content=str(row["content"]),
                score=int(row["score"]),
                date=row["at"].to_pydatetime(),
                thumbs_up=int(row.get("thumbsUpCount", 0)),
            )
        )
    return records


def load_reviews_from_bytes(
    csv_bytes: bytes,
    weeks: int | None = None,
    reference_date: datetime | None = None,
) -> list[ReviewRecord]:
    """
    Full ingestion pipeline for CSV bytes (e.g. from Streamlit file uploader).

    1. Parse CSV
    2. Validate columns
    3. Normalize dates
    4. Filter by date window (last 8-12 weeks)
    5. Drop empty content
    6. Return list of ReviewRecord
    """
    df = pd.read_csv(io.BytesIO(csv_bytes))
    _validate_columns(df)
    df = _parse_dates(df)
    df = _filter_by_date_window(df, weeks=weeks, reference_date=reference_date)
    df = _drop_empty_content(df)

    if df.empty:
        return []

    return _to_records(df)


def load_reviews_from_path(
    csv_path: str,
    weeks: int | None = None,
    reference_date: datetime | None = None,
) -> list[ReviewRecord]:
    """Convenience wrapper that loads from a file path."""
    with open(csv_path, "rb") as f:
        return load_reviews_from_bytes(f.read(), weeks=weeks, reference_date=reference_date)
