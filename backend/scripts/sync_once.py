"""One-shot full sync: all Asana projects + sprint sheets + Jira."""
import asyncio
import sys

from app.services.auto_sync import run_auto_sync


async def main() -> int:
    print("Starting full sync for all projects...")
    result = await run_auto_sync()
    if result.get("skipped"):
        print("Skipped:", result.get("reason"))
        return 1

    for entry in result.get("projects", []):
        name = entry.get("project") or entry.get("project_gid") or "?"
        if entry.get("success"):
            print(f"  OK  {name}: {entry.get('tasks', 0)} tasks synced")
        else:
            err = entry.get("error", "unknown error")
            print(f"  FAIL {name}: {err[:200]}")

    print("Done at", result.get("synced_at", "n/a"))
    failed = sum(1 for e in result.get("projects", []) if not e.get("success"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
