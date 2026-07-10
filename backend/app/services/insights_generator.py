"""Generate executive summary and page insights from live ticket data."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Ticket, AIInsight, ExecutiveSummary, AsanaProject, TicketStatus
from app.config import get_settings
from app.services.analytics import AnalyticsService
from app.services.ticket_parser import WORKFLOW_KEYWORDS

settings = get_settings()


def _clear_old_insights(db: Session, project_id: int) -> None:
    db.query(AIInsight).filter(AIInsight.project_id == project_id).delete()
    db.query(ExecutiveSummary).filter(ExecutiveSummary.project_id == project_id).delete()


def generate_insights(db: Session, project_id: int, date_from: datetime | None = None) -> None:
    """Build rule-based executive summary and per-page insights after sync."""
    project = db.query(AsanaProject).filter(AsanaProject.id == project_id).first()
    if not project:
        return

    gid = project.gid
    analytics = AnalyticsService(db, project_gid=gid, date_from=date_from)
    metrics = analytics.get_executive_metrics()
    blockers = analytics.get_blocker_analytics()
    workshops = analytics.get_customer_pain()
    support = analytics.get_support_team_analytics()
    resolution = analytics.get_resolution_analytics()

    _clear_old_insights(db, project_id)

    now = datetime.utcnow()
    open_tickets = analytics._tickets_operational().filter(
        Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED])
    ).all()

    overdue = [
        t for t in open_tickets
        if t.expected_delivery and t.expected_delivery < now
    ]
    workflow_concerns: dict[str, int] = {}
    for t in open_tickets:
        title_lower = (t.title or "").lower()
        for kw, label in WORKFLOW_KEYWORDS.items():
            if kw in title_lower:
                workflow_concerns[label] = workflow_concerns.get(label, 0) + 1

    top_workflow = sorted(workflow_concerns.items(), key=lambda x: x[1], reverse=True)[:3]
    top_creator = support.top_creator
    top_closer = support.top_closer
    top_workshop = workshops.top_pain_customer

    summary_parts = [
        f"{metrics.open_tickets} open tickets in the selected period.",
        f"Average resolution is {metrics.avg_resolution_hours:.0f}h with {metrics.sla_compliance_rate:.0f}% SLA compliance.",
    ]
    if blockers.total_blockers:
        summary_parts.append(
            f"{blockers.total_blockers} workflow blockers are open — titles indicate customer-facing failures (invoice, job card, inward, etc.)."
        )
    if overdue:
        summary_parts.append(f"{len(overdue)} tickets are past expected delivery date.")
    if top_workflow:
        areas = ", ".join(f"{name} ({n})" for name, n in top_workflow)
        summary_parts.append(f"Hottest workshop workflow areas: {areas}.")

    recommendations = []
    if blockers.total_blockers >= 3:
        recommendations.append("Prioritize open blockers — assign owners and set expected delivery on high-impact tickets.")
    if overdue:
        recommendations.append(f"Review {len(overdue)} overdue tickets and update Expected Delivery dates in Asana.")
    if top_workshop and top_workshop != "N/A":
        recommendations.append(f"Check in with {top_workshop} — highest workshop ticket volume in this period.")
    if top_creator:
        recommendations.append(f"Support intake is led by {top_creator} — balance load if volume is uneven.")
    if metrics.sla_compliance_rate < 50:
        recommendations.append("SLA compliance is below 50% — focus on closing tickets older than 48h.")

    db.add(ExecutiveSummary(
        project_id=project_id,
        summary=" ".join(summary_parts),
        key_metrics={
            "open_tickets": metrics.open_tickets,
            "blockers": blockers.total_blockers,
            "overdue": len(overdue),
            "avg_resolution_hours": metrics.avg_resolution_hours,
            "sla_rate": metrics.sla_compliance_rate,
            "workshops": workshops.total_customers,
        },
        recommendations=recommendations[:5],
    ))

    insight_rows = [
        ("executive", "alert", "Workflow blockers", f"{blockers.total_blockers} open blockers affecting {blockers.affected_customers} workshops.", "high" if blockers.total_blockers else "info"),
        ("executive", "trend", "Resolution pace", f"Avg close time {resolution.avg_resolution_hours:.0f}h in selected date range.", "info"),
        ("blockers", "focus", "Title-based blockers", f"Blockers detected from ticket titles (unable, failed, error, missing, etc.) — not just priority flags.", "warning"),
        ("customers", "workshop", "Workshop pain", f"Top workshop by volume: {top_workshop}.", "warning" if workshops.total_customers else "info"),
        ("support-team", "people", "Top creator", f"Most tickets created by: {top_creator or 'Unknown'}.", "info"),
        ("support-team", "people", "Top closer", f"Most tickets closed (assignee): {top_closer or 'Unknown'}.", "info"),
        ("clustering", "pattern", "Semantic clusters", "Tickets grouped by similar meaning in title + description — same issue, different wording.", "info"),
        ("resolution", "trend", "Monthly view", "Compare created, closed, bugs, and close time month by month with prior-month deltas.", "info"),
        ("classification", "types", "Ticket types", f"Breakdown uses Asana Type field only (Bug, Task, Enhancement, etc.).", "info"),
        ("release-notes", "workflow", "Released section", f"Tracks tickets moved to '{settings.asana_released_section_name}' using Asana section history.", "info"),
        ("sprint-sheet", "planning", "Prioritized backlog", f"Build sprint sheets from tickets in '{settings.asana_sprint_section_name}' with dev/QA estimates.", "info"),
    ]
    for page, itype, title, content, severity in insight_rows:
        db.add(AIInsight(
            page=page,
            project_id=project_id,
            insight_type=itype,
            title=title,
            content=content,
            severity=severity,
        ))

    db.commit()
