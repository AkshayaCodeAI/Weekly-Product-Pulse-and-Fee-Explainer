from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from src.config import GMAIL_APP_PASSWORD, GMAIL_RECIPIENT, GMAIL_SENDER, OUTPUT_DIR
from src.phase5_mcp_actions.notes_append import _ensure_output_dir, _write_audit

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_TEMPLATE = """\
Subject: Weekly Pulse + Fee Explainer — {date}

---
WEEKLY PULSE
Week ending: {week_ending}
Reviews analyzed: {total_reviews}

{weekly_note}

---
FEE EXPLAINER
Scenario: {fee_scenario}

{bullet_points}

Sources:
{source_links}

Last checked: {last_checked}
---
"""


def _format_bullets(bullets: list[str]) -> str:
    return "\n".join(f"• {b}" for b in bullets)


def _format_sources(links: list[dict[str, str]]) -> str:
    return "\n".join(f"- {link.get('title', '')}: {link.get('url', '')}" for link in links)


def build_email_body(
    date: str,
    weekly_pulse: dict[str, Any],
    fee_scenario: str,
    explanation_bullets: list[str],
    source_links: list[dict[str, str]],
    last_checked: str = "",
) -> str:
    """Render the email body from pulse and fee data."""
    return EMAIL_TEMPLATE.format(
        date=date,
        week_ending=weekly_pulse.get("week_ending", date),
        total_reviews=weekly_pulse.get("total_reviews", 0),
        weekly_note=weekly_pulse.get("weekly_note", ""),
        fee_scenario=fee_scenario,
        bullet_points=_format_bullets(explanation_bullets),
        source_links=_format_sources(source_links),
        last_checked=last_checked or date,
    )


def execute(
    date: str,
    weekly_pulse: dict[str, Any],
    fee_scenario: str,
    explanation_bullets: list[str],
    source_links: list[dict[str, str]],
    last_checked: str = "",
) -> Path:
    """
    Generate an email draft file (no SMTP, file-based only).

    Writes to output/email_draft_YYYY-MM-DD.md and logs to audit.log.
    Returns the path to the created draft file.
    """
    try:
        _ensure_output_dir()

        body = build_email_body(
            date=date,
            weekly_pulse=weekly_pulse,
            fee_scenario=fee_scenario,
            explanation_bullets=explanation_bullets,
            source_links=source_links,
            last_checked=last_checked,
        )

        draft_path = OUTPUT_DIR / f"email_draft_{date}.md"
        draft_path.write_text(body, encoding="utf-8")

        _write_audit("email_draft", "success", str(draft_path))
        logger.info("Email draft saved to %s", draft_path)
        return draft_path
    except Exception as exc:
        _write_audit("email_draft", "error", str(exc))
        logger.error("Failed to create email draft: %s", exc)
        raise


class EmailConfigError(Exception):
    """Raised when Gmail SMTP credentials are not configured."""


def send_email(
    date: str,
    weekly_pulse: dict[str, Any],
    fee_scenario: str,
    explanation_bullets: list[str],
    source_links: list[dict[str, str]],
    last_checked: str = "",
    recipient: str = "",
) -> None:
    """
    Send the weekly pulse email via Gmail SMTP.

    Uses App Password authentication over TLS.
    Also saves a local draft file for the audit trail.
    Raises EmailConfigError if sender/password are not set.
    """
    sender = GMAIL_SENDER
    password = GMAIL_APP_PASSWORD
    to_addr = recipient or GMAIL_RECIPIENT

    if not sender or not password:
        raise EmailConfigError(
            "Gmail credentials not configured. "
            "Set GMAIL_SENDER and GMAIL_APP_PASSWORD in your .env file. "
            "See .env.example for instructions."
        )
    if not to_addr:
        raise EmailConfigError("No recipient email address provided.")

    subject = f"Weekly Pulse + Fee Explainer — {date}"
    body = build_email_body(
        date=date,
        weekly_pulse=weekly_pulse,
        fee_scenario=fee_scenario,
        explanation_bullets=explanation_bullets,
        source_links=source_links,
        last_checked=last_checked,
    )

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [to_addr], msg.as_string())

        _write_audit("email_send", "success", f"to={to_addr}")
        logger.info("Email sent to %s", to_addr)

        execute(
            date=date,
            weekly_pulse=weekly_pulse,
            fee_scenario=fee_scenario,
            explanation_bullets=explanation_bullets,
            source_links=source_links,
            last_checked=last_checked,
        )
    except smtplib.SMTPAuthenticationError as exc:
        _write_audit("email_send", "error", f"auth_failed: {exc}")
        logger.error("SMTP authentication failed: %s", exc)
        raise EmailConfigError(
            "Gmail authentication failed. Check your GMAIL_SENDER and "
            "GMAIL_APP_PASSWORD. Make sure you're using an App Password, "
            "not your regular Gmail password."
        ) from exc
    except smtplib.SMTPException as exc:
        _write_audit("email_send", "error", str(exc))
        logger.error("SMTP error: %s", exc)
        raise
