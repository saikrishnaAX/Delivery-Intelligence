"""Extract module themes for CEO PPT — understanding, not ticket titles."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from app.database import SessionLocal
from app.models import RecurringIssue, Ticket
from app.services.ceo_intelligence import _effective_category
from app.services.ticket_parser import infer_module_affected

AI = datetime(2026, 5, 1)
PRE_END = datetime(2026, 4, 30, 23, 59, 59)
POST_END = datetime(2026, 6, 30, 23, 59, 59)
PRE_START = datetime(2025, 12, 1)

# Human-readable themes — map ticket text to product understanding
THEME_RULES: list[tuple[str, str, re.Pattern]] = [
    (
        "Customer Concerns (AI module)",
        "Work orders, customer concerns, Arabic/localisation, concern sync and updates",
        re.compile(
            r"customer concern|work\s*order|workorder|arabic|concern.*not|not reflect|"
            r"not updat|not getting|cep|gms|motrex|payload",
            re.I,
        ),
    ),
    (
        "Invoice & billing",
        "Invoice numbers, sequences, tax/GST, PDF content, amount mismatches",
        re.compile(
            r"invoice number|invoice.*generat|sequence|gst|tax|amount mismatch|billing|zoho",
            re.I,
        ),
    ),
    (
        "Job Card lifecycle",
        "Open/close job card, status, inward, parts on job card, vehicle on job card",
        re.compile(r"job card|jobcard|work order status|close job|open job|inward", re.I),
    ),
    (
        "Reports & analytics",
        "Report loading, sales register, HSN, offline sync, logout on reports",
        re.compile(r"report|sales register|hsn|offline.*sync|logout", re.I),
    ),
    (
        "Notifications",
        "WhatsApp, email, SMS delivery delays or failures",
        re.compile(r"whatsapp|notification|email.*not|sms|otp|deliver", re.I),
    ),
    (
        "PDF & print",
        "PDF generation, print layout, missing content in printed documents",
        re.compile(r"\bpdf\b|print|stamp|render", re.I),
    ),
    (
        "Stock & parts",
        "Stock value, bulk upload, parts inward, master data duplicates",
        re.compile(r"stock|parts inward|bulk upload|master.*part", re.I),
    ),
    (
        "Performance",
        "Slow screens, hangs, loading delays",
        re.compile(r"slow|performance|lag|hang|loading|timeout", re.I),
    ),
    (
        "UI & display",
        "Screen rendering, buttons, layout, visibility",
        re.compile(r"display|screen|button|layout|visible|blank|ui ", re.I),
    ),
    (
        "Integration & API",
        "External sync, API failures, third-party connections",
        re.compile(r"integration|api|sync fail|zoho|webhook", re.I),
    ),
]


def classify_theme(t: Ticket) -> str:
    text = f"{t.title or ''} {t.description or ''}"
    mod = infer_module_affected(t.title or "", t.description or "")
    combined = f"{mod} {text}"
    for name, _, pat in THEME_RULES:
        if pat.search(combined):
            return name
    return "Other / cross-cutting"


def theme_description(name: str) -> str:
    for n, desc, _ in THEME_RULES:
        if n == name:
            return desc
    return "Miscellaneous defects"


def run() -> dict:
    db = SessionLocal()
    try:
        all_t = db.query(Ticket).filter(
            Ticket.created_at >= PRE_START,
            Ticket.created_at <= datetime(2026, 7, 4, 23, 59, 59),
        ).all()
        bugs = [t for t in all_t if _effective_category(t) == "bug"]
        pre = [t for t in bugs if t.created_at < AI]
        post = [t for t in bugs if AI <= t.created_at <= POST_END]

        months_pre = 5.0
        months_post = 2.0

        def theme_counts(group: list[Ticket]) -> Counter:
            return Counter(classify_theme(t) for t in group)

        pre_themes = theme_counts(pre)
        post_themes = theme_counts(post)

        themes = []
        all_names = set(pre_themes) | set(post_themes)
        for name in sorted(all_names, key=lambda x: -(post_themes.get(x, 0) + pre_themes.get(x, 0))):
            b, a = pre_themes.get(name, 0), post_themes.get(name, 0)
            themes.append({
                "name": name,
                "description": theme_description(name),
                "pre": b,
                "post": a,
                "pre_per_month": round(b / months_pre, 1),
                "post_per_month": round(a / months_post, 1),
            })

        # Recurring clusters — product bugs only, group by engineering fix label
        rec = (
            db.query(RecurringIssue)
            .filter(RecurringIssue.issue_type == "product_bug")
            .order_by(RecurringIssue.priority_score.desc())
            .limit(20)
            .all()
        )
        fix_areas: dict[str, dict] = {}
        for ri in rec:
            intel = ri.intelligence or {}
            fix = str(intel.get("engineering_fix") or ri.engineering_fix_key or "General").split(":")[-1]
            fix = fix.replace("_", " ").title() if ":" in str(ri.engineering_fix_key or "") else str(intel.get("engineering_fix") or "General product area")
            key = classify_theme_from_name(ri.issue_name, ri.affected_modules or [])
            if key not in fix_areas:
                fix_areas[key] = {"tickets": 0, "clusters": 0, "trend_increasing": 0}
            fix_areas[key]["tickets"] += ri.ticket_count
            fix_areas[key]["clusters"] += 1
            if ri.trend == "increasing":
                fix_areas[key]["trend_increasing"] += 1

        # Causality stats
        causality_path = Path(__file__).resolve().parents[2] / "assets" / "ai-causality-investigation.json"
        causality = json.loads(causality_path.read_text()) if causality_path.exists() else {}

        return {
            "volume": {
                "bugs_pre_total": len(pre),
                "bugs_post_total": len(post),
                "bugs_per_month_pre": round(len(pre) / months_pre, 1),
                "bugs_per_month_post": round(len(post) / months_post, 1),
                "enh_per_month_pre": round(
                    sum(1 for t in all_t if _effective_category(t) == "enhancement" and t.created_at < AI) / months_pre, 1
                ),
                "enh_per_month_post": round(
                    sum(1 for t in all_t if _effective_category(t) == "enhancement" and AI <= t.created_at <= POST_END) / months_post, 1
                ),
            },
            "themes": themes,
            "fix_areas": fix_areas,
            "recurring_pre_ai_pct": causality.get("step2_3_classification", {}).get("pct_existed_before_ai"),
            "recurring_new_post_ai": causality.get("step2_3_classification", {}).get("category_b_new_after_ai"),
            "recurring_total": causality.get("step2_3_classification", {}).get("total_unique_recurring"),
        }
    finally:
        db.close()


def classify_theme_from_name(issue_name: str, modules: list) -> str:
  text = f"{issue_name} {' '.join(modules)}"
  for name, _, pat in THEME_RULES:
    if pat.search(text):
      return name
  return "Other / cross-cutting"


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, indent=2))
