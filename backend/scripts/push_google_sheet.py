import json
import urllib.request

url = "http://127.0.0.1:8003/api/v1/sprint-sheet?project_gid=1211199289980978&sprint_name=Sprint&refresh=true"
print("Refreshing sprint sheet + Google Sheet...")
with urllib.request.urlopen(url, timeout=300) as resp:
    data = json.load(resp)

rows = [r for r in data.get("rows", []) if r.get("sheet_status") != "removed"]
print("Google synced:", data.get("google_synced_at") or data.get("google_sync_error") or "not linked")
print("\nFirst 5 rows (Status column):")
for i, r in enumerate(rows[:5]):
    print(f"  {i+1}. status={r.get('status')} | {(r.get('title') or '')[:50]}")
print("\nLast 3 rows:")
for i, r in enumerate(rows[-3:], start=len(rows) - 2):
    print(f"  {i}. status={r.get('status')} | {(r.get('title') or '')[:50]}")
