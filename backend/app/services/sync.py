"""Sync Asana projects/tasks and Jira issues into the local database."""

import asyncio
from datetime import datetime, timedelta

from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.asana import AsanaClient
from app.integrations.jira import JiraClient
from app.models import (
    AsanaProject, Ticket, Module, Customer, JiraIssue,
    TicketStatus, TicketCategory, TicketPriority,
)
from app.services.jira_linking import link_jira_asana_tickets
from app.db_utils import commit_with_retry, flush_with_retry
from app.services.ticket_parser import (
    parse_custom_field, parse_date_field,
    extract_workshop_name, extract_ax_id, extract_workshop_id,
    detect_workflow_blocker, map_asana_priority, parse_custom_number,
    extract_jira_key, extract_jira_key_from_attachments,
)
from app.services.section_tracking import record_section_change, backfill_project_releases
from app.services.section_utils import is_sprint_pipeline_section
from app.services.insights_generator import generate_insights
from app.services.status_move_notifier import StatusMoveEvent, notify_status_moves
from app.services.subtask_estimates import (
    parent_gids_from_synced_tasks,
    pipeline_parent_gids,
    sync_subtask_estimates,
    _parent_gid,
)

settings = get_settings()

TYPE_TO_CATEGORY: dict[str, TicketCategory] = {
    "bug": TicketCategory.BUG,
    "enhancement": TicketCategory.ENHANCEMENT,
    "enhance": TicketCategory.ENHANCEMENT,
    "task": TicketCategory.TASK,
    "requirement": TicketCategory.REQUIREMENT,
    "requirements": TicketCategory.REQUIREMENT,
    "configuration": TicketCategory.CONFIGURATION,
    "config": TicketCategory.CONFIGURATION,
    "knowledge gap": TicketCategory.KNOWLEDGE_GAP,
    "knowledge_gap": TicketCategory.KNOWLEDGE_GAP,
    "duplicate": TicketCategory.DUPLICATE,
    "feature": TicketCategory.ENHANCEMENT,
    "feature request": TicketCategory.ENHANCEMENT,
    "question": TicketCategory.KNOWLEDGE_GAP,
    "support": TicketCategory.KNOWLEDGE_GAP,
}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return date_parser.parse(value).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _map_category(raw: str | None) -> TicketCategory | None:
    if not raw:
        return None
    key = raw.strip().lower().replace("-", " ").replace("_", " ")
    if key in TYPE_TO_CATEGORY:
        return TYPE_TO_CATEGORY[key]
    for label, cat in TYPE_TO_CATEGORY.items():
        if label in key:
            return cat
    return None


def _map_status(completed: bool, tags: list) -> TicketStatus:
    tag_names = {t.get("name", "").lower() for t in (tags or [])}
    if completed:
        return TicketStatus.CLOSED
    if "blocked" in tag_names or "blocker" in tag_names:
        return TicketStatus.BLOCKED
    if "in progress" in tag_names or "in-progress" in tag_names:
        return TicketStatus.IN_PROGRESS
    return TicketStatus.OPEN


def _section_name(task: dict) -> str:
    for m in task.get("memberships") or []:
        section = m.get("section") or {}
        if section.get("name"):
            return section["name"]
    return "General"


def _get_or_create_module(db: Session, name: str, project_id: int) -> Module:
    mod = db.query(Module).filter(Module.name == name, Module.project_id == project_id).first()
    if not mod:
        mod = Module(name=name, product_area="Asana Section", project_id=project_id)
        db.add(mod)
        db.flush()
    return mod


def _get_or_create_customer(db: Session, workshop_name: str | None) -> Customer | None:
    if not workshop_name or workshop_name.lower() in ("unknown", "—", "-"):
        return None
    cust = db.query(Customer).filter(Customer.name == workshop_name).first()
    if not cust:
        cust = Customer(name=workshop_name, tier="workshop")
        db.add(cust)
        db.flush()
    return cust


async def _board_index_for_project(asana: AsanaClient, project_gid: str) -> dict[str, int]:
    """Asana board order — Prioritized section first, then other pipeline sections."""
    board_index_by_gid: dict[str, int] = {}
    try:
        sections = await asana.fetch_project_sections(project_gid)
        sprint_section = settings.asana_sprint_section_name.strip().lower()

        def _section_rank(name: str | None) -> int:
            if (name or "").strip().lower() == sprint_section:
                return 0
            if is_sprint_pipeline_section(name):
                return 1
            return 2

        ordered = sorted(
            sections,
            key=lambda s: (_section_rank(s.get("name")), s.get("name") or ""),
        )
        pipeline = [s for s in ordered if _section_rank(s.get("name")) < 2]

        async def index_section(section: dict) -> list[tuple[str, int]]:
            section_tasks = await asana.fetch_section_tasks(section["gid"])
            return [(t["gid"], idx) for idx, t in enumerate(section_tasks) if t.get("gid")]

        results = await asyncio.gather(
            *[index_section(s) for s in pipeline],
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                continue
            for gid, idx in result:
                board_index_by_gid[gid] = idx
    except Exception:
        pass
    return board_index_by_gid


class SyncService:
    def __init__(self, db: Session):
        self.db = db
        self.asana = AsanaClient()
        self.jira = JiraClient()

    def get_project_by_gid(self, project_gid: str) -> AsanaProject | None:
        return self.db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()

    async def discover_projects(self) -> list[AsanaProject]:
        if not self.asana.is_configured:
            return self.db.query(AsanaProject).order_by(AsanaProject.name).all()

        remote = await self.asana.fetch_projects()
        for p in remote:
            existing = self.db.query(AsanaProject).filter(AsanaProject.gid == p["gid"]).first()
            if existing:
                existing.name = p["name"]
            else:
                self.db.add(AsanaProject(
                    gid=p["gid"],
                    name=p["name"],
                    workspace_gid=settings.asana_workspace_gid,
                    jira_project_key=settings.jira_project_key or None,
                ))
        self.db.commit()
        return self.db.query(AsanaProject).order_by(AsanaProject.name).all()

    async def sync_asana_project(
        self,
        project_gid: str,
        *,
        incremental: bool = False,
    ) -> dict:
        project = self.get_project_by_gid(project_gid)
        if not project:
            remote = await self.asana.fetch_projects()
            match = next((p for p in remote if p["gid"] == project_gid), None)
            if not match:
                return {"success": False, "error": f"Project {project_gid} not found in Asana"}
            project = AsanaProject(
                gid=project_gid,
                name=match["name"],
                workspace_gid=settings.asana_workspace_gid,
                jira_project_key=settings.jira_project_key or None,
            )
            self.db.add(project)
            self.db.flush()

        # First sync (or no watermark) must be full — otherwise we'd miss existing tickets.
        use_incremental = bool(incremental and project.last_synced_at)
        modified_since: str | None = None
        if use_incremental and project.last_synced_at:
            # Small overlap so we don't miss updates that happened during the last sync.
            watermark = project.last_synced_at - timedelta(minutes=2)
            modified_since = watermark.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        try:
            tasks = await self.asana.fetch_project_tasks(
                project_gid, modified_since=modified_since
            )
            if use_incremental:
                # Full membership is cheap (gid only) and keeps removals / sheet cleanup correct.
                synced_gids = await self.asana.fetch_project_task_gids(project_gid)
            else:
                synced_gids = {task["gid"] for task in tasks}

            board_index_by_gid = await _board_index_for_project(self.asana, project_gid)

            synced = 0
            batch_size = 25
            status_moves: list[StatusMoveEvent] = []

            for task in tasks:
                gid = task["gid"]
                title = task.get("name") or "Untitled"
                notes = task.get("notes") or ""
                custom_fields = task.get("custom_fields") or []

                type_raw = parse_custom_field(custom_fields, settings.asana_type_field_name)
                support_cat = _map_category(type_raw)
                priority_raw = parse_custom_field(custom_fields, "Priority")
                ticket_owner = parse_custom_field(custom_fields, "Ticket Owner")
                workshop_field = parse_custom_field(custom_fields, "Workshop/s")
                source = parse_custom_field(custom_fields, "Source")
                expected_delivery = parse_date_field(custom_fields, "Expected Delivery on")
                completion_date = parse_date_field(custom_fields, "Completion Date")

                workshop_name = extract_workshop_name(title, notes, workshop_field)
                ax_id = extract_ax_id(notes)
                workshop_id = extract_workshop_id(notes, workshop_field)

                section = _section_name(task)
                parent_asana_gid = _parent_gid(task)
                module = _get_or_create_module(self.db, section, project.id)
                customer = _get_or_create_customer(self.db, workshop_name)

                created = _parse_dt(task.get("created_at")) or datetime.utcnow()
                completed = task.get("completed", False)
                closed = _parse_dt(task.get("completed_at")) if completed else None
                status = _map_status(completed, task.get("tags") or [])

                resolution_hours = None
                sla_met = None
                if closed and created:
                    resolution_hours = (closed - created).total_seconds() / 3600
                    sla_met = resolution_hours <= 48

                tags = [t.get("name") for t in (task.get("tags") or []) if t.get("name")]
                priority = map_asana_priority(priority_raw, tags)
                is_workflow_blocker = detect_workflow_blocker(title, notes, priority_raw, status != TicketStatus.CLOSED)

                created_by_user = task.get("created_by") or {}
                created_by = created_by_user.get("name") or created_by_user.get("email")
                assignee = (task.get("assignee") or {}).get("name")

                existing = self.db.query(Ticket).filter(Ticket.asana_gid == gid).first()
                previous_status = existing.status if existing else None
                is_new_ticket = existing is None
                old_section = None
                if existing and existing.module:
                    old_section = existing.module.name

                dev_effort = parse_custom_number(custom_fields, "Dev. Effort in Hours")
                qa_effort = parse_custom_number(custom_fields, "QA Effort in Hours")
                total_effort = parse_custom_number(custom_fields, "Total-Effort_in_Hrs")
                if total_effort is None and (dev_effort is not None or qa_effort is not None):
                    total_effort = (dev_effort or 0) + (qa_effort or 0)
                product_stage = parse_custom_field(custom_fields, "Product stage")
                build_in = parse_custom_field(custom_fields, "Build In")
                dor_value = parse_custom_field(custom_fields, "DoR")
                jira_key = extract_jira_key(title, notes, settings.jira_project_key)
                # Reuse known Jira links — attachment probing is the main sync bottleneck.
                if not jira_key and existing and existing.jira_key:
                    jira_key = existing.jira_key
                if not jira_key:
                    attachments = await self.asana.fetch_task_attachments(gid)
                    jira_key = extract_jira_key_from_attachments(attachments, settings.jira_project_key)

                fields = dict(
                    title=title,
                    description=notes,
                    status=status,
                    support_category=support_cat,
                    ai_category=support_cat,
                    priority=priority,
                    module_id=module.id,
                    customer_id=customer.id if customer else None,
                    project_id=project.id,
                    assignee=assignee,
                    reporter=created_by,
                    ticket_owner=ticket_owner,
                    workshop_name=workshop_name,
                    workshop_id=workshop_id,
                    ax_id=ax_id,
                    asana_type_raw=type_raw,
                    asana_priority_raw=priority_raw,
                    source=source,
                    expected_delivery=expected_delivery,
                    completion_date=completion_date,
                    is_workflow_blocker=is_workflow_blocker,
                    is_critical_blocker=is_workflow_blocker,
                    sla_met=sla_met,
                    resolution_hours=round(resolution_hours, 1) if resolution_hours else None,
                    tags=tags,
                    asana_url=task.get("permalink_url"),
                    jira_key=jira_key,
                    dev_effort_hours=dev_effort,
                    qa_effort_hours=qa_effort,
                    total_effort_hours=total_effort,
                    product_stage=product_stage,
                    build_in=build_in,
                    dor_value=dor_value,
                    asana_board_index=board_index_by_gid.get(gid),
                    parent_asana_gid=parent_asana_gid,
                    removed_from_asana=False,
                    created_at=created,
                    closed_at=closed,
                    updated_at=_parse_dt(task.get("modified_at")) or datetime.utcnow(),
                )
                if existing:
                    for k, v in fields.items():
                        setattr(existing, k, v)
                    ticket_row = existing
                else:
                    ticket_row = Ticket(asana_gid=gid, **fields)
                    self.db.add(ticket_row)
                flush_with_retry(self.db)

                if section != (old_section or "") and not parent_asana_gid:
                    await record_section_change(
                        self.db, ticket_row, old_section, section, self.asana,
                    )
                    if old_section:
                        status_moves.append(
                            StatusMoveEvent(
                                title=ticket_row.title or title,
                                from_section=old_section,
                                to_section=section,
                                jira_key=ticket_row.jira_key,
                                asana_url=ticket_row.asana_url,
                                assignee=ticket_row.assignee,
                            )
                        )

                synced += 1
                if synced % batch_size == 0:
                    commit_with_retry(self.db)

            # Refresh board order for unchanged tickets too (cheap local update).
            if board_index_by_gid:
                for ticket in (
                    self.db.query(Ticket)
                    .filter(
                        Ticket.project_id == project.id,
                        Ticket.asana_gid.in_(list(board_index_by_gid.keys())),
                    )
                    .all()
                ):
                    idx = board_index_by_gid.get(ticket.asana_gid)
                    if idx is not None and ticket.asana_board_index != idx:
                        ticket.asana_board_index = idx

            if synced_gids:
                stale = (
                    self.db.query(Ticket)
                    .filter(
                        Ticket.project_id == project.id,
                        Ticket.asana_gid.isnot(None),
                        Ticket.parent_asana_gid.is_(None),
                        Ticket.asana_gid.notin_(synced_gids),
                        Ticket.removed_from_asana.is_(False),
                    )
                    .all()
                )
                for ticket in stale:
                    ticket.removed_from_asana = True
                    ticket.updated_at = datetime.utcnow()

            if use_incremental:
                subtask_parents = parent_gids_from_synced_tasks(tasks)
            else:
                subtask_parents = pipeline_parent_gids(self.db, project.id)
            try:
                await sync_subtask_estimates(
                    self.db, self.asana, project.id, subtask_parents
                )
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Subtask estimate sync failed for %s", project_gid
                )

            if not use_incremental:
                await backfill_project_releases(self.db, project.id, self.asana)
            link_jira_asana_tickets(self.db)
            project.ticket_count = self.db.query(Ticket).filter(Ticket.project_id == project.id).count()
            project.last_synced_at = datetime.utcnow()
            commit_with_retry(self.db)

            clusters_created = 0
            if not use_incremental:
                try:
                    from app.services.clustering import run_semantic_clustering
                    clusters_created = run_semantic_clustering(self.db, project.id)
                except Exception:
                    pass
                try:
                    generate_insights(self.db, project.id, date_from=datetime(2026, 2, 1))
                except Exception:
                    pass

            notify_result = {}
            try:
                # Tech-team alerts: Sprint Planning board only (not support / other projects).
                name_l = (project.name or "").lower()
                if "sprint" in name_l and "planning" in name_l:
                    notify_result = await notify_status_moves(project.name, status_moves)
                else:
                    notify_result = {
                        "skipped_reason": "not_sprint_planning",
                        "filtered_count": 0,
                        "chat_sent": False,
                        "email_sent": False,
                    }
            except Exception:
                notify_result = {"error": "status_move_notify_failed"}

            return {
                "success": True,
                "project_gid": project_gid,
                "project_name": project.name,
                "tasks_synced": synced,
                "total_in_project": project.ticket_count,
                "clusters_created": clusters_created,
                "incremental": use_incremental,
                "modified_since": modified_since,
                "status_moves": notify_result,
            }
        finally:
            await self.asana.close()

    async def sync_jira_for_project(self, project_gid: str) -> dict:
        project = self.get_project_by_gid(project_gid)
        if not project:
            return {"success": False, "error": "Asana project not found. Sync Asana first."}
        jira_key = project.jira_project_key or settings.jira_project_key
        return await self._sync_jira_issues(project.id, jira_key=jira_key)

    async def sync_jira_global(self) -> dict:
        """Pull all Jira issues for the configured project key (not scoped to Asana selection)."""
        jira_key = settings.jira_project_key
        if not jira_key:
            return {"success": True, "skipped": True, "message": "No JIRA_PROJECT_KEY — Jira sync skipped"}
        if not self.jira.is_configured:
            return {
                "success": True,
                "skipped": True,
                "message": "Jira API token not set.",
            }

        sprint = (
            self.db.query(AsanaProject)
            .filter(AsanaProject.name.ilike("%sprint%planning%"))
            .first()
        )
        project_id = sprint.id if sprint else None
        result = await self._sync_jira_issues(project_id, jira_key=jira_key)
        linked = link_jira_asana_tickets(self.db)
        result["linked_count"] = linked
        return result

    async def _sync_jira_issues(
        self,
        asana_project_id: int | None,
        jira_key: str | None = None,
    ) -> dict:
        jira_key = jira_key or settings.jira_project_key
        if not jira_key:
            return {"success": True, "skipped": True, "message": "No JIRA_PROJECT_KEY — Jira sync skipped"}
        if not self.jira.is_configured:
            return {
                "success": True,
                "skipped": True,
                "message": "Jira API token not set — Asana data is still available. Add JIRA_API_TOKEN later.",
            }

        issues = await self.jira.fetch_project_issues(jira_key)
        synced = 0
        new_bug_events: list = []
        # key -> summary for parent lookup after the loop
        known_summaries: dict[str, str] = {}
        pending_bugs: list[dict] = []

        for issue in issues:
            key = issue["key"]
            fields = issue.get("fields") or {}
            status = (fields.get("status") or {}).get("name")
            issue_type = (fields.get("issuetype") or {}).get("name")
            assignee = (fields.get("assignee") or {}).get("displayName")
            summary = fields.get("summary")
            story_points = fields.get("customfield_10016")
            parent = fields.get("parent") or {}
            parent_key = (parent.get("key") or "").strip() or None
            parent_summary = None
            if parent_key:
                parent_fields = parent.get("fields") or {}
                parent_summary = (parent_fields.get("summary") or "").strip() or None
            if summary:
                known_summaries[key] = summary
            if parent_key and parent_summary:
                known_summaries[parent_key] = parent_summary

            existing = self.db.query(JiraIssue).filter(JiraIssue.jira_key == key).first()
            is_new = existing is None
            jira_url = f"{settings.jira_base_url.rstrip('/')}/browse/{key}"
            data = dict(
                summary=summary,
                status=status,
                issue_type=issue_type,
                parent_jira_key=parent_key,
                assignee=assignee,
                story_points=story_points,
                sprint_name=None,
                sprint_state=None,
                jira_url=jira_url,
                project_id=asana_project_id,
                project_key=jira_key,
                synced_at=datetime.utcnow(),
            )
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
            else:
                self.db.add(JiraIssue(jira_key=key, ticket_id=None, **data))

            if is_new and parent_key:
                from app.services.jira_bug_notifier import (
                    description_snippet,
                    is_notifiable_bug_subtask,
                )

                if is_notifiable_bug_subtask(parent_key=parent_key, issue_type=issue_type):
                    pending_bugs.append(
                        {
                            "bug_key": key,
                            "bug_summary": summary or "",
                            "bug_url": jira_url,
                            "parent_key": parent_key,
                            "parent_summary": parent_summary,
                            "parent_url": f"{settings.jira_base_url.rstrip('/')}/browse/{parent_key}",
                            "assignee": assignee,
                            "issue_type": issue_type,
                            "status": status,
                            "description": description_snippet(fields.get("description")),
                        }
                    )
            synced += 1

        self.db.commit()
        linked = link_jira_asana_tickets(self.db)

        notify_result = {}
        if pending_bugs:
            from app.services.jira_bug_notifier import JiraBugSubtaskEvent, notify_jira_bug_subtasks

            for item in pending_bugs:
                parent_key = item["parent_key"]
                parent_summary = item["parent_summary"] or known_summaries.get(parent_key)
                if not parent_summary:
                    parent_row = (
                        self.db.query(JiraIssue)
                        .filter(JiraIssue.jira_key == parent_key)
                        .first()
                    )
                    parent_summary = parent_row.summary if parent_row else None
                new_bug_events.append(
                    JiraBugSubtaskEvent(
                        bug_key=item["bug_key"],
                        bug_summary=item["bug_summary"],
                        bug_url=item["bug_url"],
                        parent_key=parent_key,
                        action="created",
                        status=item.get("status"),
                        parent_summary=parent_summary,
                        parent_url=item["parent_url"],
                        assignee=item["assignee"],
                        issue_type=item["issue_type"],
                        description=item.get("description"),
                    )
                )
            try:
                notify_result = await notify_jira_bug_subtasks(new_bug_events)
            except Exception:
                notify_result = {"error": "jira_bug_notify_failed"}

        project_name = None
        if asana_project_id:
            proj = self.db.query(AsanaProject).filter(AsanaProject.id == asana_project_id).first()
            project_name = proj.name if proj else None
        return {
            "success": True,
            "project_key": jira_key,
            "issues_synced": synced,
            "linked_to": project_name,
            "linked_count": linked,
            "new_bug_subtasks": notify_result,
        }

    async def sync_all(self, project_gid: str, *, incremental: bool = False) -> dict:
        asana_result = await self.sync_asana_project(project_gid, incremental=incremental)
        if not asana_result.get("success"):
            return asana_result
        # Always pull Jira so new bug sub-tasks can alert the Bugs Chat space.
        jira_result = await self.sync_jira_for_project(project_gid)
        return {
            "success": True,
            "asana": asana_result,
            "jira": jira_result,
        }

    def integration_status(self) -> dict:
        from app.services.auto_sync import get_meta
        from app.services import google_sheets_sync as gsync
        from app.services.asana_webhooks import webhook_target_url
        from app.services.jira_webhooks import jira_webhook_target_url

        cfg = get_settings()
        return {
            "asana_configured": self.asana.is_configured,
            "jira_configured": cfg.jira_configured,
            "google_sheets_configured": gsync.is_configured(),
            "google_service_account_email": gsync.service_account_email(),
            "mock_mode": settings.use_mock_data,
            "asana_workspace_gid": settings.asana_workspace_gid or None,
            "jira_project_key": settings.jira_project_key or None,
            "type_field_name": settings.asana_type_field_name,
            "auto_sync_enabled": settings.auto_sync_enabled,
            "auto_sync_interval_minutes": settings.auto_sync_interval_minutes,
            "auto_sync_ui_poll_seconds": settings.auto_sync_ui_poll_seconds,
            "asana_webhooks_enabled": bool(webhook_target_url()),
            "jira_webhooks_enabled": bool(jira_webhook_target_url()),
            "email_configured": cfg.email_configured,
            "last_auto_sync_at": get_meta(self.db, "last_auto_sync_at"),
        }
