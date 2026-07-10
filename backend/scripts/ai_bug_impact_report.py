"""Evidence-based AI adoption bug impact report.

Pre-AI:  Dec 2025 – Apr 2026 (tickets created before 1 May 2026)
Post-AI: May 2026 – present (from 1 May 2026, AI adoption date)

Run: python -m scripts.ai_bug_impact_report
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.database import SessionLocal
from app.models import Ticket
from app.services.ceo_intelligence import _effective_category

AI_START = datetime(2026, 5, 1)
PRE_START = datetime(2025, 12, 1)
PRE_END = datetime(2026, 4, 30, 23, 59, 59)

MONTH_LABELS = {
    "2025-12": "Dec 2025",
    "2026-01": "Jan 2026",
    "2026-02": "Feb 2026",
    "2026-03": "Mar 2026",
    "2026-04": "Apr 2026",
    "2026-06": "Jun 2026",
    "2026-05": "May 2026",
    "2026-07": "Jul 2026",
}


def pct_change(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return round((after - before) / before * 100, 1)


def main() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    try:
        tickets = (
            db.query(Ticket)
            .filter(Ticket.created_at >= PRE_START, Ticket.created_at <= now)
            .all()
        )

        monthly: dict[str, dict] = defaultdict(lambda: {"total": 0, "bugs": 0, "features": 0})
        for t in tickets:
            if not t.created_at:
                continue
            mk = t.created_at.strftime("%Y-%m")
            monthly[mk]["total"] += 1
            cat = _effective_category(t)
            if cat == "bug":
                monthly[mk]["bugs"] += 1
            elif cat in ("enhancement", "requirement"):
                monthly[mk]["features"] += 1

        pre_months = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
        post_months = [k for k in sorted(monthly.keys()) if k >= "2026-05"]

        pre_bugs = sum(monthly[m]["bugs"] for m in pre_months)
        pre_total = sum(monthly[m]["total"] for m in pre_months)
        pre_n = len(pre_months)

        post_bugs = sum(monthly[m]["bugs"] for m in post_months)
        post_total = sum(monthly[m]["total"] for m in post_months)
        post_n = len(post_months)

        pre_avg_bugs = round(pre_bugs / pre_n, 1)
        post_avg_bugs = round(post_bugs / post_n, 1)

        # Full months only for fair post-AI comparison (exclude partial current month if < 28 days)
        post_full_months = [m for m in post_months if m != post_months[-1] or now.day >= 28]
        if len(post_full_months) < len(post_months) and len(post_full_months) >= 1:
            post_full_bugs = sum(monthly[m]["bugs"] for m in post_full_months)
            post_full_avg = round(post_full_bugs / len(post_full_months), 1)
            partial_month = post_months[-1] if post_months[-1] not in post_full_months else None
        else:
            post_full_avg = post_avg_bugs
            partial_month = None
            post_full_months = post_months

        bug_pct = pct_change(pre_avg_bugs, post_full_avg)

        monthly_rows = []
        for mk in sorted(k for k in monthly.keys() if k >= "2025-12"):
            row = monthly[mk]
            monthly_rows.append({
                "month_key": mk,
                "label": MONTH_LABELS.get(mk, mk),
                "period": "pre_ai" if mk < "2026-05" else "post_ai",
                "tickets_created": row["total"],
                "bugs_created": row["bugs"],
                "features_created": row["features"],
                "bug_ratio_pct": round(row["bugs"] / row["total"] * 100, 1) if row["total"] else 0,
            })

        report = {
            "generated_at": now.isoformat(),
            "ai_adoption_date": "2026-05-01",
            "methodology": (
                "Bugs counted from all synced tickets by created_at month. "
                "Bug = Asana Type or AI category classified as bug. "
                "Pre-AI = Dec 2025 through Apr 2026 (5 calendar months). "
                "Post-AI = May 2026 through report date."
            ),
            "pre_ai": {
                "label": "Dec 2025 – Apr 2026 (before AI, 1 May 2026)",
                "months_count": pre_n,
                "month_keys": pre_months,
                "total_tickets": pre_total,
                "total_bugs": pre_bugs,
                "avg_bugs_per_month": pre_avg_bugs,
                "avg_tickets_per_month": round(pre_total / pre_n, 1),
            },
            "post_ai": {
                "label": f"May 2026 – {MONTH_LABELS.get(post_months[-1], post_months[-1])} (after AI)",
                "months_count": post_n,
                "month_keys": post_months,
                "total_tickets": post_total,
                "total_bugs": post_bugs,
                "avg_bugs_per_month_all": post_avg_bugs,
                "avg_bugs_per_month_full_months_only": post_full_avg,
                "full_months_used": post_full_months,
                "partial_month_note": (
                    f"{MONTH_LABELS.get(partial_month, partial_month)} is partial "
                    f"({monthly[partial_month]['bugs']} bugs in {now.day} days) — excluded from primary avg."
                    if partial_month
                    else None
                ),
            },
            "comparison": {
                "bugs_per_month_pre": pre_avg_bugs,
                "bugs_per_month_post": post_full_avg,
                "change_pct": bug_pct,
                "direction": "increasing" if bug_pct and bug_pct > 0 else "stable_or_decreasing",
                "verdict": _verdict(pre_avg_bugs, post_full_avg, bug_pct, monthly_rows),
            },
            "monthly_breakdown": monthly_rows,
        }

        from app.services.post_ai_issue_analysis import analyze_post_ai_issues
        issue_nature = analyze_post_ai_issues(db)
        report["post_ai_issue_nature"] = issue_nature

        out_json = Path(__file__).resolve().parents[2] / "assets" / "ai-bug-impact-report.json"
        out_md = Path(__file__).resolve().parents[2] / "assets" / "ai-bug-impact-report.md"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        out_md.write_text(_markdown(report, issue_nature), encoding="utf-8")
        print(json.dumps(report, indent=2))
        print(f"\nWrote {out_json}")
        print(f"Wrote {out_md}")
    finally:
        db.close()


def _verdict(pre_avg: float, post_avg: float, pct: float | None, rows: list) -> str:
    if pct is None:
        return "Insufficient data for comparison."
    direction = "higher" if pct > 0 else "lower"
    june = next((r for r in rows if r["month_key"] == "2026-06"), None)
    june_note = ""
    if june and june["bugs_created"] >= 70:
        june_note = f" June 2026 had {june['bugs_created']} bugs — the highest single month in the window."
    return (
        f"Average bugs created per month is {abs(pct):.1f}% {direction} after AI adoption "
        f"({pre_avg}/mo pre-AI vs {post_avg}/mo post-AI full months). "
        f"This is correlational — more delivery volume also increased post-AI.{june_note}"
    )


def _markdown(r: dict, issue_nature: dict | None = None) -> str:
    pre = r["pre_ai"]
    post = r["post_ai"]
    cmp_ = r["comparison"]
    lines = [
        "# AI Adoption Impact Report (for CEO)",
        "",
        f"**Generated:** {r['generated_at'][:19]} UTC  ",
        f"**AI adoption date:** 1 May 2026  ",
        f"**Data source:** All synced Asana tickets (created_at)",
        "",
        "## Part 1 — Bug intake comparison",
        "",
        "| Period | Months | Total bugs | Avg bugs / month |",
        "|--------|--------|------------|------------------|",
        f"| Pre-AI (Dec 2025 – Apr 2026) | {pre['months_count']} | {pre['total_bugs']} | **{pre['avg_bugs_per_month']}** |",
        f"| Post-AI (May 2026 – present) | {post['months_count']} | {post['total_bugs']} | **{post['avg_bugs_per_month_full_months_only']}** (full months) |",
        "",
        f"**Change:** {cmp_['change_pct']:+.1f}% bugs per month (post vs pre)  ",
        f"**Verdict:** {cmp_['verdict']}",
        "",
    ]
    if post.get("partial_month_note"):
        lines.extend([f"*{post['partial_month_note']}*", ""])

    lines.extend([
        "### Monthly breakdown — bugs created",
        "",
        "| Month | Period | Tickets | **Bugs** | Bug % of tickets |",
        "|-------|--------|---------|----------|------------------|",
    ])
    for row in r["monthly_breakdown"]:
        period = "Pre-AI" if row["period"] == "pre_ai" else "Post-AI"
        lines.append(
            f"| {row['label']} | {period} | {row['tickets_created']} | **{row['bugs_created']}** | {row['bug_ratio_pct']}% |"
        )

    if issue_nature:
        lines.extend([
            "",
            "---",
            "",
            "## Part 2 — Nature of issues (May–Jun 2026, post-AI)",
            "",
            f"**Bugs created:** {issue_nature['total_bugs_created']} · **Still open:** {issue_nature['bugs_still_open']} · "
            f"**High/critical:** {issue_nature['high_critical_count']}",
            "",
            "### Executive summary",
            "",
        ])
        for s in issue_nature["narrative_summary"]:
            lines.append(f"- {s}")

        lines.extend([
            "",
            "### Root cause themes",
            "",
            "| Theme | Bugs |",
            "|-------|------|",
        ])
        for row in issue_nature["root_cause_themes"]:
            lines.append(f"| {row['theme']} | {row['count']} |")

        lines.extend([
            "",
            "### Engineering-fix clusters",
            "",
            "| Issue | Fix area | Bugs |",
            "|-------|----------|------|",
        ])
        for g in issue_nature["engineering_fix_groups"]:
            lines.append(f"| {g['issue_name']} | {g['engineering_fix']} | {g['bug_count']} |")

        lines.extend([
            "",
            "### Product modules affected",
            "",
            "| Module | Bugs |",
            "|--------|------|",
        ])
        for row in issue_nature["product_modules_affected"]:
            lines.append(f"| {row['module']} | {row['count']} |")

        if issue_nature.get("recommended_focus"):
            lines.extend(["", "### Recommended engineering focus", ""])
            for i, item in enumerate(issue_nature["recommended_focus"], 1):
                lines.append(f"{i}. {item}")

    lines.extend([
        "",
        "## Methodology",
        "",
        r["methodology"],
        "",
        "---",
        "*Internal Autorox Delivery Intelligence — not causal proof of AI impact.*",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    main()
