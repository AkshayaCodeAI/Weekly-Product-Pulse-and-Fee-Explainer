"""
Streamlit entry point for the Weekly Product Pulse and Fee Explainer.

Launch with:  streamlit run app.py
"""

from __future__ import annotations

import json
import logging
import os

import streamlit as st

# Inject Streamlit Cloud secrets into env vars before config.py loads.
# This ensures os.getenv() works on both local (.env) and cloud (st.secrets).
try:
    for key in st.secrets:
        if key not in os.environ:
            os.environ[key] = str(st.secrets[key])
except Exception:
    pass

from src.config import GMAIL_RECIPIENT, GMAIL_SENDER, GROQ_API_KEY
from src.phase1_data_ingestion.csv_loader import CSVValidationError
from src.phase3_weekly_pulse.formatter import to_markdown
from src.phase5_mcp_actions import notes_append, email_draft
from src.phase6_ui_integration.one_pager import render_one_pager
from src.pipeline import PipelineError, run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Weekly Pulse & Fee Explainer",
    page_icon="\U0001f4ca",
    layout="wide",
)


def _check_api_key() -> bool:
    """Show an error banner if the Groq API key is missing."""
    if not GROQ_API_KEY:
        st.error(
            "**Groq API key not configured.** "
            "Create a `.env` file with `GROQ_API_KEY=gsk_...` "
            "and restart the app. See `.env.example` for reference."
        )
        return False
    return True


def _render_sidebar() -> tuple[bytes | None, int, str]:
    """
    Render the sidebar with upload, config, and return user inputs.
    Returns (csv_bytes, weeks, fee_scenario).
    """
    st.sidebar.title("\U0001f4ca Weekly Pulse")
    st.sidebar.markdown("---")

    uploaded = st.sidebar.file_uploader(
        "Upload Reviews CSV",
        type=["csv"],
        help="Export from Google Play Console (last 8-12 weeks)",
    )
    csv_bytes = uploaded.getvalue() if uploaded else None

    weeks = st.sidebar.slider(
        "Analysis Window (weeks)",
        min_value=8,
        max_value=12,
        value=8,
        help="Filter reviews to the most recent N weeks",
    )

    fee_scenario = st.sidebar.text_input(
        "Fee Scenario",
        value="Mutual Fund Exit Load",
        help="Describe the fee scenario to explain",
    )

    return csv_bytes, weeks, fee_scenario


def _render_mcp_actions(pulse_data, fee_data) -> None:
    """Render the MCP action buttons in the sidebar after generation."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("MCP Actions")

    pulse_dict = pulse_data.model_dump()
    fee_dict = fee_data.model_dump()
    current_date = pulse_data.week_ending
    source_links_raw = [{"title": sl.title, "url": sl.url} for sl in fee_data.source_links]

    col1, col2 = st.sidebar.columns(2)

    if col1.button("Append to Notes", type="primary", use_container_width=True):
        try:
            payload = notes_append.build_payload(
                date=current_date,
                weekly_pulse=pulse_dict,
                fee_scenario=fee_data.scenario,
                explanation_bullets=fee_data.bullets,
                source_links=source_links_raw,
            )
            notes_append.execute(payload)
            st.sidebar.success("Appended to notes_log.jsonl")
        except Exception as exc:
            st.sidebar.error(f"Failed to append notes: {exc}")

    if col2.button("Save Email Draft", type="primary", use_container_width=True):
        try:
            draft_path = email_draft.execute(
                date=current_date,
                weekly_pulse=pulse_dict,
                fee_scenario=fee_data.scenario,
                explanation_bullets=fee_data.bullets,
                source_links=source_links_raw,
                last_checked=fee_data.last_checked,
            )
            st.sidebar.success(f"Draft saved: {draft_path.name}")
            with open(draft_path, encoding="utf-8") as f:
                st.sidebar.download_button(
                    "Download Email Draft",
                    f.read(),
                    file_name=draft_path.name,
                    mime="text/markdown",
                )
        except Exception as exc:
            st.sidebar.error(f"Failed to create draft: {exc}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Send via Gmail")
    gmail_configured = bool(GMAIL_SENDER)
    recipient = st.sidebar.text_input(
        "Recipient Email",
        value=GMAIL_RECIPIENT,
        help="Email address to send the weekly pulse report to",
    )

    send_disabled = not gmail_configured
    send_help = (
        "Set GMAIL_SENDER and GMAIL_APP_PASSWORD in .env to enable"
        if send_disabled else None
    )
    if st.sidebar.button(
        "Send via Gmail",
        type="primary",
        use_container_width=True,
        disabled=send_disabled,
        help=send_help,
    ):
        try:
            email_draft.send_email(
                date=current_date,
                weekly_pulse=pulse_dict,
                fee_scenario=fee_data.scenario,
                explanation_bullets=fee_data.bullets,
                source_links=source_links_raw,
                last_checked=fee_data.last_checked,
                recipient=recipient,
            )
            st.sidebar.success(f"Email sent to {recipient}")
        except email_draft.EmailConfigError as exc:
            st.sidebar.error(str(exc))
        except Exception as exc:
            st.sidebar.error(f"Failed to send email: {exc}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Download One-Pager")
    md_content = to_markdown(pulse_data)
    st.sidebar.download_button(
        "Download as Markdown",
        md_content,
        file_name=f"weekly_pulse_{current_date}.md",
        mime="text/markdown",
        use_container_width=True,
    )


def main() -> None:
    if not _check_api_key():
        return

    csv_bytes, weeks, fee_scenario = _render_sidebar()

    if csv_bytes is None:
        st.info(
            "\U0001f449 **Upload a reviews CSV** in the sidebar to get started. "
            "The file should be exported from the Google Play Console "
            "and contain columns: reviewId, userName, content, score, "
            "thumbsUpCount, at."
        )
        return

    generate_clicked = st.sidebar.button(
        "Generate Pulse",
        type="primary",
        use_container_width=True,
    )

    if generate_clicked:
        try:
            with st.spinner("Running analysis pipeline... This may take a minute."):
                pulse, fee = run_pipeline(csv_bytes, weeks=weeks, fee_scenario=fee_scenario)

            st.session_state["pulse"] = pulse
            st.session_state["fee"] = fee
        except CSVValidationError as exc:
            st.error(f"**Invalid CSV format:** {exc}")
            return
        except PipelineError as exc:
            st.warning(str(exc))
            return
        except Exception as exc:
            st.error(f"**Pipeline error:** {exc}")
            logger.exception("Pipeline failed")
            return

    if "pulse" in st.session_state and "fee" in st.session_state:
        pulse = st.session_state["pulse"]
        fee = st.session_state["fee"]
        render_one_pager(pulse, fee)
        _render_mcp_actions(pulse, fee)
    elif not generate_clicked:
        st.info("\U0001f449 Configure your settings and click **Generate Pulse** in the sidebar.")


if __name__ == "__main__":
    main()
