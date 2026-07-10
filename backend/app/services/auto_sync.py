"""Background Asana auto-sync every N minutes + helpers for webhooks."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import AppMeta, AsanaProject
from app.services.sync import SyncService
from app.services.sprint_sheet import sync_all_sprint_sheets
from app.services.sync_lock import sync_lock

logger = logging.getLogger(__name__)
settings = get_settings()


def _set_meta(db: Session, key: str, value: str) -> None:
    row = db.query(AppMeta).filter(AppMeta.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppMeta(key=key, value=value))
    db.commit()


def get_meta(db: Session, key: str) -> str | None:
    row = db.query(AppMeta).filter(AppMeta.key == key).first()
    return row.value if row else None


async def sync_project_after_asana_change(
    db: Session,
    project_gid: str,
    *,
    source: str = "auto",
) -> dict:
    """Pull one Asana project, refresh sprint sheets, optional Jira."""
    svc = SyncService(db)
    result = await svc.sync_all(project_gid)
    sheet_results: list[dict] = []
    if result.get("success"):
        sheet_results = sync_all_sprint_sheets(db, project_gid)
    now = datetime.utcnow().isoformat()
    _set_meta(db, "last_auto_sync_at", now)
    _set_meta(db, "last_auto_sync_source", source)
    return {
        "project_gid": project_gid,
        "success": result.get("success", False),
        "source": source,
        "tasks": (result.get("asana") or {}).get("tasks_synced"),
        "sprint_sheets": sheet_results,
    }


async def run_auto_sync() -> dict:
    if not settings.asana_configured:
        return {"skipped": True, "reason": "Asana not configured"}

    db = SessionLocal()
    results: list[dict] = []
    try:
        svc = SyncService(db)
        projects = await svc.discover_projects()

        for project in projects:
            try:
                async with sync_lock:
                    entry = await sync_project_after_asana_change(db, project.gid, source="auto")
                entry["project"] = project.name
                results.append(entry)
            except Exception as exc:
                logger.exception("Auto-sync failed for %s", project.name)
                results.append({"project": project.name, "success": False, "error": str(exc)})

        now = datetime.utcnow().isoformat()
        _set_meta(db, "last_auto_sync_at", now)
        _set_meta(db, "last_auto_sync_count", str(len(results)))
        return {"synced_at": now, "projects": results}
    finally:
        db.close()


async def auto_sync_loop() -> None:
    interval = max(settings.auto_sync_interval_minutes, 5) * 60
    await asyncio.sleep(30)
    while True:
        if settings.auto_sync_enabled and settings.asana_configured:
            try:
                summary = await run_auto_sync()
                logger.info("Auto-sync complete: %d projects", len(summary.get("projects", [])))
            except Exception:
                logger.exception("Auto-sync loop error")
        # Process due workshop feedback reminders (daily check each loop)
        try:
            db = SessionLocal()
            try:
                from app.services.reminder_service import ReminderService
                sent = ReminderService(db).process_due_reminders()
                if sent:
                    logger.info("Processed %d reminder(s)", len(sent))
            finally:
                db.close()
        except Exception:
            logger.exception("Reminder processing error")
        try:
            from app.services.ceo_report_scheduler import process_scheduled_ceo_reports
            report_result = await process_scheduled_ceo_reports()
            if report_result and report_result.get("success"):
                logger.info("Scheduled CEO report delivered")
        except Exception:
            logger.exception("CEO report scheduler error")
        await asyncio.sleep(interval)
