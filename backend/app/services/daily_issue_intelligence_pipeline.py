"""Daily Issue Intelligence — 5 PM IST Cursor enrich for urgent recurring-issue data."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import AsanaProject, RecurringIssue, Ticket
from app.services.auto_sync import get_meta, _set_meta
from app.services.ceo_intelligence import CEOIntelligenceService
from app.services.ceo_report import CEOReportService, period_window
from app.services.cursor_analysis import (
    build_ceo_brief_overlay,
    build_facts_packet,
    cursor_available,
    enrich_issue_group,
)
from app.services.cursor_brief_store import (
    META_ANALYSIS_ERROR,
    META_ANALYSIS_STATUS,
    META_CEO_BRIEF_OVERLAY,
    META_DAILY_II_ERROR,
    META_DAILY_II_LAST,
    META_DAILY_II_STATUS,
    META_ISSUES_ENRICHED,
    META_LAST_ANALYSIS,
)
from app.services.issue_intelligence import IssueIntelligenceService

logger = logging.getLogger(__name__)
settings = get_settings()

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    return datetime.now(IST)


def _resolve_project_gid(db: Session) -> str | None:
    gid = get_meta(db, CEOReportService.META_SCHEDULE_PROJECT) or None
    if gid:
        return gid
    first = db.query(AsanaProject).order_by(AsanaProject.id).first()
    return first.gid if first else None


def _last_daily_run_ist_date(db: Session) -> date | None:
    raw = get_meta(db, META_DAILY_II_LAST)
    if not raw:
        return None
    try:
        last = datetime.fromisoformat(raw)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return last.astimezone(IST).date()
    except ValueError:
        return None


def _cursor_enrich_job_issues(db: Session, job_id: int, project_gid: str) -> tuple[int, list[RecurringIssue]]:
    limit = max(1, settings.cursor_issue_enrich_limit)
    issues = (
        db.query(RecurringIssue)
        .filter(RecurringIssue.job_id == job_id)
        .order_by(RecurringIssue.priority_score.desc())
        .limit(limit)
        .all()
    )
    enriched = 0
    for issue in issues:
        ticket_ids = issue.ticket_ids or []
        if not ticket_ids:
            continue
        tickets = db.query(Ticket).filter(Ticket.id.in_(ticket_ids)).all()
        samples = [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "workshop_name": t.workshop_name,
                "description": (t.description or "")[:400],
                "is_workflow_blocker": bool(t.is_workflow_blocker),
            }
            for t in tickets[:20]
        ]
        intel = issue.intelligence or {}
        overlay = enrich_issue_group(
            issue.issue_name,
            issue.engineering_fix_key or "",
            intel.get("engineering_fix_label") or "",
            samples,
        )
        if not overlay:
            continue
        merged = {**intel, **overlay}
        if overlay.get("issue_name"):
            issue.issue_name = str(overlay["issue_name"])[:500]
        if overlay.get("confidence") is not None:
            issue.confidence = float(overlay["confidence"])
        issue.intelligence = merged
        enriched += 1
    db.commit()
    return enriched, issues


def _save_ceo_brief_overlay(db: Session, project_gid: str, issues: list[RecurringIssue]) -> bool:
    date_from, date_to, _ = period_window("weekly")
    intel_data = CEOIntelligenceService(db, project_gid, date_from, date_to).build()
    facts = build_facts_packet(intel_data)
    facts["cursor_enriched_issues"] = [
        {
            "name": i.issue_name,
            "ticket_count": i.ticket_count,
            "open_count": i.open_count,
            "claim_tier": (i.intelligence or {}).get("claim_tier", "hypothesis"),
            "evidence_summary": (i.intelligence or {}).get("evidence_summary", "")[:200],
        }
        for i in issues[:6]
    ]
    brief_overlay = build_ceo_brief_overlay(facts)
    if not brief_overlay:
        return False
    _set_meta(db, META_CEO_BRIEF_OVERLAY, json.dumps(brief_overlay, ensure_ascii=False))
    _set_meta(db, META_ANALYSIS_STATUS, "completed")
    return True


def run_daily_issue_intelligence(
    db: Session,
    project_gid: str | None = None,
    *,
    include_ceo_brief: bool = False,
) -> dict:
    """Rules-based grouping + Cursor enrich. Optional CEO brief overlay (Monday 5 PM)."""
    project_gid = project_gid or _resolve_project_gid(db)
    if not project_gid:
        return {"success": False, "error": "No project configured"}

    project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
    if not project:
        return {"success": False, "error": "Project not found"}

    _set_meta(db, META_DAILY_II_STATUS, "running")
    issues_enriched = 0
    ceo_brief_saved = False

    try:
        ii = IssueIntelligenceService(db)
        job = ii.run_analysis_sync(project_gid)
        if job.status != "completed":
            raise RuntimeError(job.error_message or "Issue intelligence failed")

        if cursor_available():
            issues_enriched, issues = _cursor_enrich_job_issues(db, job.id, project_gid)
            if include_ceo_brief:
                ceo_brief_saved = _save_ceo_brief_overlay(db, project_gid, issues)
        else:
            logger.warning("Cursor not configured — daily issue intelligence ran rules only")

        now = datetime.utcnow().isoformat()
        _set_meta(db, META_DAILY_II_LAST, now)
        _set_meta(db, META_LAST_ANALYSIS, now)
        _set_meta(db, META_ISSUES_ENRICHED, str(issues_enriched))
        _set_meta(db, META_DAILY_II_STATUS, "completed")
        _set_meta(db, META_DAILY_II_ERROR, "")

        return {
            "success": True,
            "project_gid": project_gid,
            "job_id": job.id,
            "issues_found": job.issues_found,
            "issues_cursor_enriched": issues_enriched,
            "ceo_brief_overlay_saved": ceo_brief_saved,
            "analysis_at": now,
            "cursor_used": cursor_available(),
            "schedule": "daily_5pm_ist",
        }
    except Exception as exc:
        logger.exception("Daily issue intelligence failed")
        _set_meta(db, META_DAILY_II_STATUS, "failed")
        _set_meta(db, META_DAILY_II_ERROR, str(exc)[:500])
        db.commit()
        return {"success": False, "error": str(exc)}


async def process_daily_issue_intelligence() -> dict | None:
    """Run once per IST calendar day at/after 5 PM. Does not require CEO email schedule."""
    if not settings.issue_intelligence_daily_enabled:
        return None
    if not cursor_available():
        return None

    db = SessionLocal()
    try:
        now = now_ist()
        if now.hour < settings.issue_intelligence_daily_hour_ist:
            return None

        if _last_daily_run_ist_date(db) == now.date():
            return None

        # Monday 5 PM: refresh CEO brief draft for Tuesday email
        include_ceo_brief = now.weekday() == 0

        result = run_daily_issue_intelligence(db, include_ceo_brief=include_ceo_brief)
        if result.get("success"):
            logger.info(
                "Daily issue intelligence (5 PM IST): %s issues, %s Cursor-enriched",
                result.get("issues_found"),
                result.get("issues_cursor_enriched"),
            )
        return result
    finally:
        db.close()


def get_daily_issue_intelligence_status(db: Session) -> dict:
    return {
        "enabled": settings.issue_intelligence_daily_enabled,
        "cursor_configured": cursor_available(),
        "daily_hour_ist": settings.issue_intelligence_daily_hour_ist,
        "last_run_at": get_meta(db, META_DAILY_II_LAST),
        "last_run_ist_date": (
            _last_daily_run_ist_date(db).isoformat() if _last_daily_run_ist_date(db) else None
        ),
        "status": get_meta(db, META_DAILY_II_STATUS) or "idle",
        "error": get_meta(db, META_DAILY_II_ERROR),
        "issues_enriched": int(get_meta(db, META_ISSUES_ENRICHED) or "0"),
    }
