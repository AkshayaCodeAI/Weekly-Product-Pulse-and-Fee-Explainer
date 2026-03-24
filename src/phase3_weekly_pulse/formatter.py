from __future__ import annotations

import json
from pathlib import Path

from src.config import OUTPUT_DIR
from src.phase3_weekly_pulse.generator import PulseResult


def to_markdown(pulse: PulseResult) -> str:
    """Render a PulseResult as a human-readable Markdown report."""
    lines = [
        f"# Weekly Pulse — Week of {pulse.week_ending}",
        "",
        f"**Reviews analyzed:** {pulse.total_reviews}  ",
        f"**Average rating:** {pulse.avg_rating:.1f}/5",
        "",
        "---",
        "",
        "## Top Themes",
        "",
    ]

    for t in pulse.themes:
        sentiment_badge = {
            "negative": "🔴",
            "positive": "🟢",
            "mixed": "🟡",
        }.get(t.get("sentiment", ""), "⚪")
        lines.append(
            f"{t['rank']}. **{t['name']}** {sentiment_badge} — {t['description']} "
            f"({t['review_count']} reviews)"
        )

    lines += ["", "---", "", "## User Quotes", ""]

    for q in pulse.quotes:
        stars = "★" * q.get("star_rating", 0) + "☆" * (5 - q.get("star_rating", 0))
        lines.append(f"> \"{q['text']}\"  ")
        lines.append(f"> — {stars} | Theme: {q['theme']}")
        lines.append("")

    lines += ["---", "", "## Weekly Note", "", pulse.weekly_note, ""]

    lines += ["---", "", "## Action Ideas", ""]
    for i, idea in enumerate(pulse.action_ideas, 1):
        lines.append(f"{i}. {idea}")

    lines.append("")
    return "\n".join(lines)


def to_json(pulse: PulseResult) -> str:
    """Render a PulseResult as a JSON string for MCP actions."""
    payload = {
        "week_ending": pulse.week_ending,
        "total_reviews": pulse.total_reviews,
        "avg_rating": pulse.avg_rating,
        "themes": pulse.themes,
        "quotes": pulse.quotes,
        "weekly_note": pulse.weekly_note,
        "action_ideas": pulse.action_ideas,
        "word_count": pulse.word_count,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def save_markdown(pulse: PulseResult, output_dir: Path | None = None) -> Path:
    """Save the Markdown report to output/pulse_YYYY-MM-DD.md."""
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"pulse_{pulse.week_ending}.md"
    path.write_text(to_markdown(pulse), encoding="utf-8")
    return path


def save_json(pulse: PulseResult, output_dir: Path | None = None) -> Path:
    """Save the JSON payload to output/pulse_YYYY-MM-DD.json."""
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"pulse_{pulse.week_ending}.json"
    path.write_text(to_json(pulse), encoding="utf-8")
    return path


def save_both(pulse: PulseResult, output_dir: Path | None = None) -> tuple[Path, Path]:
    """Save both Markdown and JSON formats. Returns (md_path, json_path)."""
    md_path = save_markdown(pulse, output_dir)
    json_path = save_json(pulse, output_dir)
    return md_path, json_path
