"""Match Jira issues to Asana tickets by key in title, description, or jira_key field."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import JiraIssue, Ticket
from app.services.ticket_parser import extract_jira_key, extract_jira_key_from_attachments

CLOSED_JIRA_STATUSES = frozenset({
    "done", "closed", "resolved", "cancelled", "canceled",
    "won't do", "wont do", "released", "complete", "completed",
})


def is_open_jira_status(status: str | None) -> bool:
    if not status:
        return True
    normalized = status.strip().lower()
    if normalized in CLOSED_JIRA_STATUSES:
        return False
    return not any(word in normalized for word in ("done", "closed", "resolved", "released"))


def link_jira_asana_tickets(db: Session) -> int:
    """Set Ticket.jira_key from titles and link JiraIssue.ticket_id by matching key."""
    cfg = get_settings()
    prefix = cfg.jira_project_key

    by_key: dict[str, Ticket] = {}
    tickets = (
        db.query(Ticket)
        .options(joinedload(Ticket.module), joinedload(Ticket.project))
        .filter(Ticket.asana_gid.isnot(None))
        .all()
    )

    for ticket in tickets:
        key = ticket.jira_key or extract_jira_key(
            ticket.title, ticket.description or "", prefix,
        )
        if not key:
            continue
        if not ticket.jira_key:
            ticket.jira_key = key
        upper = key.upper()
        existing = by_key.get(upper)
        if existing is None:
            by_key[upper] = ticket
            continue
        # Prefer sprint-planning tickets when the same key appears in multiple projects.
        proj = (ticket.project.name or "").lower() if ticket.project else ""
        existing_proj = (existing.project.name or "").lower() if existing.project else ""
        if "sprint" in proj and "sprint" not in existing_proj:
            by_key[upper] = ticket

    linked = 0
    for issue in db.query(JiraIssue).all():
        ticket = by_key.get(issue.jira_key.upper())
        if ticket:
            issue.ticket_id = ticket.id
            linked += 1
        elif issue.ticket_id:
            issue.ticket_id = None

    db.commit()
    return linked
