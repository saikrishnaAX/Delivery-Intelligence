"""Scheduled CEO report — daily Issue Intelligence at 5 PM IST; CEO email Tuesday IST."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import AsanaProject
from app.services.ceo_report import CEOReportService
from app.services.daily_issue_intelligence_pipeline import process_daily_issue_intelligence

logger = logging.getLogger(__name__)
settings = get_settings()

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> datetime:
    return datetime.now(IST)


def _is_weekly_send_due(last_sent: datetime | None, now_ist: datetime) -> bool:
    if now_ist.weekday() != settings.ceo_weekly_send_weekday:
        return False
    if now_ist.hour < settings.ceo_weekly_send_hour_ist:
        return False
    if last_sent is None:
        return True
    return (datetime.utcnow() - last_sent).days >= 6


def _is_legacy_due(frequency: str, last_sent: datetime | None, now: datetime) -> bool:
    """Monthly / 6-month schedules (UTC-based, unchanged)."""
    if last_sent is None:
        return now.weekday() == 0 and now.hour >= 7

    if frequency == "monthly":
        if now.day != 1:
            return False
        return last_sent.month != now.month or last_sent.year != now.year

    if frequency == "6months":
        if now.day != 1 or now.month not in (1, 7):
            return False
        return (now - last_sent).days >= 170

    return False


async def process_scheduled_ceo_reports() -> dict | None:
    daily_result = await process_daily_issue_intelligence()

    db = SessionLocal()
    try:
        svc = CEOReportService(db)
        cfg = svc.get_settings()
        if not cfg["schedule_enabled"]:
            return daily_result
        if not cfg["email_configured"]:
            logger.debug("CEO report schedule skipped — email not configured")
            return daily_result

        frequency = cfg["schedule_frequency"]
        if frequency not in ("weekly", "monthly", "6months"):
            frequency = "weekly"

        last_raw = cfg.get("last_sent_at")
        last_sent = datetime.fromisoformat(last_raw) if last_raw else None
        now_utc = datetime.utcnow()
        now_ist = _now_ist()

        if frequency == "weekly":
            if not _is_weekly_send_due(last_sent, now_ist):
                return daily_result
        elif not _is_legacy_due(frequency, last_sent, now_utc):
            return daily_result

        project_gid = cfg.get("schedule_project_gid")
        if not project_gid:
            first = db.query(AsanaProject).order_by(AsanaProject.id).first()
            project_gid = first.gid if first else None

        if not project_gid:
            logger.warning("CEO report schedule skipped — no project")
            return daily_result

        result = svc.send_report(
            project_gid=project_gid,
            period=frequency,  # type: ignore[arg-type]
            source="scheduled",
        )
        logger.info("Scheduled CEO report sent to %s", result.get("sent_to"))
        return result
    except Exception:
        logger.exception("Scheduled CEO report failed")
        return {"success": False}
    finally:
        db.close()
