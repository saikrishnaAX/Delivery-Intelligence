"""Record Asana section transitions during sync."""

from datetime import datetime

from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from app.models import Ticket, TicketSectionMove
from app.services.section_utils import is_released_section


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return date_parser.parse(value).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


async def find_release_story(asana_client, asana_gid: str) -> tuple[datetime | None, str | None, str | None]:
    """Latest move into Released from Asana task stories."""
    if not asana_client or not asana_client.is_configured or not asana_gid:
        return None, None, None
    try:
        stories = await asana_client.fetch_task_stories(asana_gid)
    except Exception:
        return None, None, None

    for story in reversed(stories):
        if story.get("resource_subtype") != "section_changed":
            continue
        new_name = (story.get("new_section") or {}).get("name")
        if not is_released_section(new_name):
            continue
        moved_at = _parse_dt(story.get("created_at"))
        old_name = (story.get("old_section") or {}).get("name")
        return moved_at, old_name, new_name
    return None, None, None


async def backfill_release_for_ticket(
    db: Session,
    ticket: Ticket,
    asana_client,
) -> bool:
    """Fill released_at and a release move row from Asana when missing."""
    if not ticket.asana_gid:
        return False

    moved_at, from_section, to_section = await find_release_story(asana_client, ticket.asana_gid)
    if not moved_at:
        return False

    changed = False
    if ticket.released_at != moved_at:
        ticket.released_at = moved_at
        changed = True

    existing = (
        db.query(TicketSectionMove)
        .filter(TicketSectionMove.ticket_id == ticket.id)
        .order_by(TicketSectionMove.moved_at.desc())
        .all()
    )
    has_release = any(is_released_section(m.to_section) for m in existing)

    if not has_release:
        db.add(
            TicketSectionMove(
                ticket_id=ticket.id,
                asana_gid=ticket.asana_gid,
                from_section=from_section,
                to_section=to_section or "Released",
                moved_at=moved_at,
            )
        )
        changed = True
    else:
        for move in existing:
            if is_released_section(move.to_section):
                if move.moved_at != moved_at:
                    move.moved_at = moved_at
                    changed = True
                if from_section and not move.from_section:
                    move.from_section = from_section
                    changed = True
                break

    return changed


async def backfill_project_releases(
    db: Session,
    project_id: int,
    asana_client,
    *,
    only_missing: bool = True,
) -> int:
    """Backfill release timestamps from Asana for tickets in the Released section."""
    from app.models import Module

    modules = db.query(Module).filter(Module.project_id == project_id).all()
    released_module_ids = [m.id for m in modules if is_released_section(m.name)]
    if not released_module_ids:
        return 0

    tickets = (
        db.query(Ticket)
        .filter(Ticket.project_id == project_id, Ticket.module_id.in_(released_module_ids))
        .all()
    )

    targets: list[Ticket] = []
    for ticket in tickets:
        if not only_missing:
            targets.append(ticket)
            continue
        if ticket.released_at is None:
            targets.append(ticket)
            continue
        moves = (
            db.query(TicketSectionMove)
            .filter(TicketSectionMove.ticket_id == ticket.id)
            .all()
        )
        if not any(is_released_section(m.to_section) for m in moves):
            targets.append(ticket)

    updated = 0
    for ticket in targets:
        if await backfill_release_for_ticket(db, ticket, asana_client):
            updated += 1
    return updated


async def record_section_change(
    db: Session,
    ticket: Ticket,
    from_section: str | None,
    to_section: str,
    asana_client,
    moved_at: datetime | None = None,
) -> None:
    if from_section and from_section.strip().lower() == to_section.strip().lower():
        return

    when = moved_at or datetime.utcnow()
    if is_released_section(to_section):
        story_at, story_from, story_to = await find_release_story(asana_client, ticket.asana_gid)
        if story_at:
            when = story_at
        if story_from and not from_section:
            from_section = story_from
        ticket.released_at = when

    db.add(
        TicketSectionMove(
            ticket_id=ticket.id,
            asana_gid=ticket.asana_gid,
            from_section=from_section,
            to_section=to_section,
            moved_at=when,
        )
    )
