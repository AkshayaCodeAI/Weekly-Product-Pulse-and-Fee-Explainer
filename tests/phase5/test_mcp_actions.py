import json
import smtplib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.phase5_mcp_actions.notes_append import (
    NotesPayload,
    build_payload,
    execute as notes_execute,
    AUDIT_LOG,
)
from src.phase5_mcp_actions.email_draft import (
    EmailConfigError,
    build_email_body,
    execute as email_execute,
    send_email,
    _format_bullets,
    _format_sources,
)


# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------

_WEEKLY_PULSE = {
    "week_ending": "2026-03-21",
    "total_reviews": 347,
    "weekly_note": "Groww continues to see strong adoption with user sentiment leaning positive.",
    "themes": [
        {"name": "App Crashes", "sentiment": "negative", "rank": 1},
        {"name": "Ease of Use", "sentiment": "positive", "rank": 2},
    ],
    "quotes": [
        {"text": "Great app for beginners!", "star_rating": 5, "theme": "Ease of Use"},
    ],
    "action_ideas": ["Prioritize crash fixes", "Expand onboarding flow", "Add help tooltips"],
    "word_count": 120,
    "avg_rating": 3.8,
}

_FEE_SCENARIO = "Mutual Fund Exit Load"
_BULLETS = [
    "Exit load is a fee charged when units are redeemed before a specified period.",
    "Most equity funds charge 1% exit load for redemptions within 1 year.",
]
_SOURCE_LINKS = [
    {"title": "Groww Blog", "url": "https://groww.in/blog/what-is-exit-load-in-mutual-funds"},
    {"title": "AMFI India", "url": "https://www.amfiindia.com/investor-corner/knowledge-center/exit-load.html"},
]
_DATE = "2026-03-21"


# ---------------------------------------------------------------------------
# NotesPayload tests
# ---------------------------------------------------------------------------

class TestNotesPayload:
    def test_build_payload(self):
        payload = build_payload(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        assert isinstance(payload, NotesPayload)
        assert payload.date == _DATE
        assert payload.fee_scenario == _FEE_SCENARIO
        assert len(payload.explanation_bullets) == 2
        assert len(payload.source_links) == 2

    def test_payload_serialization(self):
        payload = build_payload(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        data = json.loads(payload.model_dump_json())
        assert data["date"] == _DATE
        assert data["fee_scenario"] == _FEE_SCENARIO
        assert isinstance(data["weekly_pulse"], dict)


# ---------------------------------------------------------------------------
# Notes append tests
# ---------------------------------------------------------------------------

class TestNotesAppend:
    def test_execute_creates_jsonl(self, tmp_path):
        payload = build_payload(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        notes_file = tmp_path / "notes_log.jsonl"
        audit_file = tmp_path / "audit.log"

        with (
            patch("src.phase5_mcp_actions.notes_append.NOTES_FILE", notes_file),
            patch("src.phase5_mcp_actions.notes_append.AUDIT_LOG", audit_file),
            patch("src.phase5_mcp_actions.notes_append.OUTPUT_DIR", tmp_path),
        ):
            result = notes_execute(payload)

        assert notes_file.exists()
        lines = notes_file.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["date"] == _DATE
        assert data["fee_scenario"] == _FEE_SCENARIO

    def test_execute_appends_multiple(self, tmp_path):
        payload = build_payload(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        notes_file = tmp_path / "notes_log.jsonl"
        audit_file = tmp_path / "audit.log"

        with (
            patch("src.phase5_mcp_actions.notes_append.NOTES_FILE", notes_file),
            patch("src.phase5_mcp_actions.notes_append.AUDIT_LOG", audit_file),
            patch("src.phase5_mcp_actions.notes_append.OUTPUT_DIR", tmp_path),
        ):
            notes_execute(payload)
            notes_execute(payload)

        lines = notes_file.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_audit_log_written(self, tmp_path):
        payload = build_payload(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        notes_file = tmp_path / "notes_log.jsonl"
        audit_file = tmp_path / "audit.log"

        with (
            patch("src.phase5_mcp_actions.notes_append.NOTES_FILE", notes_file),
            patch("src.phase5_mcp_actions.notes_append.AUDIT_LOG", audit_file),
            patch("src.phase5_mcp_actions.notes_append.OUTPUT_DIR", tmp_path),
        ):
            notes_execute(payload)

        assert audit_file.exists()
        content = audit_file.read_text()
        assert "notes_append" in content
        assert "success" in content


# ---------------------------------------------------------------------------
# Email draft formatting tests
# ---------------------------------------------------------------------------

class TestFormatBullets:
    def test_format(self):
        result = _format_bullets(["First point.", "Second point."])
        assert "• First point." in result
        assert "• Second point." in result

    def test_empty(self):
        assert _format_bullets([]) == ""


class TestFormatSources:
    def test_format(self):
        result = _format_sources(_SOURCE_LINKS)
        assert "Groww Blog" in result
        assert "groww.in" in result
        assert "AMFI India" in result

    def test_empty(self):
        assert _format_sources([]) == ""


class TestBuildEmailBody:
    def test_contains_subject(self):
        body = build_email_body(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        assert f"Subject: Weekly Pulse + Fee Explainer — {_DATE}" in body

    def test_contains_pulse_section(self):
        body = build_email_body(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        assert "WEEKLY PULSE" in body
        assert "Week ending: 2026-03-21" in body
        assert "Reviews analyzed: 347" in body
        assert "Groww continues" in body

    def test_contains_fee_section(self):
        body = build_email_body(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        assert "FEE EXPLAINER" in body
        assert "Mutual Fund Exit Load" in body
        assert "• Exit load is a fee" in body

    def test_contains_sources(self):
        body = build_email_body(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        assert "groww.in" in body
        assert "amfiindia.com" in body

    def test_last_checked_fallback(self):
        body = build_email_body(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
        )
        assert f"Last checked: {_DATE}" in body

    def test_last_checked_override(self):
        body = build_email_body(
            date=_DATE,
            weekly_pulse=_WEEKLY_PULSE,
            fee_scenario=_FEE_SCENARIO,
            explanation_bullets=_BULLETS,
            source_links=_SOURCE_LINKS,
            last_checked="2026-03-20",
        )
        assert "Last checked: 2026-03-20" in body


# ---------------------------------------------------------------------------
# Email draft execute tests
# ---------------------------------------------------------------------------

class TestEmailDraftExecute:
    def test_creates_draft_file(self, tmp_path):
        audit_file = tmp_path / "audit.log"

        with (
            patch("src.phase5_mcp_actions.email_draft.OUTPUT_DIR", tmp_path),
            patch("src.phase5_mcp_actions.notes_append.AUDIT_LOG", audit_file),
            patch("src.phase5_mcp_actions.notes_append.OUTPUT_DIR", tmp_path),
        ):
            path = email_execute(
                date=_DATE,
                weekly_pulse=_WEEKLY_PULSE,
                fee_scenario=_FEE_SCENARIO,
                explanation_bullets=_BULLETS,
                source_links=_SOURCE_LINKS,
            )

        assert path.exists()
        assert path.name == f"email_draft_{_DATE}.md"
        content = path.read_text()
        assert "Subject:" in content
        assert "WEEKLY PULSE" in content
        assert "FEE EXPLAINER" in content

    def test_audit_logged_for_email(self, tmp_path):
        audit_file = tmp_path / "audit.log"

        with (
            patch("src.phase5_mcp_actions.email_draft.OUTPUT_DIR", tmp_path),
            patch("src.phase5_mcp_actions.notes_append.AUDIT_LOG", audit_file),
            patch("src.phase5_mcp_actions.notes_append.OUTPUT_DIR", tmp_path),
        ):
            email_execute(
                date=_DATE,
                weekly_pulse=_WEEKLY_PULSE,
                fee_scenario=_FEE_SCENARIO,
                explanation_bullets=_BULLETS,
                source_links=_SOURCE_LINKS,
            )

        content = audit_file.read_text()
        assert "email_draft" in content
        assert "success" in content

    def test_draft_content_matches_template(self, tmp_path):
        audit_file = tmp_path / "audit.log"

        with (
            patch("src.phase5_mcp_actions.email_draft.OUTPUT_DIR", tmp_path),
            patch("src.phase5_mcp_actions.notes_append.AUDIT_LOG", audit_file),
            patch("src.phase5_mcp_actions.notes_append.OUTPUT_DIR", tmp_path),
        ):
            path = email_execute(
                date=_DATE,
                weekly_pulse=_WEEKLY_PULSE,
                fee_scenario=_FEE_SCENARIO,
                explanation_bullets=_BULLETS,
                source_links=_SOURCE_LINKS,
                last_checked="2026-03-20",
            )

        content = path.read_text()
        assert "Last checked: 2026-03-20" in content
        assert "347" in content


# ---------------------------------------------------------------------------
# Gmail send_email tests
# ---------------------------------------------------------------------------

class TestSendEmail:
    def test_missing_sender_raises(self):
        with (
            patch("src.phase5_mcp_actions.email_draft.GMAIL_SENDER", ""),
            patch("src.phase5_mcp_actions.email_draft.GMAIL_APP_PASSWORD", "pass"),
        ):
            with pytest.raises(EmailConfigError, match="credentials not configured"):
                send_email(
                    date=_DATE,
                    weekly_pulse=_WEEKLY_PULSE,
                    fee_scenario=_FEE_SCENARIO,
                    explanation_bullets=_BULLETS,
                    source_links=_SOURCE_LINKS,
                    recipient="test@example.com",
                )

    def test_missing_password_raises(self):
        with (
            patch("src.phase5_mcp_actions.email_draft.GMAIL_SENDER", "me@gmail.com"),
            patch("src.phase5_mcp_actions.email_draft.GMAIL_APP_PASSWORD", ""),
        ):
            with pytest.raises(EmailConfigError, match="credentials not configured"):
                send_email(
                    date=_DATE,
                    weekly_pulse=_WEEKLY_PULSE,
                    fee_scenario=_FEE_SCENARIO,
                    explanation_bullets=_BULLETS,
                    source_links=_SOURCE_LINKS,
                    recipient="test@example.com",
                )

    def test_missing_recipient_raises(self):
        with (
            patch("src.phase5_mcp_actions.email_draft.GMAIL_SENDER", "me@gmail.com"),
            patch("src.phase5_mcp_actions.email_draft.GMAIL_APP_PASSWORD", "pass"),
            patch("src.phase5_mcp_actions.email_draft.GMAIL_RECIPIENT", ""),
        ):
            with pytest.raises(EmailConfigError, match="No recipient"):
                send_email(
                    date=_DATE,
                    weekly_pulse=_WEEKLY_PULSE,
                    fee_scenario=_FEE_SCENARIO,
                    explanation_bullets=_BULLETS,
                    source_links=_SOURCE_LINKS,
                )

    def test_successful_send(self, tmp_path):
        mock_smtp_instance = MagicMock()
        mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=False)
        audit_file = tmp_path / "audit.log"

        with (
            patch("src.phase5_mcp_actions.email_draft.GMAIL_SENDER", "me@gmail.com"),
            patch("src.phase5_mcp_actions.email_draft.GMAIL_APP_PASSWORD", "testpass"),
            patch("src.phase5_mcp_actions.email_draft.smtplib.SMTP", mock_smtp_class),
            patch("src.phase5_mcp_actions.email_draft.OUTPUT_DIR", tmp_path),
            patch("src.phase5_mcp_actions.notes_append.AUDIT_LOG", audit_file),
            patch("src.phase5_mcp_actions.notes_append.OUTPUT_DIR", tmp_path),
        ):
            send_email(
                date=_DATE,
                weekly_pulse=_WEEKLY_PULSE,
                fee_scenario=_FEE_SCENARIO,
                explanation_bullets=_BULLETS,
                source_links=_SOURCE_LINKS,
                recipient="team@example.com",
            )

        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("me@gmail.com", "testpass")
        mock_smtp_instance.sendmail.assert_called_once()

        call_args = mock_smtp_instance.sendmail.call_args
        assert call_args[0][0] == "me@gmail.com"
        assert call_args[0][1] == ["team@example.com"]
        raw_msg = call_args[0][2]
        assert "From: me@gmail.com" in raw_msg
        assert "To: team@example.com" in raw_msg
        assert "Weekly_Pulse" in raw_msg or "Weekly Pulse" in raw_msg

    def test_send_also_saves_draft(self, tmp_path):
        mock_smtp_instance = MagicMock()
        mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=False)
        audit_file = tmp_path / "audit.log"

        with (
            patch("src.phase5_mcp_actions.email_draft.GMAIL_SENDER", "me@gmail.com"),
            patch("src.phase5_mcp_actions.email_draft.GMAIL_APP_PASSWORD", "testpass"),
            patch("src.phase5_mcp_actions.email_draft.smtplib.SMTP", mock_smtp_class),
            patch("src.phase5_mcp_actions.email_draft.OUTPUT_DIR", tmp_path),
            patch("src.phase5_mcp_actions.notes_append.AUDIT_LOG", audit_file),
            patch("src.phase5_mcp_actions.notes_append.OUTPUT_DIR", tmp_path),
        ):
            send_email(
                date=_DATE,
                weekly_pulse=_WEEKLY_PULSE,
                fee_scenario=_FEE_SCENARIO,
                explanation_bullets=_BULLETS,
                source_links=_SOURCE_LINKS,
                recipient="team@example.com",
            )

        draft = tmp_path / f"email_draft_{_DATE}.md"
        assert draft.exists()
        assert "WEEKLY PULSE" in draft.read_text()

    def test_audit_logged_for_send(self, tmp_path):
        mock_smtp_instance = MagicMock()
        mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=False)
        audit_file = tmp_path / "audit.log"

        with (
            patch("src.phase5_mcp_actions.email_draft.GMAIL_SENDER", "me@gmail.com"),
            patch("src.phase5_mcp_actions.email_draft.GMAIL_APP_PASSWORD", "testpass"),
            patch("src.phase5_mcp_actions.email_draft.smtplib.SMTP", mock_smtp_class),
            patch("src.phase5_mcp_actions.email_draft.OUTPUT_DIR", tmp_path),
            patch("src.phase5_mcp_actions.notes_append.AUDIT_LOG", audit_file),
            patch("src.phase5_mcp_actions.notes_append.OUTPUT_DIR", tmp_path),
        ):
            send_email(
                date=_DATE,
                weekly_pulse=_WEEKLY_PULSE,
                fee_scenario=_FEE_SCENARIO,
                explanation_bullets=_BULLETS,
                source_links=_SOURCE_LINKS,
                recipient="team@example.com",
            )

        content = audit_file.read_text()
        assert "email_send" in content
        assert "success" in content
        assert "team@example.com" in content

    def test_auth_error_raises_config_error(self):
        mock_smtp_instance = MagicMock()
        mock_smtp_class = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_instance.__exit__ = MagicMock(return_value=False)
        mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"Authentication failed"
        )

        with (
            patch("src.phase5_mcp_actions.email_draft.GMAIL_SENDER", "me@gmail.com"),
            patch("src.phase5_mcp_actions.email_draft.GMAIL_APP_PASSWORD", "badpass"),
            patch("src.phase5_mcp_actions.email_draft.smtplib.SMTP", mock_smtp_class),
        ):
            with pytest.raises(EmailConfigError, match="authentication failed"):
                send_email(
                    date=_DATE,
                    weekly_pulse=_WEEKLY_PULSE,
                    fee_scenario=_FEE_SCENARIO,
                    explanation_bullets=_BULLETS,
                    source_links=_SOURCE_LINKS,
                    recipient="team@example.com",
                )
