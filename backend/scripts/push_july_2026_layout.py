"""Rebuild July 2026 sprint sheet and push to Google — drops unverified Jira links."""
from app.database import SessionLocal
from app.models import AsanaProject, SprintSheet
from app.services.sprint_sheet import SprintSheetService
from app.services import google_sheets_sync as gsync

db = SessionLocal()
try:
    proj = db.query(AsanaProject).filter(AsanaProject.gid == "1211199289980978").first()
    svc = SprintSheetService(db, proj.gid)
    sheet = (
        db.query(SprintSheet)
        .filter(SprintSheet.project_id == proj.id, SprintSheet.name == "July 2026")
        .first()
    )
    if not sheet:
        raise SystemExit("July 2026 sheet not found")

    payload = svc.build("July 2026", refresh=False)
    active = [r for r in payload["rows"] if r.get("sheet_status") != "removed"]
    with_jira = [r for r in active if r.get("doc_link")]
    without = [r for r in active if not r.get("doc_link")]
    print(f"rows={len(active)} real_jira={len(with_jira)} no_jira={len(without)}")
    for r in with_jira[:8]:
        print(" ", r.get("doc_link"), "|", (r.get("title") or "")[:45])

    if sheet.google_spreadsheet_id:
        synced = gsync.push_sheet(sheet.google_spreadsheet_id, "July 2026", payload)
        sheet.google_synced_at = synced
        sheet.google_sheet_url = gsync.sheet_url(sheet.google_spreadsheet_id, "July 2026")
        db.commit()
        print("pushed", synced.isoformat())
        print("url", sheet.google_sheet_url)
    else:
        print("not linked to Google — app payload updated only")
finally:
    db.close()
