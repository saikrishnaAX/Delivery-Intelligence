"""Daily execution board — operational status, today's tasks, workshop health."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.schemas import (
    ExecutionBoardResponse,
    ExecutionTask,
    ExecutiveMetrics,
    WorkshopOperationalStatus,
)
from app.services.executive_dashboard import ExecutiveDashboardService
from app.services.operational_snapshot import ESCALATION_DAYS, TESTING_STUCK_DAYS, build_operational_snapshot
from app.services.workshop_email_drafts import WorkshopEmailDraftService

AMBER_OPEN_THRESHOLD = 3


def _workshop_rag(show_stoppers: int, escalations: int, open_tickets: int) -> str:
    if show_stoppers > 0:
        return "red"
    if escalations > 0 or open_tickets >= AMBER_OPEN_THRESHOLD:
        return "amber"
    return "green"


def _global_rag(workshops: list[WorkshopOperationalStatus], show_stopper_count: int) -> str:
    if show_stopper_count > 0 or any(w.status == "red" for w in workshops):
        return "red"
    if any(w.status == "amber" for w in workshops):
        return "amber"
    return "green"


class ExecutionBoardService:
    def __init__(
        self,
        db: Session,
        project_gid: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        self.db = db
        self.project_gid = project_gid
        self.date_from = date_from
        self.date_to = date_to

    def build(self) -> ExecutionBoardResponse:
        snap = build_operational_snapshot(self.db, self.project_gid, self.date_from, self.date_to)
        metrics = ExecutiveDashboardService(
            self.db, self.project_gid, self.date_from, self.date_to, snapshot=snap
        ).get_metrics(include_ticket_lists=False)
        blockers = snap.analytics.get_blocker_analytics()
        pending_emails = WorkshopEmailDraftService(self.db).pending_count(self.project_gid)

        workshop_statuses = self._workshop_statuses(metrics, blockers, snap)
        show_stopper_count = blockers.total_blockers
        workshops_with_show_stoppers = sum(1 for w in workshop_statuses if w.show_stoppers > 0)
        workshops_at_risk = sum(1 for w in workshop_statuses if w.status == "amber")
        workshops_healthy = sum(1 for w in workshop_statuses if w.status == "green")
        non_green = [w for w in workshop_statuses if w.status != "green"]
        display_workshops = non_green[:40]
        workshops_hidden_count = max(0, len(non_green) - len(display_workshops))

        operational_status = _global_rag(workshop_statuses, show_stopper_count)
        status_headline, status_detail = self._status_copy(
            operational_status,
            show_stopper_count,
            workshops_with_show_stoppers,
            workshops_at_risk,
            metrics,
        )

        today_tasks = self._today_tasks(metrics, blockers, pending_emails)
        today_task_count = len(today_tasks)
        today_item_count = sum(t.count for t in today_tasks)

        return ExecutionBoardResponse(
            operational_status=operational_status,
            status_headline=status_headline,
            status_detail=status_detail,
            show_stopper_count=show_stopper_count,
            workshops_with_show_stoppers=workshops_with_show_stoppers,
            workshops_at_risk=workshops_at_risk,
            workshops_healthy=workshops_healthy,
            today_task_count=today_task_count,
            today_item_count=today_item_count,
            today_tasks=today_tasks,
            workshop_statuses=display_workshops,
            workshops_hidden_count=workshops_hidden_count,
            metrics=metrics,
        )

    def _workshop_statuses(self, metrics: ExecutiveMetrics, blockers, snap) -> list[WorkshopOperationalStatus]:
        if metrics.project_type == "sprint":
            return self._sprint_workshop_statuses(metrics, blockers)

        now = snap.now
        escalation_cutoff = now - timedelta(days=ESCALATION_DAYS)
        workshop_map: dict[str, dict] = {}
        for t in snap.open_list:
            name = t.workshop_name
            if not name or name.lower() == "asana project":
                continue
            if name not in workshop_map:
                workshop_map[name] = {"open": 0, "show_stoppers": 0, "escalations": 0}
            workshop_map[name]["open"] += 1
            if t.is_workflow_blocker:
                workshop_map[name]["show_stoppers"] += 1
            if t.created_at and t.created_at <= escalation_cutoff:
                workshop_map[name]["escalations"] += 1

        statuses: list[WorkshopOperationalStatus] = []
        for name, data in sorted(
            workshop_map.items(),
            key=lambda x: (
                0 if x[1]["show_stoppers"] else (1 if x[1]["escalations"] or x[1]["open"] >= AMBER_OPEN_THRESHOLD else 2),
                -(x[1]["show_stoppers"] * 10 + x[1]["escalations"] * 3 + x[1]["open"]),
            ),
        ):
            status = _workshop_rag(data["show_stoppers"], data["escalations"], data["open"])
            headline = self._workshop_headline(status, data["show_stoppers"], data["escalations"], data["open"])
            statuses.append(
                WorkshopOperationalStatus(
                    name=name,
                    status=status,
                    open_tickets=data["open"],
                    show_stoppers=data["show_stoppers"],
                    escalations=data["escalations"],
                    headline=headline,
                )
            )
        return statuses

    def _sprint_workshop_statuses(self, metrics: ExecutiveMetrics, blockers) -> list[WorkshopOperationalStatus]:
        """Sprint projects: group by pipeline concern area instead of customer workshops."""
        statuses: list[WorkshopOperationalStatus] = []

        if blockers.total_blockers:
            statuses.append(
                WorkshopOperationalStatus(
                    name="Pipeline blockers",
                    status="red",
                    open_tickets=blockers.total_blockers,
                    show_stoppers=blockers.total_blockers,
                    escalations=0,
                    headline=f"{blockers.total_blockers} show-stopper(s) in active sprint work",
                )
            )

        testing_stage = next((s for s in metrics.pipeline_stages if s.stage == "Testing"), None)
        stuck_count = metrics.testing_stuck_count
        if testing_stage and testing_stage.count and stuck_count:
            statuses.append(
                WorkshopOperationalStatus(
                    name="Testing (UAT / Pre-Prod)",
                    status="amber",
                    open_tickets=testing_stage.count,
                    show_stoppers=0,
                    escalations=stuck_count,
                    headline=f"{stuck_count} item(s) in testing {TESTING_STUCK_DAYS}+ days",
                )
            )

        if metrics.backlog_count >= 10:
            statuses.append(
                WorkshopOperationalStatus(
                    name="Sprint backlog",
                    status="amber",
                    open_tickets=metrics.backlog_count,
                    show_stoppers=0,
                    escalations=0,
                    headline=f"{metrics.backlog_count} items waiting in backlog",
                )
            )

        if not statuses:
            statuses.append(
                WorkshopOperationalStatus(
                    name="Sprint pipeline",
                    status="green",
                    open_tickets=metrics.in_pipeline_count or metrics.open_tickets,
                    show_stoppers=0,
                    escalations=0,
                    headline="No show-stoppers - pipeline is moving",
                )
            )
        return statuses

    def _workshop_headline(self, status: str, show_stoppers: int, escalations: int, open_tickets: int) -> str:
        if status == "red":
            return f"{show_stoppers} show-stopper(s) need immediate action"
        if status == "amber":
            if escalations:
                return f"{escalations} ticket(s) past {ESCALATION_DAYS}-day escalation window"
            return f"{open_tickets} open tickets - watch for escalation"
        return "No major issues"

    def _status_copy(
        self,
        status: str,
        show_stopper_count: int,
        workshops_with_show_stoppers: int,
        workshops_at_risk: int,
        metrics: ExecutiveMetrics,
    ) -> tuple[str, str]:
        if status == "red":
            headline = "Critical - show-stoppers active"
            if workshops_with_show_stoppers:
                detail = (
                    f"{show_stopper_count} show-stopper(s) across "
                    f"{workshops_with_show_stoppers} workshop(s). Resolve before end of day."
                )
            else:
                detail = f"{show_stopper_count} show-stopper(s) in this project need immediate attention."
            return headline, detail

        if status == "amber":
            headline = "Caution - escalation risk"
            detail = (
                f"{workshops_at_risk} workshop(s) approaching escalation or high open load. "
                "Prioritize before they become show-stoppers."
            )
            return headline, detail

        if metrics.project_type == "sprint":
            return (
                "All clear - sprint on track",
                f"{metrics.in_pipeline_count or metrics.open_tickets} items in pipeline with no blockers.",
            )
        return (
            "All clear - workshops stable",
            "No show-stoppers detected. Focus on today's intake and planned releases.",
        )

    def _today_tasks(self, metrics: ExecutiveMetrics, blockers, pending_emails: int) -> list[ExecutionTask]:
        tasks: list[ExecutionTask] = []

        if blockers.total_blockers:
            tasks.append(
                ExecutionTask(
                    id="show-stoppers",
                    title="Resolve workflow show-stoppers",
                    description="Tickets blocking customer workflows — highest priority",
                    count=blockers.total_blockers,
                    priority="critical",
                    route="/blockers",
                    category="blockers",
                )
            )

        if metrics.escalations_count:
            tasks.append(
                ExecutionTask(
                    id="escalations",
                    title=f"Clear escalations ({ESCALATION_DAYS}+ days open)",
                    description="Open tickets past the escalation window",
                    count=metrics.escalations_count,
                    priority="high",
                    route="/?scroll=escalations",
                    category="escalations",
                )
            )

        if pending_emails:
            tasks.append(
                ExecutionTask(
                    id="release-drafts",
                    title="Send workshop release announcements",
                    description="Pending release emails awaiting your review",
                    count=pending_emails,
                    priority="high",
                    route="/workshop-emails",
                    category="comms",
                )
            )

        if metrics.tickets_created_today:
            tasks.append(
                ExecutionTask(
                    id="triage-today",
                    title="Triage tickets created today",
                    description="New intake — assign, prioritize, or close",
                    count=metrics.tickets_created_today,
                    priority="high" if metrics.tickets_created_today >= 5 else "medium",
                    route="/?scroll=created-today",
                    category="intake",
                )
            )

        if metrics.project_type == "sprint":
            if metrics.testing_stuck_count:
                tasks.append(
                    ExecutionTask(
                        id="testing-stuck",
                        title="Unblock testing-stage items",
                        description=f"Items in UAT/Pre-Prod {TESTING_STUCK_DAYS}+ days",
                        count=metrics.testing_stuck_count,
                        priority="high",
                        route="/sprint-sheet",
                        category="sprint",
                    )
                )
            if metrics.backlog_count >= 5:
                tasks.append(
                    ExecutionTask(
                        id="sprint-backlog",
                        title="Prioritize sprint backlog",
                        description="Backlog items waiting to enter the pipeline",
                        count=metrics.backlog_count,
                        priority="medium",
                        route="/sprint-sheet",
                        category="sprint",
                    )
                )

        if metrics.tickets_closed_today == 0 and metrics.open_tickets > 0 and metrics.project_type != "sprint":
            tasks.append(
                ExecutionTask(
                    id="close-tickets",
                    title="Drive closures today",
                    description="No tickets closed yet today — pick highest-impact open items",
                    count=min(metrics.open_tickets, 10),
                    priority="medium",
                    route="/?scroll=open-tickets",
                    category="resolution",
                )
            )

        priority_order = {"critical": 0, "high": 1, "medium": 2}
        tasks.sort(key=lambda t: priority_order.get(t.priority, 9))
        return tasks
