"""AI polish for release note items — grammar, terminology, and team document style."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

POLISH_SYSTEM = """You are a senior technical writer for Autorox GMS (garage management software).
Rewrite release note entries for a customer-facing Word document.

Rules:
- Fix grammar, spelling, and awkward BA phrasing; use clear professional English.
- Keep workshop/garage/customer names OUT (already redacted).
- Use GMS terminology: Job Card, Work Order, SKU Master, Service Advisor, Counter Sale, etc.
- Enhancement/performance items need: title (keep emoji if provided), summary (1-2 sentences),
  whats_new (1 concise paragraph OR 1-3 short bullets as strings), impact (label as impact_benefit).
- Bug items: short title, fix (one sentence starting with action verb — use field "fix" not summary).
- Security-related items: category "security", same structure as enhancement.
- module_affected: comma-separated modules (fix spacing/capitalization).
- release_category: one of "Enhancement", "Requirement", "Performance Improvement", "Bug Fix", "Security Enhancement".
- Do NOT invent features not implied by the source text.

Return ONLY valid JSON: {"items": [ ... same order as input ... ]}"""

BATCH_SIZE = 8


def _client() -> OpenAI | None:
    key = (settings.openai_api_key or "").strip()
    if not key or "your" in key.lower() and "key" in key.lower():
        return None
    return OpenAI(api_key=key)


def _rule_polish_item(item: dict[str, Any]) -> dict[str, Any]:
    """Lightweight fallback when OpenAI is unavailable."""
    out = dict(item)
    title = re.sub(r"\s+", " ", (item.get("title") or "").strip())
    out["title"] = title[0].upper() + title[1:] if title else title

    if item.get("category") == "bug":
        summary = (item.get("summary") or "").strip()
        fix = item.get("fix") or summary
        if fix and not fix.lower().startswith(("fix", "resolved", "corrected")):
            fix = f"Resolved {fix[0].lower()}{fix[1:]}" if fix else fix
        out["fix"] = fix[:300]
        out["impact"] = ""
        out["whats_new"] = []
        return out

    summary = re.sub(r"\s+", " ", (item.get("summary") or "").strip())
    if summary and not summary.endswith("."):
        summary += "."
    out["summary"] = summary

    whats = item.get("whats_new") or []
    if isinstance(whats, list) and whats:
        out["whats_new"] = [re.sub(r"\s+", " ", str(w).strip()) for w in whats if str(w).strip()][:3]
    impact = (item.get("impact") or "").strip()
    out["impact_benefit"] = impact if impact else item.get("impact_benefit", "")
    return out


def _merge_polished(original: dict[str, Any], polished: dict[str, Any]) -> dict[str, Any]:
    out = dict(original)
    for key in (
        "title", "emoji", "summary", "whats_new", "impact", "impact_benefit",
        "fix", "module_affected", "release_category", "category", "note",
    ):
        if key in polished and polished[key] not in (None, "", []):
            out[key] = polished[key]
    if out.get("fix") and out.get("category") == "bug":
        out["summary"] = out["fix"]
    if out.get("impact_benefit"):
        out["impact"] = out["impact_benefit"]
    return out


def polish_release_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not items:
        return items

    client = _client()
    if not client:
        return [_rule_polish_item(i) for i in items]

    polished_all: list[dict[str, Any]] = []
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start : start + BATCH_SIZE]
        payload = [
            {
                "title": i.get("title"),
                "category": i.get("category"),
                "release_category": i.get("release_category"),
                "module_affected": i.get("module_affected"),
                "summary": i.get("summary"),
                "whats_new": i.get("whats_new"),
                "impact": i.get("impact"),
                "emoji": i.get("emoji"),
                "raw_description_excerpt": (i.get("summary") or "")[:500],
            }
            for i in batch
        ]
        try:
            resp = client.chat.completions.create(
                model=settings.openai_model,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": POLISH_SYSTEM},
                    {
                        "role": "user",
                        "content": f"Polish these {len(batch)} release note items:\n{json.dumps(payload, ensure_ascii=False)}",
                    },
                ],
            )
            content = resp.choices[0].message.content or "{}"
            data = json.loads(content)
            batch_out = data.get("items") or data.get("polished") or []
            if len(batch_out) != len(batch):
                logger.warning("Polish batch size mismatch; using rule fallback for batch")
                polished_all.extend(_rule_polish_item(i) for i in batch)
            else:
                polished_all.extend(_merge_polished(o, p) for o, p in zip(batch, batch_out))
        except Exception:
            logger.exception("Release notes AI polish failed for batch; using rule fallback")
            polished_all.extend(_rule_polish_item(i) for i in batch)

    return polished_all
