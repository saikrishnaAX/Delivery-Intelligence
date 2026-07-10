import json
import urllib.request

url = "http://127.0.0.1:8003/api/v1/sprint-sheet?project_gid=1211199289980978&sprint_name=Sprint&refresh=true"
print("Fetching sprint sheet (refresh=true)...")
with urllib.request.urlopen(url, timeout=300) as resp:
    data = json.load(resp)

rows = [r for r in data.get("rows", []) if r.get("sheet_status") != "removed"]
print("Total active rows:", len(rows))
print("\nFirst 8 (should be Done / furthest along):")
for i, r in enumerate(rows[:8]):
    sec = r.get("section_name") or r.get("status") or "?"
    print(f"  {i+1}. [{sec}] {(r.get('title') or '')[:55]}")

print("\nLast 5 (should be Prioritized):")
for i, r in enumerate(rows[-5:], start=len(rows) - 4):
    sec = r.get("section_name") or r.get("status") or "?"
    print(f"  {i}. [{sec}] {(r.get('title') or '')[:55]}")
