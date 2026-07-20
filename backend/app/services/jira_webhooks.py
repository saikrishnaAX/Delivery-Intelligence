"""Jira webhook receiver — near-instant Chat alerts for Sub-Bug lifecycle."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.integrations.jira import JiraClient
from app.models import AsanaProject, JiraIssue
from app.services.auto_sync import _set_meta
from app.services.jira_bug_notifier import (
    JiraBugSubtaskEvent,
    description_snippet,
    is_notifiable_bug_subtask,
    notify_cooldown_key,
    notify_jira_bug_subtasks,
)
from app.services.jira_linking import link_jira_asana_tickets

logger = logging.getLogger(__name__)
settings = get_settings()

_recent_notified: dict[str, float] = {}
_NOTIFY_COOLDOWN_SECONDS = 90


def jira_webhook_target_url() -> str | None:
    base = (settings.asana_webhook_target_url or "").strip().rstrip("/")
    if not base:
        return None
    prefix = settings.api_prefix.rstrip("/")
    return f"{base}{prefix}/webhooks/jira"


def _sprint_project_id(db: Session) -> int | None:
    sprint = (
        db.query(AsanaProject)
        .filter(AsanaProject.name.ilike("%sprint%planning%"))
        .first()
    )
    return sprint.id if sprint else None


def _status_from_issue(issue: dict) -> str | None:
    fields = issue.get("fields") or {}
    return (fields.get("status") or {}).get("name")


def _status_change_from_changelog(changelog: dict | None) -> tuple[str | None, str | None]:
    if not changelog:
        return None, None
    for item in changelog.get("items") or []:
        if (item.get("field") or "").lower() == "status":
            prev = (item.get("fromString") or item.get("from") or "").strip() or None
            new = (item.get("toString") or item.get("to") or "").strip() or None
            return prev, new
    return None, None


def _issue_to_event(
    issue: dict,
    *,
    action: str,
    status: str | None,
    previous_status: str | None = None,
) -> JiraBugSubtaskEvent | None:
    key = issue.get("key")
    fields = issue.get("fields") or {}
    if not key:
        return None
    issue_type = (fields.get("issuetype") or {}).get("name")
    parent = fields.get("parent") or {}
    parent_key = (parent.get("key") or "").strip() or None
    if not is_notifiable_bug_subtask(parent_key=parent_key, issue_type=issue_type):
        return None
    parent_fields = parent.get("fields") or {}
    parent_summary = (parent_fields.get("summary") or "").strip() or None
    base = settings.jira_base_url.rstrip("/")
    return JiraBugSubtaskEvent(
        bug_key=key,
        bug_summary=(fields.get("summary") or "").strip(),
        bug_url=f"{base}/browse/{key}",
        parent_key=parent_key or "",
        action=action,
        status=status or _status_from_issue(issue),
        previous_status=previous_status,
        parent_summary=parent_summary,
        parent_url=f"{base}/browse/{parent_key}" if parent_key else None,
        assignee=(fields.get("assignee") or {}).get("displayName"),
        issue_type=issue_type,
        description=description_snippet(fields.get("description")),
    )


def upsert_jira_issue(db: Session, issue: dict, *, project_id: int | None) -> tuple[JiraIssue, bool]:
    key = issue.get("key")
    fields = issue.get("fields") or {}
    if not key:
        raise ValueError("Issue missing key")

    parent = fields.get("parent") or {}
    parent_key = (parent.get("key") or "").strip() or None
    project_field = fields.get("project") or {}
    project_key = project_field.get("key") or settings.jira_project_key
    jira_url = f"{settings.jira_base_url.rstrip('/')}/browse/{key}"

    data = dict(
        summary=fields.get("summary"),
        status=_status_from_issue(issue),
        issue_type=(fields.get("issuetype") or {}).get("name"),
        parent_jira_key=parent_key,
        assignee=(fields.get("assignee") or {}).get("displayName"),
        jira_url=jira_url,
        project_id=project_id,
        project_key=project_key,
        synced_at=datetime.utcnow(),
    )

    existing = db.query(JiraIssue).filter(JiraIssue.jira_key == key).first()
    if existing:
        for k, v in data.items():
            setattr(existing, k, v)
        return existing, False

    row = JiraIssue(jira_key=key, ticket_id=None, **data)
    db.add(row)
    return row, True


async def _maybe_notify(event: JiraBugSubtaskEvent | None) -> dict:
    if not event:
        return {"skipped_reason": "not_sub_bug"}
    now = datetime.utcnow().timestamp()
    key = notify_cooldown_key(event)
    last = _recent_notified.get(key, 0)
    if now - last < _NOTIFY_COOLDOWN_SECONDS:
        return {"skipped_reason": "cooldown", "action": event.action, "status": event.status}
    result = await notify_jira_bug_subtasks([event])
    if result.get("chat_sent"):
        _recent_notified[key] = now
    return result


async def _process_issue_event(
    webhook_event: str,
    issue: dict,
    *,
    changelog: dict | None = None,
) -> dict:
    db = SessionLocal()
    try:
        project_id = _sprint_project_id(db)
        key = issue.get("key")
        jira = JiraClient()
        if key and jira.is_configured:
            full = await jira.fetch_issue(key)
            if full:
                issue = full

        existing = db.query(JiraIssue).filter(JiraIssue.jira_key == key).first() if key else None
        old_status = existing.status if existing else None

        row, is_new = upsert_jira_issue(db, issue, project_id=project_id)
        db.commit()
        link_jira_asana_tickets(db)

        new_status = row.status
        notify_result: dict = {"skipped_reason": "no_notify_rule"}

        if webhook_event == "jira:issue_created" and is_new:
            event = _issue_to_event(
                issue,
                action="created",
                status=new_status,
            )
            notify_result = await _maybe_notify(event)

        elif webhook_event == "jira:issue_updated":
            ch_prev, ch_new = _status_change_from_changelog(changelog)
            prev_status = ch_prev or old_status
            status_now = ch_new or new_status
            if prev_status and status_now and prev_status.strip().lower() != status_now.strip().lower():
                event = _issue_to_event(
                    issue,
                    action="status_changed",
                    status=status_now,
                    previous_status=prev_status,
                )
                notify_result = await _maybe_notify(event)
            else:
                notify_result = {"skipped_reason": "status_unchanged"}

        return {
            "key": row.jira_key,
            "is_new": is_new,
            "parent": row.parent_jira_key,
            "status": new_status,
            "notify": notify_result,
        }
    except Exception:
        db.rollback()
        logger.exception("Jira webhook issue processing failed")
        return {"error": "processing_failed"}
    finally:
        db.close()


async def handle_jira_webhook(request: Request) -> Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return Response(status_code=400, content="Invalid JSON")

    webhook_event = (body.get("webhookEvent") or "").strip()
    issue = body.get("issue")
    if not issue or not webhook_event:
        return Response(status_code=200)

    if webhook_event not in {"jira:issue_created", "jira:issue_updated"}:
        return Response(status_code=200)

    result = await _process_issue_event(
        webhook_event,
        issue,
        changelog=body.get("changelog"),
    )
    logger.info("Jira webhook %s → %s", webhook_event, result)
    return Response(status_code=200)


async def ensure_jira_webhooks() -> dict:
    target = jira_webhook_target_url()
    if not target:
        return {"enabled": False, "reason": "public webhook URL not configured"}
    jira = JiraClient()
    if not jira.is_configured:
        return {"enabled": False, "reason": "Jira not configured"}

    project_key = settings.jira_project_key
    try:
        existing = await jira.list_webhooks()
        for wh in existing:
            url = (wh.get("url") or "").strip()
            wid = wh.get("id")
            if wid and url.endswith("/webhooks/jira") and url != target:
                try:
                    await jira.delete_webhook(wid)
                except Exception:
                    logger.exception("Failed deleting stale Jira webhook %s", wid)

        already = any((wh.get("url") or "").strip() == target for wh in existing)
        if already:
            status = {"status": "existing", "url": target}
        else:
            created = await jira.register_webhook(target, project_key=project_key)
            status = {"status": "created", "url": target, "response": created}

        db = SessionLocal()
        try:
            _set_meta(db, "jira_webhooks_registered_at", datetime.utcnow().isoformat())
            _set_meta(db, "jira_webhook_target", target)
        finally:
            db.close()

        return {
            "enabled": True,
            "target": target,
            "project_key": project_key,
            "registration": status,
            "manual_fallback": (
                "Jira → Settings → System → WebHooks → Create "
                f"URL {target}, events Issue created + Issue updated, "
                f"JQL project = {project_key}."
            ),
        }
    except Exception as exc:
        logger.exception("Jira webhook registration failed")
        return {
            "enabled": False,
            "target": target,
            "error": str(exc),
            "manual_fallback": (
                "Create webhook manually in Jira admin: "
                f"URL {target}, events Issue created + Issue updated, "
                f"JQL project = {project_key}."
            ),
        }
