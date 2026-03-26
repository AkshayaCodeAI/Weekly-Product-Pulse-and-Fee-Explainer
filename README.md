# Weekly Product Pulse & Fee Explainer

A Streamlit-powered tool that transforms **Groww Play Store reviews** into a concise weekly pulse report and generates neutral, source-backed fee explanations for mutual fund scenarios — all driven by the **Groq LLM**.

---

## What It Does

1. **Weekly Pulse Report** — Upload a CSV of Play Store reviews, and the pipeline automatically:
   - Cleans PII (emails, phone numbers, Aadhaar, PAN)
   - Groups reviews into ranked themes using an LLM
   - Extracts verbatim user quotes
   - Generates a 250-word weekly note with 3 action ideas

2. **Fee Explainer** — Enter a fee scenario (e.g. "Mutual Fund Exit Load") and get a structured, neutral bullet-point explanation with official source links from Groww, AMFI, and SEBI.

3. **MCP Actions** (approval-gated) — After reviewing the one-pager, approve actions to:
   - Append results to a local notes log (`notes_log.jsonl`)
   - Save or send an email draft via Gmail SMTP

---

## Demo Screenshot

> Upload a reviews CSV → Click "Generate Pulse" → View the one-pager → Approve MCP actions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| LLM | Groq (`llama-3.3-70b-versatile`) |
| UI | Streamlit |
| Data | pandas, Pydantic |
| Testing | pytest |
| Config | python-dotenv |

---

## Project Structure

```
Weekly-Product-Pulse-and-Fee-Explainer/
├── app.py                          # Streamlit entry point
├── requirements.txt
├── .env.example
├── ARCHITECTURE.md                 # Detailed phase-wise architecture
├── data/
│   └── sample_reviews.csv          # 50-row synthetic dataset
├── src/
│   ├── config.py                   # Shared configuration
│   ├── pipeline.py                 # Pipeline orchestrator
│   ├── phase1_data_ingestion/      # CSV loading + PII scrubbing
│   ├── phase2_theme_analysis/      # Groq LLM theme grouping + quote extraction
│   ├── phase3_weekly_pulse/        # Weekly note generation + formatting
│   ├── phase4_fee_explainer/       # Neutral fee explanation engine
│   ├── phase5_mcp_actions/         # Notes append + email draft actions
│   └── phase6_ui_integration/      # One-pager renderer + UI components
├── tests/                          # pytest tests for each phase
│   ├── phase1/ ... phase6/
└── output/                         # Generated artifacts (gitignored)
```

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- A [Groq API key](https://console.groq.com/) (free tier works)

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/Weekly-Product-Pulse-and-Fee-Explainer.git
cd Weekly-Product-Pulse-and-Fee-Explainer

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Copy the example environment file and add your Groq API key:

```bash
cp .env.example .env
```

Edit `.env`:

```
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=llama-3.3-70b-versatile
REVIEW_WINDOW_WEEKS=8
```

**Optional — Gmail SMTP** (for sending email drafts):

```
GMAIL_SENDER=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
GMAIL_RECIPIENT=recipient@example.com
```

> Generate an App Password at https://myaccount.google.com/apppasswords (requires 2-Step Verification).

### Run the App

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. Upload the included `data/sample_reviews.csv` to try it out.

---

## How It Works

The pipeline runs 6 stages when you click **Generate Pulse**:

```
CSV Upload → PII Scrubbing → Theme Analysis (LLM) → Quote Extraction (LLM)
          → Weekly Note Generation (LLM) → Fee Explanation (LLM) → One-Pager
```

| Stage | Module | What Happens |
|---|---|---|
| 1 | `phase1_data_ingestion` | Parses CSV, validates columns, filters by date window, removes PII via regex |
| 2 | `phase2_theme_analysis` | Sends cleaned reviews to Groq LLM; groups into up to 5 themes, ranks top 3, extracts 3 verbatim quotes |
| 3 | `phase3_weekly_pulse` | Generates a 250-word weekly note with sentiment trends, theme highlights, inline quotes, and 3 action ideas |
| 4 | `phase4_fee_explainer` | Produces up to 6 neutral bullet points for the fee scenario with 2 official source links |
| 5 | `phase5_mcp_actions` | Approval-gated actions: append to notes log, create/send email draft |
| 6 | `phase6_ui_integration` | Renders the full one-pager with metric cards, theme breakdowns, quotes, and the fee panel |

All LLM calls use **JSON mode** for structured, parseable responses.

---

## PII Protection

The system uses a two-pass PII scrubbing approach:

- **Pre-LLM pass** — Regex-based removal of emails, phone numbers (Indian & international), Aadhaar numbers, and PAN before any data is sent to the Groq API.
- **Post-LLM pass** — Validates LLM output to catch any leaked PII before rendering.

No personally identifiable information ever leaves the local machine.

---

## Running Tests

```bash
pytest
```

Tests cover CSV validation, PII scrubbing, theme analysis parsing, fee explainer output, and MCP actions.

---

## Streamlit Cloud Deployment

The app supports deployment on [Streamlit Community Cloud](https://streamlit.io/cloud):

1. Push the repo to GitHub.
2. Connect it on Streamlit Cloud.
3. Add your secrets in the Streamlit Cloud dashboard under **Settings → Secrets**:
   ```toml
   GROQ_API_KEY = "gsk_your_key_here"
   GROQ_MODEL = "llama-3.3-70b-versatile"
   ```
4. The app automatically reads from `st.secrets` when running on the cloud.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Groq API key for LLM inference |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model to use |
| `REVIEW_WINDOW_WEEKS` | No | `8` | Number of weeks to filter reviews |
| `GMAIL_SENDER` | No | — | Gmail address for sending drafts |
| `GMAIL_APP_PASSWORD` | No | — | Gmail App Password (not your account password) |
| `GMAIL_RECIPIENT` | No | — | Default recipient for email drafts |

---

