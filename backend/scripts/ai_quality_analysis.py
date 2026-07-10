"""Engineering quality analysis: last 2 months vs previous 6 months."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import (
    RecurringIssue,
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketSectionMove,
    TicketStatus,
)

TODAY = datetime(2026, 7, 4, 23, 59, 59)
AFTER_START = TODAY - timedelta(days=60)  # ~May 5
BEFORE_START = AFTER_START - timedelta(days=183)  # ~Nov 3
BEFORE_END = AFTER_START

ROOT_CAUSE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Business Logic", re.compile(r"logic|calculation|wrong amount|incorrect total|mismatch|not reflect", re.I)),
    ("UI", re.compile(r"display|screen|button|layout|ui |font|align|visible|blank screen|not show", re.I)),
    ("API", re.compile(r"api|endpoint|integration|timeout|response|500|404|request fail", re.I)),
    ("Performance", re.compile(r"slow|performance|lag|timeout|hang|freeze|loading", re.I)),
    ("Database", re.compile(r"database|db |sql|record|sync|data not|missing data", re.I)),
    ("Validation", re.compile(r"valid|mandatory|required field|cannot save|error message", re.I)),
    ("Integration", re.compile(r"jira|asana|third.?party|webhook|import|export", re.I)),
    ("Configuration", re.compile(r"config|setting|setup|permission|access denied|role", re.I)),
    ("Permission", re.compile(r"permission|unauthorized|access|forbidden|login", re.I)),
    ("Workflow", re.compile(r"workflow|status|stage|approval|process|block", re.I)),
    ("Requirements", re.compile(r"requirement|spec|expected|should be|as per", re.I)),
    ("Data Migration", re.compile(r"migration|migrate|legacy|old data|historical", re.I)),
]

AI_INDICATOR_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Missing edge cases", re.compile(r"edge case|corner case|specific scenario|only when|sometimes", re.I)),
    ("Regression defects", re.compile(r"regression|reappear|again|reopen|came back|still happening|previously fix", re.I)),
    ("Missing validations", re.compile(r"validation|mandatory|required|should not allow|without check", re.I)),
    ("Incomplete workflows", re.compile(r"incomplete|partial|stuck|not proceed|workflow break", re.I)),
    ("Copy/paste mistakes", re.compile(r"duplicate|same issue|copy|typo|wrong label", re.I)),
    ("Incorrect business logic", re.compile(r"wrong calculation|incorrect|logic error|business rule", re.I)),
]


def period_label(dt: datetime | None) -> str:
    if not dt:
        return "unknown"
    if dt >= AFTER_START:
        return "after"
    if BEFORE_START <= dt < BEFORE_END:
        return "before"
    return "outside"


def effective_category(t: Ticket) -> str:
    cat = t.ai_category or t.support_category
    if not cat:
        raw = (t.asana_type_raw or "").lower()
        if "bug" in raw:
            return "bug"
        if "enhance" in raw:
            return "enhancement"
        if "config" in raw:
            return "configuration"
        if "requirement" in raw:
            return "requirement"
        return "task"
    return cat.value if hasattr(cat, "value") else str(cat)


def effective_priority(t: Ticket) -> str:
    return t.priority.value if t.priority else "medium"


def classify_root_cause(text: str) -> str:
    for label, pat in ROOT_CAUSE_PATTERNS:
        if pat.search(text):
            return label
    return "Unclassified"


def classify_ai_indicator(text: str) -> list[str]:
    hits = [label for label, pat in AI_INDICATOR_PATTERNS if pat.search(text)]
    return hits


def pct_change(before: float, after: float) -> float | None:
    if before == 0:
        return None if after == 0 else 100.0
    return round((after - before) / before * 100, 1)


def month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def run() -> dict[str, Any]:
    db = SessionLocal()
    try:
        tickets = (
            db.query(Ticket)
            .options(joinedload(Ticket.module), joinedload(Ticket.customer))
            .filter(Ticket.created_at >= BEFORE_START, Ticket.created_at <= TODAY)
            .all()
        )

        before_tickets = [t for t in tickets if period_label(t.created_at) == "before"]
        after_tickets = [t for t in tickets if period_label(t.created_at) == "after"]

        def summarize(group: list[Ticket]) -> dict[str, Any]:
            cats = Counter(effective_category(t) for t in group)
            total = len(group)
            bugs = cats.get("bug", 0)
            enhancements = cats.get("enhancement", 0)
            support_cfg = cats.get("configuration", 0) + cats.get("knowledge_gap", 0) + cats.get("task", 0)
            return {
                "total": total,
                "bugs": bugs,
                "enhancements": enhancements,
                "support_configuration": support_cfg,
                "requirements": cats.get("requirement", 0),
                "duplicates": cats.get("duplicate", 0),
                "bug_pct": round(bugs / total * 100, 1) if total else 0,
            }

        before_sum = summarize(before_tickets)
        after_sum = summarize(after_tickets)

        # Monthly bug trend (full 8 month window)
        monthly: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "bugs": 0, "enhancements": 0})
        for t in tickets:
            if not t.created_at:
                continue
            mk = month_key(t.created_at)
            monthly[mk]["total"] += 1
            cat = effective_category(t)
            if cat == "bug":
                monthly[mk]["bugs"] += 1
            elif cat == "enhancement":
                monthly[mk]["enhancements"] += 1

        months_sorted = sorted(monthly.keys())
        monthly_trend = [{"month": m, **monthly[m]} for m in months_sorted]

        # Severity
        def severity_breakdown(group: list[Ticket]) -> dict[str, int]:
            c = Counter(effective_priority(t) for t in group if effective_category(t) == "bug")
            return {k: c.get(k, 0) for k in ["critical", "high", "medium", "low"]}

        sev_before = severity_breakdown(before_tickets)
        sev_after = severity_breakdown(after_tickets)

        # Module bugs
        def module_bugs(group: list[Ticket]) -> list[dict]:
            c = Counter(
                (t.module.name if t.module else "Unassigned")
                for t in group
                if effective_category(t) == "bug"
            )
            return [{"module": k, "count": v} for k, v in c.most_common(15)]

        mod_before = module_bugs(before_tickets)
        mod_after = module_bugs(after_tickets)
        before_mod_set = {m["module"]: m["count"] for m in mod_before}
        after_mod_set = {m["module"]: m["count"] for m in mod_after}
        new_problem_areas = []
        for mod, cnt in after_mod_set.items():
            prev = before_mod_set.get(mod, 0)
            if cnt >= 3 and (prev == 0 or cnt > prev * 1.5):
                new_problem_areas.append({"module": mod, "before": prev, "after": cnt})

        # Root cause
        def root_causes(group: list[Ticket]) -> dict[str, int]:
            c = Counter()
            for t in group:
                if effective_category(t) != "bug":
                    continue
                text = f"{t.title or ''} {t.description or ''}"
                c[classify_root_cause(text)] += 1
            return dict(c.most_common())

        rc_before = root_causes(before_tickets)
        rc_after = root_causes(after_tickets)

        # Regressions / reopen
        reopen_before = sum(1 for t in before_tickets if t.is_reopened and effective_category(t) == "bug")
        reopen_after = sum(1 for t in after_tickets if t.is_reopened and effective_category(t) == "bug")
        bugs_before_count = before_sum["bugs"] or 1
        bugs_after_count = after_sum["bugs"] or 1
        reopen_rate_before = round(reopen_before / bugs_before_count * 100, 1)
        reopen_rate_after = round(reopen_after / bugs_after_count * 100, 1)

        regression_tickets = [
            t for t in tickets
            if effective_category(t) == "bug" and (t.is_reopened or "regression" in (t.title or "").lower() or "again" in (t.title or "").lower())
        ]
        regression_titles = Counter(t.title.strip()[:80] for t in regression_tickets if t.title)
        top_regressions = [{"title": k, "count": v} for k, v in regression_titles.most_common(10)]

        # Recurring issues from DB
        recurring = db.query(RecurringIssue).all()
        rec_before_ids: set[int] = set()
        rec_after_ids: set[int] = set()
        top_recurring_before: list[dict] = []
        top_recurring_after: list[dict] = []

        for ri in recurring:
            tids = ri.ticket_ids or []
            before_cnt = 0
            after_cnt = 0
            for tid in tids:
                t = next((x for x in tickets if x.id == tid), None)
                if not t or not t.created_at:
                    continue
                p = period_label(t.created_at)
                if p == "before":
                    before_cnt += 1
                    rec_before_ids.add(tid)
                elif p == "after":
                    after_cnt += 1
                    rec_after_ids.add(tid)
            entry = {"name": ri.issue_name, "count": ri.ticket_count, "open": ri.open_count, "workshops": ri.workshop_count}
            if before_cnt >= after_cnt and before_cnt > 0:
                top_recurring_before.append({**entry, "period_tickets": before_cnt})
            if after_cnt > 0:
                top_recurring_after.append({**entry, "period_tickets": after_cnt})

        top_recurring_before.sort(key=lambda x: x["period_tickets"], reverse=True)
        top_recurring_after.sort(key=lambda x: x["period_tickets"], reverse=True)

        # Customer / workshop impact
        def workshop_impact(group: list[Ticket]) -> dict[str, int]:
            bug_tickets = [t for t in group if effective_category(t) == "bug"]
            workshops = {t.workshop_name for t in bug_tickets if t.workshop_name and t.workshop_name.lower() != "asana project"}
            customers = {t.customer_id for t in bug_tickets if t.customer_id}
            return {
                "workshops_affected": len(workshops),
                "customers_affected": len(customers),
                "bug_tickets": len(bug_tickets),
            }

        impact_before = workshop_impact(before_tickets)
        impact_after = workshop_impact(after_tickets)

        # Release stability
        releases = (
            db.query(TicketSectionMove)
            .filter(
                TicketSectionMove.moved_at >= BEFORE_START,
                TicketSectionMove.moved_at <= TODAY,
            )
            .all()
        )
        release_moves_before = [r for r in releases if r.moved_at and BEFORE_START <= r.moved_at < BEFORE_END]
        release_moves_after = [r for r in releases if r.moved_at and r.moved_at >= AFTER_START]

        def count_release_events(moves: list) -> int:
            return len({(r.ticket_id, r.to_section, r.moved_at.date() if r.moved_at else None) for r in moves})

        releases_before = count_release_events(release_moves_before)
        releases_after = count_release_events(release_moves_after)

        # Normalize to per-month rates
        before_months = 6.0
        after_months = 2.0
        bugs_per_month_before = round(before_sum["bugs"] / before_months, 1)
        bugs_per_month_after = round(after_sum["bugs"] / after_months, 1)
        releases_per_month_before = round(releases_before / before_months, 1)
        releases_per_month_after = round(releases_after / after_months, 1)
        bugs_per_release_before = round(before_sum["bugs"] / releases_before, 2) if releases_before else None
        bugs_per_release_after = round(after_sum["bugs"] / releases_after, 2) if releases_after else None

        # Bug-to-feature ratio
        def bug_feature_ratio(group: list[Ticket]) -> float | None:
            bugs = sum(1 for t in group if effective_category(t) == "bug")
            feats = sum(1 for t in group if effective_category(t) in ("enhancement", "requirement"))
            return round(bugs / feats, 2) if feats else None

        bfr_before = bug_feature_ratio(before_tickets)
        bfr_after = bug_feature_ratio(after_tickets)

        # Duplicates
        dup_before = sum(1 for t in before_tickets if effective_category(t) == "duplicate")
        dup_after = sum(1 for t in after_tickets if effective_category(t) == "duplicate")

        # AI indicators
        ai_indicators_before: Counter = Counter()
        ai_indicators_after: Counter = Counter()
        for t in before_tickets:
            if effective_category(t) != "bug":
                continue
            text = f"{t.title or ''} {t.description or ''}"
            for hit in classify_ai_indicator(text):
                ai_indicators_before[hit] += 1
        for t in after_tickets:
            if effective_category(t) != "bug":
                continue
            text = f"{t.title or ''} {t.description or ''}"
            for hit in classify_ai_indicator(text):
                ai_indicators_after[hit] += 1

        # Developer load (assignee)
        def bugs_per_dev(group: list[Ticket]) -> list[dict]:
            c = Counter(
                (t.assignee or t.ticket_owner or "Unassigned")
                for t in group
                if effective_category(t) == "bug"
            )
            return [{"assignee": k, "bugs": v} for k, v in c.most_common(8)]

        dev_before = bugs_per_dev(before_tickets)
        dev_after = bugs_per_dev(after_tickets)

        # Statistical note: monthly rate comparison
        monthly_bugs_before = [monthly[m]["bugs"] for m in months_sorted if m < month_key(AFTER_START)]
        monthly_bugs_after = [monthly[m]["bugs"] for m in months_sorted if m >= month_key(AFTER_START)]
        avg_monthly_bugs_before = round(sum(monthly_bugs_before) / len(monthly_bugs_before), 1) if monthly_bugs_before else 0
        avg_monthly_bugs_after = round(sum(monthly_bugs_after) / len(monthly_bugs_after), 1) if monthly_bugs_after else 0

        return {
            "meta": {
                "generated_at": datetime.utcnow().isoformat(),
                "before_period": f"{BEFORE_START.date()} to {BEFORE_END.date()}",
                "after_period": f"{AFTER_START.date()} to {TODAY.date()}",
                "after_label": "Last 2 months (AI-assisted period proxy)",
                "before_label": "Previous 6 months (pre-comparison baseline)",
                "total_tickets_analyzed": len(tickets),
                "data_note": "AI adoption start date not recorded in system; 'after' period uses last 60 days as proxy per management request.",
            },
            "overall_trend": {
                "before": before_sum,
                "after": after_sum,
                "pct_change": {
                    "total": pct_change(before_sum["total"], after_sum["total"]),
                    "bugs": pct_change(before_sum["bugs"], after_sum["bugs"]),
                    "enhancements": pct_change(before_sum["enhancements"], after_sum["enhancements"]),
                    "support_configuration": pct_change(before_sum["support_configuration"], after_sum["support_configuration"]),
                },
                "normalized_per_month": {
                    "tickets_before": round(before_sum["total"] / before_months, 1),
                    "tickets_after": round(after_sum["total"] / after_months, 1),
                    "bugs_before": bugs_per_month_before,
                    "bugs_after": bugs_per_month_after,
                },
            },
            "monthly_trend": monthly_trend,
            "avg_monthly_bugs": {"before": avg_monthly_bugs_before, "after": avg_monthly_bugs_after},
            "severity": {"before": sev_before, "after": sev_after},
            "modules": {"before": mod_before, "after": mod_after, "new_problem_areas": new_problem_areas[:10]},
            "root_causes": {"before": rc_before, "after": rc_after},
            "regressions": {
                "reopen_count_before": reopen_before,
                "reopen_count_after": reopen_after,
                "reopen_rate_before_pct": reopen_rate_before,
                "reopen_rate_after_pct": reopen_rate_after,
                "top_regressions": top_regressions,
            },
            "recurring": {
                "top_before": top_recurring_before[:10],
                "top_after": top_recurring_after[:10],
                "unique_recurring_tickets_before": len(rec_before_ids),
                "unique_recurring_tickets_after": len(rec_after_ids),
            },
            "engineering_quality": {
                "bugs_per_release_before": bugs_per_release_before,
                "bugs_per_release_after": bugs_per_release_after,
                "releases_before": releases_before,
                "releases_after": releases_after,
                "releases_per_month_before": releases_per_month_before,
                "releases_per_month_after": releases_per_month_after,
                "duplicate_before": dup_before,
                "duplicate_after": dup_after,
                "dev_bugs_before": dev_before,
                "dev_bugs_after": dev_after,
            },
            "customer_impact": {"before": impact_before, "after": impact_after},
            "productivity": {
                "bug_feature_ratio_before": bfr_before,
                "bug_feature_ratio_after": bfr_after,
                "enhancements_per_month_before": round(before_sum["enhancements"] / before_months, 1),
                "enhancements_per_month_after": round(after_sum["enhancements"] / after_months, 1),
            },
            "ai_indicators": {
                "before": dict(ai_indicators_before.most_common()),
                "after": dict(ai_indicators_after.most_common()),
                "note": "Keyword-based classification on ticket titles/descriptions; not direct proof of AI-generated code.",
            },
        }
    finally:
        db.close()


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
