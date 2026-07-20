"""Push / pull sprint sheet data to Google Sheets (service account)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

PULL_FIELDS = {
    "priority",
    "qa_estimate",
    "dev_assigned",
    "qa_assigned",
    "status",
}

# Accept current + older Google header labels when pulling manual edits.
PULL_HEADER_ALIASES = {
    "asana link": "asana_link",
    "asana": "asana_link",
    "jira link": "doc_link",
    "jira": "doc_link",
    "dev est (hrs)": "dev_estimate",
    "dev est": "dev_estimate",
    "qa est (hrs)": "qa_estimate",
    "qa est": "qa_estimate",
    "total est (hrs)": "total_estimate",
    "total": "total_estimate",
    "priority": "priority",
    "status": "status",
    "dev assigned": "dev_assigned",
    "qa assigned": "qa_assigned",
    "asana gid": "asana_gid",
    "ticket": "title",
    "type": "ticket_type",
    "jira status": "jira_status",
}


def _column_defs() -> list[tuple[str, str]]:
    """Always read from sprint_sheet so Google columns match the app table."""
    from app.services.sprint_sheet import SPRINT_COLUMNS

    return list(SPRINT_COLUMNS)


def _header_keys() -> list[str]:
    return ["asana_gid"] + [key for key, _ in _column_defs()]


def _header_labels() -> list[str]:
    return ["Asana GID"] + [label for _, label in _column_defs()]


# Back-compat for scripts that import HEADER_LABELS at module load.
def __getattr__(name: str):
    if name == "HEADER_LABELS":
        return _header_labels()
    if name == "HEADER_KEYS":
        return _header_keys()
    if name == "SPRINT_COLUMNS":
        return _column_defs()
    raise AttributeError(name)

SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
GID_IN_URL_RE = re.compile(r"gid=(\d+)")


def is_configured() -> bool:
    return _credentials_info() is not None


def service_account_email() -> str | None:
    info = _credentials_info()
    if not info:
        return None
    return info.get("client_email")


def parse_spreadsheet_id(url_or_id: str) -> str:
    raw = (url_or_id or "").strip()
    if not raw:
        raise ValueError("Spreadsheet URL or ID is required")
    match = SPREADSHEET_ID_RE.search(raw)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", raw):
        return raw
    raise ValueError("Invalid Google Sheets URL — paste the full link from your browser")


def sanitize_tab_name(name: str) -> str:
    cleaned = re.sub(r"[\[\]:*?/\\]", "-", name.strip())[:90] or "Sprint"
    return cleaned


def _credentials_info() -> dict | None:
    if settings.google_service_account_json:
        try:
            return json.loads(settings.google_service_account_json)
        except json.JSONDecodeError:
            logger.warning("Invalid GOOGLE_SERVICE_ACCOUNT_JSON")
            return None
    path = settings.google_service_account_file
    if path:
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = Path(__file__).resolve().parents[2] / path
        if file_path.exists():
            return json.loads(file_path.read_text(encoding="utf-8"))
    return None


def _service():
    info = _credentials_info()
    if not info:
        raise RuntimeError(
            "Google Sheets not configured. Set GOOGLE_SERVICE_ACCOUNT_FILE or "
            "GOOGLE_SERVICE_ACCOUNT_JSON in backend/.env"
        )
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _ensure_tab(service, spreadsheet_id: str, tab_name: str) -> str:
    tab = sanitize_tab_name(tab_name)
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = meta.get("sheets", [])
    for sheet in sheets:
        title = sheet["properties"]["title"]
        if title == tab:
            return tab
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
    ).execute()
    return tab


def _payload_to_values(payload: dict) -> list[list[Any]]:
    from app.services.sprint_sheet import _row_sort_key

    columns = _column_defs()
    headers = _header_labels()
    # Hard guarantee: Status sits immediately after Priority (same as app UI).
    labels_only = [label for _, label in columns]
    assert labels_only[:4] == ["Ticket", "Type", "Priority", "Status"], (
        f"Sprint sheet columns drifted from app UI: {labels_only[:4]}"
    )

    totals = payload.get("totals") or {}
    rows_out: list[list[Any]] = [
        [
            f"Sprint Sheet — {payload.get('sprint_name', 'Sprint')}",
            f"Project: {payload.get('project_name') or '—'}",
            f"Last sync: {payload.get('generated_at', datetime.utcnow().isoformat())}",
        ],
        [
            f"Prioritized: {totals.get('prioritized', 0)}",
            f"In progress: {totals.get('in_progress', 0)}",
            f"Done: {totals.get('done', 0)}",
            f"Dev: {totals.get('dev_hours', 0):.0f}h",
            f"QA: {totals.get('qa_hours', 0):.0f}h",
            "Edit yellow columns in app or sheet — both stay in sync",
        ],
        headers,
    ]

    active_rows = [
        row for row in (payload.get("rows") or [])
        if row.get("sheet_status") != "removed"
    ]
    active_rows.sort(key=_row_sort_key)

    for row in active_rows:
        line: list[Any] = [row.get("asana_gid")]
        for key, _ in columns:
            val = row.get(key)
            line.append("" if val is None else val)
        rows_out.append(line)
    return rows_out


def push_sheet(spreadsheet_id: str, tab_name: str, payload: dict) -> datetime:
    service = _service()
    tab = _ensure_tab(service, spreadsheet_id, tab_name)
    values = _payload_to_values(payload)
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab}'!A:Z",
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()
    _format_sheet(service, spreadsheet_id, tab, len(values))
    return datetime.utcnow()


def _format_sheet(service, spreadsheet_id: str, tab: str, row_count: int) -> None:
    """Light formatting only — do not reset column widths/visibility (user layout is preserved)."""
    headers = _header_labels()
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == tab
    )
    requests: list[dict] = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 3}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 2,
                    "endRowIndex": 3,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(headers),
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.12, "green": 0.16, "blue": 0.22},
                        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        # Keep Asana GID key column hidden; leave all other column sizes as the user set them.
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser",
            }
        },
    ]
    if row_count > 3:
        # Editable yellow: Priority, Status, QA Est, Dev Assigned, QA Assigned
        # 0=gid … 3=priority, 4=status, 9=qa, 10=dev_as, 11=qa_as, 12=total
        for col in (3, 4, 9, 10, 11):
            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 3,
                            "endRowIndex": row_count,
                            "startColumnIndex": col,
                            "endColumnIndex": col + 1,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {"red": 1.0, "green": 0.97, "blue": 0.88},
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                }
            )
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()


def pull_sheet(spreadsheet_id: str, tab_name: str) -> list[dict[str, Any]]:
    service = _service()
    tab = sanitize_tab_name(tab_name)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{tab}'!A:Z")
        .execute()
    )
    values = result.get("values") or []
    if len(values) < 4:
        return []

    header_row = values[2]
    key_by_col: dict[int, str] = {}
    for col_idx, label in enumerate(header_row):
        label_norm = (label or "").strip().lower()
        key = PULL_HEADER_ALIASES.get(label_norm)
        if key:
            key_by_col[col_idx] = key

    gid_col = next((i for i, k in key_by_col.items() if k == "asana_gid"), 0)
    field_cols = {col: key for col, key in key_by_col.items() if key in PULL_FIELDS}

    pulled: list[dict[str, Any]] = []
    for row in values[3:]:
        if len(row) <= gid_col:
            continue
        gid = str(row[gid_col]).strip()
        if not gid:
            continue
        item: dict[str, Any] = {"asana_gid": gid}
        for col, field in field_cols.items():
            if col >= len(row):
                continue
            val = row[col]
            if val == "" or val is None:
                continue
            if field in ("dev_estimate", "qa_estimate"):
                try:
                    item[field] = float(val)
                except (TypeError, ValueError):
                    item[field] = val
            else:
                item[field] = str(val).strip()
        pulled.append(item)
    return pulled


def sheet_url(spreadsheet_id: str, tab_name: str | None = None) -> str:
    base = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    if not tab_name:
        return base
    try:
        service = _service()
        tab = sanitize_tab_name(tab_name)
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for sheet in meta.get("sheets", []):
            props = sheet.get("properties") or {}
            if props.get("title") == tab:
                gid = props.get("sheetId")
                if gid is not None:
                    return f"{base}#gid={gid}"
    except Exception:
        logger.exception("Could not resolve sheet gid for %s", tab_name)
    return base