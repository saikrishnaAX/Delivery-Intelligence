"""Sync Sprint planning from Asana + Jira, then rebuild/push July 2026 sheet."""
import asyncio
import sys

from app.database import SessionLocal
from app.models import AsanaProject, SprintSheet
from app.services.sync import SyncService
from app.services.sprint_sheet import SprintSheetService, sync_all_sprint_sheets
from app.services import google_sheets_sync as gsync
from app.services.sync_lock import sync_lock

SPRINT_GID = "1211199289980978"
SPRINT_NAME = "July 2026"


async def main() -> int:
    db = SessionLocal()
    try:
        proj = db.query(AsanaProject).filter(AsanaProject.gid == SPRINT_GID).first()
        if not proj:
            print("ERROR: Sprint planning project not found")
            return 1

        print(f"Project: {proj.name} ({SPRINT_GID})")
        print(f"Last synced: {proj.last_synced_at}")
        print("---")

        svc = SyncService(db)

        # 1) Asana (incremental if we already have a watermark; else full)
        use_incremental = bool(proj.last_synced_at)
        print(f"1/3 Asana sync ({'incremental' if use_incremental else 'full'})...")
        async with sync_lock:
            asana = await svc.sync_asana_project(SPRINT_GID, incremental=use_incremental)
        if not asana.get("success"):
            print("Asana FAILED:", asana.get("error"))
            return 1
        print(
            f"   OK tasks_synced={asana.get('tasks_synced')} "
            f"total={asana.get('total_in_project')} "
            f"incremental={asana.get('incremental')}"
        )

        # 2) Jira (full project pull + link)
        print("2/3 Jira sync...")
        jira = await svc.sync_jira_for_project(SPRINT_GID)
        if not jira.get("success") and not jira.get("skipped"):
            print("Jira FAILED:", jira.get("error") or jira)
            return 1
        print(
            f"   OK issues_synced={jira.get('issues_synced')} "
            f"linked={jira.get('linked_count')} skipped={jira.get('skipped')}"
        )

        # 3) Rebuild sprint sheets + Google push
        print("3/3 Sprint sheet rebuild + Google push...")
        sheet_results = sync_all_sprint_sheets(db, SPRINT_GID)
        for r in sheet_results:
            status = "OK" if r.get("success") else "FAIL"
            print(f"   {status} {r.get('sprint')}: {r.get('error') or 'rebuilt'}")

        sheet = (
            db.query(SprintSheet)
            .filter(SprintSheet.project_id == proj.id, SprintSheet.name == SPRINT_NAME)
            .first()
        )
        if sheet and sheet.google_spreadsheet_id:
            sprint_svc = SprintSheetService(db, SPRINT_GID)
            payload = sprint_svc.build(SPRINT_NAME, refresh=True)
            active = [r for r in payload.get("rows", []) if r.get("sheet_status") != "removed"]
            with_jira = sum(1 for r in active if r.get("doc_link"))
            print("---")
            print(f"July 2026 rows={len(active)} real_jira_links={with_jira}")
            print(f"Google synced at: {payload.get('google_synced_at') or sheet.google_synced_at}")
            print(f"URL: {payload.get('google_sheet_url') or gsync.sheet_url(sheet.google_spreadsheet_id, SPRINT_NAME)}")
            if active:
                top = active[0]
                print(f"Top row: [{top.get('status')}] {top.get('priority') or '-'} | {(top.get('title') or '')[:50]}")
        else:
            print("July 2026 sheet not linked to Google — in-app sheet still rebuilt")

        print("Done.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
