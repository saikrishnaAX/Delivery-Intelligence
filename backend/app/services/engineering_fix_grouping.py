"""Group tickets by engineering fix — NOT keyword similarity.

Merge rule: would the same code change resolve these tickets?
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models import Ticket, TicketStatus
from app.services.ticket_parser import infer_module_affected, infer_primary_module


@dataclass
class TicketFixProfile:
    ticket_id: int
    product_problem: str
    engineering_fix_key: str
    engineering_fix_label: str
    issue_type: str  # product_bug | enhancement | configuration | training | duplicate | support_mistake
    module: str


# Ordered: more specific patterns first. anti_patterns prevent misclassification.
_FIX_RULES: list[dict] = [
    {
        "key": "render:pdf",
        "label": "PDF / print rendering",
        "issue_name": "Content Missing or Incorrect in PDF / Print",
        "patterns": [
            r"\bpdf\b", r"\bprint(?:ed|ing)?\b", r"download.*(?:invoice|report)",
            r"missing in pdf", r"not show(?:ing)?.*pdf", r"blank pdf", r"pdf.*blank",
            r"print preview", r"printed invoice", r"invoice.*pdf",
        ],
        "anti": [],
        "type": "product_bug",
    },
    {
        "key": "notify:messaging",
        "label": "Email / WhatsApp / SMS delivery",
        "issue_name": "Notification Not Sent or Delivered",
        "patterns": [
            r"whatsapp", r"\bsms\b", r"email not", r"notification", r"message not sent",
            r"not receiving", r"otp", r"did not receive",
        ],
        "anti": [],
        "type": "product_bug",
    },
    {
        "key": "auth:permission",
        "label": "Permissions / role access",
        "issue_name": "Permission or Access Denied",
        "patterns": [
            r"permission", r"access denied", r"not authorized", r"role", r"cannot access",
            r"unauthorized", r"login fail", r"locked out",
        ],
        "anti": [],
        "type": "product_bug",
    },
    {
        "key": "integration:api",
        "label": "External API / sync integration",
        "issue_name": "Integration or API Sync Failure",
        "patterns": [
            r"\bapi\b", r"sync fail", r"integration", r"zoho", r"tally", r"timeout",
            r"connection fail", r"webhook", r"third.?party",
        ],
        "anti": [r"\bpdf\b"],
        "type": "product_bug",
    },
    {
        "key": "calc:tax",
        "label": "Tax / GST / calculation logic",
        "issue_name": "Tax or Amount Calculation Incorrect",
        "patterns": [
            r"\bgst\b", r"tax calcul", r"wrong amount", r"total mismatch", r"round(?:ing)?",
            r"discount calcul", r"grand total",
        ],
        "anti": [],
        "type": "product_bug",
    },
    {
        "key": "gen:sequence",
        "label": "Number / sequence / auto-ID generation",
        "issue_name": "Number or Sequence Not Generated",
        "patterns": [
            r"number missing", r"sequence", r"auto.?gen", r"auto.?number", r"blank number",
            r"empty number", r"generation fail", r"id empty", r"invoice number",
            r"job.?card.?number", r"estimate number", r"number not generat", r"sequence missing",
            r"number blank", r"missing number", r"no invoice number", r"number not show",
        ],
        "anti": [r"\bpdf\b", r"\bprint", r"wrong number", r"incorrect number"],
        "type": "product_bug",
    },
    {
        "key": "ui:display",
        "label": "UI display / screen rendering",
        "issue_name": "UI Display or Screen Rendering Issue",
        "patterns": [
            r"not show(?:ing)?", r"not visible", r"screen blank", r"ui issue", r"layout",
            r"button not", r"dropdown", r"display issue", r"css", r"alignment",
        ],
        "anti": [r"\bpdf\b", r"number missing", r"sequence"],
        "type": "product_bug",
    },
    {
        "key": "data:persistence",
        "label": "Data not saved / lost",
        "issue_name": "Data Not Saved or Lost",
        "patterns": [
            r"not sav", r"data loss", r"disappeared", r"deleted unintentionally",
            r"record missing", r"lost data",
        ],
        "anti": [],
        "type": "product_bug",
    },
    {
        "key": "config:settings",
        "label": "Configuration / settings",
        "issue_name": "Configuration or Settings Issue",
        "patterns": [
            r"configur", r"\bsetting\b", r"enable feature", r"how to enable", r"setup",
            r"turn on", r"preference",
        ],
        "anti": [],
        "type": "configuration",
    },
    {
        "key": "training:user",
        "label": "User training / how-to",
        "issue_name": "User Training or How-To Question",
        "patterns": [
            r"how to", r"how do i", r"training", r"user error", r"steps to",
            r"guide me", r"explain how",
        ],
        "anti": [r"error", r"fail", r"bug", r"not work"],
        "type": "training",
    },
    {
        "key": "enhancement:request",
        "label": "Enhancement request",
        "issue_name": "Enhancement Request",
        "patterns": [
            r"enhancement", r"feature request", r"add feature", r"new feature",
            r"improvement request", r"wish to have", r"please add",
        ],
        "anti": [],
        "type": "enhancement",
    },
    {
        "key": "duplicate:ticket",
        "label": "Duplicate report",
        "issue_name": "Duplicate Ticket",
        "patterns": [r"duplicate", r"already reported", r"same issue"],
        "anti": [],
        "type": "duplicate",
    },
]


def _normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text) for p in patterns)


def infer_fix_profile(title: str, description: str | None = "", asana_type: str | None = None) -> tuple[str, str, str, str]:
    """Return (fix_key, fix_label, issue_name, issue_type)."""
    text = _normalize(f"{title} {description or ''}")
    at = (asana_type or "").lower()

    if "enhancement" in at or "requirement" in at:
        if not _matches_any(text, [r"error", r"fail", r"bug", r"not work", r"broken"]):
            return "enhancement:request", "Enhancement request", "Enhancement Request", "enhancement"

    for rule in _FIX_RULES:
        if rule["anti"] and _matches_any(text, rule["anti"]):
            continue
        if _matches_any(text, rule["patterns"]):
            return rule["key"], rule["label"], rule["issue_name"], rule["type"]

    module = infer_primary_module(title or "", description or "")
    return (
        f"general:{module.lower().replace(' ', '_')[:40]}",
        f"{module} — general product issue",
        _product_problem_label(title),
        "product_bug",
    )


def _product_problem_label(title: str) -> str:
    t = (title or "").strip()
    if not t:
        return "Unspecified product issue"
    t = re.sub(r"^(ticket|support|request|issue)[:\s-]+", "", t, flags=re.I).strip()
    return t[:120] if t else "Unspecified product issue"


def profile_ticket(ticket: Ticket) -> TicketFixProfile:
    fix_key, fix_label, default_name, issue_type = infer_fix_profile(
        ticket.title or "",
        ticket.description,
        ticket.asana_type_raw,
    )
    return TicketFixProfile(
        ticket_id=ticket.id,
        product_problem=_product_problem_label(ticket.title or ""),
        engineering_fix_key=fix_key,
        engineering_fix_label=fix_label,
        issue_type=issue_type,
        module=infer_module_affected(ticket.title or "", ticket.description or ""),
    )


def group_tickets_by_engineering_fix(tickets: list[Ticket]) -> list[dict]:
    """Merge tickets that would be fixed by the same engineering change."""
    buckets: dict[str, list[Ticket]] = defaultdict(list)
    profiles: dict[int, TicketFixProfile] = {}

    for t in tickets:
        p = profile_ticket(t)
        profiles[t.id] = p
        buckets[p.engineering_fix_key].append(t)

    groups: list[dict] = []
    for fix_key, group_tickets in buckets.items():
        if not group_tickets:
            continue
        profile = profiles[group_tickets[0].id]
        issue_name = _derive_issue_name(group_tickets, profile)
        groups.append({
            "engineering_fix_key": fix_key,
            "engineering_fix_label": profile.engineering_fix_label,
            "issue_name": issue_name,
            "issue_type": profile.issue_type,
            "tickets": group_tickets,
            "profiles": [profiles[t.id] for t in group_tickets],
        })

    groups.sort(key=lambda g: len(g["tickets"]), reverse=True)
    return groups


def _derive_issue_name(tickets: list[Ticket], profile: TicketFixProfile) -> str:
    """Pick the clearest human name for the recurring issue."""
    if len(tickets) == 1:
        return profile.product_problem

    rule_name = None
    for rule in _FIX_RULES:
        if rule["key"] == profile.engineering_fix_key:
            rule_name = rule["issue_name"]
            break

    if profile.engineering_fix_key == "gen:sequence" and len(tickets) >= 2:
        combined = " ".join(
            f"{t.title or ''} {t.description or ''}" for t in tickets
        ).lower()
        if "invoice" in combined:
            return "Invoice Number Not Generated"
        if "job card" in combined or "jobcard" in combined:
            return "Job Card Number Not Generated"
        if "estimate" in combined:
            return "Estimate Number Not Generated"

    if rule_name and len(tickets) >= 2:
        module_counts = Counter(
            infer_primary_module(t.title or "", t.description or "") for t in tickets
        )
        top_module = module_counts.most_common(1)[0][0] if module_counts else ""
        if top_module and top_module != "General":
            return f"{top_module} — {rule_name}"
        return rule_name

    titles = [t.title or "" for t in tickets if t.title]
    return _most_representative_title(titles) or profile.product_problem


def _most_representative_title(titles: list[str]) -> str:
    if not titles:
        return "Recurring product issue"
    if len(titles) == 1:
        return titles[0][:100]

    def words(s: str) -> set[str]:
        return set(_normalize(s).split()) - {"the", "a", "an", "in", "on", "for", "to", "and", "is", "not"}

    best, best_score = titles[0], -1.0
    for t in titles:
        ws = words(t)
        if not ws:
            continue
        others = [words(o) for o in titles if o != t]
        if not others:
            continue
        score = sum(len(ws & o) / max(len(ws | o), 1) for o in others) / len(others)
        if score > best_score:
            best_score = score
            best = t
    return best[:100]


def compute_trend(tickets: list[Ticket], now: datetime | None = None) -> str:
    """increasing | stable | decreasing based on ticket creation rate."""
    now = now or datetime.utcnow()
    if len(tickets) < 3:
        return "stable"

    recent_cut = now - timedelta(days=30)
    prior_cut = now - timedelta(days=60)

    recent = sum(1 for t in tickets if t.created_at and t.created_at >= recent_cut)
    prior = sum(
        1 for t in tickets
        if t.created_at and prior_cut <= t.created_at < recent_cut
    )

    if prior == 0:
        return "increasing" if recent >= 2 else "stable"
    ratio = recent / prior
    if ratio >= 1.25:
        return "increasing"
    if ratio <= 0.75:
        return "decreasing"
    return "stable"


def compute_severity(open_count: int, workshop_count: int, issue_type: str) -> str:
    if issue_type in ("training", "duplicate", "enhancement"):
        return "low"
    if open_count >= 10 or workshop_count >= 8:
        return "critical"
    if open_count >= 5 or workshop_count >= 4:
        return "high"
    if open_count >= 2:
        return "medium"
    return "low"


def compute_confidence(ticket_count: int, fix_key: str) -> float:
    base = 0.45
    if fix_key.startswith("general:"):
        base = 0.35
    elif fix_key in ("gen:sequence", "render:pdf", "integration:api", "calc:tax"):
        base = 0.72
    else:
        base = 0.58
    return round(min(0.95, base + min(0.2, ticket_count / 50)), 2)
