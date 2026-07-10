"""Classify sprint tickets as Bug vs Requirement/Enhancement from title and Asana Type."""

from __future__ import annotations

import re
from typing import Literal

from app.models import TicketCategory

SprintWorkType = Literal["bug", "requirement", "other"]

BUG_LABEL = "Bug"
ENHANCEMENT_LABEL = "Enhancement"
REQUIREMENT_LABEL = "Requirement"

# Title patterns — primary signal when Asana Type is not set.
BUG_TITLE_PATTERNS = (
    re.compile(r"\bnot (?:working|populated|visible|generating|fetching|updating|creating|displaying|showing|reflecting|sending|receiving|applied|saved|loaded|opening|closing)\b", re.I),
    re.compile(r"\bis not\b", re.I),
    re.compile(r"\bare not\b", re.I),
    re.compile(r"\bdoes not\b", re.I),
    re.compile(r"\bdoesn't\b", re.I),
    re.compile(r"\bunable to\b", re.I),
    re.compile(r"\bcannot\b", re.I),
    re.compile(r"\bcan't\b", re.I),
    re.compile(r"\bfailed\b", re.I),
    re.compile(r"\bfailure\b", re.I),
    re.compile(r"\berror\b", re.I),
    re.compile(r"\bincorrect\b", re.I),
    re.compile(r"\bwrong\b", re.I),
    re.compile(r"\bmissing\b", re.I),
    re.compile(r"\bduplicate\b", re.I),
    re.compile(r"\bmismatch\b", re.I),
    re.compile(r"\bblocker\b", re.I),
    re.compile(r"\bnot able\b", re.I),
    re.compile(r"\bstuck\b", re.I),
    re.compile(r"\bcrash(?:ed|ing)?\b", re.I),
    re.compile(r"\btimeout\b", re.I),
    re.compile(r"\bfix(?:ed|ing)?\b", re.I),
    re.compile(r"\bissue in\b", re.I),
    re.compile(r"\bissue with\b", re.I),
    re.compile(r"\binvestigation required\b", re.I),
)

REQ_TITLE_PATTERNS = (
    re.compile(r"^(?:add|implement|create|introduce|enable|build|integrate|develop|design)\b", re.I),
    re.compile(r"\badd(?:ing|ition|itional)?\s+(?:new|a|the)\b", re.I),
    re.compile(r"\bnew (?:feature|module|screen|flow|functionality|option|field|report|filter|button|tab|page)\b", re.I),
    re.compile(r"\bfeature request\b", re.I),
    re.compile(r"\benhancement\b", re.I),
    re.compile(r"\brequirement\b", re.I),
    re.compile(r"\bsupport for\b", re.I),
    re.compile(r"\bintegration with\b", re.I),
    re.compile(r"\bautomate\b", re.I),
    re.compile(r"\bprovide (?:an|a|the)?\s*(?:option|ability|feature)\b", re.I),
)


def _requirement_display(type_raw: str | None) -> str:
    raw = (type_raw or "").strip()
    lower = raw.lower()
    if "enhance" in lower:
        return ENHANCEMENT_LABEL
    if "feature" in lower:
        return "Feature"
    if "requirement" in lower:
        return REQUIREMENT_LABEL
    return ENHANCEMENT_LABEL


def _title_suggests_bug(title: str) -> bool:
    return any(p.search(title) for p in BUG_TITLE_PATTERNS)


def _title_suggests_requirement(title: str) -> bool:
    return any(p.search(title) for p in REQ_TITLE_PATTERNS)


GENERIC_ASANA_TYPES = frozenset({"", "task", "subtask", "story", "general", "milestone"})


def classify_work_type(
    title: str,
    description: str | None = None,
    type_raw: str | None = None,
    support_category: TicketCategory | None = None,
) -> tuple[SprintWorkType, str]:
    """
    Bug — broken/missing/failing in the current setup.
    Requirement/Enhancement — new capability, addition, or greenfield work.
    Uses ticket title as the main signal when Asana Type is blank.
    """
    raw = (type_raw or "").strip()
    raw_lower = raw.lower()

    if support_category == TicketCategory.BUG:
        return "bug", BUG_LABEL

    if support_category == TicketCategory.ENHANCEMENT:
        return "requirement", _requirement_display(raw)

    if raw_lower and raw_lower not in GENERIC_ASANA_TYPES and "bug" in raw_lower:
        return "bug", BUG_LABEL

    if raw_lower and raw_lower not in GENERIC_ASANA_TYPES and any(
        w in raw_lower for w in ("requirement", "enhance", "feature")
    ):
        return "requirement", _requirement_display(raw)

    # Title is the primary classifier when Asana Type is blank or generic (Task, etc.).
    title_bug = _title_suggests_bug(title)
    title_req = _title_suggests_requirement(title)
    if title_bug and not title_req:
        return "bug", BUG_LABEL
    if title_req and not title_bug:
        return "requirement", _requirement_display(raw)

    # Light description fallback when title is ambiguous.
    desc = (description or "")[:500]
    if desc:
        if _title_suggests_bug(desc) and not _title_suggests_requirement(desc):
            return "bug", BUG_LABEL
        if _title_suggests_requirement(desc) and not _title_suggests_bug(desc):
            return "requirement", _requirement_display(raw)

    # Both or neither — additive verbs in title lean requirement, else bug (support default).
    if title_req:
        return "requirement", ENHANCEMENT_LABEL
    return "bug", BUG_LABEL


def work_type_bucket(row: dict) -> SprintWorkType:
    wt = row.get("work_type")
    if wt in ("bug", "requirement"):
        return wt
    label = (row.get("ticket_type") or "").lower()
    if "bug" in label:
        return "bug"
    if any(w in label for w in ("requirement", "enhance", "feature")):
        return "requirement"
    title = row.get("title") or ""
    if _title_suggests_requirement(title) and not _title_suggests_bug(title):
        return "requirement"
    return "bug"
