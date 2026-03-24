from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from src.config import OUTPUT_DIR

logger = logging.getLogger(__name__)

NOTES_FILE = OUTPUT_DIR / "notes_log.jsonl"
AUDIT_LOG = OUTPUT_DIR / "audit.log"


class NotesPayload(BaseModel):
    """Schema for the structured JSON payload appended to the notes log."""
    date: str
    weekly_pulse: dict[str, Any]
    fee_scenario: str
    explanation_bullets: list[str]
    source_links: list[dict[str, str]]


def _ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _write_audit(action: str, status: str, detail: str = "") -> None:
    """Append an audit entry with timestamp, action name, and result."""
    _ensure_output_dir()
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    entry = f"[{ts}] action={action} status={status}"
    if detail:
        entry += f" detail={detail}"
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def build_payload(
    date: str,
    weekly_pulse: dict[str, Any],
    fee_scenario: str,
    explanation_bullets: list[str],
    source_links: list[dict[str, str]],
) -> NotesPayload:
    """Construct and validate a NotesPayload from raw parts."""
    return NotesPayload(
        date=date,
        weekly_pulse=weekly_pulse,
        fee_scenario=fee_scenario,
        explanation_bullets=explanation_bullets,
        source_links=source_links,
    )


def execute(payload: NotesPayload) -> Path:
    """
    Append the validated payload to notes_log.jsonl and log the action.

    Returns the path to the notes file.
    Raises ValueError if the payload fails validation.
    """
    try:
        _ensure_output_dir()
        line = payload.model_dump_json() + "\n"
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(line)
        _write_audit("notes_append", "success", str(NOTES_FILE))
        logger.info("Appended payload to %s", NOTES_FILE)
        return NOTES_FILE
    except Exception as exc:
        _write_audit("notes_append", "error", str(exc))
        logger.error("Failed to append notes: %s", exc)
        raise
