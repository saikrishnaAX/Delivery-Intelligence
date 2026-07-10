"""Nature of issues in the first 2 full months after AI adoption (May–Jun 2026).

Run: python -m scripts.post_ai_issue_nature
"""
from __future__ import annotations

import json
from pathlib import Path

from app.database import SessionLocal
from app.services.post_ai_issue_analysis import analyze_post_ai_issues


def main() -> None:
    db = SessionLocal()
    try:
        report = analyze_post_ai_issues(db)
        out_json = Path(__file__).resolve().parents[2] / "assets" / "post-ai-issue-nature.json"
        out_md = Path(__file__).resolve().parents[2] / "assets" / "post-ai-issue-nature.md"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        out_md.write_text(_markdown(report), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nWrote {out_md}")
    finally:
        db.close()


def _markdown(r: dict) -> str:
    lines = [
        "# Nature of Issues — Post-AI (May–Jun 2026)",
        "",
        f"**Period:** {r['period']}  ",
        f"**Bugs created:** {r['total_bugs_created']} (of {r['total_tickets_created']} total tickets)  ",
        f"**Still open:** {r['bugs_still_open']}",
        "",
        "## Executive summary",
        "",
    ]
    for s in r["narrative_summary"]:
        lines.append(f"- {s}")
    lines.extend([
        "",
        "## Root cause themes (from ticket title + description)",
        "",
        "| Theme | Bug count |",
        "|-------|-----------|",
    ])
    for row in r["root_cause_themes"]:
        lines.append(f"| {row['theme']} | {row['count']} |")

    lines.extend([
        "",
        "## Engineering-fix clusters (same code change would fix)",
        "",
        "| Recurring issue | Engineering fix area | Bugs | Example tickets |",
        "|-----------------|----------------------|------|-----------------|",
    ])
    for g in r["engineering_fix_groups"]:
        examples = "; ".join(g.get("sample_titles", [])[:2])
        if len(examples) > 80:
            examples = examples[:77] + "..."
        lines.append(f"| {g['issue_name']} | {g['engineering_fix']} | {g['bug_count']} | {examples} |")

    lines.extend([
        "",
        "## Product modules most affected",
        "",
        "| Module | Bugs |",
        "|--------|------|",
    ])
    for row in r["product_modules_affected"]:
        lines.append(f"| {row['module']} | {row['count']} |")

    lines.extend([
        "",
        "## Priority mix",
        "",
        "| Priority | Count |",
        "|----------|-------|",
    ])
    for row in r["priority_breakdown"]:
        lines.append(f"| {row['priority']} | {row['count']} |")

    if r.get("recommended_focus"):
        lines.extend([
            "",
            "## Recommended engineering focus",
            "",
        ])
        for i, item in enumerate(r["recommended_focus"], 1):
            lines.append(f"{i}. {item}")

    lines.extend([
        "",
        "---",
        "*Evidence from synced Asana tickets · rule-based classification · internal use only*",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    main()
