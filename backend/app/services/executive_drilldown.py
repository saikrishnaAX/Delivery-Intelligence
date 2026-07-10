"""On-demand ticket drilldown lists for Executive Dashboard metrics."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas import ExecutiveTicketItem
from app.services.executive_dashboard import CLOSED_DRILLDOWN_LIMIT, ExecutiveDashboardService
from app.services.operational_snapshot import OperationalSnapshot, build_operational_snapshot

SUPPORT_METRICS = frozenset({
    "created_today",
    "closed_today",
    "open",
    "closed_range",
    "escalations",
    "reopened_open",
})

SPRINT_METRICS = frozenset({"backlog", "released", "pipeline", "in_pipeline"})


class ExecutiveDrilldownService:
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

    def get(
        self,
        metric: str,
        *,
        stage: str | None = None,
        limit: int = CLOSED_DRILLDOWN_LIMIT,
        offset: int = 0,
    ) -> tuple[list[ExecutiveTicketItem], int]:
        metric = metric.strip().lower()
        if metric in SUPPORT_METRICS:
            return self._support_drilldown(metric, limit, offset)
        if metric in SPRINT_METRICS or stage:
            return self._sprint_drilldown(metric, stage, limit, offset)
        raise ValueError(f"Unknown drilldown metric: {metric}")

    def _support_drilldown(
        self, metric: str, limit: int, offset: int
    ) -> tuple[list[ExecutiveTicketItem], int]:
        snap = build_operational_snapshot(self.db, self.project_gid, self.date_from, self.date_to)
        svc = ExecutiveDashboardService(
            self.db, self.project_gid, self.date_from, self.date_to, snapshot=snap
        )

        if metric == "created_today":
            items = svc._ticket_items_created_today(snap)
        elif metric == "closed_today":
            items = svc._ticket_items_closed_today(snap)
        elif metric == "open":
            items = svc._ticket_items_open(snap)
        elif metric == "closed_range":
            items = svc._ticket_items_closed_range(snap)
        elif metric == "escalations":
            items = svc._ticket_items_escalations(snap)
        elif metric == "reopened_open":
            items = svc._ticket_items_reopened_open(snap)
        else:
            items = []

        total = len(items)
        return items[offset : offset + limit], total

    def _sprint_drilldown(
        self, metric: str, stage: str | None, limit: int, offset: int
    ) -> tuple[list[ExecutiveTicketItem], int]:
        svc = ExecutiveDashboardService(self.db, self.project_gid, self.date_from, self.date_to)
        metrics = svc.get_metrics(include_ticket_lists=True)

        if metric == "backlog":
            items = metrics.backlog_tickets
        elif metric == "released":
            items = metrics.released_tickets
        elif metric == "in_pipeline":
            items = metrics.open_tickets_list
        elif metric == "pipeline" and stage:
            match = next((s for s in metrics.pipeline_stages if s.stage.lower() == stage.lower()), None)
            items = match.tickets if match else []
        else:
            items = []

        total = len(items)
        return items[offset : offset + limit], total
