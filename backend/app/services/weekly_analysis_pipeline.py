"""Backward-compatible wrappers — daily 5 PM IST pipeline is the source of truth."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.auto_sync import get_meta
from app.services.cursor_analysis import cursor_available
from app.services.cursor_brief_store import META_CEO_BRIEF_OVERLAY
from app.services.daily_issue_intelligence_pipeline import (
    get_daily_issue_intelligence_status,
    run_daily_issue_intelligence,
)

settings = get_settings()


def run_weekly_analysis(db: Session, project_gid: str | None = None) -> dict:
    """Manual trigger with CEO brief overlay (same as Monday 5 PM run)."""
    return run_daily_issue_intelligence(db, project_gid, include_ceo_brief=True)


def get_weekly_analysis_status(db: Session) -> dict:
    daily = get_daily_issue_intelligence_status(db)
    return {
        **daily,
        "last_analysis_at": daily.get("last_run_at"),
        "ceo_brief_ready": bool(get_meta(db, META_CEO_BRIEF_OVERLAY)),
        "send_weekday_ist": settings.ceo_weekly_send_weekday,
        "send_hour_ist": settings.ceo_weekly_send_hour_ist,
        "schedule": "daily_5pm_ist",
    }
