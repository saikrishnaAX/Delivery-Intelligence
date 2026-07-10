"""Persisted Cursor CEO brief overlay (AppMeta keys)."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.services.auto_sync import get_meta

META_CEO_BRIEF_OVERLAY = "cursor_ceo_brief_overlay_json"
META_LAST_ANALYSIS = "cursor_weekly_analysis_at"
META_ANALYSIS_STATUS = "cursor_weekly_analysis_status"
META_ANALYSIS_ERROR = "cursor_weekly_analysis_error"
META_ISSUES_ENRICHED = "cursor_issues_enriched_count"
META_DAILY_II_LAST = "cursor_daily_issue_intel_at"
META_DAILY_II_STATUS = "cursor_daily_issue_intel_status"
META_DAILY_II_ERROR = "cursor_daily_issue_intel_error"


def load_ceo_brief_overlay(db: Session) -> dict | None:
    raw = get_meta(db, META_CEO_BRIEF_OVERLAY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
