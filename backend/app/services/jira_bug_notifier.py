"""Notify Google Chat when Jira Sub-Bug sub-tasks are created or change status."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Sequence

from app.config import get_settings
from app.services.status_move_notifier import _post_google_chat

logger = logging.getLogger(__name__)

_SUBTASK_TYPES = {
    "sub-task",
    "subtask",
    "sub-bug",
    "subbug",
    "sub bug",
    "bug",
    "defect",
}


@dataclass(frozen=True)
class JiraBugSubtaskEvent:
    bug_key: str
    bug_summary: str
    bug_url: str
    parent_key: str
    action: str  # created | status_changed
    status: str | None = None
    previous_status: str | None = None
    parent_summary: str | None = None
    parent_url: str | None = None
    assignee: str | None = None
    issue_type: str | None = None
    description: str | None = None


def _is_subtask_type(issue_type: str | None) -> bool:
    name = (issue_type or "").strip().lower()
    if not name:
        return False
    compact = name.replace(" ", "").replace("_", "-")
    if name in _SUBTASK_TYPES or compact in _SUBTASK_TYPES:
        return True
    if "sub" in name and ("bug" in name or "task" in name or "defect" in name):
        return True
    return False


def is_notifiable_bug_subtask(
    *,
    parent_key: str | None,
    issue_type: str | None,
) -> bool:
    """Sub-task / Sub-Bug (etc.) that sits under a parent requirement Jira."""
    if not (parent_key or "").strip():
        return False
    return _is_subtask_type(issue_type)


def _adf_to_plain(node: object) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(_adf_to_plain(n) for n in node)
    if not isinstance(node, dict):
        return ""
    parts: list[str] = []
    text = node.get("text")
    if isinstance(text, str):
        parts.append(text)
    for child in node.get("content") or []:
        parts.append(_adf_to_plain(child))
    return " ".join(p for p in parts if p)


def description_snippet(description: object, *, max_len: int = 220) -> str | None:
    plain = re.sub(r"\s+", " ", _adf_to_plain(description)).strip()
    if not plain:
        return None
    if len(plain) <= max_len:
        return plain
    return plain[: max_len - 1].rstrip() + "…"


def _action_label(event: JiraBugSubtaskEvent) -> str:
    status = (event.status or "Unknown").strip()
    if event.action == "created":
        return f"Created · *{status}*"
    prev = (event.previous_status or "").strip()
    if prev and prev.lower() != status.lower():
        return f"*{prev}* → *{status}*"
    return f"Status → *{status}*"


def _format_single_event(event: JiraBugSubtaskEvent) -> str:
    bug_key = f"<{event.bug_url}|{event.bug_key}>" if event.bug_url else event.bug_key
    parent_key = (
        f"<{event.parent_url}|{event.parent_key}>" if event.parent_url else event.parent_key
    )
    parent_summary = f" — {event.parent_summary}" if event.parent_summary else ""
    return (
        f"*Jira · {_action_label(event)}*\n"
        f"🐛 *{bug_key}*\n"
        f"↳ Parent: *{parent_key}*{parent_summary}"
    )


def _format_chat_message(events: Sequence[JiraBugSubtaskEvent]) -> str:
    return "\n\n".join(_format_single_event(e) for e in events)


def notify_cooldown_key(event: JiraBugSubtaskEvent) -> str:
    status = (event.status or "").strip().lower()
    return f"{event.bug_key}:{event.action}:{status}"


async def notify_jira_bug_subtasks(events: Sequence[JiraBugSubtaskEvent]) -> dict:
    settings = get_settings()
    result = {
        "attempted": False,
        "filtered_count": 0,
        "chat_sent": False,
        "messages_sent": 0,
        "skipped_reason": None,
    }
    if not settings.jira_bug_notify_enabled:
        result["skipped_reason"] = "disabled"
        return result
    if not events:
        result["skipped_reason"] = "no_events"
        return result

    result["filtered_count"] = len(events)
    result["attempted"] = True

    if not settings.google_chat_configured:
        result["skipped_reason"] = "no_channels_configured"
        return result

    webhook = settings.google_chat_webhook_url.strip()
    sent = 0
    try:
        for event in events:
            await _post_google_chat(webhook, _format_single_event(event))
            sent += 1
        result["chat_sent"] = sent > 0
        result["messages_sent"] = sent
    except Exception:
        logger.exception("Google Chat Jira bug-subtask notify failed")
        result["skipped_reason"] = "chat_failed"
        result["messages_sent"] = sent
        result["chat_sent"] = sent > 0

    return result
