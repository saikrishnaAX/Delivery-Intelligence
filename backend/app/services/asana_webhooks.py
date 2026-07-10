"""Asana webhook receiver — near-instant sync when tasks change."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from fastapi import Request, Response

from app.config import get_settings
from app.database import SessionLocal
from app.integrations.asana import AsanaClient
from app.services.auto_sync import _set_meta, sync_project_after_asana_change
from app.services.sync import SyncService

logger = logging.getLogger(__name__)
settings = get_settings()

_debounce_tasks: dict[str, asyncio.Task] = {}
DEBOUNCE_SECONDS = 12


def webhook_target_url() -> str | None:
    base = (settings.asana_webhook_target_url or "").strip().rstrip("/")
    if not base:
        return None
    prefix = settings.api_prefix.rstrip("/")
    return f"{base}{prefix}/webhooks/asana"


async def _debounced_project_sync(project_gid: str) -> None:
    await asyncio.sleep(DEBOUNCE_SECONDS)
    db = SessionLocal()
    try:
        await sync_project_after_asana_change(db, project_gid, source="webhook")
    except Exception:
        logger.exception("Webhook sync failed for project %s", project_gid)
    finally:
        db.close()
        _debounce_tasks.pop(project_gid, None)


def schedule_project_sync(project_gid: str) -> None:
    existing = _debounce_tasks.get(project_gid)
    if existing and not existing.done():
        existing.cancel()
    _debounce_tasks[project_gid] = asyncio.create_task(_debounced_project_sync(project_gid))


async def _resolve_project_gids(events: list[dict], asana: AsanaClient) -> set[str]:
    gids: set[str] = set()
    task_gids: set[str] = set()

    for ev in events:
        parent = ev.get("parent") or {}
        if parent.get("resource_type") == "project" and parent.get("gid"):
            gids.add(str(parent["gid"]))
        resource = ev.get("resource") or {}
        rtype = resource.get("resource_type")
        rgid = resource.get("gid")
        if rtype == "project" and rgid:
            gids.add(str(rgid))
        elif rtype == "task" and rgid:
            task_gids.add(str(rgid))

    for task_gid in task_gids:
        try:
            for pgid in await asana.fetch_task_project_gids(task_gid):
                gids.add(pgid)
        except Exception:
            logger.exception("Could not resolve projects for task %s", task_gid)

    return gids


async def handle_asana_webhook(request: Request) -> Response:
    """Asana handshake + event delivery."""
    hook_secret = request.headers.get("X-Hook-Secret")
    if hook_secret:
        return Response(status_code=200, headers={"X-Hook-Secret": hook_secret})

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return Response(status_code=400, content="Invalid JSON")

    events = body.get("events") or []
    if not events:
        return Response(status_code=200)

    asana = AsanaClient()
    if not asana.is_configured:
        return Response(status_code=200)

    project_gids = await _resolve_project_gids(events, asana)
    for gid in project_gids:
        schedule_project_sync(gid)

    logger.info("Asana webhook: %s events → sync %s project(s)", len(events), len(project_gids))
    return Response(status_code=200)


async def ensure_asana_webhooks() -> dict:
    """Register (or refresh) project webhooks when a public target URL is configured."""
    target = webhook_target_url()
    if not target or not settings.asana_configured:
        return {"enabled": False, "reason": "webhook target or Asana not configured"}

    asana = AsanaClient()
    db = SessionLocal()
    try:
        projects = await SyncService(db).discover_projects()
        existing = await asana.list_webhooks()
        by_resource = {
            str(w.get("resource", {}).get("gid")): w
            for w in existing
            if w.get("resource", {}).get("gid")
        }

        registered = []
        for project in projects:
            gid = project.gid
            current = by_resource.get(gid)
            if current and current.get("target") == target and not current.get("inactive"):
                registered.append({"project": project.name, "status": "existing"})
                continue
            try:
                await asana.create_webhook(gid, target)
                registered.append({"project": project.name, "status": "created"})
            except Exception as exc:
                logger.exception("Webhook register failed for %s", project.name)
                registered.append({"project": project.name, "status": "error", "error": str(exc)})

        _set_meta(db, "asana_webhooks_registered_at", datetime.utcnow().isoformat())
        return {"enabled": True, "target": target, "projects": registered}
    finally:
        db.close()
