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

SPRINT_COLUMNS = [
    ("title", "Ticket"),
    ("ticket_type", "Type"),
    ("priority", "Priority"),
    ("asana_link", "Asana Link"),
    ("doc_link", "Jira Link"),
    ("jira_status", "Jira Status"),
    ("dev_estimate", "Dev Est (hrs)"),
    ("qa_estimate", "QA Est (hrs)"),
    ("total_estimate", "Total Est (hrs)"),
    ("dev_assigned", "Dev Assigned"),
    ("qa_assigned", "QA Assigned"),
    ("status", "Status"),
]

# Hidden key column + export columns (matches sprint_sheet.SPRINT_COLUMNS)
HEADER_KEYS = ["asana_gid"] + [key for key, _ in SPRINT_COLUMNS]
HEADER_LABELS = ["Asana GID"] + [label for _, label in SPRINT_COLUMNS]

PULL_FIELDS = {
    "qa_estimate",
    "dev_assigned",
    "qa_assigned",
    "status",
}

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
        HEADER_LABELS,
    ]

    active_rows = [
        row for row in (payload.get("rows") or [])
        if row.get("sheet_status") != "removed"
    ]
    active_rows.sort(key=_row_sort_key)

    for row in active_rows:
        line: list[Any] = [row.get("asana_gid")]
        for key, _ in SPRINT_COLUMNS:
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
                    "endColumnIndex": len(HEADER_LABELS),
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
    ]
    # Hide Asana GID column (A)
    requests.append(
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                "properties": {"hiddenByUser": True},
                "fields": "hiddenByUser",
            }
        }
    )
    if row_count > 3:
        # QA est, Dev assigned, QA assigned, Status — light yellow (editable)
        for col in (7, 9, 10, 11):
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
        for key, hdr in zip(HEADER_KEYS, HEADER_LABELS):
            if hdr.lower() == label_norm:
                key_by_col[col_idx] = key
                break

    gid_col = next((i for i, k in key_by_col.items() if k == "asana_gid"), 0)
    field_cols = {
        col: HEADER_KEYS[HEADER_LABELS.index(hdr)]
        for col, hdr in enumerate(header_row)
        if hdr in HEADER_LABELS and HEADER_KEYS[HEADER_LABELS.index(hdr)] in PULL_FIELDS
    }

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
    if tab_name:
        return f"{base}#gid=0"
    return base