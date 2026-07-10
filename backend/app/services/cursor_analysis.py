"""Cursor agent integration — contextual analysis for weekly CEO brief and issue enrich."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def cursor_available() -> bool:
    return settings.cursor_configured


def _extract_json(text: str) -> Any:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def _run_cursor_prompt(prompt: str, *, system: str | None = None) -> str | None:
    if not cursor_available():
        return None
    try:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
    except ImportError:
        logger.warning("cursor-sdk not installed — pip install cursor-sdk")
        return None

    messages_system = system or (
        "You are an engineering intelligence analyst for Autorox workshop software. "
        "Use ONLY facts provided. Return valid JSON only. "
        "Never invent ticket titles, root causes, or business impact without citing ticket ids. "
        "If evidence is weak, say so and use claim_tier hypothesis."
    )
    full_prompt = f"{messages_system}\n\n{prompt}"
    try:
        result = Agent.prompt(
            full_prompt,
            AgentOptions(
                api_key=settings.cursor_api_key.strip(),
                model=settings.cursor_model,
                local=LocalAgentOptions(cwd=str(PROJECT_ROOT)),
            ),
        )
        if result.status == "error":
            logger.error("Cursor agent run failed: %s", getattr(result, "id", ""))
            return None
        return (result.result or "").strip()
    except Exception:
        logger.exception("Cursor agent prompt failed")
        return None


def enrich_issue_group(
    issue_name: str,
    engineering_fix_key: str,
    engineering_fix_label: str,
    tickets: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Review a rule-based ticket group; return intelligence overlay or None."""
    if not tickets:
        return None

    ticket_ids = [t["id"] for t in tickets]
    prompt = (
        "Review whether these support tickets describe ONE engineering defect or should stay separate.\n\n"
        f"Issue name (rule-based): {issue_name}\n"
        f"Engineering area key: {engineering_fix_key}\n"
        f"Engineering area label: {engineering_fix_label}\n\n"
        f"Tickets JSON:\n{json.dumps(tickets[:20], ensure_ascii=False)}\n\n"
        "Return JSON object:\n"
        "{\n"
        '  "issue_name": "clear PM-friendly title",\n'
        '  "should_split": false,\n'
        '  "root_cause": "verified from tickets OR Insufficient evidence — ...",\n'
        '  "business_impact": "cite ticket ids and workshops OR say limited evidence",\n'
        '  "evidence_summary": "1-2 sentences citing actual ticket titles",\n'
        '  "customer_impact": "quote themes from titles",\n'
        '  "executive_summary": "2 sentences max, numbers from tickets only",\n'
        '  "confidence": 0.35-0.95,\n'
        '  "claim_tier": "verified|likely|hypothesis",\n'
        f'  "ticket_ids": subset of {ticket_ids}\n'
        "}\n"
        "Rules: ticket_ids must only include ids from the input list. "
        "Do not claim blocking unless tickets mention unable/failed/blocked. "
        "regression_test_cases must be [] unless a ticket explicitly documents a fix."
    )
    raw = _run_cursor_prompt(prompt)
    if not raw:
        return None
    try:
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return None
        returned_ids = [int(x) for x in (data.get("ticket_ids") or ticket_ids) if int(x) in ticket_ids]
        if not returned_ids:
            returned_ids = ticket_ids
        data["ticket_ids"] = returned_ids
        data["cursor_enriched"] = True
        data["analysis_source"] = "cursor"
        conf = data.get("confidence")
        if isinstance(conf, (int, float)):
            data["confidence"] = max(0.0, min(0.95, float(conf)))
        return data
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.exception("Invalid Cursor issue enrich JSON")
        return None


def build_ceo_brief_overlay(facts: dict[str, Any]) -> dict[str, Any] | None:
    """Generate CEO email narrative from verified metrics packet (numbers-only input)."""
    prompt = (
        "Write a CEO weekly engineering brief using ONLY the facts JSON below.\n"
        "Keep it minimal — CEO wants numbers and status reasons, not long narratives.\n"
        "Do not invent numbers. Do not claim AI caused quality changes.\n\n"
        f"FACTS:\n{json.dumps(facts, ensure_ascii=False, indent=2)}\n\n"
        "Return JSON:\n"
        "{\n"
        '  "ceo_brief": ["max 2 short headline sentences with numbers"],\n'
        '  "scorecard": [\n'
        '    {"name": "Engineering Delivery", "status": "improving|stable|watch|critical", '
        '"metric": "before → after with % (e.g. 11 → 18 enhancements/mo (+64%))", '
        '"status_reason": "one line: why this status tag"}\n'
        "    /* same for Product Quality, Release Stability, Customer Impact, "
        "Recurring Product Issues, AI Impact */\n"
        "  ],\n"
        '  "leadership_decisions": [{"decision": "...", "evidence": "one line with a number from facts"}],\n'
        '  "ai_impact": {"verdict": "positive|mixed|negative|insufficient", "summary": "one sentence"},\n'
        '  "leadership_questions": ["max 3 short questions"]\n'
        "}\n"
        "Do NOT include key_changes or risks — scorecard status_reason covers watch items."
    )
    raw = _run_cursor_prompt(prompt)
    if not raw:
        return None
    try:
        data = _extract_json(raw)
        if isinstance(data, dict):
            data["analysis_source"] = "cursor"
            data["generated_from"] = "weekly_facts_packet"
            return data
    except json.JSONDecodeError:
        logger.exception("Invalid Cursor CEO brief JSON")
    return None


def build_facts_packet(intelligence_data: dict[str, Any]) -> dict[str, Any]:
    """Strip CEO intelligence payload to high-confidence numbers for Cursor narrative."""
    qv = intelligence_data.get("ceo_quick_view") or {}
    bugs = qv.get("bugs") or {}
    d30 = (intelligence_data.get("quality_trends") or {}).get("windows", {}).get("last_30d") or {}
    health = intelligence_data.get("health_score") or {}
    recurring = intelligence_data.get("recurring_issues") or []
    modules = qv.get("modules") or []
    issues = qv.get("issues") or {}

    return {
        "period_note": "Weekly brief — narrative must cite these figures only",
        "ai_adoption_date": qv.get("ai_adoption_date") or intelligence_data.get("meta", {}).get("ai_adoption_date"),
        "bugs_per_month_pre": bugs.get("per_month_pre"),
        "bugs_per_month_post": bugs.get("per_month_post"),
        "enhancements_per_month_pre": bugs.get("enhancements_per_month_pre"),
        "enhancements_per_month_post": bugs.get("enhancements_per_month_post"),
        "bugs_total_pre": bugs.get("total_pre"),
        "bugs_total_post": bugs.get("total_post"),
        "health_score": health.get("score"),
        "health_label": health.get("label"),
        "bugs_last_30d": d30.get("bugs"),
        "enhancements_last_30d": d30.get("enhancements"),
        "critical_bugs_last_30d": d30.get("critical_bugs"),
        "reopened_last_30d": d30.get("reopened"),
        "workshops_affected_last_30d": d30.get("workshops_affected"),
        "clusters_existed_before_ai": issues.get("clusters_existed_before_ai"),
        "clusters_new_after_ai": issues.get("clusters_new_after_ai"),
        "top_recurring_issues": [
            {
                "name": r.get("name"),
                "ticket_count": r.get("ticket_count"),
                "open_count": r.get("open_count"),
                "workshops": r.get("workshops"),
                "trend": r.get("trend"),
                "claim_tier": (r.get("claim_tier") or "hypothesis"),
            }
            for r in recurring[:8]
        ],
        "product_areas": [
            {
                "area": m.get("area"),
                "per_month_pre": m.get("per_month_pre"),
                "per_month_post": m.get("per_month_post"),
                "status": m.get("status"),
            }
            for m in modules[:10]
        ],
        "monthly_bug_trend": (intelligence_data.get("charts") or {}).get("monthly_trends", [])[-6:],
        "ai_impact_note": (intelligence_data.get("ai_impact") or {}).get("note"),
    }
