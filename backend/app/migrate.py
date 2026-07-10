"""Apply lightweight SQLite schema updates without dropping data."""

import re
import sqlite3
import time
from pathlib import Path

from app.config import get_settings

settings = get_settings()
db_path = Path("delivery_intelligence.db")
if not db_path.exists():
    db_path = Path("..") / "delivery_intelligence.db"

MIGRATIONS = [
    ("asana_projects", "CREATE TABLE IF NOT EXISTS asana_projects ("
     "id INTEGER PRIMARY KEY, gid VARCHAR(50) UNIQUE NOT NULL, name VARCHAR(255) NOT NULL, "
     "workspace_gid VARCHAR(50), jira_project_key VARCHAR(50), ticket_count INTEGER DEFAULT 0, "
     "last_synced_at DATETIME, created_at DATETIME)"),
    ("modules", "project_id", "INTEGER"),
    ("tickets", "project_id", "INTEGER"),
    ("issue_clusters", "project_id", "INTEGER"),
    ("jira_issues", "project_id", "INTEGER"),
    ("jira_issues", "project_key", "VARCHAR(50)"),
    ("ai_insights", "project_id", "INTEGER"),
    ("executive_summaries", "project_id", "INTEGER"),
    ("tickets", "ticket_owner", "VARCHAR(255)"),
    ("tickets", "workshop_name", "VARCHAR(255)"),
    ("tickets", "workshop_id", "VARCHAR(50)"),
    ("tickets", "ax_id", "VARCHAR(50)"),
    ("tickets", "asana_type_raw", "VARCHAR(100)"),
    ("tickets", "asana_priority_raw", "VARCHAR(50)"),
    ("tickets", "source", "VARCHAR(100)"),
    ("tickets", "expected_delivery", "DATETIME"),
    ("tickets", "completion_date", "DATETIME"),
    ("tickets", "is_workflow_blocker", "BOOLEAN DEFAULT 0"),
    ("tickets", "dev_effort_hours", "REAL"),
    ("tickets", "qa_effort_hours", "REAL"),
    ("tickets", "total_effort_hours", "REAL"),
    ("tickets", "product_stage", "VARCHAR(100)"),
    ("tickets", "build_in", "VARCHAR(100)"),
    ("tickets", "dor_value", "VARCHAR(50)"),
    ("tickets", "released_at", "DATETIME"),
    ("tickets", "asana_board_index", "INTEGER"),
    ("tickets", "removed_from_asana", "BOOLEAN DEFAULT 0"),
    ("ticket_section_moves", "CREATE TABLE IF NOT EXISTS ticket_section_moves ("
     "id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL, asana_gid VARCHAR(50), "
     "from_section VARCHAR(255), to_section VARCHAR(255) NOT NULL, "
     "moved_at DATETIME NOT NULL, created_at DATETIME)"),
    ("sprint_sheets", "CREATE TABLE IF NOT EXISTS sprint_sheets ("
     "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, name VARCHAR(255) NOT NULL, "
     "is_active BOOLEAN DEFAULT 1, created_at DATETIME, updated_at DATETIME)"),
    ("sprint_sheet_rows", "CREATE TABLE IF NOT EXISTS sprint_sheet_rows ("
     "id INTEGER PRIMARY KEY, sheet_id INTEGER NOT NULL, ticket_id INTEGER, "
     "asana_gid VARCHAR(50) NOT NULL, sheet_status VARCHAR(50) DEFAULT 'in_sprint', "
     "row_data TEXT NOT NULL, created_at DATETIME, updated_at DATETIME)"),
    ("app_meta", "CREATE TABLE IF NOT EXISTS app_meta (key VARCHAR(100) PRIMARY KEY, value TEXT)"),
    ("release_note_archives", "CREATE TABLE IF NOT EXISTS release_note_archives ("
     "id INTEGER PRIMARY KEY, project_id INTEGER, release_date DATETIME NOT NULL, "
     "title VARCHAR(255), sprint_name VARCHAR(255), original_filename VARCHAR(500) NOT NULL, "
     "file_path VARCHAR(500) NOT NULL, file_size INTEGER DEFAULT 0, source VARCHAR(50) DEFAULT 'upload', "
     "created_at DATETIME)"),
    ("sprint_sheets", "google_spreadsheet_id", "VARCHAR(100)"),
    ("sprint_sheets", "google_sheet_url", "VARCHAR(500)"),
    ("sprint_sheets", "google_tab_name", "VARCHAR(100)"),
    ("sprint_sheets", "google_synced_at", "DATETIME"),
    ("sprint_sheets", "apps_script_url", "VARCHAR(500)"),
    ("sprint_sheets", "apps_script_secret", "VARCHAR(255)"),
    ("cluster_analysis_results", "topic_module", "VARCHAR(100)"),
    ("cluster_analysis_results", "ticket_percentage", "REAL"),
    ("cluster_analysis_results", "intelligence", "TEXT"),
    ("cluster_analysis_jobs", "open_ticket_count_snapshot", "INTEGER DEFAULT 0"),
    ("cluster_analysis_jobs", "dismissed_at", "DATETIME"),
    ("issue_intelligence_jobs", "CREATE TABLE IF NOT EXISTS issue_intelligence_jobs ("
     "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, status VARCHAR(50) DEFAULT 'pending', "
     "tickets_total INTEGER DEFAULT 0, tickets_processed INTEGER DEFAULT 0, issues_found INTEGER DEFAULT 0, "
     "analysis_mode VARCHAR(50) DEFAULT 'engineering_fix', error_message TEXT, "
     "started_at DATETIME, completed_at DATETIME, created_at DATETIME)"),
    ("recurring_issues", "CREATE TABLE IF NOT EXISTS recurring_issues ("
     "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, job_id INTEGER NOT NULL, "
     "issue_name VARCHAR(500) NOT NULL, engineering_fix_key VARCHAR(100), issue_type VARCHAR(50) DEFAULT 'product_bug', "
     "severity VARCHAR(50) DEFAULT 'medium', ticket_count INTEGER DEFAULT 0, open_count INTEGER DEFAULT 0, "
     "workshop_count INTEGER DEFAULT 0, trend VARCHAR(50) DEFAULT 'stable', confidence REAL DEFAULT 0.5, "
     "priority_score REAL DEFAULT 0, recurring_since VARCHAR(20), latest_occurrence VARCHAR(20), "
     "ticket_ids TEXT, affected_workshops TEXT, affected_modules TEXT, affected_releases TEXT, "
     "intelligence TEXT, created_at DATETIME)"),
    ("customer_accounts", "workshop_email", "VARCHAR(255)"),
    ("customer_accounts", "support_contact_email", "VARCHAR(255)"),
    ("customer_accounts", "ax_id", "VARCHAR(50)"),
    ("workshop_email_drafts", "CREATE TABLE IF NOT EXISTS workshop_email_drafts ("
     "id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL, project_id INTEGER, "
     "draft_type VARCHAR(50) NOT NULL, status VARCHAR(50) DEFAULT 'pending', "
     "workshop_name VARCHAR(255), to_emails TEXT, cc_emails TEXT, "
     "subject VARCHAR(500) NOT NULL, body_text TEXT NOT NULL, body_html TEXT, "
     "ticket_snapshot TEXT, created_at DATETIME, sent_at DATETIME, cancelled_at DATETIME)"),
]


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _indexes(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=?", (table,)
    ).fetchall()
    return {name: sql for name, sql in rows if name}


def _fix_modules_unique_index(conn: sqlite3.Connection) -> None:
    """Replace global modules.name unique index with per-project uniqueness."""
    indexes = _indexes(conn, "modules")
    if "ix_modules_name" in indexes and "ix_modules_name_project" not in indexes:
        conn.execute("DROP INDEX ix_modules_name")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_modules_name_project ON modules (name, project_id)"
        )


def _purge_test_release_archives(conn: sqlite3.Connection) -> None:
    """Remove dev/test archive rows left from local upload testing."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "release_note_archives" not in tables:
        return
    rows = conn.execute(
        "SELECT id, title, original_filename FROM release_note_archives"
    ).fetchall()
    for row_id, title, filename in rows:
        t = (title or "").strip().lower()
        f = (filename or "").strip().lower()
        is_test = (
            t in {"test", "test upload"}
            or t.startswith("test upload")
            or f in {"test.docx", "hist.docx"}
            or "_test." in f
            or ("hist.docx" in f and t.startswith("test"))
        )
        if is_test:
            conn.execute("DELETE FROM release_note_archives WHERE id = ?", (row_id,))


def _backfill_customer_ax_ids(conn: sqlite3.Connection) -> None:
    """Move AX ID from legacy notes field into customer_accounts.ax_id."""
    if "customer_accounts" not in {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}:
        return
    if "ax_id" not in _columns(conn, "customer_accounts"):
        return
    rows = conn.execute(
        "SELECT id, notes, ax_id FROM customer_accounts WHERE (ax_id IS NULL OR ax_id = '') AND notes IS NOT NULL"
    ).fetchall()
    for row_id, notes, _ in rows:
        match = re.search(r"AX ID:\s*(\S+)", notes or "", re.I)
        if match:
            conn.execute(
                "UPDATE customer_accounts SET ax_id = ? WHERE id = ?",
                (match.group(1).strip(), row_id),
            )


def migrate() -> None:
    if not db_path.exists():
        return
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            _run_migrations()
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    if last_err:
        raise last_err


def _run_migrations() -> None:
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute(MIGRATIONS[0][1])
        for item in MIGRATIONS[1:]:
            if len(item) == 2:
                table, ddl = item
                conn.execute(ddl)
                continue
            table, col, col_type = item
            if table not in {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}:
                continue
            if col not in _columns(conn, table):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        _fix_modules_unique_index(conn)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_sprint_sheets_project_name "
            "ON sprint_sheets (project_id, name)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_sprint_sheet_rows_sheet_gid "
            "ON sprint_sheet_rows (sheet_id, asana_gid)"
        )
        _purge_test_release_archives(conn)
        _backfill_customer_ax_ids(conn)
        _workshop_email_drafts_nullable_ticket(conn)
        conn.commit()
    finally:
        conn.close()
    _backfill_support_emails_from_teams()


def _workshop_email_drafts_nullable_ticket(conn: sqlite3.Connection) -> None:
    """Allow release announcement drafts without a linked ticket."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "workshop_email_drafts" not in tables:
        return
    info = conn.execute("PRAGMA table_info(workshop_email_drafts)").fetchall()
    ticket_col = next((c for c in info if c[1] == "ticket_id"), None)
    if not ticket_col or ticket_col[3] == 0:
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workshop_email_drafts_new (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER,
            project_id INTEGER,
            draft_type VARCHAR(50) NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            workshop_name VARCHAR(255),
            to_emails TEXT,
            cc_emails TEXT,
            subject VARCHAR(500) NOT NULL,
            body_text TEXT NOT NULL,
            body_html TEXT,
            ticket_snapshot TEXT,
            created_at DATETIME,
            sent_at DATETIME,
            cancelled_at DATETIME
        )
        """
    )
    conn.execute(
        """
        INSERT INTO workshop_email_drafts_new
        SELECT id, ticket_id, project_id, draft_type, status, workshop_name,
               to_emails, cc_emails, subject, body_text, body_html, ticket_snapshot,
               created_at, sent_at, cancelled_at
        FROM workshop_email_drafts
        """
    )
    conn.execute("DROP TABLE workshop_email_drafts")
    conn.execute("ALTER TABLE workshop_email_drafts_new RENAME TO workshop_email_drafts")


def _backfill_support_emails_from_teams() -> None:
    """Match workshop support agents to team roster emails."""
    try:
        from app.database import SessionLocal
        from app.services.org_service import OrgService

        db = SessionLocal()
        try:
            OrgService(db).reconcile_workshop_support_from_teams()
        finally:
            db.close()
    except Exception:
        pass


if __name__ == "__main__":
    migrate()
    print("Migration complete")
