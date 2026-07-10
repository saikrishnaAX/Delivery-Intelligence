"""Organization, activity, communications, cluster analysis, and impact APIs."""

import csv
import io
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.database import get_db, SessionLocal
from app.models import (
    ActivityLog, AsanaProject, SprintSheet, ClusterAnalysisJob, ClusterAnalysisResult,
    Team, TeamMembership, Person, CustomerAccount, IssueCluster, Ticket,
)
from app.schemas import (
    TeamResponse, TeamMemberResponse, PersonResponse, CustomerAccountResponse,
    CsvImportResponse, ActivityLogListResponse, ActivityLogResponse,
    CreateTeamRequest, AddTeamMemberRequest, UpdateTeamMemberRequest, UpdateTeamRequest,
    CreateCustomerAccountRequest, UpdateCustomerAccountRequest,
    WorkshopEmailDraftResponse, UpdateWorkshopEmailDraftRequest, WorkshopEmailDraftSummary,
    ReleaseNotesSendRequest, ReleaseNotesSendResponse,
    WorkshopHistoryResponse, WorkshopHistoryItem, WorkshopHistoryTicket,
    ScheduledReminderResponse, MarkSprintReleasedRequest,
    ClusterTicketResponse, ClusterAnalysisJobResponse, ClusterAnalysisResultResponse,
    ImpactMetricsResponse, ImpactTopWorkshop,
)
from app.services.org_service import OrgService
from app.services.activity_log import log_activity
from app.services.email_service import EmailService
from app.services.release_notes import ReleaseNotesService
from app.services.workshop_history import WorkshopHistoryService
from app.services.reminder_service import ReminderService
from app.services.cluster_analysis import ClusterAnalysisService
from app.services.impact_analytics import ImpactAnalyticsService
from app.services.workshop_email_drafts import WorkshopEmailDraftService
from app.models import ReleaseNoteSend

settings = get_settings()
org_router = APIRouter()


def _team_to_response(team: Team) -> TeamResponse:
    members = []
    for m in team.memberships:
        if m.person:
            members.append(TeamMemberResponse(
                person=PersonResponse.model_validate(m.person),
                is_lead=m.is_lead,
            ))
    return TeamResponse(
        id=team.id,
        name=team.name,
        description=team.description,
        members=members,
    )


def _customer_to_response(c: CustomerAccount) -> CustomerAccountResponse:
    return CustomerAccountResponse(
        id=c.id,
        name=c.name,
        workshop_name=c.workshop_name,
        tier=c.tier,
        industry=c.industry,
        workshop_email=c.workshop_email,
        support_person_name=c.primary_support.name if c.primary_support else None,
        support_person_email=c.primary_support.email if c.primary_support else None,
        support_contact_email=c.support_contact_email,
        ax_id=c.ax_id,
        notes=c.notes,
    )


@org_router.get("/org/teams", response_model=list[TeamResponse])
def list_teams(db: Session = Depends(get_db)):
    teams = OrgService(db).list_teams()
    return [_team_to_response(t) for t in teams]


@org_router.get("/org/people", response_model=list[PersonResponse])
def list_people(db: Session = Depends(get_db)):
    return [PersonResponse.model_validate(p) for p in OrgService(db).list_people()]


@org_router.get("/org/customers", response_model=list[CustomerAccountResponse])
def list_customer_accounts(db: Session = Depends(get_db)):
    return [_customer_to_response(c) for c in OrgService(db).list_customer_accounts()]


@org_router.post("/org/customers", response_model=CustomerAccountResponse)
def create_customer_account(body: CreateCustomerAccountRequest, db: Session = Depends(get_db)):
    svc = OrgService(db)
    try:
        account = svc.create_customer_account_record(
            body.workshop_name,
            support_person_name=body.support_person_name,
            support_person_email=body.support_person_email,
            workshop_email=body.workshop_email,
            support_contact_email=body.support_contact_email,
            ax_id=body.ax_id,
            tier=body.tier,
            location=body.location,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Database busy — try again shortly") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _customer_to_response(account)


@org_router.patch("/org/customers/{customer_id}", response_model=CustomerAccountResponse)
def update_customer_account(
    customer_id: int, body: UpdateCustomerAccountRequest, db: Session = Depends(get_db)
):
    svc = OrgService(db)
    try:
        account = svc.update_customer_account_record(
            customer_id,
            workshop_name=body.workshop_name,
            support_person_name=body.support_person_name,
            support_person_email=body.support_person_email,
            workshop_email=body.workshop_email,
            support_contact_email=body.support_contact_email,
            ax_id=body.ax_id,
            tier=body.tier,
            location=body.location,
        )
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg.lower() else 400
        raise HTTPException(status_code=code, detail=msg) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Database busy — try again shortly") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    from sqlalchemy.orm import joinedload
    loaded = (
        db.query(CustomerAccount)
        .options(joinedload(CustomerAccount.primary_support))
        .filter(CustomerAccount.id == customer_id)
        .first()
    )
    c = loaded or account
    return _customer_to_response(c)


@org_router.delete("/org/customers/{customer_id}")
def delete_customer_account(customer_id: int, db: Session = Depends(get_db)):
    svc = OrgService(db)
    try:
        svc.delete_customer_account_record(customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Database busy — try again shortly") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"success": True}


@org_router.post("/org/customers/reconcile-support-emails")
def reconcile_customer_support_emails(db: Session = Depends(get_db)):
  """Re-link workshop support contacts to team member emails by agent name."""
  return OrgService(db).reconcile_workshop_support_from_teams()


@org_router.post("/org/teams", response_model=TeamResponse)
def create_team(body: CreateTeamRequest, db: Session = Depends(get_db)):
    svc = OrgService(db)
    try:
        team = svc.create_team(body.name, body.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(
                status_code=503,
                detail="Database is busy (sync in progress). Please try again in a few seconds.",
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Database busy — try again shortly") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    from sqlalchemy.orm import joinedload
    loaded = (
        db.query(Team)
        .options(joinedload(Team.memberships).joinedload(TeamMembership.person))
        .filter(Team.id == team.id)
        .first()
    )
    return _team_to_response(loaded or team)


@org_router.post("/org/teams/{team_id}/members", response_model=TeamResponse)
def add_team_member(team_id: int, body: AddTeamMemberRequest, db: Session = Depends(get_db)):
    svc = OrgService(db)
    try:
        svc.add_member_to_team(
            team_id, body.name, body.email, designation=body.designation, is_lead=body.is_lead
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(
                status_code=503,
                detail="Database is busy (sync in progress). Please try again in a few seconds.",
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    from sqlalchemy.orm import joinedload
    updated = (
        db.query(Team)
        .options(joinedload(Team.memberships).joinedload(TeamMembership.person))
        .filter(Team.id == team_id)
        .first()
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Team not found")
    return _team_to_response(updated)


@org_router.patch("/org/teams/{team_id}/members/{person_id}", response_model=TeamResponse)
def update_team_member(
    team_id: int,
    person_id: int,
    body: UpdateTeamMemberRequest,
    db: Session = Depends(get_db),
):
    svc = OrgService(db)
    try:
        svc.update_team_member(
            team_id,
            person_id,
            name=body.name,
            email=body.email,
            designation=body.designation,
            is_lead=body.is_lead,
        )
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg.lower() else 400
        raise HTTPException(status_code=code, detail=msg) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Database busy — try again shortly") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    from sqlalchemy.orm import joinedload
    updated = (
        db.query(Team)
        .options(joinedload(Team.memberships).joinedload(TeamMembership.person))
        .filter(Team.id == team_id)
        .first()
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Team not found")
    return _team_to_response(updated)


@org_router.delete("/org/teams/{team_id}/members/{person_id}", response_model=TeamResponse)
def remove_team_member(team_id: int, person_id: int, db: Session = Depends(get_db)):
    svc = OrgService(db)
    try:
        svc.remove_team_member(team_id, person_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Database busy — try again shortly") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    from sqlalchemy.orm import joinedload
    updated = (
        db.query(Team)
        .options(joinedload(Team.memberships).joinedload(TeamMembership.person))
        .filter(Team.id == team_id)
        .first()
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Team not found")
    return _team_to_response(updated)


@org_router.patch("/org/teams/{team_id}", response_model=TeamResponse)
def update_team(team_id: int, body: UpdateTeamRequest, db: Session = Depends(get_db)):
    svc = OrgService(db)
    try:
        svc.update_team(team_id, body.name, body.description)
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "not found" in msg.lower() else 400
        raise HTTPException(status_code=code, detail=msg) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Database busy — try again shortly") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    from sqlalchemy.orm import joinedload
    loaded = (
        db.query(Team)
        .options(joinedload(Team.memberships).joinedload(TeamMembership.person))
        .filter(Team.id == team_id)
        .first()
    )
    if not loaded:
        raise HTTPException(status_code=404, detail="Team not found")
    return _team_to_response(loaded)


@org_router.delete("/org/teams/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db)):
    svc = OrgService(db)
    try:
        svc.delete_team(team_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(status_code=503, detail="Database busy — try again shortly") from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"success": True}


@org_router.get("/org/templates/teams")
def download_teams_template():
    return Response(
        content=OrgService.TEAMS_CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="teams_template.csv"'},
    )


@org_router.get("/org/templates/customers")
def download_customers_template():
    return Response(
        content=OrgService.CUSTOMERS_CSV_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="customers_template.csv"'},
    )


@org_router.post("/org/import/teams", response_model=CsvImportResponse)
async def import_teams_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = (await file.read()).decode("utf-8-sig")
    result = OrgService(db).import_teams_csv(content)
    return CsvImportResponse(
        success=result["success"],
        errors=result.get("errors", []),
        rows_processed=result.get("rows_processed", 0),
    )


@org_router.post("/org/import/customers", response_model=CsvImportResponse)
async def import_customers_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = (await file.read()).decode("utf-8-sig")
    result = OrgService(db).import_customers_csv(content)
    return CsvImportResponse(
        success=result["success"],
        errors=result.get("errors", []),
        imported=result.get("imported", 0),
    )


@org_router.get("/activity", response_model=ActivityLogListResponse)
def list_activity(
    module: str | None = Query(None),
    action: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(ActivityLog)
    if module:
        q = q.filter(ActivityLog.module == module)
    if action:
        q = q.filter(ActivityLog.action == action)
    if date_from:
        try:
            start = datetime.strptime(date_from[:10], "%Y-%m-%d")
            q = q.filter(ActivityLog.created_at >= start)
        except ValueError:
            q = q.filter(ActivityLog.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        try:
            end = datetime.strptime(date_to[:10], "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q = q.filter(ActivityLog.created_at <= end)
        except ValueError:
            q = q.filter(ActivityLog.created_at <= datetime.fromisoformat(date_to))
    total = q.count()
    items = (
        q.order_by(ActivityLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ActivityLogListResponse(
        items=[ActivityLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@org_router.post("/release-notes/send", response_model=ReleaseNotesSendResponse)
async def send_release_notes(
    body: ReleaseNotesSendRequest,
    project_gid: str = Query(...),
    db: Session = Depends(get_db),
):
    project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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

    rn_svc = ReleaseNotesService(db, project_gid)
    payload = await rn_svc.build(
        lookback_days=body.lookback_days,
        date_from=body.date_from,
        date_to=body.date_to,
        sprint_name=body.sprint_name,
        refresh_releases=True,
    )
    if payload.get("total_items", 0) == 0:
        raise HTTPException(
            status_code=400,
            detail="No tickets moved to Released in the selected window — nothing to send.",
        )
    docx_bytes = rn_svc.build_docx(payload)
    sprint_label = body.sprint_name or "Release"
    filename = f"Release Notes {payload['release_date']}.docx"
    subject = f"Release Notes — {sprint_label} ({payload['release_date']})"
    text, html = email_svc.release_notes_body(sprint_label, payload["total_items"], payload["release_date"])

    try:
        email_svc.send_email(emails, subject, text, html, attachment=(filename, docx_bytes))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    storage_dir = Path(settings.release_notes_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    docx_path = storage_dir / f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
    docx_path.write_bytes(docx_bytes)

    entry = log_activity(
        db,
        module="release_notes",
        action="email_sent",
        summary=f"Sent release notes for {sprint_label} to {len(emails)} recipient(s)",
        entity_type="sprint_sheet",
        entity_id=body.sprint_name or "",
        payload={"recipients": emails, "item_count": payload["total_items"], "docx": str(docx_path)},
    )
    send_record = ReleaseNoteSend(
        project_id=project.id,
        sprint_name=body.sprint_name,
        subject=subject,
        recipient_emails=emails,
        item_count=payload["total_items"],
        docx_path=str(docx_path),
        payload_snapshot=payload,
        activity_log_id=entry.id,
    )
    db.add(send_record)
    db.commit()
    db.refresh(send_record)

    return ReleaseNotesSendResponse(
        success=True,
        recipient_count=len(emails),
        sent_to=[],
        item_count=payload["total_items"],
        activity_log_id=entry.id,
        release_note_send_id=send_record.id,
    )


@org_router.get("/workshops/history", response_model=WorkshopHistoryResponse)
def workshop_history(
    project_gid: str | None = Query(None),
    db: Session = Depends(get_db),
):
    items = WorkshopHistoryService(db, project_gid).get_sprint_history()
    return WorkshopHistoryResponse(
        items=[WorkshopHistoryItem(**{**i, "tickets": [WorkshopHistoryTicket(**t) for t in i.get("tickets", [])]}) for i in items]
    )


@org_router.get("/workshops/reminders", response_model=list[ScheduledReminderResponse])
def list_reminders(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    reminders = ReminderService(db).list_reminders(status)
    out = []
    for r in reminders:
        sprint_name = (r.meta_data or {}).get("sprint_name")
        if not sprint_name and r.sprint_sheet:
            sprint_name = r.sprint_sheet.name
        out.append(ScheduledReminderResponse(
            id=r.id,
            workshop_name=r.workshop_name,
            sprint_name=sprint_name,
            support_person_name=r.support_person.name if r.support_person else None,
            due_at=r.due_at,
            status=r.status,
            sent_at=r.sent_at,
        ))
    return out


@org_router.post("/sprint-sheet/mark-released")
def mark_sprint_released(
    body: MarkSprintReleasedRequest,
    project_gid: str = Query(...),
    db: Session = Depends(get_db),
):
    project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    sheet = (
        db.query(SprintSheet)
        .filter(SprintSheet.project_id == project.id, SprintSheet.name == body.sprint_name)
        .first()
    )
    if not sheet:
        raise HTTPException(status_code=404, detail="Sprint sheet not found")

    release_date = datetime.fromisoformat(body.release_date) if body.release_date else datetime.utcnow()
    reminders = ReminderService(db).schedule_feedback_reminders_for_sprint(sheet.id, release_date)
    return {"success": True, "reminders_scheduled": len(reminders), "release_date": release_date.isoformat()}


@org_router.get("/clusters/{cluster_id}/tickets", response_model=list[ClusterTicketResponse])
def cluster_tickets(
    cluster_id: int,
    status: str = Query("open"),
    db: Session = Depends(get_db),
):
    svc = ClusterAnalysisService(db)
    if status == "open":
        tickets = svc.get_open_tickets(cluster_id)
    else:
        from app.models import Ticket
        tickets = db.query(Ticket).filter(Ticket.cluster_id == cluster_id).all()
    return [
        ClusterTicketResponse(
            id=t.id,
            title=t.title,
            status=t.status.value,
            workshop_name=t.workshop_name,
            assignee=t.assignee,
            asana_url=t.asana_url,
        )
        for t in tickets
    ]


@org_router.post("/clusters/{cluster_id}/analyze", response_model=ClusterAnalysisJobResponse)
def start_cluster_analysis(
    cluster_id: int,
    batch_size: int | None = Query(None),
    db: Session = Depends(get_db),
):
    svc = ClusterAnalysisService(db)
    svc.recover_stale_jobs(cluster_id)
    active = svc.get_active_job(cluster_id)
    if active:
        return _job_response(active, db, svc)

    allowed, reason = svc.can_start_analysis(cluster_id)
    if not allowed:
        raise HTTPException(status_code=409, detail=reason)

    cluster = db.query(IssueCluster).filter(IssueCluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    tickets = svc.get_cluster_tickets(cluster_id, status="all")
    open_count = svc.count_open_tickets(cluster_id)
    cap = settings.cluster_analysis_ticket_cap
    bs = batch_size or settings.cluster_analysis_batch_size
    to_analyze = tickets[:cap]

    job = ClusterAnalysisJob(
        cluster_id=cluster_id,
        status="pending",
        batch_size=bs,
        tickets_total=len(to_analyze),
        tickets_processed=0,
        ticket_cap=cap,
        open_ticket_count_snapshot=open_count,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    ticket_ids = [t.id for t in to_analyze]

    def _run():
        bg_db = SessionLocal()
        try:
            bg_svc = ClusterAnalysisService(bg_db)
            j = bg_svc.get_job(job_id)
            if j:
                bg_tickets = (
                    bg_db.query(Ticket)
                    .options(joinedload(Ticket.module))
                    .filter(Ticket.id.in_(ticket_ids))
                    .order_by(Ticket.created_at.desc())
                    .all()
                )
                bg_svc._run_job(j, bg_tickets, bs)
        except Exception as exc:
            j = bg_db.query(ClusterAnalysisJob).filter(ClusterAnalysisJob.id == job_id).first()
            if j:
                j.status = "failed"
                j.error_message = str(exc)
                j.completed_at = datetime.utcnow()
                bg_db.commit()
        finally:
            bg_db.close()

    threading.Thread(target=_run, daemon=True).start()
    return _job_response(job, db, svc)


@org_router.post("/clusters/{cluster_id}/analysis/dismiss")
def dismiss_cluster_analysis(cluster_id: int, db: Session = Depends(get_db)):
    svc = ClusterAnalysisService(db)
    job = svc.dismiss_latest_analysis(cluster_id)
    if not job:
        raise HTTPException(status_code=404, detail="No active intelligence report to dismiss")
    return {"success": True, "job_id": job.id}


@org_router.get("/cluster-analysis/{job_id}", response_model=ClusterAnalysisJobResponse)
def get_cluster_analysis_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ClusterAnalysisJob).filter(ClusterAnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(job, db, ClusterAnalysisService(db))


@org_router.get("/clusters/{cluster_id}/analysis/latest", response_model=ClusterAnalysisJobResponse)
def get_latest_cluster_analysis(cluster_id: int, db: Session = Depends(get_db)):
    svc = ClusterAnalysisService(db)
    job = svc.get_latest_completed_job(cluster_id)
    if not job:
        raise HTTPException(status_code=404, detail="No completed analysis for this cluster")
    return _job_response(job, db, svc)


def _job_response(
    job: ClusterAnalysisJob, db: Session, svc: ClusterAnalysisService | None = None
) -> ClusterAnalysisJobResponse:
    results = db.query(ClusterAnalysisResult).filter(ClusterAnalysisResult.job_id == job.id).all()
    svc = svc or ClusterAnalysisService(db)
    can_reanalyze, _ = svc.can_start_analysis(job.cluster_id)
    if job.status in ("pending", "running"):
        can_reanalyze = False
    return ClusterAnalysisJobResponse(
        id=job.id,
        cluster_id=job.cluster_id,
        status=job.status,
        batch_size=job.batch_size,
        tickets_total=job.tickets_total,
        tickets_processed=job.tickets_processed,
        open_ticket_count_snapshot=job.open_ticket_count_snapshot or 0,
        dismissed_at=job.dismissed_at,
        can_reanalyze=can_reanalyze,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        results=[ClusterAnalysisResultResponse.model_validate(r) for r in results],
    )


@org_router.get("/impact", response_model=ImpactMetricsResponse)
def get_impact_metrics(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    m = ImpactAnalyticsService(db, project_gid, date_from, date_to).get_metrics()
    return ImpactMetricsResponse(
        view_mode=m["view_mode"],
        project_name=m["project_name"],
        items_released=m["items_released"],
        points_released=m["points_released"],
        workshops_helped=m["workshops_helped"],
        support_people_helped=m["support_people_helped"],
        blockers_cleared=m["blockers_cleared"],
        avg_days_to_release=m["avg_days_to_release"],
        release_notes_sent=m["release_notes_sent"],
        last_release_note_at=m["last_release_note_at"],
        followups_sent=m["followups_sent"],
        cluster_analyses_run=m["cluster_analyses_run"],
        active_sprint_sheets=m["active_sprint_sheets"],
        sprint_sheet_rows=m["sprint_sheet_rows"],
        top_workshops=[ImpactTopWorkshop(**w) for w in m["top_workshops"]],
        recent_activity=m["recent_activity"],
    )


@org_router.get("/impact/export")
def export_impact_csv(
    project_gid: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    rows = ImpactAnalyticsService(db, project_gid, date_from, date_to).export_csv_rows()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["metric", "value"])
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="impact_report.csv"'},
    )


def _draft_to_response(d) -> WorkshopEmailDraftResponse:
    return WorkshopEmailDraftResponse(
        id=d.id,
        ticket_id=d.ticket_id,
        project_id=d.project_id,
        draft_type=d.draft_type,
        status=d.status,
        workshop_name=d.workshop_name,
        to_emails=d.to_emails or [],
        cc_emails=d.cc_emails or [],
        subject=d.subject,
        body_text=d.body_text,
        body_html=d.body_html,
        ticket_snapshot=d.ticket_snapshot or {},
        created_at=d.created_at,
        sent_at=d.sent_at,
        cancelled_at=d.cancelled_at,
    )


@org_router.get("/workshop-email-drafts/summary", response_model=WorkshopEmailDraftSummary)
def workshop_email_drafts_summary(db: Session = Depends(get_db)):
    return WorkshopEmailDraftSummary(pending_count=WorkshopEmailDraftService(db).pending_count())


@org_router.get("/workshop-email-drafts", response_model=list[WorkshopEmailDraftResponse])
def list_workshop_email_drafts(
    status: str | None = Query("pending"),
    db: Session = Depends(get_db),
):
    drafts = WorkshopEmailDraftService(db).list_drafts(status=status or None)
    return [_draft_to_response(d) for d in drafts]


@org_router.get("/workshop-email-drafts/{draft_id}", response_model=WorkshopEmailDraftResponse)
def get_workshop_email_draft(draft_id: int, db: Session = Depends(get_db)):
    draft = WorkshopEmailDraftService(db).get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return _draft_to_response(draft)


@org_router.patch("/workshop-email-drafts/{draft_id}", response_model=WorkshopEmailDraftResponse)
def update_workshop_email_draft(
    draft_id: int,
    body: UpdateWorkshopEmailDraftRequest,
    db: Session = Depends(get_db),
):
    svc = WorkshopEmailDraftService(db)
    try:
        draft = svc.update_draft(
            draft_id,
            subject=body.subject,
            body_text=body.body_text,
            body_html=body.body_html,
            to_emails=body.to_emails,
            cc_emails=body.cc_emails,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _draft_to_response(draft)


@org_router.post("/workshop-email-drafts/{draft_id}/send", response_model=WorkshopEmailDraftResponse)
def send_workshop_email_draft(draft_id: int, db: Session = Depends(get_db)):
    svc = WorkshopEmailDraftService(db)
    try:
        draft = svc.send_draft(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _draft_to_response(draft)


@org_router.post("/workshop-email-drafts/{draft_id}/cancel", response_model=WorkshopEmailDraftResponse)
def cancel_workshop_email_draft(draft_id: int, db: Session = Depends(get_db)):
    svc = WorkshopEmailDraftService(db)
    try:
        draft = svc.cancel_draft(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _draft_to_response(draft)
