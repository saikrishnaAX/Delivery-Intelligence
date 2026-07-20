"""Notify office when tickets move between Asana sprint stages (Google Chat + email)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Sequence

import httpx

from app.config import get_settings
from app.services.email_service import EmailService
from app.services.section_utils import (
    is_chat_status_move,
    is_testing_section,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StatusMoveEvent:
    title: str
    from_section: str
    to_section: str
    jira_key: str | None = None
    asana_url: str | None = None
    assignee: str | None = None


def _should_include(event: StatusMoveEvent, *, highlight_only: bool) -> bool:
    """Only Prioritized → … before Done (e.g. Dev→Test). No Done/Backlog/Released/noise."""
    if not is_chat_status_move(event.from_section, event.to_section):
        return False
    if highlight_only and not is_testing_section(event.to_section):
        return False
    return True


def _ticket_label(event: StatusMoveEvent) -> str:
    key = (event.jira_key or "").strip()
    title = (event.title or "Untitled").strip()
    if key:
        return f"{key} — {title}"
    return title


def _format_chat_message(project_name: str, events: Sequence[StatusMoveEvent]) -> str:
    lines = [f"*Sprint status updates* — {project_name}", ""]
    for e in events:
        label = _ticket_label(e)
        arrow = f"{e.from_section} → *{e.to_section}*"
        prefix = "🧪 Ready for QA: " if is_testing_section(e.to_section) else "• "
        extra = []
        if e.assignee:
            extra.append(e.assignee)
        if e.asana_url:
            extra.append(f"<{e.asana_url}|Asana>")
        suffix = f" ({', '.join(extra)})" if extra else ""
        lines.append(f"{prefix}{label}: {arrow}{suffix}")
    return "\n".join(lines)


def _format_email_bodies(
    project_name: str, events: Sequence[StatusMoveEvent]
) -> tuple[str, str]:
    text_lines = [
        f"Status moves detected for {project_name}:",
        "",
    ]
    html_rows: list[str] = []
    for e in events:
        label = _ticket_label(e)
        text_lines.append(f"- {label}: {e.from_section} → {e.to_section}")
        if e.assignee:
            text_lines.append(f"  Assignee: {e.assignee}")
        if e.asana_url:
            text_lines.append(f"  Asana: {e.asana_url}")
        link = (
            f' <a href="{e.asana_url}">Open in Asana</a>'
            if e.asana_url
            else ""
        )
        qa = " <strong>(Ready for QA)</strong>" if is_testing_section(e.to_section) else ""
        html_rows.append(
            "<tr>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{label}{qa}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{e.from_section}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee'><strong>{e.to_section}</strong>{link}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{e.assignee or '—'}</td>"
            "</tr>"
        )
    text_lines.append("")
    text_lines.append("— Autorox Command Center")
    html = (
        f"<p>Status moves detected for <strong>{project_name}</strong>:</p>"
        "<table cellpadding='0' cellspacing='0' style='border-collapse:collapse;font-family:sans-serif;font-size:14px'>"
        "<thead><tr>"
        "<th align='left' style='padding:6px 10px;border-bottom:2px solid #ccc'>Ticket</th>"
        "<th align='left' style='padding:6px 10px;border-bottom:2px solid #ccc'>From</th>"
        "<th align='left' style='padding:6px 10px;border-bottom:2px solid #ccc'>To</th>"
        "<th align='left' style='padding:6px 10px;border-bottom:2px solid #ccc'>Assignee</th>"
        "</tr></thead>"
        f"<tbody>{''.join(html_rows)}</tbody></table>"
        "<p style='color:#666;font-size:12px'>— Autorox Command Center</p>"
    )
    return "\n".join(text_lines), html


async def _post_google_chat(webhook_url: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(webhook_url, json={"text": text})
        resp.raise_for_status()


async def notify_status_moves(
    project_name: str,
    events: Sequence[StatusMoveEvent],
) -> dict:
    """Post a Google Chat message and/or email digest for this sync's moves."""
    settings = get_settings()
    result = {
        "attempted": False,
        "filtered_count": 0,
        "chat_sent": False,
        "email_sent": False,
        "skipped_reason": None,
    }
    if not settings.status_move_notify_enabled:
        result["skipped_reason"] = "disabled"
        return result

    filtered = [
        e
        for e in events
        if _should_include(e, highlight_only=settings.status_move_highlight_only)
    ]
    result["filtered_count"] = len(filtered)
    if not filtered:
        result["skipped_reason"] = "no_moves"
        return result

    result["attempted"] = True
    chat_text = _format_chat_message(project_name, filtered)
    email_text, email_html = _format_email_bodies(project_name, filtered)

    if settings.google_chat_configured:
        try:
            await _post_google_chat(settings.google_chat_webhook_url.strip(), chat_text)
            result["chat_sent"] = True
        except Exception:
            logger.exception("Google Chat status-move notify failed")
    else:
        logger.debug("Google Chat webhook not configured — skipping Chat notify")

    recipients = settings.status_move_email_recipients
    if recipients and settings.email_configured:
        try:
            EmailService().send_email(
                to_emails=recipients,
                subject=f"Sprint status updates — {project_name} ({len(filtered)})",
                body_text=email_text,
                body_html=email_html,
            )
            result["email_sent"] = True
        except Exception:
            logger.exception("Email status-move digest failed")
    elif not recipients:
        logger.debug("STATUS_MOVE_EMAIL_TO empty — skipping email digest")

    if not result["chat_sent"] and not result["email_sent"]:
        result["skipped_reason"] = "no_channels_configured"

    return result
