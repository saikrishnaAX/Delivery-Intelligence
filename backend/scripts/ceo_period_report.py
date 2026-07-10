"""CEO period comparison: May-Jun 2026 (post-AI) vs Dec 2025-Apr 2026 (pre-AI)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime

from app.database import SessionLocal
from app.models import Ticket, TicketSectionMove
from app.services.ceo_intelligence import (
    _classify_root,
    _effective_category,
    _effective_priority,
)
from app.services.section_utils import is_released_section

AI_START = datetime(2026, 5, 1)
BEFORE_START = datetime(2025, 12, 1)
BEFORE_END = datetime(2026, 4, 30, 23, 59, 59)
AFTER_END = datetime(2026, 6, 30, 23, 59, 59)


def summarize(tickets: list[Ticket], months: float) -> dict:
    cats = Counter(_effective_category(t) for t in tickets)
    bugs = [t for t in tickets if _effective_category(t) == "bug"]
    feats = cats.get("enhancement", 0) + cats.get("requirement", 0)
    root = Counter(_classify_root(f"{t.title} {t.description or ''}") for t in bugs)
    modules = Counter((t.module.name if t.module else "Unassigned") for t in bugs)
    res_hours = [t.resolution_hours for t in tickets if t.resolution_hours]
    return {
        "total": len(tickets),
        "bugs": len(bugs),
        "enhancements": cats.get("enhancement", 0),
        "requirements": cats.get("requirement", 0),
        "config_support": cats.get("configuration", 0)
        + cats.get("knowledge_gap", 0)
        + cats.get("task", 0),
        "critical_bugs": sum(1 for t in bugs if _effective_priority(t) == "critical"),
        "high_bugs": sum(1 for t in bugs if _effective_priority(t) == "high"),
        "reopened": sum(1 for t in tickets if t.is_reopened),
        "bug_share_pct": round(len(bugs) / len(tickets) * 100, 1) if tickets else 0,
        "bug_feature_ratio": round(len(bugs) / feats, 2) if feats else None,
        "per_month_total": round(len(tickets) / months, 1),
        "per_month_bugs": round(len(bugs) / months, 1),
        "per_month_features": round(feats / months, 1),
        "workshops_affected": len(
            {
                t.workshop_name
                for t in bugs
                if t.workshop_name and t.workshop_name.lower() != "asana project"
            }
        ),
        "avg_resolution_hours": round(sum(res_hours) / len(res_hours), 1) if res_hours else None,
        "top_root_causes": [{"cause": k, "count": v} for k, v in root.most_common(5)],
        "top_modules": [{"module": k, "count": v} for k, v in modules.most_common(5)],
    }


def release_count(db, start: datetime, end: datetime) -> int:
    moves = (
        db.query(TicketSectionMove)
        .filter(TicketSectionMove.moved_at >= start, TicketSectionMove.moved_at <= end)
        .all()
    )
    released = [m for m in moves if is_released_section(m.to_section)]
    return len({m.ticket_id for m in released})


def main() -> None:
    db = SessionLocal()
    try:
        before = (
            db.query(Ticket)
            .filter(Ticket.created_at >= BEFORE_START, Ticket.created_at <= BEFORE_END)
            .all()
        )
        after = (
            db.query(Ticket)
            .filter(Ticket.created_at >= AI_START, Ticket.created_at <= AFTER_END)
            .all()
        )
        rb = release_count(db, BEFORE_START, BEFORE_END)
        ra = release_count(db, AI_START, AFTER_END)
        sb = summarize(before, 5.0)
        sa = summarize(after, 2.0)
        bpr_b = round(sb["bugs"] / rb, 2) if rb else None
        bpr_a = round(sa["bugs"] / ra, 2) if ra else None

        monthly: dict[str, dict] = defaultdict(lambda: {"total": 0, "bugs": 0, "features": 0})
        for t in before + after:
            if not t.created_at:
                continue
            mk = t.created_at.strftime("%Y-%m")
            monthly[mk]["total"] += 1
            cat = _effective_category(t)
            if cat == "bug":
                monthly[mk]["bugs"] += 1
            elif cat in ("enhancement", "requirement"):
                monthly[mk]["features"] += 1

        def pct_change(b: float, a: float) -> float | None:
            if b == 0:
                return None
            return round((a - b) / b * 100, 1)

        report = {
            "before": {
                "label": "Dec 2025 – Apr 2026 (pre-AI)",
                "months": 5,
                **sb,
                "releases": rb,
                "bugs_per_release": bpr_b,
                "releases_per_month": round(rb / 5, 1),
            },
            "after": {
                "label": "May – Jun 2026 (post-AI, from 1 May)",
                "months": 2,
                **sa,
                "releases": ra,
                "bugs_per_release": bpr_a,
                "releases_per_month": round(ra / 2, 1),
            },
            "changes": {
                "tickets_per_month_pct": pct_change(sb["per_month_total"], sa["per_month_total"]),
                "bugs_per_month_pct": pct_change(sb["per_month_bugs"], sa["per_month_bugs"]),
                "features_per_month_pct": pct_change(sb["per_month_features"], sa["per_month_features"]),
                "bug_share_pct_delta": round(sa["bug_share_pct"] - sb["bug_share_pct"], 1),
                "bug_feature_ratio_delta": (
                    round(sa["bug_feature_ratio"] - sb["bug_feature_ratio"], 2)
                    if sa["bug_feature_ratio"] and sb["bug_feature_ratio"]
                    else None
                ),
                "bugs_per_release_delta": (
                    round((bpr_a or 0) - (bpr_b or 0), 2)
                    if bpr_a is not None and bpr_b is not None
                    else None
                ),
            },
            "monthly": {k: monthly[k] for k in sorted(monthly.keys()) if k >= "2025-12"},
        }
        print(json.dumps(report, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
