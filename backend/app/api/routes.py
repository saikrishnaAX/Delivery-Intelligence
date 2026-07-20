from datetime import datetime
import logging
import re
from pathlib import Path

from dateutil import parser as date_parser

from fastapi import APIRouter, Depends, Query, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError, PendingRollbackError, SQLAlchemyError

from app.config import get_settings
from app.database import get_db
from app.models import AsanaProject, ExecutiveSummary, ReleaseNoteArchive
from app.schemas import (
    ExecutiveMetrics, ExecutionBoardResponse, ExecutiveDrilldownResponse, TicketListResponse, ClassificationAnalytics,
    ClusteringAnalytics, HeatMapAnalytics, SupportAccuracyAnalytics,
    BlockerAnalytics, CustomerPainAnalytics, JiraAnalytics,
    ResolutionAnalytics, MonthlyProgressAnalytics, SupportTeamAnalytics, AIInsightResponse, ExecutiveSummaryResponse,
    ChatRequest, ChatResponse, ProjectResponse, IntegrationStatusResponse,
    GoogleSheetLinkRequest,
    SyncResponse, ReleaseNotesResponse, ReleaseNoteArchiveResponse,
    SprintSheetResponse, SprintSheetExportRequest,
    ReleaseNoteArchiveSendRequest, ReleaseNotesSendResponse,
    WorkshopAnnouncementDraftsRequest, WorkshopAnnouncementDraftsResponse,
    IssueIntelligenceDashboard, IssueIntelligenceJobResponse, RecurringIssueDetail,
    CEOReportSendRequest, CEOReportSendResponse, CEOReportPreviewResponse, CEOReportSettingsResponse, CEOReportSettingsUpdate,
)
from app.services.analytics import AnalyticsService
from app.services.ai import AIService
from app.services.sync import SyncService
from app.services.release_notes import ReleaseNotesService
from app.services.org_service import OrgService
from app.services.email_service import EmailService
from app.services.sprint_sheet import SprintSheetService, _totals, sync_all_sprint_sheets
from app.services.sync_lock import sync_lock
from app.services.activity_log import log_activity
from app.db_utils import commit_with_retry, flush_with_retry, persist_with_retry

settings = get_settings()

router = APIRouter()
logger = logging.getLogger(__name__)


def _analytics(
    db: Session,
    project_gid: str | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> AnalyticsService:
    return AnalyticsService(db, project_gid=project_gid, date_from=date_from, date_to=date_to)


@router.get("/integrations/status", response_model=IntegrationStatusResponse)
def integration_status(db: Session = Depends(get_db)):
    return SyncService(db).integration_status()


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(db: Session = Depends(get_db)):
    return await SyncService(db).discover_projects()


@router.post("/sync/{project_gid}", response_model=SyncResponse)
async def sync_project(
    project_gid: str,
    incremental: bool = Query(
        False,
        description="If true, only pull Asana tasks changed since last sync (faster for Sprint Sheet)",
    ),
    db: Session = Depends(get_db),
):
    async with sync_lock:
        result = await SyncService(db).sync_all(project_gid, incremental=incremental)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Sync failed"))
        sheet_sync = sync_all_sprint_sheets(db, project_gid)
    asana = result.get("asana", {})
    if sheet_sync:
        asana = {**asana, "google_sheets": sheet_sync}
    jira = result.get("jira", {})
    return SyncResponse(
        success=True,
        project_gid=project_gid,
        project_name=asana.get("project_name"),
        tasks_synced=asana.get("tasks_synced"),
        issues_synced=jira.get("issues_synced"),
        asana=asana,
        jira=jira,
    )


@router.post("/webhooks/asana")
async def asana_webhook(request: Request):
    from app.services.asana_webhooks import handle_asana_webhook
    return await handle_asana_webhook(request)


@router.post("/webhooks/jira")
async def jira_webhook(request: Request):
    from app.services.jira_webhooks import handle_jira_webhook
    return await handle_jira_webhook(request)


@router.get("/execution", response_model=ExecutionBoardResponse)
def get_execution_board(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from app.services.execution_board import ExecutionBoardService
    return ExecutionBoardService(db, project_gid, date_from, date_to).build()


@router.get("/execution/drilldown", response_model=ExecutiveDrilldownResponse)
def get_execution_drilldown(
    metric: str = Query(..., description="Drilldown metric key"),
    stage: str | None = Query(None, description="Pipeline stage for sprint drilldown"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from app.services.executive_drilldown import ExecutiveDrilldownService

    try:
        tickets, total = ExecutiveDrilldownService(db, project_gid, date_from, date_to).get(
            metric, stage=stage, limit=limit, offset=offset
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExecutiveDrilldownResponse(
        metric=metric,
        stage=stage,
        total=total,
        tickets=tickets,
        limit=limit,
        offset=offset,
    )


@router.get("/executive/analytics")
def get_executive_analytics(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from app.services.executive_analytics import ExecutiveAnalyticsService
    return ExecutiveAnalyticsService(db, project_gid, date_from, date_to).build()


@router.get("/ceo-intelligence")
def get_ceo_intelligence(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from app.services.ceo_intelligence import CEOIntelligenceService
    return CEOIntelligenceService(db, project_gid, date_from, date_to).build()


@router.get("/ceo-intelligence/report-settings", response_model=CEOReportSettingsResponse)
def get_ceo_report_settings(db: Session = Depends(get_db)):
    from app.services.ceo_report import CEOReportService
    return CEOReportService(db).get_settings()


@router.patch("/ceo-intelligence/report-settings", response_model=CEOReportSettingsResponse)
def update_ceo_report_settings(
    body: CEOReportSettingsUpdate,
    db: Session = Depends(get_db),
):
    from app.services.ceo_report import CEOReportService
    return CEOReportService(db).update_settings(
        ceo_email=body.ceo_email,
        schedule_enabled=body.schedule_enabled,
        schedule_frequency=body.schedule_frequency,
        schedule_project_gid=body.schedule_project_gid,
    )


@router.post("/issue-intelligence/run-daily-cursor")
def run_daily_cursor_analysis(
    project_gid: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Manual trigger: Issue Intelligence + Cursor enrich (normally daily 5 PM IST)."""
    from app.services.daily_issue_intelligence_pipeline import run_daily_issue_intelligence

    result = run_daily_issue_intelligence(db, project_gid, include_ceo_brief=False)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
    return result


@router.post("/ceo-intelligence/run-weekly-analysis")
def run_weekly_cursor_analysis(
    project_gid: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Manual trigger: daily pipeline + CEO brief overlay (normally Monday 5 PM IST)."""
    from app.services.weekly_analysis_pipeline import run_weekly_analysis

    result = run_weekly_analysis(db, project_gid)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Analysis failed"))
    return result


@router.get("/ceo-intelligence/report-preview", response_model=CEOReportPreviewResponse)
def preview_ceo_report(
    project_gid: str | None = Query(None),
    period: str = Query("weekly"),
    db: Session = Depends(get_db),
):
    from app.services.ceo_report import CEOReportService

    p = period if period in ("weekly", "monthly", "6months") else "weekly"
    return CEOReportService(db).preview_report(project_gid=project_gid, period=p)  # type: ignore[arg-type]


@router.post("/ceo-intelligence/send-report", response_model=CEOReportSendResponse)
def send_ceo_report(
    body: CEOReportSendRequest,
    project_gid: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from app.services.ceo_report import CEOReportService

    period = body.period if body.period in ("weekly", "monthly", "6months") else "weekly"
    emails = [*(body.recipient_emails or []), *(body.extra_emails or [])]
    try:
        result = CEOReportService(db).send_report(
            project_gid=project_gid,
            period=period,  # type: ignore[arg-type]
            recipient_emails=emails or None,
            source="manual",
        )
        return CEOReportSendResponse(**result)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/tickets", response_model=TicketListResponse)
def list_tickets(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    ticket_type: str | None = Query(None, description="task, requirement, enhancement, or bug"),
    db: Session = Depends(get_db),
):
    tickets, total = _analytics(db, project_gid, date_from, date_to).get_tickets(
        page, page_size, status, ticket_type
    )
    return TicketListResponse(tickets=tickets, total=total, page=page, page_size=page_size)


@router.get("/classification", response_model=ClassificationAnalytics)
def get_classification(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return _analytics(db, project_gid, date_from, date_to).get_classification_analytics()


@router.get("/clustering", response_model=ClusteringAnalytics)
def get_clustering(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return _analytics(db, project_gid, date_from, date_to).get_clustering_analytics()


@router.post("/clustering/rebuild")
def rebuild_clustering(
    project_gid: str = Query(...),
    db: Session = Depends(get_db),
):
    """Re-run symptom-based clustering without a full Asana sync."""
    project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    from app.services.clustering import run_semantic_clustering

    try:
        count = run_semantic_clustering(db, project.id)
        return {"success": True, "clusters_created": count, "project_gid": project_gid}
    except Exception as exc:
        db.rollback()
        logger.exception("Cluster rebuild failed for project %s", project_gid)
        raise HTTPException(
            status_code=500,
            detail=f"Cluster rebuild failed: {exc}. Try again in a few seconds.",
        ) from exc


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return date_parser.parse(value)
    except (ValueError, TypeError):
        return None


@router.get("/issue-intelligence", response_model=IssueIntelligenceDashboard)
def get_issue_intelligence(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from app.services.issue_intelligence import IssueIntelligenceService
    if not project_gid:
        raise HTTPException(status_code=400, detail="project_gid is required")
    svc = IssueIntelligenceService(db)
    data = svc.get_dashboard(project_gid, _parse_date(date_from), _parse_date(date_to))
    return IssueIntelligenceDashboard(**data)


@router.post("/issue-intelligence/analyze", response_model=IssueIntelligenceJobResponse)
def start_issue_intelligence_analysis(
    project_gid: str = Query(...),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    from app.services.issue_intelligence import IssueIntelligenceService
    svc = IssueIntelligenceService(db)
    try:
        job = svc.start_analysis(project_gid, _parse_date(date_from), _parse_date(date_to))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IssueIntelligenceJobResponse(
        id=job.id,
        status=job.status,
        tickets_total=job.tickets_total,
        tickets_processed=job.tickets_processed,
        issues_found=job.issues_found or 0,
        analysis_mode=job.analysis_mode or "engineering_fix",
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get("/issue-intelligence/jobs/{job_id}", response_model=IssueIntelligenceJobResponse)
def get_issue_intelligence_job(job_id: int, db: Session = Depends(get_db)):
    from app.services.issue_intelligence import IssueIntelligenceService
    job = IssueIntelligenceService(db).get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return IssueIntelligenceJobResponse(
        id=job.id,
        status=job.status,
        tickets_total=job.tickets_total,
        tickets_processed=job.tickets_processed,
        issues_found=job.issues_found or 0,
        analysis_mode=job.analysis_mode or "engineering_fix",
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get("/issue-intelligence/issues/{issue_id}", response_model=RecurringIssueDetail)
def get_recurring_issue_detail(issue_id: int, db: Session = Depends(get_db)):
    from app.services.issue_intelligence import IssueIntelligenceService
    detail = IssueIntelligenceService(db).get_issue_detail(issue_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Issue not found")
    return RecurringIssueDetail(**detail)


@router.get("/heatmap", response_model=HeatMapAnalytics)
def get_heatmap(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return _analytics(db, project_gid, date_from, date_to).get_heatmap_analytics()


@router.get("/accuracy", response_model=SupportAccuracyAnalytics)
def get_accuracy(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return _analytics(db, project_gid, date_from, date_to).get_support_accuracy()


@router.get("/blockers", response_model=BlockerAnalytics)
def get_blockers(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return _analytics(db, project_gid, date_from, date_to).get_blocker_analytics()


@router.get("/customers", response_model=CustomerPainAnalytics)
def get_customer_pain(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return _analytics(db, project_gid, date_from, date_to).get_customer_pain()


@router.get("/support-team", response_model=SupportTeamAnalytics)
def get_support_team(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return _analytics(db, project_gid, date_from, date_to).get_support_team_analytics()


@router.get("/jira", response_model=JiraAnalytics)
def get_jira(db: Session = Depends(get_db)):
    return AnalyticsService(db).get_jira_analytics()


@router.post("/jira/sync", response_model=SyncResponse)
async def sync_jira(db: Session = Depends(get_db)):
    result = await SyncService(db).sync_jira_global()
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Jira sync failed"))
    return SyncResponse(
        success=True,
        issues_synced=result.get("issues_synced"),
        jira=result,
    )


@router.get("/resolution", response_model=ResolutionAnalytics)
def get_resolution(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return _analytics(db, project_gid, date_from, date_to).get_resolution_analytics()


@router.get("/resolution/monthly", response_model=MonthlyProgressAnalytics)
def get_monthly_progress(
    project_gid: str | None = Query(None),
    year: int | None = Query(None),
    db: Session = Depends(get_db),
):
    selected_year = year or datetime.utcnow().year
    return _analytics(db, project_gid).get_monthly_progress(selected_year)


@router.get("/insights/{page}", response_model=list[AIInsightResponse])
def get_insights(
    page: str,
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return AIService(db, project_gid, date_from=date_from, date_to=date_to).get_insights_for_page(page)


@router.post("/assistant/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    return AIService(db, project_gid, date_from=date_from, date_to=date_to).chat(request)


@router.get("/release-notes", response_model=ReleaseNotesResponse)
async def get_release_notes(
    project_gid: str | None = Query(None),
    lookback_days: int = Query(2, ge=1, le=30),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    sprint_name: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if not project_gid:
        raise HTTPException(status_code=400, detail="Select a project to generate release notes.")
    payload = await ReleaseNotesService(db, project_gid).build(
        lookback_days=lookback_days,
        date_from=date_from,
        date_to=date_to,
        sprint_name=sprint_name,
    )
    return payload


@router.get("/release-notes/download")
async def download_release_notes(
    project_gid: str | None = Query(None),
    lookback_days: int = Query(2, ge=1, le=30),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    sprint_name: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if not project_gid:
        raise HTTPException(status_code=400, detail="Select a project to download release notes.")
    service = ReleaseNotesService(db, project_gid)
    payload = await service.build(
        lookback_days=lookback_days,
        date_from=date_from,
        date_to=date_to,
        sprint_name=sprint_name,
    )
    docx_bytes = service.build_docx(payload)
    filename = f"Release Notes {payload['release_date']}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/release-notes/workshop-audience")
def release_notes_workshop_audience(db: Session = Depends(get_db)):
    from app.services.workshop_email_drafts import WorkshopEmailDraftService
    return WorkshopEmailDraftService(db).audience_preview_counts()


@router.post("/release-notes/workshop-announcement/drafts", response_model=WorkshopAnnouncementDraftsResponse)
async def create_workshop_release_drafts(
    project_gid: str = Query(...),
    body: WorkshopAnnouncementDraftsRequest = ...,
    db: Session = Depends(get_db),
):
    project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    service = ReleaseNotesService(db, project_gid)
    payload = await service.build(
        lookback_days=body.lookback_days or 2,
        date_from=body.date_from,
        date_to=body.date_to,
        sprint_name=body.sprint_name,
    )
    if not payload.get("total_items"):
        raise HTTPException(status_code=400, detail="No release items in the selected window.")
    from app.services.workshop_email_drafts import WorkshopEmailDraftService
    result = WorkshopEmailDraftService(db).create_release_announcement_drafts(
        project_id=project.id,
        release_payload=payload,
        sprint_name=body.sprint_name,
        audience=body.audience,
        workshop_ids=body.workshop_ids,
    )
    return result


def _parse_release_date(value: str) -> datetime:
    try:
        return date_parser.parse(value).replace(tzinfo=None, hour=12, minute=0, second=0, microsecond=0)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid release_date") from exc


def _archive_to_response(row: ReleaseNoteArchive) -> ReleaseNoteArchiveResponse:
    return ReleaseNoteArchiveResponse(
        id=row.id,
        project_id=row.project_id,
        project_name=row.project.name if row.project else None,
        release_date=row.release_date.isoformat(),
        title=row.title,
        sprint_name=row.sprint_name,
        original_filename=row.original_filename,
        file_size=row.file_size or 0,
        source=row.source or "upload",
        created_at=row.created_at,
    )


@router.get("/release-notes/archive", response_model=list[ReleaseNoteArchiveResponse])
def list_release_note_archives(
    project_gid: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = (
        db.query(ReleaseNoteArchive)
        .options(joinedload(ReleaseNoteArchive.project))
        .order_by(ReleaseNoteArchive.release_date.desc())
    )
    if project_gid:
        project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
        if project:
            q = q.filter(
                or_(
                    ReleaseNoteArchive.project_id == project.id,
                    ReleaseNoteArchive.project_id.is_(None),
                )
            )
    rows = q.limit(100).all()
    rows = [r for r in rows if not _is_test_archive(r)]
    return [_archive_to_response(r) for r in rows]


def _is_test_archive(row: ReleaseNoteArchive) -> bool:
    title = (row.title or "").strip().lower()
    filename = (row.original_filename or "").strip().lower()
    if title in {"test", "test upload"} or title.startswith("test upload"):
        return True
    if filename in {"test.docx", "hist.docx"} or "_test." in filename:
        return True
    if "hist.docx" in filename and title.startswith("test"):
        return True
    return False


@router.post("/release-notes/archive", response_model=ReleaseNoteArchiveResponse)
async def upload_release_note_archive(
    file: UploadFile = File(...),
    project_gid: str | None = Query(None),
    release_date: str = Query(...),
    title: str | None = Query(None),
    sprint_name: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")
    allowed = (".docx", ".doc", ".pdf")
    lower = file.filename.lower()
    if not any(lower.endswith(ext) for ext in allowed):
        raise HTTPException(status_code=400, detail="Upload a .docx, .doc, or .pdf file")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 25 MB)")

    project_id = None
    if project_gid:
        project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        project_id = project.id

    parsed_date = _parse_release_date(release_date)
    storage_dir = Path(settings.release_notes_storage_dir) / "archive"
    storage_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\s.\-]", "", file.filename).strip() or "release_notes.docx"
    stored_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
    file_path = storage_dir / stored_name
    file_path.write_bytes(data)

    archive = ReleaseNoteArchive(
        project_id=project_id,
        release_date=parsed_date,
        title=title or f"Release Notes {parsed_date.strftime('%d %B %Y')}",
        sprint_name=sprint_name,
        original_filename=file.filename,
        file_path=str(file_path),
        file_size=len(data),
        source="upload",
    )

    def _write_archive() -> None:
        db.add(archive)
        db.flush()
        log_activity(
            db,
            module="release_notes",
            action="archive_uploaded",
            summary=f"Uploaded release notes archive: {archive.title}",
            entity_type="release_note_archive",
            entity_id=str(archive.id),
        )

    try:
        persist_with_retry(db, _write_archive, retries=5)
    except (OperationalError, PendingRollbackError) as exc:
        if "locked" in str(exc).lower() or "rolled back" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Database busy — try again in a few seconds") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        detail = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
        if "no such table" in detail.lower():
            raise HTTPException(
                status_code=500,
                detail="Archive table missing — restart the backend to run migrations",
            ) from exc
        raise HTTPException(status_code=500, detail=detail) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    db.refresh(archive)
    return _archive_to_response(archive)


@router.get("/release-notes/archive/{archive_id}/download")
def download_release_note_archive(archive_id: int, db: Session = Depends(get_db)):
    row = db.query(ReleaseNoteArchive).filter(ReleaseNoteArchive.id == archive_id).first()
    if not row or _is_test_archive(row):
        raise HTTPException(status_code=404, detail="Archive not found")
    path = Path(row.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File missing on server")
    media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if row.original_filename.lower().endswith(".pdf"):
        media = "application/pdf"
    elif row.original_filename.lower().endswith(".doc"):
        media = "application/msword"
    return Response(
        content=path.read_bytes(),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{row.original_filename}"'},
    )


@router.post("/release-notes/archive/{archive_id}/send", response_model=ReleaseNotesSendResponse)
def send_release_note_archive(
    archive_id: int,
    body: ReleaseNoteArchiveSendRequest,
    db: Session = Depends(get_db),
):
    row = db.query(ReleaseNoteArchive).filter(ReleaseNoteArchive.id == archive_id).first()
    if not row or _is_test_archive(row):
        raise HTTPException(status_code=404, detail="Archive not found")

    path = Path(row.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File missing on server")

    org = OrgService(db)
    emails = org.resolve_recipient_emails(
        body.team_ids, body.person_ids, body.excluded_person_ids
    )
    emails.extend(e.strip().lower() for e in body.extra_emails if e.strip())
    emails = sorted(set(emails))
    if not emails:
        raise HTTPException(status_code=400, detail="Select at least one recipient")

    email_svc = EmailService()
    if not email_svc.configured:
        raise HTTPException(status_code=400, detail="Gmail not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD.")

    release_date = row.release_date.strftime("%d %B %Y")
    title = row.title or f"Release Notes {release_date}"
    subject = f"Release Notes — {title}"
    text, html = email_svc.archive_document_body(title, release_date)
    file_bytes = path.read_bytes()

    try:
        email_svc.send_email(emails, subject, text, html, attachment=(row.original_filename, file_bytes))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    log_activity(
        db,
        module="release_notes",
        action="archive_email_sent",
        summary=f"Emailed archived release notes: {title} to {len(emails)} recipient(s)",
        entity_type="release_note_archive",
        entity_id=str(row.id),
        payload={"recipients": emails},
    )
    commit_with_retry(db)

    return ReleaseNotesSendResponse(
        success=True,
        recipient_count=len(emails),
        sent_to=emails,
        item_count=0,
    )


@router.get("/sprint-sheet", response_model=SprintSheetResponse)
async def get_sprint_sheet(
    project_gid: str | None = Query(None),
    sprint_name: str = Query("Sprint"),
    section: str | None = Query(None),
    refresh: bool = Query(False, description="Re-merge sprint sheet from DB and sync Google Sheet"),
    db: Session = Depends(get_db),
):
    if not project_gid:
        raise HTTPException(status_code=400, detail="Select a project to build the sprint sheet.")
    if refresh:
        async with sync_lock:
            return SprintSheetService(db, project_gid).build(
                sprint_name=sprint_name,
                section_name=section,
                refresh=True,
            )
    return SprintSheetService(db, project_gid).build(
        sprint_name=sprint_name,
        section_name=section,
        refresh=False,
    )


@router.post("/sprint-sheet/save", response_model=SprintSheetResponse)
def save_sprint_sheet(
    body: SprintSheetExportRequest,
    project_gid: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if not project_gid:
        raise HTTPException(status_code=400, detail="Select a project to save the sprint sheet.")
    return SprintSheetService(db, project_gid).save_rows(body.sprint_name, [r.model_dump() for r in body.rows])


@router.post("/sprint-sheet/google/link", response_model=SprintSheetResponse)
def link_sprint_google_sheet(
    body: GoogleSheetLinkRequest,
    project_gid: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if not project_gid:
        raise HTTPException(status_code=400, detail="Select a project to link Google Sheets.")
    svc = SprintSheetService(db, project_gid)
    try:
        return svc.link_google_sheet(body.sprint_name, body.spreadsheet_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google Sheets error: {exc}") from exc


@router.post("/sprint-sheet/download")
def download_sprint_sheet(
    body: SprintSheetExportRequest,
    project_gid: str | None = Query(None),
    db: Session = Depends(get_db),
):
    if not project_gid:
        raise HTTPException(status_code=400, detail="Select a project to download the sprint sheet.")
    service = SprintSheetService(db, project_gid)
    if body.rows:
        from app.services.sprint_sheet import _row_sort_key

        row_dicts = [row.model_dump() for row in body.rows]
        row_dicts.sort(key=_row_sort_key)
        payload = {
            "sprint_name": body.sprint_name,
            "project_name": service._project().name if service._project() else None,
            "project_gid": project_gid,
            "section": body.section or settings.asana_sprint_section_name,
            "generated_at": datetime.utcnow().isoformat(),
            "rows": row_dicts,
            "totals": _totals(row_dicts),
            "asana_live": service.asana.is_configured,
        }
    else:
        payload = service.build(
            sprint_name=body.sprint_name,
            section_name=body.section,
        )
    xlsx_bytes = service.build_xlsx(payload)
    safe_name = re.sub(r'[^\w\s-]', '', body.sprint_name).strip() or "Sprint"
    filename = f"{safe_name} Sheet.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
