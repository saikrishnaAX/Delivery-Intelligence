"""SQLite-safe commit helpers."""

import time
from collections.abc import Callable

from sqlalchemy.exc import OperationalError, PendingRollbackError
from sqlalchemy.orm import Session


def _is_locked(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "locked" in msg or "rolled back" in msg


def commit_with_retry(db: Session, retries: int = 15) -> None:
    """Retry commits when SQLite reports database is locked."""
    for attempt in range(retries):
        try:
            db.commit()
            return
        except (OperationalError, PendingRollbackError) as exc:
            if not _is_locked(exc) or attempt >= retries - 1:
                raise
            db.rollback()
            time.sleep(min(2.0, 0.25 * (2**attempt)))


def flush_with_retry(db: Session, retries: int = 15) -> None:
    """Retry flushes when SQLite reports database is locked."""
    for attempt in range(retries):
        try:
            db.flush()
            return
        except (OperationalError, PendingRollbackError) as exc:
            if not _is_locked(exc) or attempt >= retries - 1:
                raise
            db.rollback()
            time.sleep(min(2.0, 0.25 * (2**attempt)))


def persist_with_retry(db: Session, write: Callable[[], None], retries: int = 15) -> None:
    """Run write (add rows), flush, and commit — re-running write after rollback on lock."""
    last_exc: BaseException | None = None
    for attempt in range(retries):
        try:
            write()
            db.flush()
            db.commit()
            return
        except (OperationalError, PendingRollbackError) as exc:
            last_exc = exc
            db.rollback()
            if not _is_locked(exc) or attempt >= retries - 1:
                raise
            time.sleep(min(2.0, 0.25 * (2**attempt)))
    if last_exc:
        raise last_exc
