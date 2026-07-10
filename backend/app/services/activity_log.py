"""Unified activity log helper."""

from sqlalchemy.orm import Session

from app.models import ActivityLog


def log_activity(
    db: Session,
    *,
    module: str,
    action: str,
    summary: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        payload=payload or {},
    )
    db.add(entry)
    db.flush()
    return entry
