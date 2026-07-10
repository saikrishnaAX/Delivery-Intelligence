"""Extract operational fields from Asana ticket title, description, and custom fields."""

import re
from app.models import TicketPriority

BLOCKER_TITLE_KEYWORDS = [
    "unable", "failed", "failure", "error", "not working", "not visible",
    "not generating", "not fetching", "not updating", "missing", "mismatch",
    "mandatory", "duplicate entry", "sync failure", "blocked", "cannot",
    "can't", "issue in", "issue with", "investigation required", "critical",
    "timeout", "crash", "broken", "does not", "doesn't", "not sending",
    "not receiving", "not creating", "not displaying", "incorrect",
]

WORKSHOP_PATTERNS = [
    re.compile(r"GARAGE\s*NAME\s*:\s*(.+?)(?:\n|$)", re.I),
    re.compile(r"WORKSHOP\s*NAME\s*:\s*(.+?)(?:\n|$)", re.I),
    re.compile(r"Workshop\s*Name\s*:\s*(.+?)(?:\n|$)", re.I),
    re.compile(r"Workshop/s?\s*:\s*(.+?)(?:\n|$)", re.I),
]

AX_ID_PATTERN = re.compile(r"AX\s*ID\s*:\s*(AX[\w\d]+)", re.I)
WORKSHOP_ID_PATTERN = re.compile(r"Workshop\s*id\s*:\s*(\d+)", re.I)
JIRA_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
JIRA_URL_PATTERN = re.compile(
    r"https?://[^\s\)<>\]]*atlassian\.net/browse/([A-Z][A-Z0-9]+-\d+)",
    re.I,
)


def _pick_jira_key(keys: list[str], preferred_prefix: str | None) -> str | None:
    if not keys:
        return None
    if preferred_prefix:
        prefix = preferred_prefix.upper()
        for key in keys:
            if key.upper().startswith(f"{prefix}-"):
                return key.upper()
    return keys[0].upper()


def extract_jira_key(
    title: str,
    description: str | None = None,
    preferred_prefix: str | None = None,
) -> str | None:
    """Pull a Jira issue key from title, description, or Jira browse URLs."""
    text = f"{title}\n{description or ''}"
    url_keys = JIRA_URL_PATTERN.findall(text)
    picked = _pick_jira_key(url_keys, preferred_prefix)
    if picked:
        return picked
    return _pick_jira_key(JIRA_KEY_PATTERN.findall(text), preferred_prefix)


def extract_jira_key_from_attachments(
    attachments: list[dict],
    preferred_prefix: str | None = None,
) -> str | None:
    """Read Jira keys from Asana external attachments (native Jira Cloud widget)."""
    for att in attachments:
        for field in ("view_url", "permanent_url", "name"):
            value = att.get(field) or ""
            url_keys = JIRA_URL_PATTERN.findall(value)
            picked = _pick_jira_key(url_keys, preferred_prefix)
            if picked:
                return picked
            picked = _pick_jira_key(JIRA_KEY_PATTERN.findall(value), preferred_prefix)
            if picked:
                return picked
    return None


def jira_browse_url(jira_key: str | None) -> str | None:
    if not jira_key:
        return None
    from app.config import get_settings
    cfg = get_settings()
    base = (cfg.jira_base_url or "https://autorox.atlassian.net").rstrip("/")
    return f"{base}/browse/{jira_key}"

WORKFLOW_KEYWORDS = {
    "invoice": "billing & invoicing",
    "job card": "job card workflow",
    "inward": "parts inward / stock",
    "estimate": "estimation",
    "insurance": "insurance billing",
    "otp": "security / OTP",
    "report": "reporting",
    "zoho": "Zoho integration",
    "barcode": "inventory scanning",
    "payment": "payments",
    "gst": "tax compliance",
    "whatsapp": "customer notifications",
}


def _field_value(cf: dict) -> str | None:
    val = cf.get("display_value") or cf.get("text_value")
    if val:
        return str(val).strip()
    enum_val = cf.get("enum_value")
    if isinstance(enum_val, dict):
        return enum_val.get("name", "").strip() or None
    if enum_val:
        return str(enum_val).strip()
    multi = cf.get("multi_enum_values") or []
    if multi:
        return multi[0].get("name", "").strip()
    return None


def parse_custom_field(custom_fields: list | None, field_name: str) -> str | None:
    for cf in custom_fields or []:
        if cf.get("name", "").lower() == field_name.lower():
            return _field_value(cf)
    return None


def parse_custom_number(custom_fields: list | None, field_name: str) -> float | None:
    for cf in custom_fields or []:
        if cf.get("name", "").lower() == field_name.lower():
            if cf.get("number_value") is not None:
                return float(cf["number_value"])
            raw = _field_value(cf)
            if raw:
                try:
                    return float(raw)
                except ValueError:
                    return None
    return None


def parse_date_field(custom_fields: list | None, field_name: str):
    from dateutil import parser as date_parser
    raw = parse_custom_field(custom_fields, field_name)
    if not raw:
        return None
    try:
        return date_parser.parse(raw).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def extract_workshop_name(title: str, description: str, workshop_field: str | None) -> str | None:
    text = f"{title}\n{description}"
    for pat in WORKSHOP_PATTERNS:
        m = pat.search(text)
        if m:
            name = m.group(1).strip()
            if len(name) > 3 and name.lower() not in ("—", "-", "n/a"):
                return name[:255]

    if workshop_field:
        cleaned = workshop_field.strip()
        # Multi-line workshop field — take WORKSHOP NAME line if present
        for line in cleaned.split("\n"):
            if "workshop name" in line.lower() and ":" in line:
                return line.split(":", 1)[1].strip()[:255]
        # Short single-line value
        if len(cleaned) > 2 and not cleaned.lower().startswith("workshop id"):
            first_line = cleaned.split("\n")[0].strip()
            if len(first_line) > 2:
                return first_line[:255]

    # Sometimes workshop is suffix in title after " - "
    if " - " in title:
        suffix = title.rsplit(" - ", 1)[-1].strip()
        if len(suffix) > 4 and not suffix.lower().startswith("action"):
            return suffix[:255]

    return None


def extract_ax_id(description: str) -> str | None:
    m = AX_ID_PATTERN.search(description or "")
    return m.group(1) if m else None


def extract_workshop_id(description: str, workshop_field: str | None) -> str | None:
    m = WORKSHOP_ID_PATTERN.search(description or "")
    if m:
        return m.group(1)
    if workshop_field:
        m2 = WORKSHOP_ID_PATTERN.search(workshop_field)
        if m2:
            return m2.group(1)
    return None


def detect_workflow_blocker(title: str, description: str, priority_raw: str | None, status_open: bool) -> bool:
    if not status_open:
        return False
    text = f"{title} {description}".lower()
    if any(kw in text for kw in BLOCKER_TITLE_KEYWORDS):
        return True
    if priority_raw and priority_raw.lower() in ("high", "critical", "urgent"):
        if any(w in title.lower() for w in ("unable", "failed", "error", "issue", "not ")):
            return True
    return False


def map_asana_priority(priority_raw: str | None, tags: list) -> TicketPriority:
    if priority_raw:
        p = priority_raw.lower()
        if "critical" in p or "urgent" in p:
            return TicketPriority.CRITICAL
        if "high" in p:
            return TicketPriority.HIGH
        if "low" in p:
            return TicketPriority.LOW
    tag_lower = {t.lower() for t in tags}
    if any(t in tag_lower for t in ("critical", "p0")):
        return TicketPriority.CRITICAL
    if any(t in tag_lower for t in ("high", "p1")):
        return TicketPriority.HIGH
    return TicketPriority.MEDIUM


REDACT_LINE_PREFIXES = (
    "garage name", "workshop name", "workshop/s", "workshop id", "ax id",
)

MODULE_KEYWORDS: list[tuple[str, str]] = [
    ("job card", "Job Card"),
    ("estimation", "Estimation"),
    ("estimate", "Estimation"),
    ("invoice", "Invoice"),
    ("master management", "Master Management"),
    ("parts inward", "Parts Inwarding"),
    ("inward", "Parts Inwarding"),
    ("sales register", "Sales Register"),
    ("collection report", "Collection Report"),
    ("stock", "Stock"),
    ("barcode", "Barcode Printing"),
    ("appointment", "Appointment"),
    ("booking", "Booking"),
    ("franchise", "Franchise Management"),
    ("insurance", "Insurance"),
    ("payment", "Payments"),
    ("report", "Reports"),
    ("dashboard", "Dashboard"),
    ("labour master", "Labour Master"),
    ("sell product", "Sell Product"),
    ("quick pay", "All Modules"),
    ("cep", "CEP / GMS"),
    ("gms", "CEP / GMS"),
]


def redact_workshop_names(text: str, workshop_name: str | None = None) -> str:
    if not text:
        return ""
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if any(lower.startswith(prefix) for prefix in REDACT_LINE_PREFIXES):
            continue
        lines.append(line)
    result = "\n".join(lines)
    if workshop_name and len(workshop_name.strip()) > 2:
        result = re.sub(re.escape(workshop_name.strip()), "", result, flags=re.I)
    result = re.sub(r"[ \t]{2,}", " ", result)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def clean_title_for_release(title: str, workshop_name: str | None = None) -> str:
    cleaned = title.strip()
    if workshop_name and " - " in cleaned:
        suffix = cleaned.rsplit(" - ", 1)[-1].strip()
        if suffix.lower() == workshop_name.lower() or workshop_name.lower() in suffix.lower():
            cleaned = cleaned.rsplit(" - ", 1)[0].strip()
    return redact_workshop_names(cleaned, workshop_name)


def infer_module_affected(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    modules: list[str] = []
    for keyword, label in MODULE_KEYWORDS:
        if keyword in text and label not in modules:
            modules.append(label)
    if not modules:
        for keyword, label in WORKFLOW_KEYWORDS.items():
            if keyword in text and label.title() not in modules:
                modules.append(label.title())
    return " / ".join(modules[:4]) if modules else "Multiple Modules"


# Ordered by specificity — first strong match wins for cluster topic split.
PRIMARY_MODULE_RULES: list[tuple[str, str]] = [
    ("job card", "Job Card"),
    ("jobcard", "Job Card"),
    ("invoice", "Invoice"),
    ("invoicing", "Invoice"),
    ("tax invoice", "Invoice"),
    ("parts inward", "Parts Inwarding"),
    ("part inward", "Parts Inwarding"),
    ("inward", "Parts Inwarding"),
    ("estimation", "Estimation"),
    ("estimate", "Estimation"),
    ("insurance", "Insurance"),
    ("sales register", "Sales Register"),
    ("collection report", "Collection Report"),
    ("master management", "Master Management"),
    ("labour master", "Labour Master"),
    ("barcode", "Barcode Printing"),
    ("appointment", "Appointment"),
    ("booking", "Booking"),
    ("franchise", "Franchise Management"),
    ("payment", "Payments"),
    ("stock", "Stock"),
    ("report", "Reports"),
    ("dashboard", "Dashboard"),
    ("sell product", "Sell Product"),
    ("zoho", "Zoho Integration"),
    ("whatsapp", "Customer Notifications"),
    ("otp", "Security / OTP"),
    ("gst", "Tax Compliance"),
]


def infer_primary_module(title: str, description: str) -> str:
    """Pick a single module topic so invoice vs job card tickets stay separate."""
    title_l = (title or "").lower()
    text = f"{title}\n{description or ''}".lower()
    best_score = 0
    best_label = "General"
    for keyword, label in PRIMARY_MODULE_RULES:
        if keyword not in text:
            continue
        score = 80 if keyword in title_l else 40
        score += text.count(keyword) * 8
        if len(keyword) >= 8:
            score += 10
        if score > best_score:
            best_score = score
            best_label = label
    return best_label
