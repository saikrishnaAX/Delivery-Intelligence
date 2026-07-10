"""Shared helpers for Asana section / stage names."""

import re

from app.config import get_settings

settings = get_settings()

# Sprint sheet tracks tickets across these Asana board columns (not Backlog / Released).
SPRINT_PIPELINE_SECTIONS: tuple[str, ...] = (
    "Prioritized",
    "Design/Spec- in progress",
    "Design/Spec - in progress",
    "Developing",
    "PR Raised",
    "Build in UAT",
    "Testing (UAT)",
    "Testing(UAT)",
    "Build in Pre Prod",
    "Build in Pre-Prod",
    "Testing(Pre-Prod)",
    "Testing (Pre-Prod)",
    "Done",
)

_PIPELINE_NORM = {re.sub(r"[\s\-_]+", "", s.lower()): s for s in SPRINT_PIPELINE_SECTIONS}


def normalize_section_name(name: str | None) -> str:
    return re.sub(r"[\s\-_]+", "", (name or "").strip().lower())


def is_released_section(name: str | None) -> bool:
    if not name:
        return False
    target = settings.asana_released_section_name.strip().lower()
    current = name.strip().lower()
    if current == target:
        return True
    return "released" in current and "release note" in current


def is_backlog_section(name: str | None) -> bool:
    return (name or "").strip().lower() == "backlog"


def is_prioritized_section(name: str | None) -> bool:
    if not name:
        return False
    target = settings.asana_sprint_section_name.strip().lower()
    return name.strip().lower() == target


def is_sprint_pipeline_section(name: str | None) -> bool:
    if not name or is_released_section(name) or is_backlog_section(name):
        return False
    return normalize_section_name(name) in _PIPELINE_NORM


def pipeline_section_order(name: str | None) -> int:
    norm = normalize_section_name(name)
    for idx, section in enumerate(SPRINT_PIPELINE_SECTIONS):
        if normalize_section_name(section) == norm:
            return idx
    return 999


def pipeline_section_progress_rank(name: str | None) -> int:
    """0 = Prioritized (not started), higher = further along; Done is highest."""
    order = pipeline_section_order(name)
    return order if order != 999 else -1


def sprint_sheet_display_sort_key(
    section_name: str | None,
    asana_board_index: int | None,
    ticket_id: int | None,
) -> tuple:
    """Done / in-progress first, Prioritized last; board order within each column."""
    stage = pipeline_section_progress_rank(section_name)
    board_idx = asana_board_index if asana_board_index is not None else 999999
    return (-stage, board_idx, ticket_id or 0)


def display_pipeline_status(section_name: str | None, sheet_status: str = "active") -> str:
    if sheet_status == "removed":
        return "Left sprint"
    if section_name and is_sprint_pipeline_section(section_name):
        return section_name
    return section_name or "Unknown"


def display_sprint_status(sheet_status: str, section_name: str | None = None) -> str:
    return display_pipeline_status(section_name, sheet_status)
