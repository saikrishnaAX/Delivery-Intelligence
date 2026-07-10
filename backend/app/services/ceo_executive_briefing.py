"""Executive Brief — interprets engineering data for CEO decision-making."""

from __future__ import annotations

from typing import Any, Literal

ExecStatus = Literal["improving", "stable", "watch", "critical"]
AiVerdict = Literal["positive", "mixed", "negative", "insufficient"]

# Plain business names — no engineering jargon in CEO copy
AREA_LABELS: dict[str, str] = {
    "Customer Concerns (AI)": "Customer Workflow",
    "Invoice & billing": "Invoice and Billing",
    "Job Card": "Job Card",
    "Reports": "Reports",
    "Notifications": "Customer Notifications",
    "PDF & print": "Documents and Printing",
    "Stock & parts": "Inventory and Parts",
    "Performance": "System Performance",
    "UI & display": "User Interface",
    "Integration & API": "Integrations",
    "Other": "General Product Areas",
}

SUBJECT_LINES: dict[str, str] = {
    "weekly": "CEO Weekly Engineering Brief",
    "monthly": "CEO Monthly Engineering Brief",
    "6months": "CEO Engineering and Product Health Summary",
}


def _pct(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    if before == 0:
        return 100.0 if after > 0 else 0.0
    return round((after - before) / before * 100, 1)


def _area_label(name: str | None) -> str:
    if not name:
        return "General Product Areas"
    return AREA_LABELS.get(name, name)


def _exec_status(delta_pct: float | None, *, higher_is_worse: bool, score: int | None = None) -> ExecStatus:
    if score is not None:
        if score >= 75:
            return "stable" if (delta_pct is None or abs(delta_pct or 0) < 8) else "improving"
        if score >= 55:
            return "watch"
        if score >= 40:
            return "watch"
        return "critical"
    if delta_pct is None or abs(delta_pct) < 8:
        return "stable"
    improving = (delta_pct < 0) if higher_is_worse else (delta_pct > 0)
    worsening = (delta_pct > 15) if higher_is_worse else (delta_pct < -15)
    if worsening:
        return "critical" if abs(delta_pct) > 25 else "watch"
    if improving:
        return "improving"
    return "stable"


def _fmt_pair(pre: float | None, post: float | None, unit: str, *, decimals: int = 0) -> str:
    """Before → after with optional delta for scorecard metrics."""
    if pre is None and post is None:
        return "Insufficient data"
    p = f"{pre:.{decimals}f}" if pre is not None else "—"
    a = f"{post:.{decimals}f}" if post is not None else "—"
    delta = _pct(pre, post)
    if delta is not None and abs(delta) >= 1:
        sign = "+" if delta > 0 else ""
        return f"{p} → {a} {unit} ({sign}{delta}%)"
    return f"{p} → {a} {unit}"


def _status_label(status: ExecStatus) -> str:
    return {
        "improving": "Improving",
        "stable": "Stable",
        "watch": "Watch",
        "critical": "Critical",
    }[status]


def build_executive_briefing(data: dict[str, Any], period: str = "weekly") -> dict[str, Any]:
    """Build CEO Executive Brief content from intelligence data."""
    qv = data.get("ceo_quick_view") or {}
    bugs = qv.get("bugs") or {}
    modules = qv.get("modules") or []
    issues = qv.get("issues") or {}
    health = data.get("health_score") or {}
    d7 = (data.get("quality_trends") or {}).get("windows", {}).get("last_7d") or {}
    d30 = (data.get("quality_trends") or {}).get("windows", {}).get("last_30d") or {}
    ai_before = (data.get("ai_impact") or {}).get("before") or {}
    ai_after = (data.get("ai_impact") or {}).get("after") or {}
    prod = (data.get("engineering_productivity") or {}).get("last_30d") or {}
    releases = (data.get("release_intelligence") or {}).get("last_30d") or {}
    recurring = data.get("recurring_issues") or []
    risks_raw = data.get("top_risks") or []
    monthly = (data.get("charts") or {}).get("monthly_trends") or []

    bug_pre, bug_post = bugs.get("per_month_pre"), bugs.get("per_month_post")
    enh_pre, enh_post = bugs.get("enhancements_per_month_pre"), bugs.get("enhancements_per_month_post")
    bug_delta = _pct(bug_pre, bug_post)
    enh_delta = _pct(enh_pre, enh_post)
    health_score = health.get("score", 50)
    rec_open = sum(r.get("open_count", 0) for r in recurring[:8])
    workshops = d30.get("workshops_affected", 0)
    bpr_b, bpr_a = ai_before.get("bugs_per_release"), ai_after.get("bugs_per_release")
    bpr_delta = _pct(bpr_b, bpr_a) if bpr_b and bpr_a else None
    pre_patterns = issues.get("clusters_existed_before_ai", 0)

    # Significant product-area shifts (plain labels)
    shifts: list[dict[str, Any]] = []
    for m in modules:
        pre, post = m.get("per_month_pre", 0), m.get("per_month_post", 0)
        delta = _pct(pre, post) if pre else None
        if delta is None or abs(delta) < 12:
            continue
        label = _area_label(m.get("area"))
        shifts.append({
            "area": label,
            "direction": "up" if post > pre else "down",
            "delta_pct": delta,
            "pre": pre,
            "post": post,
        })
    shifts.sort(key=lambda x: abs(x["delta_pct"]), reverse=True)

    rising = [s for s in shifts if s["direction"] == "up"]
    falling = [s for s in shifts if s["direction"] == "down"]
    worry = health_score < 55 or (bug_delta or 0) > 18 or d30.get("critical_bugs", 0) > 4
    ai_verdict, ai_why = _ai_verdict(bug_delta, enh_delta, pre_patterns)

    # ── §1 CEO Brief (max 2 sentences — headline only) ──
    if health_score >= 65 and abs(bug_delta or 0) < 10:
        ceo_brief = [
            "Overall engineering health is stable this period.",
            (
                f"Delivery is up {enh_delta:+.0f}% vs pre-AI while defects moved {bug_delta:+.0f}% — "
                "no area needs immediate escalation."
                if enh_delta is not None and bug_delta is not None
                else "No product area requires immediate escalation."
            ),
        ]
    elif worry:
        rising_names = ", ".join(s["area"] for s in rising[:2]) if rising else "quality signals"
        ceo_brief = [
            f"Leadership attention needed: {rising_names}.",
            f"Health score {health_score}/100 · {workshops} workshops affected in the last 30 days.",
        ]
    else:
        ceo_brief = [
            "Engineering delivery and quality are holding steady.",
            (
                f"{rec_open} open tickets in recurring patterns · "
                f"{workshops} workshops reported issues in 30 days."
            ),
        ]
    ceo_brief = ceo_brief[:2]

    # ── §2 Scorecard — metric + one-line status reason (no narrative depth) ──
    del_status = _exec_status(enh_delta, higher_is_worse=False)
    qual_status = _exec_status(bug_delta, higher_is_worse=True, score=health_score)
    rel_status = _exec_status(bpr_delta, higher_is_worse=True)
    cust_status: ExecStatus = "watch" if workshops > 12 else "stable" if workshops > 5 else "improving"
    rec_status: ExecStatus = "critical" if rec_open > 25 else "watch" if rec_open > 10 else "stable"
    ai_status: ExecStatus = {
        "positive": "improving",
        "mixed": "watch",
        "negative": "critical",
        "insufficient": "stable",
    }[ai_verdict]

    scorecard = [
        {
            "name": "Engineering Delivery",
            "status": del_status,
            "metric": _fmt_pair(enh_pre, enh_post, "enhancements/mo"),
            "status_reason": (
                f"{_status_label(del_status)}: shipping more product work post-AI adoption."
                if del_status == "improving"
                else f"{_status_label(del_status)}: delivery pace unchanged vs pre-AI baseline."
            ),
        },
        {
            "name": "Product Quality",
            "status": qual_status,
            "metric": f"{_fmt_pair(bug_pre, bug_post, 'bugs/mo')} · health {health_score}/100",
            "status_reason": (
                f"{_status_label(qual_status)}: defect intake within normal variance."
                if qual_status in ("stable", "improving")
                else f"{_status_label(qual_status)}: defect rate moved {bug_delta:+.0f}% vs pre-AI."
                if bug_delta is not None
                else f"{_status_label(qual_status)}: quality score below target."
            ),
        },
        {
            "name": "Release Stability",
            "status": rel_status,
            "metric": _fmt_pair(bpr_b, bpr_a, "bugs/release", decimals=1),
            "status_reason": (
                f"{_status_label(rel_status)}: fewer defects per release."
                if rel_status == "improving"
                else f"{_status_label(rel_status)}: defects per release unchanged."
                if rel_status == "stable"
                else f"{_status_label(rel_status)}: more defects reaching customers per release."
            ),
        },
        {
            "name": "Customer Impact",
            "status": cust_status,
            "metric": f"{workshops} workshops affected · {d30.get('bugs', 0)} bugs (30d)",
            "status_reason": (
                f"{_status_label(cust_status)}: limited workshop spread this period."
                if cust_status == "improving"
                else f"{_status_label(cust_status)}: {workshops} workshops hit in 30 days — monitor if rising."
                if cust_status == "watch"
                else f"{_status_label(cust_status)}: customer impact within expected range."
            ),
        },
        {
            "name": "Recurring Product Issues",
            "status": rec_status,
            "metric": f"{rec_open} open · {len(recurring)} patterns tracked",
            "status_reason": (
                f"{_status_label(rec_status)}: recurring patterns contained."
                if rec_status == "stable"
                else f"{_status_label(rec_status)}: {rec_open} open tickets in multi-workshop patterns."
            ),
        },
        {
            "name": "AI Impact",
            "status": ai_status,
            "metric": (
                f"Delivery {enh_delta:+.0f}% · defects {bug_delta:+.0f}% vs pre-AI"
                if enh_delta is not None and bug_delta is not None
                else "Insufficient post-adoption window"
            ),
            "status_reason": (ai_why.split(".")[0] + "." if ai_why else "Insufficient data."),
        },
    ]

    # ── Leadership decisions (2–3, cite numbers; no separate key-changes / risks blocks) ──
    decisions: list[dict[str, str]] = []
    if ai_verdict in ("positive", "insufficient", "mixed") and not worry:
        decisions.append({
            "decision": "Continue AI-assisted delivery rollout.",
            "evidence": f"Delivery {enh_delta:+.0f}% · defects {bug_delta:+.0f}% vs pre-AI baseline.",
        })
    for s in rising[:2]:
        decisions.append({
            "decision": f"Review {s['area']} before next customer-facing release.",
            "evidence": f"{s['pre']:.0f} → {s['post']:.0f} defects/mo ({s['delta_pct']:+.0f}%).",
        })
    if not rising and not worry:
        decisions.append({
            "decision": "No process changes recommended this week.",
            "evidence": f"Health {health_score}/100 ({health.get('label', 'stable')}).",
        })
    elif worry and len(decisions) < 3:
        decisions.append({
            "decision": "Monitor quality trends two more weeks before changing process.",
            "evidence": f"{d30.get('critical_bugs', 0)} critical bugs in 30d · {workshops} workshops affected.",
        })
    decisions = decisions[:3]

    # Legacy fields kept for Cursor overlay merge — not rendered in email
    key_changes: list[dict[str, str]] = []
    risks: list[dict[str, str]] = []

    # ── §6 Evidence — one chart, one table ──
    last_months = monthly[-6:] if monthly else []
    max_b = max((m.get("bugs", 0) for m in last_months), default=1) or 1
    bug_chart = [
        {"month": m.get("month", ""), "value": m.get("bugs", 0), "pct": max(8, int(m.get("bugs", 0) / max_b * 100))}
        for m in last_months
    ]
    attention_table = [
        {
            "area": _area_label(m.get("area")),
            "before": f"{m.get('per_month_pre', 0):.0f}",
            "current": f"{m.get('per_month_post', 0):.0f}",
            "direction": (
                "Rising" if m.get("per_month_post", 0) > m.get("per_month_pre", 0) * 1.1
                else "Falling" if m.get("per_month_post", 0) < m.get("per_month_pre", 0) * 0.9
                else "Stable"
            ),
        }
        for m in sorted(modules, key=lambda x: -(x.get("per_month_post") or 0))[:5]
    ]

    # ── Questions (max 3) ──
    questions: list[str] = []
    if rising:
        questions.append(f"Why are {rising[0]['area']} defects up {rising[0]['delta_pct']:+.0f}%?")
    if rec_open > 8:
        questions.append(f"Can we close the {rec_open} open recurring-pattern tickets faster?")
    questions.append("Is capacity balanced between delivery and quality this sprint?")
    questions = questions[:3]

    period_label = {
        "weekly": "Weekly Executive Brief",
        "monthly": "Monthly Executive Brief",
        "6months": "Six-Month Executive Brief",
    }.get(period, "Executive Brief")

    return {
        "period": period,
        "period_label": period_label,
        "subject": SUBJECT_LINES.get(period, "CEO Weekly Engineering Brief"),
        "ceo_brief": ceo_brief,
        "should_worry": worry,
        "health_label": health.get("label", "Average"),
        "scorecard": scorecard[:6],
        "key_changes": key_changes,
        "leadership_decisions": decisions,
        "risks": risks,
        "evidence": {
            "chart_title": "Are customer-reported defects accelerating or stabilising?",
            "chart": bug_chart,
            "table_title": "Product areas — average defects per month",
            "table": attention_table,
        },
        "ai_impact": {"verdict": ai_verdict, "summary": ai_why},
        "leadership_questions": questions[:5],
    }


def apply_cursor_brief_overlay(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge Cursor-generated narrative into rule-based brief; keep evidence chart/table from base."""
    if not overlay:
        return base
    merged = {**base}
    for key in (
        "ceo_brief",
        "scorecard",
        "leadership_decisions",
        "ai_impact",
        "leadership_questions",
    ):
        if overlay.get(key):
            merged[key] = overlay[key]
    # Normalise scorecard items from Cursor — ensure metric + status_reason
    sc = merged.get("scorecard") or []
    normalised = []
    for item in sc:
        row = dict(item)
        if not row.get("metric") and row.get("sentence"):
            row["metric"] = row.pop("sentence")
        if not row.get("status_reason"):
            row["status_reason"] = row.pop("sentence", "") or row.get("metric", "")
        normalised.append(row)
    if normalised:
        merged["scorecard"] = normalised
    merged["key_changes"] = []
    merged["risks"] = []
    merged["narrative_source"] = overlay.get("analysis_source", "cursor")
    merged["cursor_generated_at"] = overlay.get("generated_at")
    return merged


def _ai_verdict(
    bug_delta: float | None,
    enh_delta: float | None,
    pre_patterns: int,
) -> tuple[AiVerdict, str]:
    if bug_delta is None:
        return "insufficient", (
            "The post-adoption period is too short for a reliable conclusion. "
            "Development work is not tagged as AI-assisted in our systems."
        )

    delivery_up = (enh_delta or 0) > 12
    bugs_flat = abs(bug_delta or 0) < 10
    bugs_up = (bug_delta or 0) > 15
    mostly_preexisting = pre_patterns > 8

    if delivery_up and bugs_flat and mostly_preexisting:
        return "positive", (
            "Delivery has increased while customer-reported defects remain near the pre-adoption baseline. "
            "The majority of defect patterns pre-date AI. This is correlational — we cannot prove AI caused either outcome."
        )
    if bugs_up and not mostly_preexisting:
        return "negative", (
            "Defect intake has risen materially post-adoption with several new patterns. "
            "We cannot attribute this to AI without task-level tagging — treat as a quality signal."
        )
    if delivery_up and bugs_up:
        return "mixed", (
            "The team is shipping more while defects have edged up slightly. "
            "Most patterns existed before adoption. AI may be helping speed; legacy modules need tighter regression."
        )
    return "insufficient", (
        "Evidence is inconclusive. Defect rates are broadly flat versus pre-adoption. "
        "No change in AI strategy is warranted based on ticket data alone."
    )
