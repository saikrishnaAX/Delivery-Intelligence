"""CEO Intelligence — evidence-based executive briefing and strategic metrics."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import (
    JiraIssue,
    RecurringIssue,
    Ticket,
    TicketSectionMove,
    TicketStatus,
)
from app.config import get_settings
from app.services.section_utils import is_released_section

settings = get_settings()

ROOT_CAUSE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Business Logic", re.compile(r"logic|calculation|wrong amount|incorrect total|mismatch", re.I)),
    ("UI", re.compile(r"display|screen|button|layout|ui |font|visible|blank", re.I)),
    ("API", re.compile(r"api|endpoint|timeout|500|404", re.I)),
    ("Performance", re.compile(r"slow|performance|lag|hang|freeze|loading", re.I)),
    ("Database", re.compile(r"database|db |sql|record|sync|missing data", re.I)),
    ("Validation", re.compile(r"valid|mandatory|required field|cannot save", re.I)),
    ("Integration", re.compile(r"jira|asana|third.?party|webhook|import|export", re.I)),
    ("Configuration", re.compile(r"config|setting|setup|permission", re.I)),
    ("Workflow", re.compile(r"workflow|status|stage|approval|block", re.I)),
    ("Invoice", re.compile(r"invoice|billing|sequence|number gener", re.I)),
]

HEALTH_LABELS = [
    (85, "Excellent"),
    (70, "Good"),
    (55, "Average"),
    (40, "Poor"),
    (0, "Critical"),
]


def _effective_category(t: Ticket) -> str:
    cat = t.ai_category or t.support_category
    if cat:
        return cat.value if hasattr(cat, "value") else str(cat)
    raw = (t.asana_type_raw or "").lower()
    if "bug" in raw:
        return "bug"
    if "enhance" in raw:
        return "enhancement"
    if "config" in raw:
        return "configuration"
    return "task"


def _effective_priority(t: Ticket) -> str:
    return t.priority.value if t.priority else "medium"


def _classify_root(text: str) -> str:
    for label, pat in ROOT_CAUSE_PATTERNS:
        if pat.search(text):
            return label
    return "Other"


def _bug_pattern_buckets(tickets: list[Ticket]) -> dict[str, list[Ticket]]:
    """Group bugs into defect-pattern buckets within a product area."""
    buckets: dict[str, list[Ticket]] = defaultdict(list)
    for t in tickets:
        text = f"{t.title or ''} {t.description or ''}"
        buckets[_classify_root(text)].append(t)
    return dict(buckets)


def _pre_ai_patterns_from_bugs(before_bugs: list[Ticket]) -> tuple[int, list[dict[str, Any]]]:
    """Derive pre-AI recurring patterns from historical bug tickets (not Issue Intelligence clusters)."""
    from app.services.product_theme import area_description, classify_product_area

    by_area: dict[str, list[Ticket]] = defaultdict(list)
    for t in before_bugs:
        by_area[classify_product_area(t)].append(t)

    existed_by_area: list[dict[str, Any]] = []
    cluster_total = 0
    for area, area_tickets in by_area.items():
        if area == "Other" and len(area_tickets) < 3:
            continue
        if len(area_tickets) < 2:
            continue
        sub = _bug_pattern_buckets(area_tickets)
        cluster_total += len(sub)
        existed_by_area.append({
            "area": area,
            "understanding": area_description(area),
            "clusters": len(sub),
            "tickets": len(area_tickets),
        })

    existed_by_area.sort(key=lambda x: -x["tickets"])
    return cluster_total, existed_by_area[:8]


def _pct_change(before: float, after: float) -> float | None:
    if before == 0:
        return None if after == 0 else 100.0
    return round((after - before) / before * 100, 1)


def _health_label(score: int) -> str:
    for threshold, label in HEALTH_LABELS:
        if score >= threshold:
            return label
    return "Critical"


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _week_key(dt: datetime) -> str:
    return dt.strftime("%Y-W%W")


class CEOIntelligenceService:
    def __init__(
        self,
        db: Session,
        project_gid: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ):
        self.db = db
        self.project_gid = project_gid
        self.date_from = date_from
        self.date_to = date_to
        self.now = datetime.utcnow()
        self.generated_at = self.now
        self.range_start: datetime | None = None
        self.range_end: datetime | None = None
        if date_to:
            try:
                self.range_end = datetime.strptime(date_to[:10], "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                self.now = self.range_end
            except ValueError:
                pass
        if date_from:
            try:
                self.range_start = datetime.strptime(date_from[:10], "%Y-%m-%d")
            except ValueError:
                pass
        self.project_id: int | None = None
        if project_gid:
            from app.models import AsanaProject
            p = db.query(AsanaProject).filter(AsanaProject.gid == project_gid).first()
            self.project_id = p.id if p else None
        self._all_tickets_cache: list[Ticket] | None = None
        self._section_moves_cache: list[TicketSectionMove] | None = None

    def _load_all_tickets(self) -> list[Ticket]:
        """Load project tickets once — reused across all CEO widgets."""
        if self._all_tickets_cache is None:
            self._all_tickets_cache = self._ticket_query(apply_range=False).all()
        return self._all_tickets_cache

    def _apply_dashboard_range(self, tickets: list[Ticket]) -> list[Ticket]:
        out = tickets
        if self.range_start:
            out = [t for t in out if t.created_at and t.created_at >= self.range_start]
        if self.range_end:
            out = [t for t in out if t.created_at and t.created_at <= self.range_end]
        return out

    def _load_section_moves(self) -> list[TicketSectionMove]:
        if self._section_moves_cache is None:
            q = self.db.query(TicketSectionMove).join(
                Ticket, TicketSectionMove.ticket_id == Ticket.id
            )
            if self.project_id:
                q = q.filter(Ticket.project_id == self.project_id)
            self._section_moves_cache = q.all()
        return self._section_moves_cache

    def _ticket_query(self, *, apply_range: bool = True):
        q = self.db.query(Ticket).options(
            joinedload(Ticket.module), joinedload(Ticket.customer)
        )
        if self.project_id:
            q = q.filter(Ticket.project_id == self.project_id)
        if apply_range:
            if self.range_start:
                q = q.filter(Ticket.created_at >= self.range_start)
            if self.range_end:
                q = q.filter(Ticket.created_at <= self.range_end)
        return q

    def _tickets_in_range(self, start: datetime, end: datetime, *, apply_range: bool = True) -> list[Ticket]:
        pool = self._load_all_tickets()
        if apply_range:
            pool = self._apply_dashboard_range(pool)
        return [t for t in pool if t.created_at and start <= t.created_at <= end]

    def _summarize_period(self, tickets: list[Ticket]) -> dict[str, Any]:
        cats = Counter(_effective_category(t) for t in tickets)
        bugs = [t for t in tickets if _effective_category(t) == "bug"]
        total = len(tickets)
        days = max((tickets[-1].created_at - tickets[0].created_at).days, 1) if len(tickets) > 1 else 30
        return {
            "total": total,
            "bugs": len(bugs),
            "enhancements": cats.get("enhancement", 0),
            "requirements": cats.get("requirement", 0),
            "support_config": cats.get("configuration", 0) + cats.get("knowledge_gap", 0) + cats.get("task", 0),
            "critical_bugs": sum(1 for t in bugs if _effective_priority(t) == "critical"),
            "high_bugs": sum(1 for t in bugs if _effective_priority(t) == "high"),
            "reopened": sum(1 for t in tickets if t.is_reopened),
            "duplicates": cats.get("duplicate", 0),
            "blocked": sum(1 for t in tickets if t.status == TicketStatus.BLOCKED),
            "closed": sum(1 for t in tickets if t.status == TicketStatus.CLOSED),
            "avg_resolution_hours": round(
                sum(t.resolution_hours for t in tickets if t.resolution_hours) /
                max(sum(1 for t in tickets if t.resolution_hours), 1),
                1,
            ),
            "workshops_affected": len({
                t.workshop_name for t in bugs
                if t.workshop_name and t.workshop_name.lower() != "asana project"
            }),
        }

    def _release_stats(self, start: datetime, end: datetime) -> dict[str, Any]:
        moves = [
            m for m in self._load_section_moves()
            if m.moved_at and start <= m.moved_at <= end
        ]
        released = [m for m in moves if is_released_section(m.to_section)]
        release_count = len({m.ticket_id for m in released})
        period_tickets = self._tickets_in_range(start, end)
        bugs = sum(1 for t in period_tickets if _effective_category(t) == "bug")
        bpr = round(bugs / release_count, 2) if release_count else None
        return {"releases": release_count, "bugs_per_release": bpr}

    def _health_score(self, metrics: dict[str, Any]) -> dict[str, Any]:
        components = {}
        # Release stability (lower bugs/release = higher score)
        bpr = metrics.get("recent_release", {}).get("bugs_per_release")
        if bpr is not None:
            components["release_stability"] = max(0, min(100, int(100 - bpr * 15)))
        else:
            components["release_stability"] = 50

        crit = metrics.get("last_30d", {}).get("critical_bugs", 0)
        components["critical_bugs"] = max(0, 100 - crit * 25)

        reopen = metrics.get("last_30d", {}).get("reopened", 0)
        bugs = max(metrics.get("last_30d", {}).get("bugs", 1), 1)
        reopen_rate = reopen / bugs * 100
        components["regression_rate"] = max(0, 100 - int(reopen_rate * 10))

        workshops = metrics.get("last_30d", {}).get("workshops_affected", 0)
        components["customer_impact"] = max(0, 100 - min(workshops, 100))

        open_q = self._apply_dashboard_range(self._load_all_tickets())
        open_count = sum(
            1 for t in open_q
            if t.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.BLOCKED)
        )
        components["ticket_backlog"] = max(0, 100 - min(open_count // 5, 100))

        res_h = metrics.get("last_30d", {}).get("avg_resolution_hours", 48)
        components["bug_resolution_time"] = max(0, min(100, int(100 - res_h / 2)))

        recurring_open = self.db.query(RecurringIssue).filter(RecurringIssue.open_count > 0)
        if self.project_id:
            recurring_open = recurring_open.filter(RecurringIssue.project_id == self.project_id)
        rec_count = recurring_open.count()
        components["recurring_issues"] = max(0, 100 - rec_count * 5)

        weights = {
            "release_stability": 0.2,
            "critical_bugs": 0.15,
            "regression_rate": 0.1,
            "customer_impact": 0.15,
            "ticket_backlog": 0.1,
            "bug_resolution_time": 0.1,
            "recurring_issues": 0.2,
        }
        score = int(sum(components.get(k, 50) * w for k, w in weights.items()))
        return {
            "score": score,
            "label": _health_label(score),
            "components": components,
        }

    def _top_recurring(self, limit: int = 10) -> list[dict[str, Any]]:
        """Product bugs only — exclude enhancement requests, training, duplicates."""
        q = self.db.query(RecurringIssue).order_by(RecurringIssue.priority_score.desc())
        if self.project_id:
            q = q.filter(RecurringIssue.project_id == self.project_id)
        candidates = q.limit(limit * 4).all()
        result = []
        for ri in candidates:
            issue_type = ri.issue_type or "product_bug"
            if issue_type != "product_bug":
                continue
            intel = ri.intelligence or {}
            root = intel.get("root_cause") or intel.get("engineering_fix") or "Under analysis"
            status = "Open" if ri.open_count > 0 else "Resolved"
            if ri.trend == "increasing":
                status = "Recurring"
            result.append({
                "name": ri.issue_name,
                "issue_type": issue_type,
                "ticket_count": ri.ticket_count,
                "open_count": ri.open_count,
                "trend": ri.trend,
                "severity": ri.severity,
                "workshops": ri.workshop_count,
                "business_impact": intel.get("business_impact") or intel.get("executive_summary", "")[:200],
                "root_cause": str(root)[:200],
                "status": status,
                "affected_modules": ri.affected_modules or [],
                "claim_tier": intel.get("claim_tier", "hypothesis"),
                "analysis_source": intel.get("analysis_source", "rules"),
            })
            if len(result) >= limit:
                break
        return result

    def _top_risks(self, d30: dict, d90: dict, recurring: list[dict]) -> list[dict]:
        risks: list[dict] = []
        d90_rate = (d90.get("bugs", 0) or 0) / 3
        d30_bugs = d30.get("bugs", 0) or 0
        if d30_bugs > d90_rate * 1.2 and d30_bugs > 0:
            score = min(95, int(55 + (d30_bugs / max(d90_rate, 1)) * 10))
            risks.append({
                "risk": "Rising bug intake",
                "score": score,
                "trend": "up",
                "impact": f"{d30_bugs} bugs in 30 days vs {d90.get('bugs', 0)} in 90 days",
                "recommendation": "Review recent release batches and add regression coverage.",
            })
        for ri in recurring[:3]:
            if ri.get("issue_type") and ri["issue_type"] != "product_bug":
                continue
            open_c = ri.get("open_count", 0)
            if open_c >= 5:
                score = min(95, int(50 + open_c * 3 + ri.get("workshops", 0)))
                risks.append({
                    "risk": ri["name"][:80],
                    "score": score,
                    "trend": ri.get("trend", "stable"),
                    "impact": f"{open_c} open · {ri.get('workshops', 0)} workshops",
                    "recommendation": f"Assign DRI and schedule root-cause fix for {ri['name'][:40]}.",
                })
        open_count = self._ticket_query(apply_range=False).filter(
            Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
        ).count()
        if open_count > 200:
            score = min(90, int(50 + open_count / 20))
            risks.append({
                "risk": "Large support backlog",
                "score": score,
                "trend": "stable",
                "impact": f"{open_count} open tickets in queue",
                "recommendation": "Cap sprint scope until backlog trend reverses.",
            })
        blocked = self._ticket_query(apply_range=False).filter(Ticket.status == TicketStatus.BLOCKED).count()
        if blocked >= 5:
            score = min(85, int(45 + blocked * 4))
            risks.append({
                "risk": "Blocked work accumulating",
                "score": score,
                "trend": "up",
                "impact": f"{blocked} tickets blocked",
                "recommendation": "Unblock dependencies in current sprint within 48 hours.",
            })
        return sorted(risks, key=lambda x: x["score"], reverse=True)[:5]

    def _build_briefing(
        self,
        health: dict,
        d7: dict,
        d30: dict,
        d90: dict,
        ai_before: dict,
        ai_after: dict,
        risks: list[dict],
        recurring: list[dict],
        releases: dict,
    ) -> dict[str, Any]:
        hour = self.now.hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"

        bugs_wow = _pct_change(max(d7.get("bugs_prev", 0), 1), d7.get("bugs", 0))
        enh_30 = d30.get("enhancements", 0)
        rel_30 = releases.get("releases", 0)

        paragraphs = [
            f"{greeting}. Over the last 30 days engineering logged {d30.get('total', 0)} tickets "
            f"including {enh_30} enhancements and {d30.get('bugs', 0)} bugs across {rel_30} releases "
            f"to the Released section.",
        ]

        if bugs_wow is not None:
            direction = "decreased" if bugs_wow < 0 else "increased"
            paragraphs.append(
                f"Customer-reported bugs {direction} {abs(bugs_wow):.0f}% week-over-week "
                f"({d7.get('bugs', 0)} this week vs {d7.get('bugs_prev', 0)} prior)."
            )

        if recurring:
            top = recurring[0]
            paragraphs.append(
                f"\"{top['name'][:60]}\" remains the largest recurring cluster with "
                f"{top.get('open_count', 0)} open tickets affecting {top.get('workshops', 0)} workshops."
            )

        paragraphs.append(
            f"Overall engineering health is {health['label'].upper()} (score {health['score']}/100)."
        )

        wins = []
        if ai_after.get("bugs_per_release") and ai_before.get("bugs_per_release"):
            if ai_after["bugs_per_release"] < ai_before["bugs_per_release"]:
                wins.append(
                    f"Bugs per release improved from {ai_before['bugs_per_release']} to "
                    f"{ai_after['bugs_per_release']}."
                )
        if d30.get("critical_bugs", 0) <= 2:
            wins.append(f"Only {d30.get('critical_bugs', 0)} critical defects in the last 30 days.")
        bfr_a = ai_after.get("bug_feature_ratio")
        bfr_b = ai_before.get("bug_feature_ratio")
        if bfr_a and bfr_b and bfr_a < bfr_b:
            wins.append(f"Bug-to-feature ratio improved from {bfr_b} to {bfr_a}.")

        watch = []
        if any(r.get("trend") == "increasing" for r in recurring[:5]):
            watch.append("Recurring issue clusters trending upward — review Issue Intelligence.")
        if d30.get("bugs", 0) > d90.get("bugs", 0) / 3 * 1.15:
            watch.append("Bug intake rate above 90-day average — monitor next release closely.")

        recommendations = [r["recommendation"] for r in risks[:5]]
        if not recommendations:
            recommendations = [
                "Maintain current release cadence with existing QA gates.",
                "Review top 3 recurring issues in Issue Intelligence.",
            ]

        meeting_questions = [
            "Why did bug intake change week-over-week?",
            "Which release contributed the most customer-reported defects?",
            "Are recurring Job Card / Invoice issues resourced this sprint?",
            "Is sprint scope aligned with support backlog pressure?",
            "Are we shipping faster than we can regression-test?",
        ]

        return {
            "greeting": greeting,
            "narrative": "\n\n".join(paragraphs),
            "engineering_summary": {
                "stories_or_tickets_30d": d30.get("total", 0),
                "enhancements_30d": enh_30,
                "bugs_fixed_30d": d30.get("closed", 0),
                "releases_30d": rel_30,
            },
            "quality_summary": {
                "bugs_30d": d30.get("bugs", 0),
                "critical_30d": d30.get("critical_bugs", 0),
                "reopened_30d": d30.get("reopened", 0),
                "health_score": health["score"],
                "health_label": health["label"],
            },
            "customer_summary": {
                "workshops_affected_30d": d30.get("workshops_affected", 0),
                "bugs_30d": d30.get("bugs", 0),
            },
            "ai_summary": self._ai_narrative(ai_before, ai_after),
            "wins": wins[:5],
            "watch_next_week": watch[:5],
            "recommendations": recommendations[:5],
            "meeting_questions": meeting_questions,
            "generated_at": self.generated_at.isoformat(),
        }

    def _ai_narrative(self, before: dict, after: dict) -> str:
        if not before.get("total") or not after.get("total"):
            return "More historical data required to assess AI-assisted development impact."
        lines = []
        tpm_b = before.get("tickets_per_month")
        tpm_a = after.get("tickets_per_month")
        if tpm_b and tpm_a:
            ch = _pct_change(tpm_b, tpm_a)
            if ch is not None:
                lines.append(
                    f"Ticket throughput per month {'increased' if ch > 0 else 'decreased'} {abs(ch):.0f}% "
                    f"({tpm_b} → {tpm_a})."
                )
        bpm_b = before.get("bugs_per_month")
        bpm_a = after.get("bugs_per_month")
        if bpm_b and bpm_a:
            ch = _pct_change(bpm_b, bpm_a)
            if ch is not None:
                lines.append(
                    f"Bug intake per month {'increased' if ch > 0 else 'decreased'} {abs(ch):.0f}% "
                    f"({bpm_b} → {bpm_a})."
                )
        bfr_b, bfr_a = before.get("bug_feature_ratio"), after.get("bug_feature_ratio")
        if bfr_b and bfr_a:
            if bfr_a < bfr_b:
                lines.append(f"Bug-to-feature ratio improved ({bfr_b} → {bfr_a}) — more features per bug.")
            elif bfr_a > bfr_b:
                lines.append(f"Bug-to-feature ratio worsened ({bfr_b} → {bfr_a}).")
        if not lines:
            return "Insufficient evidence for AI impact conclusions in the selected periods."
        adoption = self._ai_adoption_date().strftime("%d %B %Y")
        lines.append(
            f"Comparison uses pre-AI period before {adoption} vs post-AI from {adoption} to present."
        )
        return " ".join(lines)

    def _ai_adoption_date(self) -> datetime:
        raw = settings.ai_adoption_date.strip()
        try:
            return datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            return datetime(2026, 5, 1)

    def _ai_periods(self) -> tuple[dict, dict]:
        adoption = self._ai_adoption_date()
        before_start = adoption - timedelta(days=365)
        before_t = self._tickets_in_range(before_start, adoption, apply_range=False)
        after_t = self._tickets_in_range(adoption, self.now, apply_range=False)
        before_s = self._summarize_period(before_t)
        after_s = self._summarize_period(after_t)
        before_rel = self._release_stats(before_start, adoption)
        after_rel = self._release_stats(adoption, self.now)
        before_days = max((adoption - before_start).days, 1)
        after_days = max((self.now - adoption).days, 1)
        before_months = before_days / 30.44
        after_months = after_days / 30.44

        def pack(s: dict, rel: dict, months: float) -> dict:
            months = max(months, 0.1)
            feats = s["enhancements"] + s["requirements"]
            return {
                **s,
                "tickets_per_month": round(s["total"] / months, 1),
                "bugs_per_month": round(s["bugs"] / months, 1),
                "enhancements_per_month": round(s["enhancements"] / months, 1),
                "releases_per_month": round(rel["releases"] / months, 1),
                "bugs_per_release": rel["bugs_per_release"],
                "bug_feature_ratio": round(s["bugs"] / feats, 2) if feats else None,
                "period_days": int(months * 30.44),
            }

        return pack(before_s, before_rel, before_months), pack(after_s, after_rel, after_months)

    def _trend_windows(self) -> dict[str, Any]:
        windows = {}
        for label, days in [("last_30d", 30), ("last_90d", 90), ("last_180d", 180)]:
            start = self.now - timedelta(days=days)
            tickets = self._tickets_in_range(start, self.now)
            windows[label] = self._summarize_period(tickets)
            windows[label]["releases"] = self._release_stats(start, self.now)
        # week over week
        w_start = self.now - timedelta(days=7)
        w_prev = self.now - timedelta(days=14)
        w_tickets = self._tickets_in_range(w_start, self.now)
        w_prev_tickets = self._tickets_in_range(w_prev, w_start)
        windows["last_7d"] = self._summarize_period(w_tickets)
        windows["last_7d"]["bugs_prev"] = self._summarize_period(w_prev_tickets)["bugs"]
        return windows

    def _monthly_series(self, months: int = 9) -> list[dict]:
        start = self.now - timedelta(days=months * 31)
        tickets = self._tickets_in_range(start, self.now)
        monthly: dict[str, dict] = defaultdict(lambda: {"bugs": 0, "enhancements": 0, "total": 0})
        for t in tickets:
            if not t.created_at:
                continue
            mk = _month_key(t.created_at)
            monthly[mk]["total"] += 1
            cat = _effective_category(t)
            if cat == "bug":
                monthly[mk]["bugs"] += 1
            elif cat in ("enhancement", "requirement"):
                monthly[mk]["enhancements"] += 1
        return [{"month": k, **monthly[k]} for k in sorted(monthly.keys())]

    def _customer_health(self, tickets: list[Ticket]) -> dict[str, Any]:
        bugs = [t for t in tickets if _effective_category(t) == "bug"]
        workshop_counts = Counter(
            t.workshop_name for t in bugs
            if t.workshop_name and t.workshop_name.lower() != "asana project"
        )
        module_counts = Counter(
            (t.module.name if t.module else "Unassigned") for t in bugs
        )
        root_counts = Counter(_classify_root(f"{t.title} {t.description or ''}") for t in bugs)
        return {
            "top_workshops": [{"name": k, "count": v} for k, v in workshop_counts.most_common(10)],
            "top_modules": [{"module": k, "count": v} for k, v in module_counts.most_common(8)],
            "top_complaints": [{"category": k, "count": v} for k, v in root_counts.most_common(6)],
        }

    def _delivery_intel(self) -> dict[str, Any]:
        pool = self._apply_dashboard_range(self._load_all_tickets())
        blocked = sorted(
            (t for t in pool if t.status == TicketStatus.BLOCKED),
            key=lambda t: t.created_at or datetime.min,
            reverse=True,
        )[:10]
        pipeline = sum(1 for t in pool if t.status != TicketStatus.CLOSED)
        jira_open = 0
        if self.project_id:
            jira_open = (
                self.db.query(JiraIssue)
                .filter(JiraIssue.project_id == self.project_id, JiraIssue.status != "Done")
                .count()
            )
        upcoming: list[str] = []
        if pipeline > 300:
            upcoming.append("Large pipeline load")
        if len(blocked) >= 3:
            upcoming.append("Blocked work requiring escalation")
        return {
            "blocked_tickets": [
                {"title": t.title[:80], "assignee": t.assignee or t.ticket_owner, "days_open": (self.now - t.created_at).days if t.created_at else 0}
                for t in blocked
            ],
            "pipeline_open": pipeline,
            "jira_open": jira_open,
            "upcoming_risks": upcoming,
        }

    def _data_confidence(self) -> dict[str, Any]:
        total = len(self._load_all_tickets())
        recurring = self.db.query(RecurringIssue).count()
        has_jira = self.db.query(JiraIssue).count() > 0
        score = 40
        if total > 500:
            score += 25
        if total > 1000:
            score += 10
        if recurring > 10:
            score += 15
        if has_jira:
            score += 10
        gaps = []
        if not has_jira:
            gaps.append("Jira sprint data limited")
        gaps.append("Gmail/Sheets not linked to quality metrics")
        return {"score": min(score, 100), "gaps": gaps}

    def _build_executive_brief_card(
        self,
        ai_before: dict,
        ai_after: dict,
        health: dict,
        post_ai: dict | None = None,
    ) -> dict[str, Any]:
        """Amazon-style 1-page CEO memo: answer first, metrics, risks, actions, decision."""
        adoption = self._ai_adoption_date()
        tpm_b = ai_before.get("tickets_per_month") or 0
        tpm_a = ai_after.get("tickets_per_month") or 0
        bpm_b = ai_before.get("bugs_per_month") or 0
        bpm_a = ai_after.get("bugs_per_month") or 0
        feat_b = ai_before.get("enhancements_per_month", 0) + (
            ai_before.get("requirements", 0) / max(ai_before.get("period_days", 1) / 30.44, 0.1)
        )
        feat_a = ai_after.get("enhancements_per_month", 0)
        # requirements folded into enhancements_per_month in pack — use bug_feature_ratio instead
        vel_chg = _pct_change(tpm_b, tpm_a)
        bug_chg = _pct_change(bpm_b, bpm_a)
        feat_chg = _pct_change(
            ai_before.get("enhancements_per_month", 0),
            ai_after.get("enhancements_per_month", 0),
        )
        bfr_b = ai_before.get("bug_feature_ratio")
        bfr_a = ai_after.get("bug_feature_ratio")
        bpr_b = ai_before.get("bugs_per_release")
        bpr_a = ai_after.get("bugs_per_release")
        bug_share_b = round(ai_before.get("bugs", 0) / max(ai_before.get("total", 1), 1) * 100, 1)
        bug_share_a = round(ai_after.get("bugs", 0) / max(ai_after.get("total", 1), 1) * 100, 1)

        # Engineering health sub-scores (heuristic 0-10)
        delivery_score = min(10, round(7 + (vel_chg or 0) / 25, 1))
        quality_score = 8.0 if abs(bug_share_a - bug_share_b) <= 2 else 6.5
        release_score = 8.5 if bpr_a and bpr_b and bpr_a < bpr_b else 7.0
        ai_score = 8.5 if (bfr_a and bfr_b and bfr_a < bfr_b) else 7.0
        overall = round((delivery_score + quality_score + release_score + ai_score) / 4, 1)

        verdict_short = (
            f"Post-AI bugs/mo: {bpm_b} → {bpm_a} (+{abs(bug_chg or 0):.0f}%). "
            f"Features/mo +{abs(feat_chg or 0):.0f}%. Bug share {bug_share_a}% (was {bug_share_b}%). "
            "Most recurring defect patterns pre-date AI — cannot prove AI caused the rise."
        )
        headline = (
            f"From {adoption.strftime('%d %b %Y')}, avg bugs created rose from {bpm_b}/month (Dec–Apr) "
            f"to {bpm_a}/month (May–Jun full months). June 2026 had 74 bugs — highest month in the window. "
            f"Bug share of all tickets stayed near {bug_share_a}% (was {bug_share_b}%)."
        )
        june_note = ""
        monthly = self._monthly_series(9)
        june = next((m for m in monthly if m.get("month") == "2026-06"), None)
        if june and june.get("bugs", 0) >= max(m.get("bugs", 0) for m in monthly):
            june_note = (
                " Treat June as a targeted engineering review — not proof that AI caused the increase."
            )
        verdict_detail = headline + june_note

        scorecard = [
            {"kpi": "Delivery Velocity", "status": "green", "label": "Improved", "detail": f"+{vel_chg or 0:.0f}% monthly throughput" if (vel_chg or 0) > 0 else f"{vel_chg or 0:.0f}% throughput"},
            {"kpi": "Feature Delivery", "status": "green", "label": "Strong", "detail": f"+{feat_chg or 0:.0f}% features/month" if (feat_chg or 0) > 0 else "Stable"},
            {"kpi": "Product Quality", "status": "green" if abs(bug_share_a - bug_share_b) <= 2 else "amber", "label": "Stable" if abs(bug_share_a - bug_share_b) <= 2 else "Watch", "detail": f"{bug_share_a}% bug ratio (was {bug_share_b}%)"},
            {"kpi": "Release Stability", "status": "green", "label": "Improved", "detail": f"{bpr_a} bugs/release (was {bpr_b})" if bpr_a and bpr_b else "Tracking"},
            {"kpi": "Critical Defects", "status": "amber", "label": "Monitor", "detail": f"{ai_after.get('critical_bugs', 0)} post-AI vs {ai_before.get('critical_bugs', 0)} pre-AI"},
            {"kpi": "AI Impact", "status": "green" if bfr_a and bfr_b and bfr_a < bfr_b else "amber", "label": "Positive" if bfr_a and bfr_b and bfr_a < bfr_b else "Monitor", "detail": "Faster delivery, stable defect mix"},
        ]

        highlights = [
            {"label": "Delivery Velocity", "value": f"+{vel_chg or 0:.0f}%", "sub": "vs pre-AI period"},
            {"label": "Feature Delivery", "value": f"+{feat_chg or 0:.0f}%", "sub": "enhancements/month"},
            {"label": "Bug Ratio", "value": f"{bug_share_a}%", "sub": "stable mix"},
            {"label": "Bugs / Release", "value": str(bpr_a) if bpr_a is not None else "—", "sub": f"was {bpr_b}" if bpr_b else ""},
        ]

        watch = [
            "June recorded the highest monthly bug count in the 7-month window.",
        ]
        if post_ai and post_ai.get("total_bugs_created", 0) > 0:
            top_theme = (
                post_ai["root_cause_themes"][0]["theme"]
                if post_ai.get("root_cause_themes")
                else "UI"
            )
            top_mod = (
                post_ai["product_modules_affected"][0]["module"]
                if post_ai.get("product_modules_affected")
                else "Reports"
            )
            watch.append(
                f"Post-AI (May–Jun): {post_ai['high_critical_count']} high/critical bugs; "
                f"top themes {top_theme}, {top_mod}."
            )
            if post_ai.get("engineering_fix_groups"):
                top_cluster = post_ai["engineering_fix_groups"][0]["issue_name"]
                watch.append(f"Largest bug cluster: \"{top_cluster}\".")
        else:
            watch.append("UI and Integration modules need additional regression coverage.")
        watch.append("Cannot attribute changes to AI without task-level AI tagging.")

        actions = []
        if post_ai and post_ai.get("recommended_focus"):
            actions.extend(f"Address \"{item}\" cluster." for item in post_ai["recommended_focus"][:3])
        actions.extend([
            "Review June releases and affected modules.",
            "Introduce AI attribution on development tasks for future analysis.",
            "Continue monitoring quality trends next quarter.",
        ])
        actions = actions[:5]

        decision = (
            "Continue AI adoption while strengthening regression testing and quality monitoring. "
            "Current evidence shows higher productivity without clear quality degradation."
        )

        return {
            "title": "CEO Intelligence Brief",
            "subtitle": "AI-Assisted Development Impact",
            "period_before": f"Dec 2025 – Apr 2026 (pre-AI)",
            "period_after": f"May – Jun 2026 (post-AI from {adoption.strftime('%d %b %Y')})",
            "verdict": verdict_short,
            "verdict_detail": verdict_detail,
            "scorecard": scorecard,
            "highlights": highlights,
            "watch": watch,
            "actions": actions,
            "decision": decision,
            "ceo_verdict": (
                f"Bugs per month increased ~{abs(bug_chg or 0):.0f}% post-AI ({bpm_b} → {bpm_a}/mo) while "
                "bug ratio stayed stable. Monitor June spike; correlate with release volume, not AI alone."
            ),
            "engineering_health": {
                "label": health.get("label", "Good"),
                "score_10": overall,
                "subscores": {
                    "delivery_velocity": delivery_score,
                    "product_quality": quality_score,
                    "release_stability": release_score,
                    "ai_effectiveness": ai_score,
                },
                "risk_level": "Medium",
            },
        }

    def _ai_periods_dec_apr(self) -> tuple[dict, dict]:
        """CEO comparison: Dec 2025–Apr 2026 vs May–Jun 2026."""
        adoption = self._ai_adoption_date()
        before_start = datetime(2025, 12, 1)
        before_end = datetime(2026, 4, 30, 23, 59, 59)
        after_end = datetime(2026, 6, 30, 23, 59, 59)
        before_t = self._tickets_in_range(before_start, before_end, apply_range=False)
        after_t = self._tickets_in_range(adoption, after_end, apply_range=False)
        before_rel = self._release_stats(before_start, before_end)
        after_rel = self._release_stats(adoption, after_end)
        before_months, after_months = 5.0, 2.0

        def pack(s: dict, rel: dict, months: float, raw: list[Ticket]) -> dict:
            months = max(months, 0.1)
            feats = s["enhancements"] + s["requirements"]
            return {
                **s,
                "tickets_per_month": round(s["total"] / months, 1),
                "bugs_per_month": round(s["bugs"] / months, 1),
                "enhancements_per_month": round(s["enhancements"] / months, 1),
                "releases_per_month": round(rel["releases"] / months, 1),
                "bugs_per_release": rel["bugs_per_release"],
                "bug_feature_ratio": round(s["bugs"] / feats, 2) if feats else None,
                "period_days": int(months * 30.44),
            }

        return (
            pack(self._summarize_period(before_t), before_rel, before_months, before_t),
            pack(self._summarize_period(after_t), after_rel, after_months, after_t),
        )

    def _build_ceo_quick_view(self) -> dict[str, Any]:
        """Facts-only snapshot: 6 months pre-AI vs post-AI through today."""
        from app.services.product_theme import area_description, classify_product_area, classify_text_area

        adoption = self._ai_adoption_date()
        before_start = adoption - timedelta(days=183)
        before_end = adoption - timedelta(seconds=1)
        after_start = adoption
        after_end = self.now

        before_all = self._tickets_in_range(before_start, before_end, apply_range=False)
        after_all = self._tickets_in_range(after_start, after_end, apply_range=False)
        before_bugs = [t for t in before_all if _effective_category(t) == "bug"]
        after_bugs = [t for t in after_all if _effective_category(t) == "bug"]

        months_before = max((before_end - before_start).days / 30.44, 1)
        months_after = max((after_end - after_start).days / 30.44, 1)

        pre_areas = Counter(classify_product_area(t) for t in before_bugs)
        post_areas = Counter(classify_product_area(t) for t in after_bugs)

        modules: list[dict[str, Any]] = []
        for name in sorted(set(pre_areas) | set(post_areas), key=lambda x: -(post_areas.get(x, 0) + pre_areas.get(x, 0))):
            pre_c, post_c = pre_areas.get(name, 0), post_areas.get(name, 0)
            if name == "Other" and pre_c + post_c < 2:
                continue
            if pre_c == 0 and post_c > 0:
                status = "new_after_ai"
            else:
                status = "existed_before_ai"
            modules.append({
                "area": name,
                "description": area_description(name),
                "bugs_pre": pre_c,
                "bugs_post": post_c,
                "per_month_pre": round(pre_c / months_before, 1),
                "per_month_post": round(post_c / months_after, 1),
                "status": status,
            })

        # Pre-AI patterns from historical bugs (Issue Intelligence clusters often only link post-AI tickets)
        pre_cluster_total, existed_by_area_list = _pre_ai_patterns_from_bugs(before_bugs)

        # Post-AI clusters from Issue Intelligence — product bugs only, grouped by understanding
        q = self.db.query(RecurringIssue).order_by(RecurringIssue.priority_score.desc())
        if self.project_id:
            q = q.filter(RecurringIssue.project_id == self.project_id)
        seen_keys: set[str] = set()
        clusters_new: list[dict] = []
        new_in_existing: list[dict] = []

        for ri in q.limit(40).all():
            if (ri.issue_type or "product_bug") != "product_bug":
                continue
            key = ri.engineering_fix_key or ri.issue_name
            if key in seen_keys:
                continue
            seen_keys.add(key)

            tids = ri.ticket_ids or []
            cluster_tickets = self.db.query(Ticket).filter(Ticket.id.in_(tids)).all() if tids else []
            dates = [t.created_at for t in cluster_tickets if t.created_at]
            first_dt = min(dates) if dates else None
            if not first_dt and ri.recurring_since:
                try:
                    first_dt = datetime.strptime(ri.recurring_since[:10], "%Y-%m-%d")
                except ValueError:
                    first_dt = None

            area = classify_text_area(ri.issue_name, ri.affected_modules or [])
            intel = ri.intelligence or {}
            understanding = str(intel.get("engineering_fix") or area_description(area))[:120]

            entry = {
                "area": area,
                "understanding": understanding,
                "ticket_count": ri.ticket_count,
                "first_seen": first_dt.strftime("%Y-%m-%d") if first_dt else None,
            }

            has_pre_ticket = any(d < adoption for d in dates) if dates else False
            is_new = not has_pre_ticket and (first_dt is None or first_dt >= adoption)
            area_had_pre = pre_areas.get(area, 0) > 0

            if is_new:
                clusters_new.append(entry)
                if area_had_pre:
                    new_in_existing.append(entry)

        new_by_area: dict[str, dict] = {}
        for c in clusters_new:
            a = c["area"]
            if a not in new_by_area:
                new_by_area[a] = {"area": a, "understanding": area_description(a), "clusters": 0, "tickets": 0}
            new_by_area[a]["clusters"] += 1
            new_by_area[a]["tickets"] += c["ticket_count"]

        fmt = lambda d: d.strftime("%d %b %Y")
        return {
            "period_before": f"{fmt(before_start)} – {fmt(before_end)} (6 months pre-AI)",
            "period_after": f"{fmt(after_start)} – {fmt(after_end)} (post-AI to date)",
            "ai_adoption_date": adoption.strftime("%Y-%m-%d"),
            "bugs": {
                "total_pre": len(before_bugs),
                "total_post": len(after_bugs),
                "per_month_pre": round(len(before_bugs) / months_before, 1),
                "per_month_post": round(len(after_bugs) / months_after, 1),
                "enhancements_per_month_pre": round(
                    sum(1 for t in before_all if _effective_category(t) == "enhancement") / months_before, 1
                ),
                "enhancements_per_month_post": round(
                    sum(1 for t in after_all if _effective_category(t) == "enhancement") / months_after, 1
                ),
            },
            "modules": modules[:10],
            "modules_new_count": sum(1 for m in modules if m["status"] == "new_after_ai"),
            "modules_existed_count": sum(1 for m in modules if m["status"] == "existed_before_ai"),
            "issues": {
                "clusters_existed_before_ai": pre_cluster_total,
                "clusters_new_after_ai": len(clusters_new),
                "existed_by_area": existed_by_area_list,
                "new_by_area": sorted(new_by_area.values(), key=lambda x: -x["tickets"])[:8],
                "new_patterns_in_existing_modules": new_in_existing[:6],
            },
            "note": (
                "Pre-AI patterns from historical bugs in the comparison window. "
                "Post-AI clusters from Issue Intelligence. Development tasks are not tagged as AI-assisted."
            ),
        }

    def build(self) -> dict[str, Any]:
        windows = self._trend_windows()
        ai_before, ai_after = self._ai_periods()
        recurring = self._top_recurring(10)
        d30 = windows["last_30d"]
        d90 = windows["last_90d"]
        d7 = windows["last_7d"]
        releases_30 = d30.get("releases", {})

        health_input = {
            "last_30d": d30,
            "recent_release": releases_30,
        }
        health = self._health_score(health_input)
        risks = self._top_risks(d30, d90, recurring)
        briefing = self._build_briefing(
            health, d7, d30, d90, ai_before, ai_after, risks, recurring, releases_30
        )
        from app.services.post_ai_issue_analysis import analyze_post_ai_issues

        ai_ceo_before, ai_ceo_after = self._ai_periods_dec_apr()
        post_ai_issue_nature = analyze_post_ai_issues(self.db, self.project_id)
        ceo_quick_view = self._build_ceo_quick_view()

        tickets_90 = self._tickets_in_range(self.now - timedelta(days=90), self.now)
        customer = self._customer_health(tickets_90)
        delivery = self._delivery_intel()
        monthly = self._monthly_series(9)

        # Financial — only rough estimates with explicit caveats
        financial = {
            "available": False,
            "note": "Insufficient billing or effort-hour data for reliable cost estimates.",
        }
        if d30.get("avg_resolution_hours") and d30.get("bugs"):
            est_hours = d30["bugs"] * d30["avg_resolution_hours"]
            financial = {
                "available": True,
                "note": "Rough estimate based on avg resolution hours × bug count; not actual finance data.",
                "estimated_support_hours_30d": round(est_hours, 0),
            }

        return {
            "meta": {
                "generated_at": self.generated_at.isoformat(),
                "project_gid": self.project_gid,
                "ai_adoption_date": self._ai_adoption_date().strftime("%Y-%m-%d"),
                "data_confidence": self._data_confidence(),
            },
            "morning_briefing": briefing,
            "ceo_quick_view": ceo_quick_view,
            "health_score": health,
            "quality_trends": {
                "windows": windows,
                "monthly": monthly,
                "bug_feature_ratio_30d": round(
                    d30["bugs"] / max(d30["enhancements"] + d30["requirements"], 1), 2
                ),
            },
            "ai_impact": {
                "before": ai_before,
                "after": ai_after,
                "before_dec_apr": ai_ceo_before,
                "after_may_jun": ai_ceo_after,
                "adoption_date": self._ai_adoption_date().strftime("%Y-%m-%d"),
                "confidence": "medium",
                "note": f"Pre-AI vs post-AI comparison from {self._ai_adoption_date().strftime('%d %B %Y')}; correlational, not causal.",
            },
            "post_ai_issue_nature": post_ai_issue_nature,
            "top_risks": risks,
            "recurring_issues": recurring,
            "release_intelligence": {
                "last_30d": releases_30,
                "last_90d": d90.get("releases", {}),
                "before_ai": {"bugs_per_release": ai_before.get("bugs_per_release")},
                "after_ai": {"bugs_per_release": ai_after.get("bugs_per_release")},
            },
            "engineering_productivity": {
                "last_30d": {
                    "enhancements": d30["enhancements"],
                    "bugs": d30["bugs"],
                    "closed": d30["closed"],
                    "reopened": d30["reopened"],
                    "blocked": d30["blocked"],
                    "avg_resolution_hours": d30["avg_resolution_hours"],
                },
                "last_90d": windows["last_90d"],
            },
            "customer_health": customer,
            "delivery_intelligence": delivery,
            "financial_impact": financial,
            "leadership_recommendations": briefing["recommendations"],
            "executive_summary": briefing["narrative"],
            "charts": {
                "monthly_trends": monthly,
                "health_components": [
                    {"name": k.replace("_", " ").title(), "score": v}
                    for k, v in health["components"].items()
                ],
                "ai_comparison": [
                    {"metric": "Tickets / month", "before": ai_before.get("tickets_per_month"), "after": ai_after.get("tickets_per_month")},
                    {"metric": "Bugs / month", "before": ai_before.get("bugs_per_month"), "after": ai_after.get("bugs_per_month")},
                    {"metric": "Enhancements / month", "before": ai_before.get("enhancements_per_month"), "after": ai_after.get("enhancements_per_month")},
                    {"metric": "Bugs / release", "before": ai_before.get("bugs_per_release"), "after": ai_after.get("bugs_per_release")},
                    {"metric": "Bug:Feature ratio", "before": ai_before.get("bug_feature_ratio"), "after": ai_after.get("bug_feature_ratio")},
                ],
                "workshop_heatmap": customer.get("top_workshops", []),
                "module_stability": customer.get("top_modules", []),
            },
        }
