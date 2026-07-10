"""Post-AI issue nature analysis — May–Jun 2026 bug clusters and themes."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Ticket, TicketStatus
from app.services.ceo_intelligence import _classify_root, _effective_category, _effective_priority
from app.services.engineering_fix_grouping import group_tickets_by_engineering_fix
from app.services.ticket_parser import infer_module_affected

AI_START = datetime(2026, 5, 1)
POST_END = datetime(2026, 6, 30, 23, 59, 59)


def analyze_post_ai_issues(db: Session, project_id: int | None = None) -> dict:
    q = db.query(Ticket).filter(
        Ticket.created_at >= AI_START,
        Ticket.created_at <= POST_END,
    )
    if project_id:
        q = q.filter(Ticket.project_id == project_id)
    tickets = q.all()
    bugs = [t for t in tickets if _effective_category(t) == "bug"]

    if not bugs:
        return {
            "period": "May – Jun 2026 (post-AI, from 1 May 2026)",
            "total_tickets_created": len(tickets),
            "total_bugs_created": 0,
            "bugs_still_open": 0,
            "high_critical_count": 0,
            "narrative_summary": ["No bugs recorded in May–Jun 2026 for this project."],
            "root_cause_themes": [],
            "product_modules_affected": [],
            "engineering_fix_groups": [],
            "priority_breakdown": [],
            "recommended_focus": [],
        }

    bug_groups = group_tickets_by_engineering_fix(bugs)
    bug_groups.sort(key=lambda g: len(g["tickets"]), reverse=True)

    root_causes = Counter(_classify_root(f"{t.title} {t.description or ''}") for t in bugs)
    modules = Counter(infer_module_affected(t.title or "", t.description or "") for t in bugs)
    priorities = Counter(_effective_priority(t) for t in bugs)
    open_bugs = sum(1 for t in bugs if t.status != TicketStatus.CLOSED)
    high_critical = sum(1 for t in bugs if _effective_priority(t) in ("high", "critical"))

    groups = []
    for g in bug_groups[:12]:
        groups.append({
            "issue_name": g["issue_name"],
            "engineering_fix": g["engineering_fix_label"],
            "bug_count": len(g["tickets"]),
            "sample_titles": [t.title[:120] for t in g["tickets"][:3]],
        })

    narrative = []
    if bug_groups:
        top = bug_groups[0]
        narrative.append(
            f"Largest cluster: \"{top['issue_name']}\" ({len(top['tickets'])} bugs) — "
            f"{top['engineering_fix_label']}."
        )
    top3_roots = root_causes.most_common(3)
    if top3_roots:
        narrative.append(
            "Dominant themes: "
            + ", ".join(f"{k} ({v})" for k, v in top3_roots)
            + "."
        )
    top_mod = modules.most_common(3)
    if top_mod:
        narrative.append(
            "Most affected areas: "
            + ", ".join(f"{k} ({v})" for k, v in top_mod)
            + "."
        )
    narrative.append(f"{high_critical} of {len(bugs)} bugs were high or critical priority.")

    recommended = [
        g["issue_name"] for g in groups[:5]
    ]

    return {
        "period": "May – Jun 2026 (post-AI, from 1 May 2026)",
        "total_tickets_created": len(tickets),
        "total_bugs_created": len(bugs),
        "bugs_still_open": open_bugs,
        "high_critical_count": high_critical,
        "narrative_summary": narrative,
        "root_cause_themes": [
            {"theme": k, "count": v} for k, v in root_causes.most_common(10)
        ],
        "product_modules_affected": [
            {"module": k, "count": v} for k, v in modules.most_common(10)
        ],
        "engineering_fix_groups": groups,
        "priority_breakdown": [
            {"priority": k, "count": v} for k, v in priorities.most_common()
        ],
        "recommended_focus": recommended,
    }
