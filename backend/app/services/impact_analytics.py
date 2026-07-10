"""Productivity / impact metrics for delivery leadership reporting."""

from datetime import datetime

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Ticket, TicketStatus, SprintSheet, SprintSheetRow,
    ReleaseNoteSend, ScheduledReminder, ClusterAnalysisJob,
    ActivityLog, AsanaProject,
)
from app.config import get_settings

settings = get_settings()


def _is_sprint_project(project: AsanaProject | None) -> bool:
    if not project:
        return False
    return "sprint" in (project.name or "").lower()


def _valid_workshop_name(name: str | None, title: str | None = None) -> bool:
    """Filter out title fragments misparsed as workshop names."""
    if not name or len(name.strip()) < 3:
        return False
    n = name.strip()
    low = n.lower()
    if low in ("asana project", "n/a", "-", "—"):
        return False
    if title and low == (title or "").strip().lower():
        return False
    if len(n) > 48:
        return False
    if n.count(" ") > 6:
        return False
    return True


class ImpactAnalyticsService:
    def __init__(
        self,
        db: Session,
        project_gid: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        self.db = db
        self.project: AsanaProject | None = None
        if project_gid:
            self.project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
        self.project_id = self.project.id if self.project else None
        self.sprint_mode = _is_sprint_project(self.project)
        self.date_from = self._parse_date(date_from) if date_from else None
        self.date_to = self._parse_date(date_to, end_of_day=True) if date_to else None

    def _parse_date(self, s: str, end_of_day: bool = False) -> datetime:
        dt = datetime.fromisoformat(s.replace("Z", ""))
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt

    def _ticket_q(self):
        q = self.db.query(Ticket)
        if self.project_id:
            q = q.filter(Ticket.project_id == self.project_id)
        return q

    def _delivered_tickets(self) -> list[Ticket]:
        """Sprint project: released. Support/ticket projects: closed (≈ released)."""
        q = (
            self._ticket_q()
            .options(joinedload(Ticket.jira_issue))
        )
        if self.sprint_mode:
            q = q.filter(Ticket.released_at.isnot(None))
            if self.date_from:
                q = q.filter(Ticket.released_at >= self.date_from)
            if self.date_to:
                q = q.filter(Ticket.released_at <= self.date_to)
        else:
            q = q.filter(Ticket.status == TicketStatus.CLOSED)
            if self.date_from or self.date_to:
                date_filters = []
                if self.date_from and self.date_to:
                    date_filters.append(
                        and_(Ticket.closed_at.isnot(None), Ticket.closed_at >= self.date_from, Ticket.closed_at <= self.date_to)
                    )
                    date_filters.append(
                        and_(Ticket.closed_at.is_(None), Ticket.released_at.isnot(None),
                             Ticket.released_at >= self.date_from, Ticket.released_at <= self.date_to)
                    )
                elif self.date_from:
                    date_filters.append(and_(Ticket.closed_at.isnot(None), Ticket.closed_at >= self.date_from))
                    date_filters.append(and_(Ticket.closed_at.is_(None), Ticket.released_at >= self.date_from))
                elif self.date_to:
                    date_filters.append(and_(Ticket.closed_at.isnot(None), Ticket.closed_at <= self.date_to))
                    date_filters.append(and_(Ticket.closed_at.is_(None), Ticket.released_at <= self.date_to))
                q = q.filter(or_(*date_filters))
        return q.all()

    def _completion_timestamp(self, ticket: Ticket) -> datetime | None:
        if self.sprint_mode:
            return ticket.released_at
        return ticket.closed_at or ticket.released_at

    def get_metrics(self) -> dict:
        delivered = self._delivered_tickets()
        view_mode = "sprint" if self.sprint_mode else "workshops"

        points_released = 0.0
        for t in delivered:
            if t.jira_issue and t.jira_issue.story_points:
                points_released += float(t.jira_issue.story_points)

        workshops_helped = len({
            t.workshop_name for t in delivered
            if _valid_workshop_name(t.workshop_name, t.title)
        })
        support_helped = len({
            t.assignee for t in delivered if t.assignee
        })
        blockers_cleared = len([t for t in delivered if t.is_workflow_blocker])

        avg_days = None
        durations = []
        for t in delivered:
            done_at = self._completion_timestamp(t)
            if done_at and t.created_at:
                durations.append((done_at - t.created_at).total_seconds() / 3600)
        if durations:
            avg_days = round(sum(durations) / len(durations) / 24, 1)

        rn_q = self.db.query(ReleaseNoteSend)
        if self.project_id:
            rn_q = rn_q.filter(ReleaseNoteSend.project_id == self.project_id)
        if self.date_from:
            rn_q = rn_q.filter(ReleaseNoteSend.sent_at >= self.date_from)
        if self.date_to:
            rn_q = rn_q.filter(ReleaseNoteSend.sent_at <= self.date_to)
        release_notes_sent = rn_q.count()
        last_release_note = rn_q.order_by(ReleaseNoteSend.sent_at.desc()).first()

        reminders_q = self.db.query(ScheduledReminder).filter(ScheduledReminder.status == "sent")
        if self.date_from:
            reminders_q = reminders_q.filter(ScheduledReminder.sent_at >= self.date_from)
        if self.date_to:
            reminders_q = reminders_q.filter(ScheduledReminder.sent_at <= self.date_to)
        followups_sent = reminders_q.count()

        analyses_q = self.db.query(ClusterAnalysisJob).filter(ClusterAnalysisJob.status == "completed")
        if self.date_from:
            analyses_q = analyses_q.filter(ClusterAnalysisJob.completed_at >= self.date_from)
        if self.date_to:
            analyses_q = analyses_q.filter(ClusterAnalysisJob.completed_at <= self.date_to)
        cluster_analyses = analyses_q.count()

        sheets_q = self.db.query(SprintSheet).filter(SprintSheet.is_active == True)  # noqa: E712
        if self.project_id:
            sheets_q = sheets_q.filter(SprintSheet.project_id == self.project_id)
        active_sheets = sheets_q.count()
        sheet_rows = (
            self.db.query(func.count(SprintSheetRow.id))
            .join(SprintSheet)
            .filter(SprintSheet.is_active == True)  # noqa: E712
        )
        if self.project_id:
            sheet_rows = sheet_rows.filter(SprintSheet.project_id == self.project_id)
        total_sheet_rows = sheet_rows.scalar() or 0

        activity_q = self.db.query(ActivityLog)
        if self.date_from:
            activity_q = activity_q.filter(ActivityLog.created_at >= self.date_from)
        if self.date_to:
            activity_q = activity_q.filter(ActivityLog.created_at <= self.date_to)
        recent_activity = activity_q.order_by(ActivityLog.created_at.desc()).limit(10).all()

        top_workshops: dict[str, int] = {}
        if not self.sprint_mode:
            for t in delivered:
                if _valid_workshop_name(t.workshop_name, t.title):
                    name = t.workshop_name.strip()
                    top_workshops[name] = top_workshops.get(name, 0) + 1
        top_workshops_list = sorted(
            [{"name": k, "count": v} for k, v in top_workshops.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:8]

        return {
            "view_mode": view_mode,
            "project_name": self.project.name if self.project else None,
            "items_released": len(delivered),
            "points_released": round(points_released, 1) if points_released else 0,
            "workshops_helped": workshops_helped,
            "support_people_helped": support_helped,
            "blockers_cleared": blockers_cleared,
            "avg_days_to_release": avg_days,
            "release_notes_sent": release_notes_sent,
            "last_release_note_at": last_release_note.sent_at.isoformat() if last_release_note else None,
            "followups_sent": followups_sent,
            "cluster_analyses_run": cluster_analyses,
            "active_sprint_sheets": active_sheets,
            "sprint_sheet_rows": total_sheet_rows,
            "top_workshops": top_workshops_list,
            "recent_activity": [
                {
                    "id": a.id,
                    "module": a.module,
                    "action": a.action,
                    "summary": a.summary,
                    "created_at": a.created_at.isoformat(),
                }
                for a in recent_activity
            ],
        }

    def export_csv_rows(self) -> list[dict]:
        m = self.get_metrics()
        rows = [
            {"metric": "Items released" if m["view_mode"] == "sprint" else "Items closed", "value": m["items_released"]},
        ]
        if m["view_mode"] == "sprint":
            rows.append({"metric": "Story points released", "value": m["points_released"]})
        else:
            rows.append({"metric": "Workshops helped", "value": m["workshops_helped"]})
        rows.extend([
            {"metric": "Support people helped", "value": m["support_people_helped"]},
            {"metric": "Blockers cleared", "value": m["blockers_cleared"]},
            {"metric": "Avg days to complete", "value": m["avg_days_to_release"] or ""},
            {"metric": "Release notes sent", "value": m["release_notes_sent"]},
            {"metric": "Follow-up emails sent", "value": m["followups_sent"]},
            {"metric": "Cluster analyses run", "value": m["cluster_analyses_run"]},
        ])
        return rows
