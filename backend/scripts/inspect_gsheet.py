"""Inspect linked sprint Google Sheet."""
from app.services import google_sheets_sync as gsync

sid = "1IK1N-6gz-nOGwOMrtZsURRydPBWBrEaj5n3O9ZT5X9E"
gid_user = 1857765487

if not gsync.is_configured():
    print("NOT CONFIGURED")
    raise SystemExit(1)

svc = gsync._service()
meta = svc.spreadsheets().get(spreadsheetId=sid).execute()
print("Tabs:")
for s in meta.get("sheets", []):
    p = s["properties"]
    mark = " <-- user gid" if p["sheetId"] == gid_user else ""
    print(f"  {p['title']!r} gid={p['sheetId']}{mark}")

for tab in ["July Sprint", "Sheet1", "Sprint"]:
    try:
        res = svc.spreadsheets().values().get(
            spreadsheetId=sid, range=f"'{tab}'!A1:L10"
        ).execute()
        vals = res.get("values", [])
        if not vals:
            continue
        print(f"\n--- {tab!r} ({len(vals)} rows) ---")
        for i, row in enumerate(vals[:8]):
            print(i + 1, row[:7])
    except Exception as e:
        print(f"{tab}: {e}")

# Tab matching user gid
user_tab = next(
    (s["properties"]["title"] for s in meta.get("sheets", []) if s["properties"]["sheetId"] == gid_user),
    None,
)
if user_tab:
    res = svc.spreadsheets().values().get(
        spreadsheetId=sid, range=f"'{user_tab}'!A1:L10"
    ).execute()
    vals = res.get("values", [])
    print(f"\n--- USER TAB {user_tab!r} ---")
    for i, row in enumerate(vals[:8]):
        print(i + 1, row[:7])
