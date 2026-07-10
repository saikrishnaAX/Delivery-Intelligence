"""Project-type aware executive dashboard metrics."""

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models import Ticket, TicketStatus, AsanaProject, TicketPriority
from app.schemas import (
    ExecutiveMetrics,
    ExecutiveTicketItem,
    ExecutiveWorkshopAlert,
    ExecutiveTeamPulse,
    ExecutivePipelineStage,
)
from app.services.analytics import AnalyticsService
from app.services.operational_snapshot import (
    ESCALATION_DAYS,
    OperationalSnapshot,
    TESTING_STUCK_DAYS,
    build_operational_snapshot,
)
from app.services.section_utils import (
    is_backlog_section,
    is_released_section,
    is_sprint_pipeline_section,
    normalize_section_name,
    pipeline_section_order,
)

# Cap drilldown payload size; card count still reflects full total_closed.
CLOSED_DRILLDOWN_LIMIT = 200

SPRINT_STAGE_GROUPS: list[tuple[str, list[str]]] = [
    ("Prioritized", ["Prioritized"]),
    ("Design / Spec", ["Design/Spec- in progress", "Design/Spec - in progress"]),
    ("Development", ["Developing", "PR Raised"]),
    (
        "Testing",
        [
            "Build in UAT",
            "Testing (UAT)",
            "Testing(UAT)",
            "Build in Pre Prod",
            "Build in Pre-Prod",
            "Testing(Pre-Prod)",
            "Testing (Pre-Prod)",
        ],
    ),
    ("Done", ["Done"]),
]

_GROUP_NORMS: dict[str, str] = {}
for label, sections in SPRINT_STAGE_GROUPS:
    for s in sections:
        _GROUP_NORMS[normalize_section_name(s)] = label


def detect_project_type(project_name: str | None) -> str:
    n = (project_name or "").lower()
    if "sprint" in n:
        return "sprint"
    if "bosch" in n:
        return "bosch"
    return "support"


class ExecutiveDashboardService:
    def __init__(
        self,
        db: Session,
        project_gid: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        snapshot: OperationalSnapshot | None = None,
    ):
        self.db = db
        self.snapshot = snapshot
        self.analytics = snapshot.analytics if snapshot else AnalyticsService(
            db, project_gid=project_gid, date_from=date_from, date_to=date_to
        )
        self.project: AsanaProject | None = None
        if project_gid:
            self.project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()

    def get_metrics(self, *, include_ticket_lists: bool = False) -> ExecutiveMetrics:
        ptype = detect_project_type(self.project.name if self.project else None)
        if ptype == "sprint":
            return self._sprint_metrics(ptype, include_ticket_lists=include_ticket_lists)
        return self._support_metrics(project_type=ptype, include_ticket_lists=include_ticket_lists)

    def _ticket_item(self, t: Ticket, days: int, detail: str | None = None) -> ExecutiveTicketItem:
        return ExecutiveTicketItem(
            id=t.id,
            title=t.title,
            workshop_name=t.workshop_name,
            assignee=t.assignee,
            ticket_owner=t.ticket_owner,
            created_by=t.reporter or t.ticket_owner or None,
            created_at=t.created_at,
            days_open=days,
            priority=t.priority.value if t.priority else "medium",
            detail=detail or (t.module.name if t.module else None),
            asana_url=t.asana_url,
            module_name=t.module.name if t.module else None,
            jira_key=t.jira_key,
        )

    def _fmt_closed(self, t: Ticket) -> str:
        h = t.resolution_hours
        if not h:
            return "closed today"
        return f"closed in {h:.0f}h" if h < 24 else f"closed in {h / 24:.1f}d"

    def _quality_fields(
        self,
        now: datetime,
        open_list: list[Ticket],
        escalations: list[Ticket],
        *,
        include_ticket_lists: bool,
    ) -> dict:
        summary = self.analytics.get_resolution_summary()
        reopened_open = [t for t in open_list if t.is_reopened]
        critical_open = sum(
            1
            for t in open_list
            if t.is_critical_blocker or (t.priority == TicketPriority.CRITICAL)
        )
        return {
            "avg_resolution_hours": summary["avg_resolution_hours"],
            "sla_compliance_rate": summary["sla_compliance_rate"],
            "reopened_tickets": summary["reopened_count"],
            "critical_open_issues": critical_open,
            "overdue_count": len(escalations),
            "reopened_tickets_list": [
                self._ticket_item(t, (now - t.created_at).days if t.created_at else 0, "reopened")
                for t in reopened_open
            ]
            if include_ticket_lists
            else [],
        }

    def _ticket_items_created_today(self, snap: OperationalSnapshot) -> list[ExecutiveTicketItem]:
        return [self._ticket_item(t, 0, "created today") for t in snap.created_today]

    def _ticket_items_closed_today(self, snap: OperationalSnapshot) -> list[ExecutiveTicketItem]:
        return [self._ticket_item(t, 0, self._fmt_closed(t)) for t in snap.closed_today]

    def _ticket_items_open(self, snap: OperationalSnapshot) -> list[ExecutiveTicketItem]:
        return [
            self._ticket_item(t, (snap.now - t.created_at).days if t.created_at else 0)
            for t in snap.open_list
        ]

    def _ticket_items_closed_range(self, snap: OperationalSnapshot) -> list[ExecutiveTicketItem]:
        return [self._ticket_item(t, 0, self._fmt_closed(t)) for t in snap.closed_range_list]

    def _ticket_items_escalations(self, snap: OperationalSnapshot) -> list[ExecutiveTicketItem]:
        return [
            self._ticket_item(
                t,
                (snap.now - t.created_at).days if t.created_at else 0,
                f"{ESCALATION_DAYS}+ days open",
            )
            for t in snap.escalations
        ]

    def _ticket_items_reopened_open(self, snap: OperationalSnapshot) -> list[ExecutiveTicketItem]:
        return [
            self._ticket_item(t, (snap.now - t.created_at).days if t.created_at else 0, "reopened")
            for t in snap.open_list
            if t.is_reopened
        ]

    def _resolve_snapshot(self) -> OperationalSnapshot:
        if self.snapshot:
            return self.snapshot
        return build_operational_snapshot(
            self.db,
            self.project.gid if self.project else None,
            self.analytics.date_from.isoformat() if self.analytics.date_from else None,
            self.analytics.date_to.isoformat() if self.analytics.date_to else None,
        )

    def _support_metrics(
        self,
        project_type: str,
        *,
        include_ticket_lists: bool,
    ) -> ExecutiveMetrics:
        snap = self._resolve_snapshot()
        now = snap.now
        open_list = snap.open_list
        quality = self._quality_fields(now, open_list, snap.escalations, include_ticket_lists=include_ticket_lists)

        workshop_map: dict[str, dict] = {}
        for t in open_list:
            name = t.workshop_name
            if not name or name.lower() == "asana project":
                continue
            if name not in workshop_map:
                workshop_map[name] = {"open": 0, "blockers": 0}
            workshop_map[name]["open"] += 1
            if t.is_workflow_blocker:
                workshop_map[name]["blockers"] += 1

        desc = {
            "support": "Support queue — intake, resolution, and escalations",
            "bosch": "Bosch partner queue — external bugs and enhancements",
        }.get(project_type, "Support queue")

        empty: list[ExecutiveTicketItem] = []
        closed_range_items = (
            self._ticket_items_closed_range(snap)[:CLOSED_DRILLDOWN_LIMIT]
            if include_ticket_lists
            else empty
        )

        return ExecutiveMetrics(
            project_type=project_type,
            project_name=self.project.name if self.project else None,
            dashboard_description=desc,
            tickets_created_today=len(snap.created_today),
            tickets_closed_today=len(snap.closed_today),
            open_tickets=len(open_list),
            total_closed=len(snap.closed_range_list),
            escalations_count=len(snap.escalations),
            avg_resolution_hours=quality["avg_resolution_hours"],
            critical_open_issues=quality["critical_open_issues"],
            sla_compliance_rate=quality["sla_compliance_rate"],
            reopened_tickets=quality["reopened_tickets"],
            overdue_count=quality["overdue_count"],
            created_today_tickets=self._ticket_items_created_today(snap) if include_ticket_lists else empty,
            closed_today_tickets=self._ticket_items_closed_today(snap) if include_ticket_lists else empty,
            open_tickets_list=self._ticket_items_open(snap) if include_ticket_lists else empty,
            total_closed_tickets=closed_range_items,
            escalation_tickets=self._ticket_items_escalations(snap) if include_ticket_lists else empty,
            reopened_tickets_list=quality["reopened_tickets_list"],
            workshop_alerts=[
                ExecutiveWorkshopAlert(name=n, open_tickets=v["open"], blockers=v["blockers"])
                for n, v in sorted(
                    workshop_map.items(),
                    key=lambda x: x[1]["open"] + x[1]["blockers"] * 3,
                    reverse=True,
                )[:5]
            ],
            team_pulse=ExecutiveTeamPulse(),
            workflow_hotspots=[],
        )

    def _section_name(self, t: Ticket) -> str | None:
        return t.module.name if t.module else None

    def _sprint_metrics(
        self,
        project_type: str,
        *,
        include_ticket_lists: bool,
    ) -> ExecutiveMetrics:
        now = datetime.utcnow()
        base = self.analytics._tickets_operational().options(joinedload(Ticket.module)).filter(
            Ticket.status != TicketStatus.CLOSED
        )
        all_active = base.all()

        backlog: list[Ticket] = []
        released: list[Ticket] = []
        pipeline: list[Ticket] = []

        for t in all_active:
            section = self._section_name(t)
            if is_backlog_section(section):
                backlog.append(t)
            elif is_released_section(section):
                released.append(t)
            elif is_sprint_pipeline_section(section):
                pipeline.append(t)

        stage_buckets: dict[str, list[Ticket]] = {label: [] for label, _ in SPRINT_STAGE_GROUPS}
        for t in pipeline:
            section = self._section_name(t) or ""
            group = _GROUP_NORMS.get(normalize_section_name(section))
            if group:
                stage_buckets[group].append(t)

        testing_tickets = stage_buckets.get("Testing", [])
        testing_stuck_count = sum(
            1
            for t in testing_tickets
            if t.created_at and (now - t.created_at).days >= TESTING_STUCK_DAYS
        )

        pipeline_stages: list[ExecutivePipelineStage] = []
        empty: list[ExecutiveTicketItem] = []
        for label, _ in SPRINT_STAGE_GROUPS:
            tickets = sorted(
                stage_buckets[label],
                key=lambda t: pipeline_section_order(self._section_name(t)),
            )
            pipeline_stages.append(
                ExecutivePipelineStage(
                    stage=label,
                    count=len(tickets),
                    tickets=[
                        self._ticket_item(
                            t, (now - t.created_at).days if t.created_at else 0, self._section_name(t)
                        )
                        for t in tickets
                    ]
                    if include_ticket_lists
                    else empty,
                )
            )

        open_list = pipeline + backlog
        quality = self._quality_fields(now, open_list, [], include_ticket_lists=include_ticket_lists)

        return ExecutiveMetrics(
            project_type=project_type,
            project_name=self.project.name if self.project else None,
            dashboard_description="Sprint pipeline — where work sits on the board",
            tickets_created_today=0,
            tickets_closed_today=0,
            open_tickets=len(pipeline),
            total_closed=0,
            escalations_count=0,
            backlog_count=len(backlog),
            released_count=len(released),
            in_pipeline_count=len(pipeline),
            testing_stuck_count=testing_stuck_count,
            avg_resolution_hours=quality["avg_resolution_hours"],
            critical_open_issues=quality["critical_open_issues"],
            sla_compliance_rate=quality["sla_compliance_rate"],
            reopened_tickets=quality["reopened_tickets"],
            overdue_count=0,
            open_tickets_list=[
                self._ticket_item(t, (now - t.created_at).days if t.created_at else 0, self._section_name(t))
                for t in pipeline
            ]
            if include_ticket_lists
            else empty,
            backlog_tickets=[
                self._ticket_item(t, (now - t.created_at).days if t.created_at else 0, "Backlog")
                for t in backlog
            ]
            if include_ticket_lists
            else empty,
            released_tickets=[self._ticket_item(t, 0, "Released") for t in released]
            if include_ticket_lists
            else empty,
            pipeline_stages=pipeline_stages,
            workshop_alerts=[],
            team_pulse=ExecutiveTeamPulse(),
            workflow_hotspots=[],
        )
