import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    ForeignKey, Enum, JSON, Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    BLOCKED = "blocked"


class TicketCategory(str, enum.Enum):
    BUG = "bug"
    ENHANCEMENT = "enhancement"
    TASK = "task"
    REQUIREMENT = "requirement"
    CONFIGURATION = "configuration"
    KNOWLEDGE_GAP = "knowledge_gap"
    DUPLICATE = "duplicate"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    tier = Column(String(50), default="standard")
    industry = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    tickets = relationship("Ticket", back_populates="customer")


class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    product_area = Column(String(100))
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True)

    tickets = relationship("Ticket", back_populates="module")
    project = relationship("AsanaProject", back_populates="modules")

    __table_args__ = (
        Index("ix_modules_name_project", "name", "project_id", unique=True),
    )


class AsanaProject(Base):
    __tablename__ = "asana_projects"

    id = Column(Integer, primary_key=True, index=True)
    gid = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    workspace_gid = Column(String(50))
    jira_project_key = Column(String(50))
    ticket_count = Column(Integer, default=0)
    last_synced_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    tickets = relationship("Ticket", back_populates="project")
    modules = relationship("Module", back_populates="project")
    clusters = relationship("IssueCluster", back_populates="project")
    jira_issues = relationship("JiraIssue", back_populates="project")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    asana_gid = Column(String(50), unique=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    status = Column(Enum(TicketStatus), default=TicketStatus.OPEN, index=True)
    support_category = Column(Enum(TicketCategory), index=True)
    ai_category = Column(Enum(TicketCategory), index=True)
    priority = Column(Enum(TicketPriority), default=TicketPriority.MEDIUM, index=True)
    module_id = Column(Integer, ForeignKey("modules.id"), index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    assignee = Column(String(255))
    reporter = Column(String(255))
    ticket_owner = Column(String(255), index=True)
    workshop_name = Column(String(255), index=True)
    workshop_id = Column(String(50))
    ax_id = Column(String(50))
    asana_type_raw = Column(String(100))
    asana_priority_raw = Column(String(50))
    source = Column(String(100))
    expected_delivery = Column(DateTime)
    completion_date = Column(DateTime)
    is_workflow_blocker = Column(Boolean, default=False, index=True)
    is_critical_blocker = Column(Boolean, default=False, index=True)
    is_reopened = Column(Boolean, default=False)
    sla_hours = Column(Integer, default=48)
    sla_met = Column(Boolean)
    resolution_hours = Column(Float)
    cluster_id = Column(Integer, ForeignKey("issue_clusters.id"), index=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True)
    jira_key = Column(String(50), index=True)
    tags = Column(JSON, default=list)
    asana_url = Column(String(500))
    dev_effort_hours = Column(Float)
    qa_effort_hours = Column(Float)
    total_effort_hours = Column(Float)
    product_stage = Column(String(100))
    build_in = Column(String(100))
    dor_value = Column(String(50))
    released_at = Column(DateTime, index=True)
    asana_board_index = Column(Integer, index=True)
    removed_from_asana = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, index=True)

    customer = relationship("Customer", back_populates="tickets")
    module = relationship("Module", back_populates="tickets")
    cluster = relationship("IssueCluster", back_populates="tickets")
    project = relationship("AsanaProject", back_populates="tickets")
    jira_issue = relationship("JiraIssue", back_populates="ticket", uselist=False)

    __table_args__ = (
        Index("ix_tickets_status_priority", "status", "priority"),
        Index("ix_tickets_created_closed", "created_at", "closed_at"),
        Index("ix_tickets_project_status", "project_id", "status"),
    )


class IssueCluster(Base):
    __tablename__ = "issue_clusters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    ai_summary = Column(Text)
    ticket_count = Column(Integer, default=0)
    severity = Column(String(50), default="medium")
    module_id = Column(Integer, ForeignKey("modules.id"))
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tickets = relationship("Ticket", back_populates="cluster")
    module = relationship("Module")
    project = relationship("AsanaProject", back_populates="clusters")


class JiraIssue(Base):
    __tablename__ = "jira_issues"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), unique=True, nullable=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True)
    project_key = Column(String(50), index=True)
    jira_key = Column(String(50), unique=True, index=True)
    summary = Column(String(500))
    status = Column(String(100))
    issue_type = Column(String(100))
    sprint_name = Column(String(255))
    sprint_state = Column(String(50))
    story_points = Column(Float)
    assignee = Column(String(255))
    jira_url = Column(String(500))
    synced_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket", back_populates="jira_issue")
    project = relationship("AsanaProject", back_populates="jira_issues")


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, index=True)
    page = Column(String(100), index=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True)
    insight_type = Column(String(50))
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    severity = Column(String(50), default="info")
    meta_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExecutiveSummary(Base):
    __tablename__ = "executive_summaries"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True)
    summary = Column(Text, nullable=False)
    key_metrics = Column(JSON, default=dict)
    recommendations = Column(JSON, default=list)
    generated_at = Column(DateTime, default=datetime.utcnow)


class TicketSectionMove(Base):
    __tablename__ = "ticket_section_moves"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), index=True, nullable=False)
    asana_gid = Column(String(50), index=True)
    from_section = Column(String(255))
    to_section = Column(String(255), nullable=False, index=True)
    moved_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    ticket = relationship("Ticket")


class SprintSheet(Base):
    __tablename__ = "sprint_sheets"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    google_spreadsheet_id = Column(String(100))
    google_sheet_url = Column(String(500))
    google_tab_name = Column(String(100))
    google_synced_at = Column(DateTime)
    apps_script_url = Column(String(500))
    apps_script_secret = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rows = relationship("SprintSheetRow", back_populates="sheet", cascade="all, delete-orphan")
    project = relationship("AsanaProject")

    __table_args__ = (
        Index("ix_sprint_sheets_project_name", "project_id", "name", unique=True),
    )


class SprintSheetRow(Base):
    __tablename__ = "sprint_sheet_rows"

    id = Column(Integer, primary_key=True, index=True)
    sheet_id = Column(Integer, ForeignKey("sprint_sheets.id"), index=True, nullable=False)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), index=True)
    asana_gid = Column(String(50), nullable=False, index=True)
    sheet_status = Column(String(50), default="in_sprint", index=True)
    row_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sheet = relationship("SprintSheet", back_populates="rows")
    ticket = relationship("Ticket")

    __table_args__ = (
        Index("ix_sprint_sheet_rows_sheet_gid", "sheet_id", "asana_gid", unique=True),
    )


class AppMeta(Base):
    __tablename__ = "app_meta"

    key = Column(String(100), primary_key=True)
    value = Column(Text)


# ── Organization ────────────────────────────────────────────────────────────

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("TeamMembership", back_populates="team", cascade="all, delete-orphan")


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    role = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("TeamMembership", back_populates="person", cascade="all, delete-orphan")
    customer_accounts = relationship("CustomerAccount", back_populates="primary_support")


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False, index=True)
    is_lead = Column(Boolean, default=False)

    team = relationship("Team", back_populates="memberships")
    person = relationship("Person", back_populates="memberships")

    __table_args__ = (
        Index("ix_team_memberships_team_person", "team_id", "person_id", unique=True),
    )


class CustomerAccount(Base):
    __tablename__ = "customer_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    workshop_name = Column(String(255), nullable=False, unique=True, index=True)
    ax_id = Column(String(50), index=True)
    tier = Column(String(50), default="standard")
    industry = Column(String(100))
    workshop_email = Column(String(255))
    support_contact_email = Column(String(255))
    primary_support_person_id = Column(Integer, ForeignKey("people.id"), index=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    primary_support = relationship("Person", back_populates="customer_accounts")
    support_history = relationship("CustomerSupportHistory", back_populates="customer_account")


class CustomerSupportHistory(Base):
    __tablename__ = "customer_support_history"

    id = Column(Integer, primary_key=True, index=True)
    customer_account_id = Column(Integer, ForeignKey("customer_accounts.id"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id"), index=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

    customer_account = relationship("CustomerAccount", back_populates="support_history")
    person = relationship("Person")


# ── Activity & Communications ───────────────────────────────────────────────

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    module = Column(String(100), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(100))
    entity_id = Column(String(100))
    summary = Column(String(500), nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ReleaseNoteSend(Base):
    __tablename__ = "release_note_sends"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True)
    sprint_name = Column(String(255))
    subject = Column(String(500))
    recipient_emails = Column(JSON, default=list)
    item_count = Column(Integer, default=0)
    docx_path = Column(String(500))
    payload_snapshot = Column(JSON, default=dict)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)
    activity_log_id = Column(Integer, ForeignKey("activity_logs.id"))


class ReleaseNoteArchive(Base):
    """Uploaded or saved historical release note documents."""

    __tablename__ = "release_note_archives"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True)
    release_date = Column(DateTime, nullable=False, index=True)
    title = Column(String(255))
    sprint_name = Column(String(255))
    original_filename = Column(String(500), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    source = Column(String(50), default="upload")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    project = relationship("AsanaProject")


class WorkshopEmailDraft(Base):
    """Human-reviewed email draft — never sent automatically."""

    __tablename__ = "workshop_email_drafts"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), index=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), index=True)
    draft_type = Column(String(50), nullable=False, index=True)  # release_announcement
    status = Column(String(50), default="pending", index=True)  # pending | sent | cancelled
    workshop_name = Column(String(255), index=True)
    to_emails = Column(JSON, default=list)
    cc_emails = Column(JSON, default=list)
    subject = Column(String(500), nullable=False)
    body_text = Column(Text, nullable=False)
    body_html = Column(Text)
    ticket_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    sent_at = Column(DateTime)
    cancelled_at = Column(DateTime)

    ticket = relationship("Ticket")
    project = relationship("AsanaProject")


class ScheduledReminder(Base):
    __tablename__ = "scheduled_reminders"

    id = Column(Integer, primary_key=True, index=True)
    reminder_type = Column(String(50), nullable=False, default="workshop_feedback", index=True)
    workshop_name = Column(String(255), index=True)
    sprint_sheet_id = Column(Integer, ForeignKey("sprint_sheets.id"), index=True)
    support_person_id = Column(Integer, ForeignKey("people.id"), index=True)
    due_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(50), default="pending", index=True)
    sent_at = Column(DateTime)
    activity_log_id = Column(Integer, ForeignKey("activity_logs.id"))
    meta_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    sprint_sheet = relationship("SprintSheet")
    support_person = relationship("Person")


# ── Cluster Deep Analysis ───────────────────────────────────────────────────

class ClusterAnalysisJob(Base):
    __tablename__ = "cluster_analysis_jobs"

    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(Integer, ForeignKey("issue_clusters.id"), nullable=False, index=True)
    status = Column(String(50), default="pending", index=True)
    batch_size = Column(Integer, default=10)
    tickets_total = Column(Integer, default=0)
    tickets_processed = Column(Integer, default=0)
    ticket_cap = Column(Integer, default=50)
    error_message = Column(Text)
    open_ticket_count_snapshot = Column(Integer, default=0)
    dismissed_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    cluster = relationship("IssueCluster")
    results = relationship("ClusterAnalysisResult", back_populates="job", cascade="all, delete-orphan")


class ClusterAnalysisResult(Base):
    __tablename__ = "cluster_analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("cluster_analysis_jobs.id"), nullable=False, index=True)
    theme_title = Column(String(255), nullable=False)
    one_line_issue = Column(Text)
    ticket_ids = Column(JSON, default=list)
    suggested_test_cases = Column(JSON, default=list)
    confidence = Column(Float)
    topic_module = Column(String(100))
    ticket_percentage = Column(Float)
    intelligence = Column(JSON, default=dict)

    job = relationship("ClusterAnalysisJob", back_populates="results")


# ── Issue Intelligence (user-facing recurring issues) ───────────────────────

class IssueIntelligenceJob(Base):
    __tablename__ = "issue_intelligence_jobs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), nullable=False, index=True)
    status = Column(String(50), default="pending", index=True)
    tickets_total = Column(Integer, default=0)
    tickets_processed = Column(Integer, default=0)
    issues_found = Column(Integer, default=0)
    analysis_mode = Column(String(50), default="engineering_fix")
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("AsanaProject")
    issues = relationship("RecurringIssue", back_populates="job", cascade="all, delete-orphan")


class RecurringIssue(Base):
    __tablename__ = "recurring_issues"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("asana_projects.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("issue_intelligence_jobs.id"), nullable=False, index=True)
    issue_name = Column(String(500), nullable=False)
    engineering_fix_key = Column(String(100), index=True)
    issue_type = Column(String(50), default="product_bug", index=True)
    severity = Column(String(50), default="medium", index=True)
    ticket_count = Column(Integer, default=0)
    open_count = Column(Integer, default=0)
    workshop_count = Column(Integer, default=0)
    trend = Column(String(50), default="stable")
    confidence = Column(Float, default=0.5)
    priority_score = Column(Float, default=0)
    recurring_since = Column(String(20))
    latest_occurrence = Column(String(20))
    ticket_ids = Column(JSON, default=list)
    affected_workshops = Column(JSON, default=list)
    affected_modules = Column(JSON, default=list)
    affected_releases = Column(JSON, default=list)
    intelligence = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("AsanaProject")
    job = relationship("IssueIntelligenceJob", back_populates="issues")
