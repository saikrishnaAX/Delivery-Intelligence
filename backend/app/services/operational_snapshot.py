"""Shared operational ticket snapshot — built once per execution board request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Ticket, TicketStatus
from app.services.analytics import AnalyticsService

ESCALATION_DAYS = 7
TESTING_STUCK_DAYS = 5

IST = timezone(timedelta(hours=5, minutes=30))


def ist_today_start_naive_utc() -> datetime:
    """Midnight IST as naive UTC — matches how ticket timestamps are stored."""
    now_ist = datetime.now(IST)
    start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_ist.astimezone(timezone.utc).replace(tzinfo=None)


@dataclass
class OperationalSnapshot:
    analytics: AnalyticsService
    now: datetime
    today_start: datetime
    open_list: list[Ticket]
    created_today: list[Ticket]
    closed_today: list[Ticket]
    closed_range_list: list[Ticket]
    escalations: list[Ticket]


def build_operational_snapshot(
    db: Session,
    project_gid: str | None,
    date_from: str | None,
    date_to: str | None,
) -> OperationalSnapshot:
    analytics = AnalyticsService(db, project_gid=project_gid, date_from=date_from, date_to=date_to)
    now = datetime.utcnow()
    today_start = ist_today_start_naive_utc()

    operational = analytics._tickets_operational().options(joinedload(Ticket.module))
    dated = analytics._tickets().options(joinedload(Ticket.module))

    open_list = (
        operational.filter(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED])
        )
        .order_by(Ticket.created_at)
        .all()
    )

    created_today = (
        operational.filter(Ticket.created_at >= today_start)
        .order_by(Ticket.created_at.desc())
        .all()
    )

    closed_today = (
        operational.filter(
            Ticket.closed_at >= today_start,
            Ticket.status == TicketStatus.CLOSED,
        )
        .order_by(Ticket.closed_at.desc())
        .all()
    )

    closed_range_q = dated.filter(Ticket.status == TicketStatus.CLOSED)
    if analytics.date_from:
        closed_range_q = closed_range_q.filter(Ticket.closed_at >= analytics.date_from)
    if analytics.date_to:
        closed_range_q = closed_range_q.filter(Ticket.closed_at <= analytics.date_to)
    closed_range_list = closed_range_q.order_by(Ticket.closed_at.desc()).all()

    escalation_cutoff = now - timedelta(days=ESCALATION_DAYS)
    escalations = [t for t in open_list if t.created_at and t.created_at <= escalation_cutoff]
    escalations.sort(key=lambda t: t.created_at or now)

    return OperationalSnapshot(
        analytics=analytics,
        now=now,
        today_start=today_start,
        open_list=open_list,
        created_today=created_today,
        closed_today=closed_today,
        closed_range_list=closed_range_list,
        escalations=escalations,
    )
