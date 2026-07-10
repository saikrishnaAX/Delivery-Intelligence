"""Single-writer lock — prevents SQLite 'database is locked' from overlapping syncs."""

from __future__ import annotations

import asyncio

# One Asana sync / sprint-sheet rebuild at a time (auto-sync + manual Sync).
sync_lock = asyncio.Lock()
