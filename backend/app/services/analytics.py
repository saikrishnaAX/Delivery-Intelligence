from datetime import datetime, timedelta

from dateutil import parser as date_parser

from sqlalchemy import func

from sqlalchemy.orm import Session, joinedload



from app.models import (
    Ticket, Module, Customer, IssueCluster, JiraIssue, AsanaProject,
    TicketStatus, TicketPriority, TicketCategory,
    ClusterAnalysisJob, ClusterAnalysisResult,
)

from app.schemas import (

    ExecutiveMetrics, ExecutiveTicketItem, ExecutiveWorkshopAlert,
    ExecutiveTeamPulse, ExecutiveWorkflowHotspot,
    TicketResponse, CategoryBreakdown,

    ClassificationAnalytics, ClusterResponse, ClusteringAnalytics,

    ModuleHeatMapItem, HeatMapAnalytics, ClassificationMismatch,

    SupportAccuracyAnalytics, BlockerResponse, BlockerAnalytics,

    CustomerPainItem, CustomerPainAnalytics, JiraIssueResponse,
    WorkshopTicketSummary,

    JiraAnalytics, ResolutionAnalytics, MonthlyProgressAnalytics, MonthlyProgressMonth,
    SupportTeamMember, SupportTeamAnalytics,

)





from app.config import get_settings
from app.services.jira_linking import is_open_jira_status
from app.services.ticket_parser import WORKFLOW_KEYWORDS


def _support_person(db: Session, workshop_name: str):
    from app.services.org_service import OrgService
    return OrgService(db).get_support_for_workshop(workshop_name)


def _support_name(db: Session, workshop_name: str) -> str | None:
    p = _support_person(db, workshop_name)
    return p.name if p else None


def _support_email(db: Session, workshop_name: str) -> str | None:
    p = _support_person(db, workshop_name)
    return p.email if p else None


def _parse_date(value: str | None) -> datetime | None:

    if not value:

        return None

    try:

        return date_parser.parse(value).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)

    except (ValueError, TypeError):

        return None





def _ticket_to_response(t: Ticket) -> TicketResponse:

    workshop = t.workshop_name or (t.customer.name if t.customer else None)

    return TicketResponse(

        id=t.id,

        asana_gid=t.asana_gid,

        title=t.title,

        description=t.description,

        status=t.status,

        support_category=t.support_category,

        ai_category=t.ai_category,

        priority=t.priority,

        module_name=t.module.name if t.module else None,

        customer_name=workshop,

        workshop_name=t.workshop_name,

        assignee=t.assignee,

        reporter=t.reporter,

        ticket_owner=t.ticket_owner,

        is_critical_blocker=t.is_workflow_blocker or t.is_critical_blocker,

        is_reopened=t.is_reopened,

        sla_met=t.sla_met,

        resolution_hours=t.resolution_hours,

        cluster_name=t.cluster.name if t.cluster else None,

        jira_key=t.jira_key,

        asana_type_raw=t.asana_type_raw,

        asana_url=t.asana_url,

        tags=t.tags or [],

        created_at=t.created_at,

        closed_at=t.closed_at,

    )





class AnalyticsService:

    def __init__(

        self,

        db: Session,

        project_gid: str | None = None,

        date_from: str | datetime | None = None,

        date_to: str | datetime | None = None,

    ):

        self.db = db

        self.project_gid = project_gid
        self.project_id: int | None = None

        if project_gid:

            project = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()

            if project:

                self.project_id = project.id



        if isinstance(date_from, str):

            date_from = _parse_date(date_from)

        if isinstance(date_to, str):

            parsed = _parse_date(date_to)

            if parsed:

                date_to = parsed.replace(hour=23, minute=59, second=59)

        self.date_from = date_from

        self.date_to = date_to



    def _tickets(self, use_closed_date: bool = False):

        q = self.db.query(Ticket)

        if self.project_id:

            q = q.filter(Ticket.project_id == self.project_id)

        if self.date_from:

            if use_closed_date:

                q = q.filter(Ticket.closed_at >= self.date_from)

            else:

                q = q.filter(Ticket.created_at >= self.date_from)

        if self.date_to:

            if use_closed_date:

                q = q.filter(Ticket.closed_at <= self.date_to)

            else:

                q = q.filter(Ticket.created_at <= self.date_to)

        return q



    def _tickets_operational(self):
        """Active operational tickets (blockers, open queue) — ignores date range."""
        q = self.db.query(Ticket)
        if self.project_id:
            q = q.filter(Ticket.project_id == self.project_id)
        return q



    def _jira_issues(self):

        cfg = get_settings()
        q = self.db.query(JiraIssue)

        if self.project_id:

            q = q.filter(JiraIssue.project_id == self.project_id)

        elif cfg.jira_project_key:

            q = q.filter(JiraIssue.project_key == cfg.jira_project_key)

        return q



    def _modules(self):

        q = self.db.query(Module)

        if self.project_id:

            q = q.filter(Module.project_id == self.project_id)

        return q



    def get_executive_metrics(self) -> ExecutiveMetrics:
        from app.services.executive_dashboard import ExecutiveDashboardService
        return ExecutiveDashboardService(
            self.db,
            project_gid=self.project_gid,
            date_from=self.date_from.isoformat() if self.date_from else None,
            date_to=self.date_to.isoformat() if self.date_to else None,
        ).get_metrics()



    def get_tickets(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        ticket_type: str | None = None,
    ) -> tuple[list[TicketResponse], int]:

        from app.services.ticket_type import canonical_type_filter

        q = self._tickets().options(

            joinedload(Ticket.module), joinedload(Ticket.customer), joinedload(Ticket.cluster)

        )

        if status:

            if status == "open":

                q = q.filter(Ticket.status.in_([

                    TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED,

                ]))

            elif status == "closed":

                q = q.filter(Ticket.status == TicketStatus.CLOSED)

            else:

                q = q.filter(Ticket.status == status)

        if ticket_type:

            q = canonical_type_filter(q, ticket_type)

        total = q.count()

        tickets = q.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return [_ticket_to_response(t) for t in tickets], total



    def get_classification_analytics(self) -> ClassificationAnalytics:

        from app.services.ticket_type import CANONICAL_TICKET_TYPES, canonical_type_filter

        total = self._tickets().count()

        support: list[CategoryBreakdown] = []

        for typ in CANONICAL_TICKET_TYPES:

            q = canonical_type_filter(self._tickets(), typ)

            count = q.count()

            open_count = q.filter(Ticket.status.in_([

                TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED,

            ])).count()

            trend = []

            now = datetime.utcnow()

            for i in range(6, -1, -1):

                day = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)

                day_end = day + timedelta(days=1)

                trend.append({

                    "date": day.strftime("%Y-%m-%d"),

                    "count": canonical_type_filter(self._tickets(), typ).filter(

                        Ticket.created_at >= day, Ticket.created_at < day_end

                    ).count(),

                })

            support.append(CategoryBreakdown(

                category=typ,

                count=count,

                open_count=open_count,

                percentage=round(count / total * 100, 1) if total else 0,

                trend=trend,

            ))

        support.sort(key=lambda x: x.count, reverse=True)

        return ClassificationAnalytics(

            support_breakdown=support,

            ai_breakdown=[],

            total_tickets=total,

            most_common_category=support[0].category if support else "unknown",

        )



    def get_clustering_analytics(self) -> ClusteringAnalytics:

        cq = self.db.query(IssueCluster).options(joinedload(IssueCluster.module))

        if self.project_id:

            cq = cq.filter(IssueCluster.project_id == self.project_id)

        clusters = cq.all()

        cluster_responses = []

        for c in clusters:

            sample_q = self._tickets().filter(Ticket.cluster_id == c.id)

            sample = [s[0] for s in sample_q.with_entities(Ticket.title).limit(3).all()]

            open_ticket_count = (
                self.db.query(Ticket)
                .filter(
                    Ticket.cluster_id == c.id,
                    Ticket.status.in_([
                        TicketStatus.OPEN,
                        TicketStatus.IN_PROGRESS,
                        TicketStatus.BLOCKED,
                    ]),
                )
                .count()
            )

            latest_job = (
                self.db.query(ClusterAnalysisJob)
                .filter(
                    ClusterAnalysisJob.cluster_id == c.id,
                    ClusterAnalysisJob.status == "completed",
                    ClusterAnalysisJob.dismissed_at.is_(None),
                )
                .order_by(ClusterAnalysisJob.completed_at.desc())
                .first()
            )

            defect_count = None
            can_reanalyze = True
            if latest_job:
                defect_count = (
                    self.db.query(ClusterAnalysisResult)
                    .filter(ClusterAnalysisResult.job_id == latest_job.id)
                    .count()
                )
                snapshot = latest_job.open_ticket_count_snapshot or 0
                can_reanalyze = open_ticket_count > snapshot

            active_job = (
                self.db.query(ClusterAnalysisJob)
                .filter(
                    ClusterAnalysisJob.cluster_id == c.id,
                    ClusterAnalysisJob.status.in_(["pending", "running"]),
                )
                .order_by(ClusterAnalysisJob.created_at.desc())
                .first()
            )
            if active_job:
                can_reanalyze = False

            cluster_responses.append(ClusterResponse(

                id=c.id, name=c.name, description=c.description, ai_summary=c.ai_summary,

                ticket_count=c.ticket_count, open_ticket_count=open_ticket_count, severity=c.severity,

                module_name=c.module.name if c.module else None, sample_tickets=sample,

                analysis_job_id=latest_job.id if latest_job else None,
                analysis_defect_count=defect_count,
                analysis_dismissed=False,
                analysis_open_snapshot=latest_job.open_ticket_count_snapshot if latest_job else None,
                can_reanalyze=can_reanalyze,
                active_analysis_job_id=active_job.id if active_job else None,
                analysis_in_progress=active_job is not None,

            ))

        unclustered = self._tickets().filter(Ticket.cluster_id.is_(None)).count()

        return ClusteringAnalytics(

            clusters=sorted(cluster_responses, key=lambda x: x.ticket_count, reverse=True),

            total_clusters=len(clusters),

            unclustered_tickets=unclustered,

        )



    def get_heatmap_analytics(self) -> HeatMapAnalytics:

        modules = self._modules().all()

        items, max_count = [], 1

        for m in modules:

            mq = self._tickets().filter(Ticket.module_id == m.id)

            total = mq.count()

            open_c = mq.filter(Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])).count()

            critical = mq.filter(

                Ticket.is_workflow_blocker == True, Ticket.status != TicketStatus.CLOSED

            ).count()

            avg_res = mq.filter(Ticket.resolution_hours.isnot(None)).with_entities(

                func.avg(Ticket.resolution_hours)

            ).scalar() or 0.0

            max_count = max(max_count, total)

            items.append(ModuleHeatMapItem(

                module=m.name, product_area=m.product_area or "General",

                ticket_count=total, open_count=open_c, critical_count=critical,

                avg_resolution_hours=round(avg_res, 1), intensity=0,

            ))

        for item in items:

            item.intensity = round(item.ticket_count / max_count, 2)

        items.sort(key=lambda x: x.ticket_count, reverse=True)

        return HeatMapAnalytics(

            modules=items,

            hottest_module=items[0].module if items else "N/A",

            total_modules=len(modules),

        )



    def get_support_accuracy(self) -> SupportAccuracyAnalytics:

        return SupportAccuracyAnalytics(

            accuracy_rate=0, total_compared=0, matches=0,

            mismatches=[], category_accuracy=[],

        )



    def get_blocker_analytics(self) -> BlockerAnalytics:

        blockers = self._tickets_operational().options(

            joinedload(Ticket.module), joinedload(Ticket.customer)

        ).filter(

            Ticket.is_workflow_blocker == True,

            Ticket.status != TicketStatus.CLOSED,

        ).order_by(Ticket.created_at).all()



        now = datetime.utcnow()

        blocker_responses, total_days, workshops = [], 0, set()

        for b in blockers:

            days_open = (now - b.created_at).days

            total_days += days_open

            wname = b.workshop_name or (b.customer.name if b.customer else None)

            if wname:

                workshops.add(wname)

            impact = f"Open {days_open}d"

            if b.ticket_owner:

                impact += f" · Owner: {b.ticket_owner}"

            if b.assignee:

                impact += f" · With: {b.assignee}"

            blocker_responses.append(BlockerResponse(

                id=b.id, title=b.title, priority=b.priority.value,

                module_name=b.module.name if b.module else None,

                customer_name=wname,

                days_open=days_open, assignee=b.assignee or b.ticket_owner,

                impact_summary=impact,

                asana_url=b.asana_url,

            ))

        return BlockerAnalytics(

            blockers=blocker_responses, total_blockers=len(blockers),

            avg_days_blocked=round(total_days / len(blockers), 1) if blockers else 0,

            affected_customers=len(workshops),

        )



    def get_customer_pain(self) -> CustomerPainAnalytics:

        tickets = self._tickets().all()

        workshop_map: dict[str, list[Ticket]] = {}

        for t in tickets:

            name = t.workshop_name or (t.customer.name if t.customer else None)

            if not name or name.lower() == "asana project":

                continue

            workshop_map.setdefault(name, []).append(t)



        items = []

        for name, w_tickets in workshop_map.items():

            open_t = sum(1 for t in w_tickets if t.status != TicketStatus.CLOSED)

            critical = sum(

                1 for t in w_tickets

                if t.is_workflow_blocker and t.status != TicketStatus.CLOSED

            )

            titles: dict[str, int] = {}

            for t in w_tickets:

                key = (t.title or "")[:40]

                titles[key] = titles.get(key, 0) + 1

            recurring = sorted(titles.items(), key=lambda x: x[1], reverse=True)[:3]

            pain_score = len(w_tickets) * 1.0 + open_t * 2.0 + critical * 5.0

            open_w_tickets = [t for t in w_tickets if t.status != TicketStatus.CLOSED]
            priority_order = {
                TicketPriority.CRITICAL: 0,
                TicketPriority.HIGH: 1,
                TicketPriority.MEDIUM: 2,
                TicketPriority.LOW: 3,
            }
            ticket_summaries = [
                WorkshopTicketSummary(
                    id=t.id,
                    title=t.title,
                    status=t.status.value,
                    is_open=True,
                )
                for t in sorted(
                    open_w_tickets,
                    key=lambda x: (
                        not x.is_workflow_blocker,
                        priority_order.get(x.priority, 9),
                        -(x.created_at or datetime.min).timestamp(),
                    ),
                )
            ]

            items.append(CustomerPainItem(
                customer_id=hash(name) % 100000,
                customer_name=name,
                tier="workshop",
                ticket_count=len(w_tickets),
                open_tickets=open_t,
                critical_tickets=critical,
                recurring_issues=[f"{m} ({n})" for m, n in recurring if n > 1],
                pain_score=round(pain_score, 1),
                tickets=ticket_summaries,
                support_person_name=_support_name(self.db, name),
                support_person_email=_support_email(self.db, name),
            ))

        items.sort(key=lambda x: x.pain_score, reverse=True)

        return CustomerPainAnalytics(

            customers=items,

            top_pain_customer=items[0].customer_name if items else "N/A",

            total_customers=len(items),

        )



    def _support_display_map(self) -> dict[str, str]:
        """Map ticket identity strings (email or name) → display name for support team."""
        from app.models import Person, Team, TeamMembership

        display: dict[str, str] = {}
        support_teams = (
            self.db.query(Team)
            .filter(Team.name.ilike("%support%"))
            .all()
        )
        team_ids = [t.id for t in support_teams]
        if team_ids:
            rows = (
                self.db.query(Person)
                .join(TeamMembership, TeamMembership.person_id == Person.id)
                .filter(TeamMembership.team_id.in_(team_ids), Person.is_active == True)  # noqa: E712
                .all()
            )
        else:
            rows = self.db.query(Person).filter(Person.is_active == True).all()  # noqa: E712

        for person in rows:
            if not person.email:
                continue
            email = person.email.strip().lower()
            name = person.name.strip()
            display[email] = name
            display[name.lower()] = name
            display[email.split("@")[0].lower()] = name
        return display

    def _resolve_support_name(self, raw: str | None, display_map: dict[str, str]) -> str | None:
        if not raw or not str(raw).strip():
            return None
        key = str(raw).strip()
        low = key.lower()
        if low in display_map:
            return display_map[low]
        if "@" in low and low in display_map:
            return display_map[low]
        if "@" in low:
            local = low.split("@")[0]
            if local in display_map:
                return display_map[local]
            return key
        return display_map.get(low, key)

    def get_support_team_analytics(self) -> SupportTeamAnalytics:

        tickets = self._tickets().all()
        open_operational = (
            self._tickets_operational()
            .filter(Ticket.status != TicketStatus.CLOSED)
            .all()
        )
        display_map = self._support_display_map()

        by_creator: dict[str, dict] = {}
        by_assignee: dict[str, dict] = {}
        open_by_member: dict[str, list[Ticket]] = {}

        def bump(bucket: dict, name: str | None, field: str):
            if not name:
                return
            if name not in bucket:
                bucket[name] = {"created": 0, "closed": 0, "open": 0, "hours": [], "open_tickets": []}
            bucket[name][field] += 1

        for t in tickets:
            creator = self._resolve_support_name(t.reporter or t.ticket_owner, display_map)
            bump(by_creator, creator, "created")
            assignee_name = self._resolve_support_name(t.assignee, display_map)
            if t.status == TicketStatus.CLOSED:
                bump(by_assignee, assignee_name, "closed")
                if t.resolution_hours and assignee_name:
                    by_assignee.setdefault(assignee_name, {"created": 0, "closed": 0, "open": 0, "hours": [], "open_tickets": []})
                    by_assignee[assignee_name]["hours"].append(t.resolution_hours)

        # Open queue: credit assignee, reporter, and ticket owner (support agents track tickets they raised)
        for t in open_operational:
            stakeholders: set[str] = set()
            for raw in (t.assignee, t.reporter, t.ticket_owner):
                resolved = self._resolve_support_name(raw, display_map)
                if resolved:
                    stakeholders.add(resolved)
            for name in stakeholders:
                open_by_member.setdefault(name, []).append(t)

        members: list[SupportTeamMember] = []
        all_names = set(by_creator) | set(by_assignee) | set(open_by_member)

        for name in all_names:
            c = by_creator.get(name, {})
            a = by_assignee.get(name, {})
            hours = a.get("hours", [])
            open_ticket_objs = open_by_member.get(name, [])
            priority_order = {
                TicketPriority.CRITICAL: 0,
                TicketPriority.HIGH: 1,
                TicketPriority.MEDIUM: 2,
                TicketPriority.LOW: 3,
            }
            open_summaries = [
                WorkshopTicketSummary(
                    id=t.id,
                    title=t.title,
                    status=t.status.value,
                    is_open=True,
                )
                for t in sorted(
                    open_ticket_objs,
                    key=lambda x: (
                        not x.is_workflow_blocker,
                        priority_order.get(x.priority, 9),
                        -(x.created_at or datetime.min).timestamp(),
                    ),
                )
            ]

            members.append(SupportTeamMember(
                name=name,
                tickets_created=c.get("created", 0),
                tickets_closed=a.get("closed", 0),
                open_assigned=len(open_summaries),
                avg_resolution_hours=round(sum(hours) / len(hours), 1) if hours else 0.0,
                open_tickets=open_summaries,
            ))

        members.sort(key=lambda m: m.open_assigned * 10 + m.tickets_created + m.tickets_closed, reverse=True)

        top_creator = max(by_creator, key=lambda k: by_creator[k]["created"], default=None) if by_creator else None
        top_closer = max(by_assignee, key=lambda k: by_assignee[k]["closed"], default=None) if by_assignee else None

        return SupportTeamAnalytics(
            members=members,
            top_creator=top_creator,
            top_closer=top_closer,
            total_members=len(members),
        )



    def get_jira_analytics(self) -> JiraAnalytics:

        issues = (
            self._jira_issues()
            .options(
                joinedload(JiraIssue.ticket).joinedload(Ticket.module),
                joinedload(JiraIssue.ticket).joinedload(Ticket.project),
            )
            .all()
        )

        issue_responses, sprint_data = [], {}

        for ji in issues:

            ticket = ji.ticket
            open_status = is_open_jira_status(ji.status)

            issue_responses.append(JiraIssueResponse(

                id=ji.id, jira_key=ji.jira_key, summary=ji.summary, status=ji.status,

                issue_type=ji.issue_type, sprint_name=ji.sprint_name, sprint_state=ji.sprint_state,

                story_points=ji.story_points, assignee=ji.assignee,

                ticket_title=ticket.title if ticket else None, jira_url=ji.jira_url,

                is_open=open_status,
                linked=ji.ticket_id is not None,
                asana_url=ticket.asana_url if ticket else None,
                asana_project_name=ticket.project.name if ticket and ticket.project else None,
                asana_section=ticket.module.name if ticket and ticket.module else None,

            ))

            if ji.sprint_name:

                if ji.sprint_name not in sprint_data:

                    sprint_data[ji.sprint_name] = {"name": ji.sprint_name, "state": ji.sprint_state, "issues": 0, "points": 0}

                sprint_data[ji.sprint_name]["issues"] += 1

                sprint_data[ji.sprint_name]["points"] += ji.story_points or 0

        open_issues = [i for i in issue_responses if i.is_open]
        closed_issues = [i for i in issue_responses if not i.is_open]
        open_issues.sort(key=lambda i: i.jira_key)
        closed_issues.sort(key=lambda i: i.jira_key)
        ordered = open_issues + closed_issues

        velocity = [{"sprint": s["name"], "points": s["points"], "issues": s["issues"]} for s in sprint_data.values()]

        return JiraAnalytics(

            issues=ordered,

            open_issues=open_issues,

            active_sprints=[s for s in sprint_data.values() if s.get("state") == "active"],

            total_linked=sum(1 for i in issue_responses if i.linked),

            total_open=len(open_issues),

            sprint_velocity=velocity,

        )



    def get_resolution_summary(self) -> dict:
        """Lightweight resolution stats for dashboard hot paths."""
        resolved = self._tickets().filter(Ticket.resolution_hours.isnot(None)).all()
        hours = [t.resolution_hours for t in resolved]
        avg = sum(hours) / len(hours) if hours else 0

        sla_base = self._tickets().filter(Ticket.sla_met.isnot(None))
        sla_total = sla_base.count()
        sla_met = sla_base.filter(Ticket.sla_met == True).count()
        sla_rate = (sla_met / sla_total * 100) if sla_total else 0

        reopened = self._tickets().filter(Ticket.is_reopened == True).count()

        return {
            "avg_resolution_hours": round(avg, 1),
            "sla_compliance_rate": round(sla_rate, 1),
            "reopened_count": reopened,
        }

    def get_resolution_analytics(self) -> ResolutionAnalytics:

        resolved = self._tickets().filter(Ticket.resolution_hours.isnot(None)).all()

        hours = [t.resolution_hours for t in resolved]

        avg = sum(hours) / len(hours) if hours else 0

        median = sorted(hours)[len(hours) // 2] if hours else 0



        sla_base = self._tickets().filter(Ticket.sla_met.isnot(None))

        sla_total = sla_base.count()

        sla_met = sla_base.filter(Ticket.sla_met == True).count()

        sla_rate = (sla_met / sla_total * 100) if sla_total else 0

        reopened = self._tickets().filter(Ticket.is_reopened == True).count()

        closed_total = self._tickets().filter(Ticket.status == TicketStatus.CLOSED).count()

        reopened_rate = (reopened / closed_total * 100) if closed_total else 0



        by_priority = []
        for p in TicketPriority:
            p_tickets = [t for t in resolved if t.priority == p]
            if p_tickets:
                by_priority.append({
                    "priority": p.value,
                    "avg_hours": round(sum(t.resolution_hours for t in p_tickets) / len(p_tickets), 1),
                    "count": len(p_tickets),
                })

        sla_by_module = []
        for m in self._modules().all():
            m_tickets = self._tickets().filter(
                Ticket.module_id == m.id, Ticket.sla_met.isnot(None)
            ).all()
            if m_tickets:
                met = sum(1 for t in m_tickets if t.sla_met)
                sla_by_module.append({
                    "module": m.name,
                    "compliance": round(met / len(m_tickets) * 100, 1),
                    "total": len(m_tickets),
                    "met": met,
                    "missed": len(m_tickets) - met,
                })

        total_resolved = len(resolved)
        sla_missed = sla_total - sla_met
        under_48h = sum(1 for t in resolved if t.resolution_hours and t.resolution_hours <= 48)
        over_7d = sum(1 for t in resolved if t.resolution_hours and t.resolution_hours > 168)

        return ResolutionAnalytics(
            avg_resolution_hours=round(avg, 1),
            median_resolution_hours=round(median, 1),
            sla_compliance_rate=round(sla_rate, 1),
            reopened_count=reopened,
            reopened_rate=round(reopened_rate, 1),
            total_resolved=total_resolved,
            sla_met_count=sla_met,
            sla_missed_count=sla_missed,
            under_48h_count=under_48h,
            over_7d_count=over_7d,
            resolution_by_priority=sorted(by_priority, key=lambda x: x["avg_hours"], reverse=True),
            sla_by_module=sorted(sla_by_module, key=lambda x: x["compliance"]),
        )

    def get_monthly_progress(self, year: int) -> MonthlyProgressAnalytics:
        from calendar import month_abbr

        from datetime import timezone

        today = datetime.now(timezone.utc)
        max_month = 12 if year < today.year else min(today.month, 12)

        q = self.db.query(Ticket)
        if self.project_id:
            q = q.filter(Ticket.project_id == self.project_id)
        tickets = q.all()

        project_name = None
        if self.project_id:
            project = self.db.query(AsanaProject).filter(AsanaProject.id == self.project_id).first()
            project_name = project.name if project else None

        def in_month(dt: datetime | None, month: int) -> bool:
            if not dt:
                return False
            return dt.year == year and dt.month == month

        def is_bug(t: Ticket) -> bool:
            if t.support_category == TicketCategory.BUG:
                return True
            if t.asana_type_raw and "bug" in t.asana_type_raw.lower():
                return True
            return False

        def is_enhancement(t: Ticket) -> bool:
            if t.support_category == TicketCategory.ENHANCEMENT:
                return True
            if t.asana_type_raw and "enhance" in t.asana_type_raw.lower():
                return True
            return False

        def pct_change(cur: int, prev: int) -> float | None:
            if prev == 0:
                return None if cur == 0 else 100.0
            return round((cur - prev) / prev * 100, 1)

        months: list[MonthlyProgressMonth] = []
        prev_created = prev_closed = prev_bugs = None
        prev_avg = None

        for m in range(1, max_month + 1):
            created_list = [t for t in tickets if in_month(t.created_at, m)]
            closed_list = [t for t in tickets if in_month(t.closed_at, m)]
            reopened_list = [t for t in closed_list if t.is_reopened]
            bugs_created = sum(1 for t in created_list if is_bug(t))
            bugs_closed = sum(1 for t in closed_list if is_bug(t))
            enhancements = sum(1 for t in created_list if is_enhancement(t))

            # Close time / SLA: only tickets opened this month (excludes backlog closed this month).
            created_cohort_resolved = [
                t for t in created_list if t.resolution_hours is not None
            ]
            hours = [t.resolution_hours for t in created_cohort_resolved]
            avg_h = round(sum(hours) / len(hours), 1) if hours else None
            median_h = round(sorted(hours)[len(hours) // 2], 1) if hours else None

            sla_pool = [t for t in created_cohort_resolved if t.sla_met is not None]
            sla_rate = round(sum(1 for t in sla_pool if t.sla_met) / len(sla_pool) * 100, 1) if sla_pool else None

            created_n = len(created_list)
            closed_n = len(closed_list)

            month_data = MonthlyProgressMonth(
                month=m,
                month_label=f"{month_abbr[m]} {year}",
                is_current_month=(year == today.year and m == today.month),
                tickets_created=created_n,
                tickets_closed=closed_n,
                reopened_count=len(reopened_list),
                avg_resolution_hours=avg_h,
                median_resolution_hours=median_h,
                sla_compliance_rate=sla_rate,
                bugs_created=bugs_created,
                bugs_closed=bugs_closed,
                enhancements_created=enhancements,
                net_flow=closed_n - created_n,
            )

            if prev_created is not None:
                month_data.created_vs_prev = created_n - prev_created
                month_data.created_vs_prev_pct = pct_change(created_n, prev_created)
                month_data.closed_vs_prev = closed_n - prev_closed
                month_data.closed_vs_prev_pct = pct_change(closed_n, prev_closed or 0)
                month_data.bugs_vs_prev = bugs_created - prev_bugs
                month_data.bugs_vs_prev_pct = pct_change(bugs_created, prev_bugs or 0)
                if avg_h is not None and prev_avg is not None:
                    month_data.avg_resolution_vs_prev = round(avg_h - prev_avg, 1)
                month_data.insight = self._monthly_insight(month_data, months[-1])

            months.append(month_data)
            prev_created, prev_closed, prev_bugs = created_n, closed_n, bugs_created
            prev_avg = avg_h

        highlights: list[str] = []
        if len(months) >= 2:
            cur, prev = months[-1], months[-2]
            if cur.bugs_vs_prev is not None and cur.bugs_vs_prev < 0:
                highlights.append(
                    f"{cur.month_label}: {abs(cur.bugs_vs_prev)} fewer bugs created than {prev.month_label} — issue volume may be reducing."
                )
            elif cur.bugs_vs_prev is not None and cur.bugs_vs_prev > 0:
                highlights.append(
                    f"{cur.month_label}: {cur.bugs_vs_prev} more bugs than {prev.month_label}."
                )
            if cur.closed_vs_prev is not None and cur.closed_vs_prev > 0:
                highlights.append(
                    f"Closed {cur.closed_vs_prev} more tickets in {cur.month_label} than the prior month."
                )
            if cur.avg_resolution_vs_prev is not None:
                if cur.avg_resolution_vs_prev < 0:
                    highlights.append(
                        f"Average close time improved by {abs(cur.avg_resolution_vs_prev):.0f}h vs last month."
                    )
                elif cur.avg_resolution_vs_prev > 0:
                    highlights.append(
                        f"Average close time slowed by {cur.avg_resolution_vs_prev:.0f}h vs last month."
                    )

        return MonthlyProgressAnalytics(
            year=year,
            project_name=project_name,
            months=months,
            year_created=sum(m.tickets_created for m in months),
            year_closed=sum(m.tickets_closed for m in months),
            year_bugs_created=sum(m.bugs_created for m in months),
            year_reopened=sum(m.reopened_count for m in months),
            highlights=highlights,
        )

    @staticmethod
    def _monthly_insight(cur: MonthlyProgressMonth, prev: MonthlyProgressMonth) -> str | None:
        parts: list[str] = []
        if cur.bugs_vs_prev is not None and cur.bugs_vs_prev < 0:
            parts.append(f"{abs(cur.bugs_vs_prev)} fewer bugs vs {prev.month_label}")
        elif cur.bugs_vs_prev is not None and cur.bugs_vs_prev > 0:
            parts.append(f"{cur.bugs_vs_prev} more bugs vs {prev.month_label}")
        if cur.closed_vs_prev is not None and cur.closed_vs_prev != 0:
            sign = "+" if cur.closed_vs_prev > 0 else ""
            parts.append(f"{sign}{cur.closed_vs_prev} closed vs prior month")
        if cur.net_flow > 0:
            parts.append("backlog reduced")
        elif cur.net_flow < 0:
            parts.append("backlog grew")
        return " · ".join(parts) if parts else None

