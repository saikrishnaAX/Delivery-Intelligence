"""Roll up Dev/QA estimates from Asana subtasks onto parent sprint tickets."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.integrations.asana import AsanaClient
from app.models import Ticket
from app.db_utils import commit_with_retry, flush_with_retry
from app.services.section_utils import is_sprint_pipeline_section
from app.services.ticket_parser import parse_custom_number


def _parent_gid(task: dict) -> str | None:
    parent = task.get("parent") or {}
    gid = parent.get("gid")
    return str(gid) if gid else None


def _effort_from_task(task: dict) -> tuple[float | None, float | None]:
    custom_fields = task.get("custom_fields") or []
    dev = parse_custom_number(custom_fields, "Dev. Effort in Hours")
    qa = parse_custom_number(custom_fields, "QA Effort in Hours")
    return dev, qa


def child_estimate_rollup_by_parent(db: Session, project_id: int) -> dict[str, dict]:
    """Sum Dev/QA from synced subtask rows grouped by parent Asana gid."""
    rows = (
        db.query(Ticket)
        .filter(
            Ticket.project_id == project_id,
            Ticket.parent_asana_gid.isnot(None),
            Ticket.removed_from_asana.is_(False),
        )
        .all()
    )
    out: dict[str, dict] = defaultdict(lambda: {"dev": 0.0, "qa": 0.0, "has": False})
    for ticket in rows:
        parent_gid = ticket.parent_asana_gid
        if not parent_gid:
            continue
        bucket = out[parent_gid]
        if ticket.dev_effort_hours is not None:
            bucket["dev"] += float(ticket.dev_effort_hours)
            bucket["has"] = True
        if ticket.qa_effort_hours is not None:
            bucket["qa"] += float(ticket.qa_effort_hours)
            bucket["has"] = True
    return dict(out)


def apply_subtask_estimate_rollup(
    dev: float | None,
    qa: float | None,
    total: float | None,
    rollup: dict | None,
) -> tuple[float | None, float | None, float | None]:
    """Parent row shows parent estimate + rolled-up subtask hours."""
    if not rollup or not rollup.get("has"):
        return dev, qa, total

    sub_dev = float(rollup.get("dev") or 0)
    sub_qa = float(rollup.get("qa") or 0)
    merged_dev = (float(dev) if dev is not None else 0.0) + sub_dev
    merged_qa = (float(qa) if qa is not None else 0.0) + sub_qa
    out_dev = merged_dev if merged_dev or dev is not None or sub_dev else None
    out_qa = merged_qa if merged_qa or qa is not None or sub_qa else None
    if out_dev is None and out_qa is None:
        return dev, qa, total
    out_total = (out_dev or 0) + (out_qa or 0)
    return out_dev, out_qa, out_total


def is_subtask_ticket(ticket: Ticket) -> bool:
    return bool((ticket.parent_asana_gid or "").strip())


async def sync_subtask_estimates(
    db: Session,
    asana: AsanaClient,
    project_id: int,
    parent_gids: set[str],
) -> int:
    """Pull subtasks from Asana for parents; store estimates only (hidden from sprint sheet)."""
    if not parent_gids or not asana.is_configured:
        return 0

    parents = {
        t.asana_gid: t
        for t in db.query(Ticket)
        .filter(
            Ticket.project_id == project_id,
            Ticket.asana_gid.in_(list(parent_gids)),
            Ticket.parent_asana_gid.is_(None),
        )
        .all()
        if t.asana_gid
    }
    if not parents:
        return 0

    synced_sub_gids: set[str] = set()
    updated = 0

    for parent_gid, parent in parents.items():
        subtasks = await asana.fetch_task_subtasks(parent_gid)
        live_gids = {str(s["gid"]) for s in subtasks if s.get("gid")}

        for sub in subtasks:
            gid = sub.get("gid")
            if not gid:
                continue
            gid = str(gid)
            synced_sub_gids.add(gid)
            dev, qa = _effort_from_task(sub)
            total = (dev or 0) + (qa or 0) if (dev is not None or qa is not None) else None

            existing = db.query(Ticket).filter(Ticket.asana_gid == gid).first()
            fields = dict(
                title=sub.get("name") or "Subtask",
                description=sub.get("notes") or "",
                project_id=project_id,
                parent_asana_gid=parent_gid,
                module_id=parent.module_id,
                dev_effort_hours=dev,
                qa_effort_hours=qa,
                total_effort_hours=total,
                asana_url=sub.get("permalink_url"),
                removed_from_asana=False,
                updated_at=datetime.utcnow(),
            )
            if existing:
                for key, value in fields.items():
                    setattr(existing, key, value)
            else:
                db.add(Ticket(asana_gid=gid, **fields))
            updated += 1

        stale_subs = (
            db.query(Ticket)
            .filter(
                Ticket.project_id == project_id,
                Ticket.parent_asana_gid == parent_gid,
                Ticket.removed_from_asana.is_(False),
            )
            .all()
        )
        for sub_ticket in stale_subs:
            if sub_ticket.asana_gid and sub_ticket.asana_gid not in live_gids:
                sub_ticket.removed_from_asana = True
                sub_ticket.updated_at = datetime.utcnow()

        flush_with_retry(db)

    commit_with_retry(db)
    return updated


def pipeline_parent_gids(db: Session, project_id: int) -> set[str]:
    """Parent tickets on the sprint board (for full subtask refresh)."""
    rows = (
        db.query(Ticket)
        .options(joinedload(Ticket.module))
        .filter(
            Ticket.project_id == project_id,
            Ticket.parent_asana_gid.is_(None),
            Ticket.asana_gid.isnot(None),
            Ticket.removed_from_asana.is_(False),
        )
        .all()
    )
    gids: set[str] = set()
    for ticket in rows:
        if ticket.module and is_sprint_pipeline_section(ticket.module.name) and ticket.asana_gid:
            gids.add(ticket.asana_gid)
    return gids


def parent_gids_from_synced_tasks(tasks: list[dict]) -> set[str]:
    """Parents to refresh after a delta sync (touched task or its parent)."""
    gids: set[str] = set()
    for task in tasks:
        gid = task.get("gid")
        parent_gid = _parent_gid(task)
        if parent_gid:
            gids.add(parent_gid)
        elif gid:
            gids.add(str(gid))
    return gids
