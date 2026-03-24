import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
DATA_DIR = PROJECT_ROOT / "data"


def _get_secret(key: str, default: str = "") -> str:
    """Read from Streamlit secrets (cloud) first, then fall back to env vars."""
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


GROQ_API_KEY: str = _get_secret("GROQ_API_KEY")
GROQ_MODEL: str = _get_secret("GROQ_MODEL", "llama-3.3-70b-versatile")

GMAIL_SENDER: str = _get_secret("GMAIL_SENDER")
GMAIL_APP_PASSWORD: str = _get_secret("GMAIL_APP_PASSWORD")
GMAIL_RECIPIENT: str = _get_secret("GMAIL_RECIPIENT")

REVIEW_WINDOW_WEEKS: int = int(_get_secret("REVIEW_WINDOW_WEEKS", "8"))

MAX_THEMES: int = 5
TOP_THEMES: int = 3
MAX_QUOTES: int = 3
PULSE_WORD_LIMIT: int = 250
FEE_BULLET_LIMIT: int = 6

EXPECTED_CSV_COLUMNS = {
    "reviewId",
    "userName",
    "content",
    "score",
    "thumbsUpCount",
    "at",
}

FEE_SOURCE_LINKS = [
    {
        "title": "What is Exit Load in Mutual Funds - Groww",
        "url": "https://groww.in/blog/what-is-exit-load-in-mutual-funds",
    },
    {
        "title": "Exit Load - AMFI India",
        "url": "https://www.amfiindia.com/investor-corner/knowledge-center/exit-load.html",
    },
    {
        "title": "Individual Investors - SEBI",
        "url": "https://www.sebi.gov.in/individual-investors.html",
    },
    {
        "title": "Exit Load Help - Groww",
        "url": "https://groww.in/mutual-funds/help/transaction-related/exit-load",
    },
]
