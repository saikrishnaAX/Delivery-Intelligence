"""Canonical Asana Type field values: Task, Requirement, Enhancement, Bug."""

from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query

from app.models import Ticket, TicketCategory

CANONICAL_TICKET_TYPES: tuple[str, ...] = ("task", "requirement", "enhancement", "bug")

_CATEGORY_BY_CANONICAL: dict[str, TicketCategory] = {
    "bug": TicketCategory.BUG,
    "task": TicketCategory.TASK,
    "requirement": TicketCategory.REQUIREMENT,
    "enhancement": TicketCategory.ENHANCEMENT,
}


def normalize_ticket_type(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    key = str(raw).strip().lower().replace("-", " ").replace("_", " ")
    if key in CANONICAL_TICKET_TYPES:
        return key
    if "requirement" in key:
        return "requirement"
    if "enhance" in key:
        return "enhancement"
    if "bug" in key:
        return "bug"
    if "task" in key:
        return "task"
    return None


def canonical_type_label(canonical: str) -> str:
    return canonical.replace("_", " ").title()


def canonical_type_filter(q: Query, canonical: str) -> Query:
    """Filter tickets whose Asana Type maps to a canonical type."""
    t = canonical.lower()
    cat = _CATEGORY_BY_CANONICAL.get(t)

    if t == "bug":
        raw_match = Ticket.asana_type_raw.ilike("%bug%")
    elif t == "task":
        raw_match = Ticket.asana_type_raw.ilike("%task%")
    elif t == "requirement":
        raw_match = Ticket.asana_type_raw.ilike("%requirement%")
    elif t == "enhancement":
        raw_match = or_(
            Ticket.asana_type_raw.ilike("%enhancement%"),
            Ticket.asana_type_raw.ilike("enhance%"),
        )
    else:
        return q.filter(Ticket.id == -1)

    if not cat:
        return q.filter(raw_match)

    missing_raw = or_(Ticket.asana_type_raw.is_(None), Ticket.asana_type_raw == "")

    return q.filter(
        or_(
            raw_match,
            and_(missing_raw, Ticket.support_category == cat),
        )
    )
