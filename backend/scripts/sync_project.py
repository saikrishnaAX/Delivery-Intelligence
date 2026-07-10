"""Sync one Asana project by GID (Asana + Jira + sprint sheets)."""
import asyncio
import sys

from app.database import SessionLocal
from app.services.auto_sync import sync_project_after_asana_change


async def main() -> int:
    gid = sys.argv[1] if len(sys.argv) > 1 else "1210572122500501"
    db = SessionLocal()
    try:
        print(f"Syncing project {gid}...")
        entry = await sync_project_after_asana_change(db, gid, source="manual")
        if entry.get("success"):
            print(f"OK: {entry.get('tasks', 0)} tasks synced")
            return 0
        print("Failed:", entry)
        return 1
    except Exception as exc:
        print("Error:", exc)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
