"""One-off: sync project from Asana and refresh sprint sheet."""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8003/api/v1"
PROJECT_GID = "1211199289980978"


def show_prioritized(sheet: dict) -> None:
    pr = sheet.get("prioritized_rows", [])
    print("Prioritized count:", len(pr))
    print("Top 10 (Asana board order):")
    for i, r in enumerate(pr[:10]):
        pri = r.get("priority") or "-"
        title = (r.get("title") or "")[:65]
        print(f"  {i + 1}. [{pri}] {title}")
    if sheet.get("google_synced_at"):
        print("Google sheet synced at:", sheet.get("google_synced_at"))
    elif sheet.get("google_sync_error"):
        print("Google sync note:", sheet.get("google_sync_error"))


def main() -> int:
    sync_only = "--sheet-only" in sys.argv

    if not sync_only:
        print("Starting Asana sync...")
        req = urllib.request.Request(f"{BASE}/sync/{PROJECT_GID}", method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=300) as resp:
            sync = json.load(resp)
        print("Sync OK:", sync.get("message") or sync.get("status") or "done")
        if sync.get("tickets_synced") is not None:
            print("Tickets synced:", sync.get("tickets_synced"))

    print("Refreshing sprint sheet...")
    sheet_url = f"{BASE}/sprint-sheet?project_gid={PROJECT_GID}&sprint_name=Sprint&refresh=true"
    with urllib.request.urlopen(sheet_url, timeout=300) as resp:
        sheet = json.load(resp)
    show_prioritized(sheet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
