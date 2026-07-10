from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.models import TicketCategory, TicketStatus, TicketPriority


# ── Shared ──────────────────────────────────────────────────────────────────

class AIInsightResponse(BaseModel):
    id: int
    page: str
    insight_type: str
    title: str
    content: str
    severity: str
    metadata: dict = Field(default={}, validation_alias="meta_data")
    created_at: datetime

    class Config:
        from_attributes = True


class ExecutiveSummaryResponse(BaseModel):
    id: int
    summary: str
    key_metrics: dict
    recommendations: list[str]
    generated_at: datetime

    class Config:
        from_attributes = True


# ── Executive Dashboard ─────────────────────────────────────────────────────

class ExecutiveTicketItem(BaseModel):
    id: int
    title: str
    workshop_name: Optional[str] = None
    assignee: Optional[str] = None
    ticket_owner: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    days_open: int
    priority: str
    detail: Optional[str] = None
    asana_url: Optional[str] = None
    module_name: Optional[str] = None
    jira_key: Optional[str] = None


class ExecutivePipelineStage(BaseModel):
    stage: str
    count: int
    tickets: list[ExecutiveTicketItem] = []


class ExecutiveWorkshopAlert(BaseModel):
    name: str
    open_tickets: int
    blockers: int


class ExecutiveTeamPulse(BaseModel):
    top_creator: Optional[str] = None
    top_creator_count: int = 0
    top_closer: Optional[str] = None
    top_closer_count: int = 0
    highest_open_load: Optional[str] = None
    highest_open_count: int = 0


class ExecutiveWorkflowHotspot(BaseModel):
    area: str
    open_count: int


class ExecutiveMetrics(BaseModel):
    project_type: str = "support"
    project_name: Optional[str] = None
    dashboard_description: Optional[str] = None
    tickets_created_today: int
    tickets_closed_today: int
    open_tickets: int
    total_closed: int = 0
    escalations_count: int = 0
    backlog_count: int = 0
    released_count: int = 0
    in_pipeline_count: int = 0
    testing_stuck_count: int = 0
    avg_resolution_hours: float
    critical_open_issues: int
    sla_compliance_rate: float
    reopened_tickets: int
    overdue_count: int = 0
    created_today_tickets: list[ExecutiveTicketItem] = []
    closed_today_tickets: list[ExecutiveTicketItem] = []
    open_tickets_list: list[ExecutiveTicketItem] = []
    total_closed_tickets: list[ExecutiveTicketItem] = []
    escalation_tickets: list[ExecutiveTicketItem] = []
    backlog_tickets: list[ExecutiveTicketItem] = []
    released_tickets: list[ExecutiveTicketItem] = []
    pipeline_stages: list[ExecutivePipelineStage] = []
    reopened_tickets_list: list[ExecutiveTicketItem] = []
    urgent_blockers: list[ExecutiveTicketItem] = []
    overdue_tickets: list[ExecutiveTicketItem] = []
    workshop_alerts: list[ExecutiveWorkshopAlert] = []
    team_pulse: ExecutiveTeamPulse = ExecutiveTeamPulse()
    workflow_hotspots: list[ExecutiveWorkflowHotspot] = []


# ── Execution Board ───────────────────────────────────────────────────────────

class ExecutionTask(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    count: int
    priority: str = "medium"
    route: str = "/"
    category: str = "general"


class WorkshopOperationalStatus(BaseModel):
    name: str
    status: str
    open_tickets: int = 0
    show_stoppers: int = 0
    escalations: int = 0
    headline: str = ""


class ExecutiveDrilldownResponse(BaseModel):
    metric: str
    total: int
    tickets: list[ExecutiveTicketItem]
    limit: int = 200
    offset: int = 0
    stage: Optional[str] = None


class ExecutionBoardResponse(BaseModel):
    operational_status: str
    status_headline: str
    status_detail: str
    show_stopper_count: int
    workshops_with_show_stoppers: int
    workshops_at_risk: int
    workshops_healthy: int
    today_task_count: int
    today_item_count: int = 0
    today_tasks: list[ExecutionTask] = []
    workshop_statuses: list[WorkshopOperationalStatus] = []
    workshops_hidden_count: int = 0
    metrics: ExecutiveMetrics


# ── Tickets ─────────────────────────────────────────────────────────────────

class TicketResponse(BaseModel):
    id: int
    asana_gid: Optional[str]
    title: str
    description: Optional[str]
    status: TicketStatus
    support_category: Optional[TicketCategory]
    ai_category: Optional[TicketCategory]
    priority: TicketPriority
    module_name: Optional[str] = None
    customer_name: Optional[str] = None
    workshop_name: Optional[str] = None
    assignee: Optional[str]
    reporter: Optional[str] = None
    ticket_owner: Optional[str] = None
    is_critical_blocker: bool
    is_reopened: bool
    sla_met: Optional[bool]
    resolution_hours: Optional[float]
    cluster_name: Optional[str] = None
    jira_key: Optional[str]
    asana_type_raw: Optional[str] = None
    asana_url: Optional[str] = None
    tags: list = []
    created_at: datetime
    closed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TicketListResponse(BaseModel):
    tickets: list[TicketResponse]
    total: int
    page: int
    page_size: int


# ── Classification ──────────────────────────────────────────────────────────

class CategoryBreakdown(BaseModel):
    category: str
    count: int
    open_count: int = 0
    percentage: float
    trend: list[dict] = []


class ClassificationAnalytics(BaseModel):
    support_breakdown: list[CategoryBreakdown]
    ai_breakdown: list[CategoryBreakdown]
    total_tickets: int
    most_common_category: str


# ── Clustering ──────────────────────────────────────────────────────────────

class ClusterResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    ai_summary: Optional[str]
    ticket_count: int
    open_ticket_count: int = 0
    severity: str
    module_name: Optional[str] = None
    sample_tickets: list[str] = []
    analysis_job_id: Optional[int] = None
    analysis_defect_count: Optional[int] = None
    analysis_dismissed: bool = False
    analysis_open_snapshot: Optional[int] = None
    can_reanalyze: bool = True
    active_analysis_job_id: Optional[int] = None
    analysis_in_progress: bool = False

    class Config:
        from_attributes = True


class ClusteringAnalytics(BaseModel):
    clusters: list[ClusterResponse]
    total_clusters: int
    unclustered_tickets: int


# ── Heat Map ────────────────────────────────────────────────────────────────

class ModuleHeatMapItem(BaseModel):
    module: str
    product_area: str
    ticket_count: int
    open_count: int
    critical_count: int
    avg_resolution_hours: float
    intensity: float


class HeatMapAnalytics(BaseModel):
    modules: list[ModuleHeatMapItem]
    hottest_module: str
    total_modules: int


# ── Support Accuracy ────────────────────────────────────────────────────────

class ClassificationMismatch(BaseModel):
    ticket_id: int
    title: str
    support_category: str
    ai_category: str
    confidence: float


class SupportAccuracyAnalytics(BaseModel):
    accuracy_rate: float
    total_compared: int
    matches: int
    mismatches: list[ClassificationMismatch]
    category_accuracy: list[dict]


# ── Workflow Blockers ───────────────────────────────────────────────────────

class BlockerResponse(BaseModel):
    id: int
    title: str
    priority: str
    module_name: Optional[str]
    customer_name: Optional[str]
    days_open: int
    assignee: Optional[str]
    impact_summary: str
    asana_url: Optional[str] = None

    class Config:
        from_attributes = True


class BlockerAnalytics(BaseModel):
    blockers: list[BlockerResponse]
    total_blockers: int
    avg_days_blocked: float
    affected_customers: int


# ── Customer Pain ───────────────────────────────────────────────────────────

class WorkshopTicketSummary(BaseModel):
    id: int
    title: str
    status: str
    is_open: bool


class CustomerPainItem(BaseModel):
    customer_id: int
    customer_name: str
    tier: str
    ticket_count: int
    open_tickets: int
    critical_tickets: int
    recurring_issues: list[str]
    pain_score: float
    tickets: list[WorkshopTicketSummary] = []
    support_person_name: Optional[str] = None
    support_person_email: Optional[str] = None


class CustomerPainAnalytics(BaseModel):
    customers: list[CustomerPainItem]
    top_pain_customer: str
    total_customers: int


# ── Support Team ────────────────────────────────────────────────────────────

class SupportTeamMember(BaseModel):
    name: str
    tickets_created: int
    tickets_closed: int
    open_assigned: int
    avg_resolution_hours: float
    open_tickets: list[WorkshopTicketSummary] = []


class SupportTeamAnalytics(BaseModel):
    members: list[SupportTeamMember]
    top_creator: Optional[str]
    top_closer: Optional[str]
    total_members: int


# ── Jira Integration ────────────────────────────────────────────────────────

class JiraIssueResponse(BaseModel):
    id: int
    jira_key: str
    summary: Optional[str]
    status: Optional[str]
    issue_type: Optional[str]
    sprint_name: Optional[str]
    sprint_state: Optional[str]
    story_points: Optional[float]
    assignee: Optional[str]
    ticket_title: Optional[str] = None
    jira_url: Optional[str]
    is_open: bool = True
    linked: bool = False
    asana_url: Optional[str] = None
    asana_project_name: Optional[str] = None
    asana_section: Optional[str] = None

    class Config:
        from_attributes = True


class JiraAnalytics(BaseModel):
    issues: list[JiraIssueResponse]
    open_issues: list[JiraIssueResponse]
    active_sprints: list[dict]
    total_linked: int
    total_open: int
    sprint_velocity: list[dict]


# ── Resolution Analytics ────────────────────────────────────────────────────

class ResolutionAnalytics(BaseModel):
    avg_resolution_hours: float
    median_resolution_hours: float
    sla_compliance_rate: float
    reopened_count: int
    reopened_rate: float
    total_resolved: int = 0
    sla_met_count: int = 0
    sla_missed_count: int = 0
    under_48h_count: int = 0
    over_7d_count: int = 0
    resolution_by_priority: list[dict]
    sla_by_module: list[dict]


class MonthlyProgressMonth(BaseModel):
    month: int
    month_label: str
    is_current_month: bool = False
    tickets_created: int
    tickets_closed: int
    reopened_count: int
    avg_resolution_hours: Optional[float] = None
    median_resolution_hours: Optional[float] = None
    sla_compliance_rate: Optional[float] = None
    bugs_created: int
    bugs_closed: int
    enhancements_created: int
    net_flow: int
    created_vs_prev: Optional[int] = None
    created_vs_prev_pct: Optional[float] = None
    closed_vs_prev: Optional[int] = None
    closed_vs_prev_pct: Optional[float] = None
    bugs_vs_prev: Optional[int] = None
    bugs_vs_prev_pct: Optional[float] = None
    avg_resolution_vs_prev: Optional[float] = None
    insight: Optional[str] = None


class MonthlyProgressAnalytics(BaseModel):
    year: int
    project_name: Optional[str] = None
    months: list[MonthlyProgressMonth]
    year_created: int
    year_closed: int
    year_bugs_created: int
    year_reopened: int
    highlights: list[str]


# ── AI Assistant ────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    response: str
    sources: list[dict] = []
    suggested_followups: list[str] = []


# ── Projects & Sync ─────────────────────────────────────────────────────────

class ProjectResponse(BaseModel):
    id: int
    gid: str
    name: str
    ticket_count: int
    last_synced_at: Optional[datetime]
    jira_project_key: Optional[str]

    class Config:
        from_attributes = True


class IntegrationStatusResponse(BaseModel):
    asana_configured: bool
    jira_configured: bool
    google_sheets_configured: bool = False
    google_service_account_email: Optional[str] = None
    mock_mode: bool
    asana_workspace_gid: Optional[str]
    jira_project_key: Optional[str]
    type_field_name: str
    auto_sync_enabled: bool = True
    auto_sync_interval_minutes: int = 10
    auto_sync_ui_poll_seconds: int = 60
    asana_webhooks_enabled: bool = False
    email_configured: bool = False
    last_auto_sync_at: Optional[str] = None


class SyncResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    project_gid: Optional[str] = None
    project_name: Optional[str] = None
    tasks_synced: Optional[int] = None
    issues_synced: Optional[int] = None
    asana: Optional[dict] = None
    jira: Optional[dict] = None


# ── Release Notes ───────────────────────────────────────────────────────────

class ReleaseNoteItem(BaseModel):
    ticket_id: int
    asana_gid: Optional[str] = None
    title: str
    category: str
    release_category: str
    module_affected: str
    summary: str
    whats_new: list[str] = []
    impact: str = ""
    impact_benefit: Optional[str] = None
    fix: Optional[str] = None
    note: Optional[str] = None
    emoji: str
    moved_at: str
    assignee: Optional[str] = None
    asana_url: Optional[str] = None


class ReleaseNotesResponse(BaseModel):
    project_name: Optional[str] = None
    project_gid: Optional[str] = None
    released_section: str
    window_start: str
    window_end: str
    lookback_days: int
    release_date: str
    document_title: Optional[str] = None
    total_items: int
    sections: dict[str, list[ReleaseNoteItem]]
    items: list[ReleaseNoteItem]
    asana_live: bool
    source: str = "database"
    executive_summary: Optional[dict] = None


class WorkshopAnnouncementDraftsRequest(BaseModel):
    sprint_name: str
    lookback_days: Optional[int] = 2
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    audience: str = "all"  # all | bosch | standard
    workshop_ids: Optional[list[int]] = None


class WorkshopAnnouncementDraftsResponse(BaseModel):
    created: int
    skipped_no_email: int
    eligible: int
    draft_ids: list[int] = []


class ReleaseNoteArchiveResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    release_date: str
    title: Optional[str] = None
    sprint_name: Optional[str] = None
    original_filename: str
    file_size: int
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Sprint Sheet ──────────────────────────────────────────────────────────────

class SprintSheetRow(BaseModel):
    ticket_id: int
    asana_gid: Optional[str] = None
    sheet_row_id: Optional[int] = None
    title: str
    team: Optional[str] = None
    dev_estimate: Optional[float] = None
    qa_estimate: Optional[float] = None
    total_estimate: Optional[float] = None
    status: str
    priority: Optional[str] = None
    doc_link: Optional[str] = None
    jira_status: Optional[str] = None
    asana_link: Optional[str] = None
    dev_assigned: Optional[str] = None
    qa_assigned: Optional[str] = None
    ticket_type: Optional[str] = None
    work_type: Optional[str] = None
    product_stage: Optional[str] = None
    build_in: Optional[str] = None
    dor: Optional[str] = None
    release: Optional[str] = None
    sheet_status: Optional[str] = None
    section_name: Optional[str] = None
    asana_board_index: Optional[int] = None


class SprintSheetTotals(BaseModel):
    ticket_count: int
    prioritized: int = 0
    prioritized_bugs: int = 0
    prioritized_requirements: int = 0
    prioritized_other: int = 0
    prioritized_bug_hours: float = 0
    prioritized_requirement_hours: float = 0
    prioritized_bug_dev_hours: float = 0
    prioritized_requirement_dev_hours: float = 0
    prioritized_bug_qa_hours: float = 0
    prioritized_requirement_qa_hours: float = 0
    in_progress: int = 0
    done: int = 0
    removed: int = 0
    dev_hours: float
    qa_hours: float
    total_hours: float
    in_sprint: int = 0
    released: int = 0


class SprintSheetResponse(BaseModel):
    sheet_id: Optional[int] = None
    sprint_name: str
    project_name: Optional[str] = None
    project_gid: Optional[str] = None
    section: str
    generated_at: str
    rows: list[SprintSheetRow]
    prioritized_rows: list[SprintSheetRow] = []
    requirement_rows: list[SprintSheetRow] = []
    bug_rows: list[SprintSheetRow] = []
    totals: SprintSheetTotals
    asana_live: bool
    persisted: bool = True
    google_sheet_url: Optional[str] = None
    google_synced_at: Optional[str] = None
    google_sheets_configured: bool = False
    google_service_account_email: Optional[str] = None
    google_sync_error: Optional[str] = None
    sync_mode: Optional[str] = None


class GoogleSheetLinkRequest(BaseModel):
    sprint_name: str = "Sprint"
    spreadsheet_url: str


class SprintSheetExportRequest(BaseModel):
    sprint_name: str = "Sprint"
    section: Optional[str] = None
    rows: list[SprintSheetRow] = []


# ── Organization ──────────────────────────────────────────────────────────────

class PersonResponse(BaseModel):
    id: int
    name: str
    email: str
    role: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class TeamMemberResponse(BaseModel):
    person: PersonResponse
    is_lead: bool = False


class TeamResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    members: list[TeamMemberResponse] = []

    class Config:
        from_attributes = True


class CustomerAccountResponse(BaseModel):
    id: int
    name: str
    workshop_name: str
    tier: str
    industry: Optional[str] = None
    workshop_email: Optional[str] = None
    support_person_name: Optional[str] = None
    support_person_email: Optional[str] = None
    support_contact_email: Optional[str] = None
    ax_id: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class CreateCustomerAccountRequest(BaseModel):
    workshop_name: str
    support_person_name: Optional[str] = None
    support_person_email: Optional[str] = None
    workshop_email: Optional[str] = None
    support_contact_email: Optional[str] = None
    ax_id: Optional[str] = None
    tier: str = "standard"
    location: Optional[str] = None


class UpdateCustomerAccountRequest(BaseModel):
    workshop_name: Optional[str] = None
    support_person_name: Optional[str] = None
    support_person_email: Optional[str] = None
    workshop_email: Optional[str] = None
    support_contact_email: Optional[str] = None
    ax_id: Optional[str] = None
    tier: Optional[str] = None
    location: Optional[str] = None


class WorkshopEmailDraftResponse(BaseModel):
    id: int
    ticket_id: int
    project_id: Optional[int] = None
    draft_type: str
    status: str
    workshop_name: Optional[str] = None
    to_emails: list[str] = []
    cc_emails: list[str] = []
    subject: str
    body_text: str
    body_html: Optional[str] = None
    ticket_snapshot: dict = {}
    created_at: datetime
    sent_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UpdateWorkshopEmailDraftRequest(BaseModel):
    subject: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    to_emails: Optional[list[str]] = None
    cc_emails: Optional[list[str]] = None


class WorkshopEmailDraftSummary(BaseModel):
    pending_count: int


class CsvImportResponse(BaseModel):
    success: bool
    errors: list[dict] = []
    rows_processed: int = 0
    imported: int = 0


class CreateTeamRequest(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateTeamRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AddTeamMemberRequest(BaseModel):
    name: str
    email: str
    designation: Optional[str] = None
    is_lead: bool = False


class UpdateTeamMemberRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    designation: Optional[str] = None
    is_lead: Optional[bool] = None


# ── Activity Log ──────────────────────────────────────────────────────────────

class ActivityLogResponse(BaseModel):
    id: int
    module: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    summary: str
    payload: dict = {}
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityLogListResponse(BaseModel):
    items: list[ActivityLogResponse]
    total: int
    page: int = 1
    page_size: int = 50


# ── Release Notes Send ────────────────────────────────────────────────────────

class ReleaseNotesSendRequest(BaseModel):
    sprint_name: Optional[str] = None
    lookback_days: int = 2
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    team_ids: list[int] = []
    person_ids: list[int] = []
    excluded_person_ids: list[int] = []
    extra_emails: list[str] = []


class ReleaseNotesSendResponse(BaseModel):
    success: bool
    recipient_count: int = 0
    sent_to: list[str] = []
    item_count: int = 0
    activity_log_id: Optional[int] = None
    release_note_send_id: Optional[int] = None


class ReleaseNoteArchiveSendRequest(BaseModel):
    team_ids: list[int] = []
    person_ids: list[int] = []
    excluded_person_ids: list[int] = []
    extra_emails: list[str] = []


# ── Workshop History ──────────────────────────────────────────────────────────

class WorkshopHistoryTicket(BaseModel):
    id: int
    title: str
    asana_url: Optional[str] = None


class WorkshopHistoryItem(BaseModel):
    workshop_name: str
    sprint_name: str
    issues_released: int
    support_person_name: Optional[str] = None
    support_person_email: Optional[str] = None
    release_date: Optional[str] = None
    sprint_sheet_id: Optional[int] = None
    tickets: list[WorkshopHistoryTicket] = []


class WorkshopHistoryResponse(BaseModel):
    items: list[WorkshopHistoryItem]


class ScheduledReminderResponse(BaseModel):
    id: int
    workshop_name: str
    sprint_name: Optional[str] = None
    support_person_name: Optional[str] = None
    due_at: datetime
    status: str
    sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MarkSprintReleasedRequest(BaseModel):
    sprint_name: str
    release_date: Optional[str] = None


# ── Cluster Analysis ──────────────────────────────────────────────────────────

class ClusterTicketResponse(BaseModel):
    id: int
    title: str
    status: str
    workshop_name: Optional[str] = None
    assignee: Optional[str] = None
    asana_url: Optional[str] = None


class ClusterAnalysisResultResponse(BaseModel):
    id: int
    theme_title: str
    one_line_issue: Optional[str] = None
    ticket_ids: list[int] = []
    suggested_test_cases: list[str] = []
    confidence: Optional[float] = None
    topic_module: Optional[str] = None
    ticket_percentage: Optional[float] = None
    intelligence: Optional[dict] = None

    class Config:
        from_attributes = True


class ClusterAnalysisJobResponse(BaseModel):
    id: int
    cluster_id: int
    status: str
    batch_size: int
    tickets_total: int
    tickets_processed: int
    open_ticket_count_snapshot: int = 0
    dismissed_at: Optional[datetime] = None
    can_reanalyze: bool = True
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: list[ClusterAnalysisResultResponse] = []

    class Config:
        from_attributes = True


# ── Issue Intelligence (Recurring Issues) ─────────────────────────────────────

class IssueIntelligenceJobResponse(BaseModel):
    id: int
    status: str
    tickets_total: int
    tickets_processed: int
    issues_found: int = 0
    analysis_mode: str = "engineering_fix"
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RecurringIssueSummary(BaseModel):
    id: int
    issue_name: str
    issue_type: str
    severity: str
    ticket_count: int
    open_count: int
    workshop_count: int
    trend: str
    confidence: float
    priority_score: float
    recurring_since: Optional[str] = None
    latest_occurrence: Optional[str] = None
    affected_modules: list[str] = []
    affected_workshops: list[str] = []
    affected_releases: list[str] = []
    fix_status: str = "unknown"
    developer_resolution_available: bool = False
    regression_tests_available: bool = False
    business_impact: Optional[str] = None
    customer_impact: Optional[str] = None
    executive_summary: Optional[str] = None


class IssueIntelligenceInsights(BaseModel):
    top_priority_issues: list[str] = []
    increasing_issues_count: int = 0
    unstable_modules: list[dict] = []
    tickets_in_range: int = 0


class IssueIntelligenceDashboard(BaseModel):
    tickets_analyzed: int
    recurring_issues_found: int
    product_defects_found: int
    last_analyzed_at: Optional[str] = None
    active_job: Optional[IssueIntelligenceJobResponse] = None
    analysis_mode: str = "engineering_fix"
    issues: list[RecurringIssueSummary] = []
    insights: IssueIntelligenceInsights = IssueIntelligenceInsights()


class IssueEvidenceTicket(BaseModel):
    id: int
    title: str
    status: str
    workshop_name: Optional[str] = None
    created_at: Optional[str] = None
    asana_url: Optional[str] = None
    description_excerpt: Optional[str] = None


class RecurringIssueDetail(RecurringIssueSummary):
    engineering_fix_key: Optional[str] = None
    engineering_fix_label: Optional[str] = None
    ticket_ids: list[int] = []
    overview: dict = {}
    evidence: list[IssueEvidenceTicket] = []
    evidence_total: int = 0
    timeline: list[dict] = []
    root_cause: Optional[str] = None
    developer_resolution: str = "Resolution Unknown."
    related_issues: list[str] = []
    regression_test_cases: list[str] = []
    suggested_permanent_fix: Optional[str] = None
    suggested_product_improvement: Optional[str] = None
    release_version_introduced: Optional[str] = None
    release_version_fixed: Optional[str] = None
    sample_tickets: list[str] = []
    all_workshops: list[str] = []
    all_modules: list[str] = []
    all_releases: list[str] = []
    issue_history: list[dict] = []
    evidence_summary: Optional[str] = None


# ── Impact / Productivity ─────────────────────────────────────────────────────

class ImpactTopWorkshop(BaseModel):
    name: str
    count: int


class ImpactMetricsResponse(BaseModel):
    view_mode: str = "sprint"
    project_name: Optional[str] = None
    items_released: int
    points_released: float = 0
    workshops_helped: int
    support_people_helped: int
    blockers_cleared: int
    avg_days_to_release: Optional[float] = None
    release_notes_sent: int
    last_release_note_at: Optional[str] = None
    followups_sent: int
    cluster_analyses_run: int
    active_sprint_sheets: int
    sprint_sheet_rows: int
    top_workshops: list[ImpactTopWorkshop] = []
    recent_activity: list[dict] = []


# ── CEO Intelligence Reports ──────────────────────────────────────────────────

class CEOReportSendRequest(BaseModel):
    period: str = "weekly"  # weekly | monthly | 6months
    recipient_emails: list[str] = []
    extra_emails: list[str] = []


class CEOReportSendResponse(BaseModel):
    success: bool
    recipient_count: int
    sent_to: list[str] = []
    period: str
    date_from: str
    date_to: str
    health_score: int
    sent_at: str


class CEOReportPreviewResponse(BaseModel):
    subject: str
    period: str
    period_label: str
    date_from: str
    date_to: str
    health_score: int
    narrative_source: str
    cursor_generated_at: Optional[str] = None
    html: str
    text: str
    brief: dict = Field(default_factory=dict)
    dashboard_note: str = (
        "The CEO Intelligence tab shows raw facts (ceo_quick_view). "
        "This preview is the interpreted executive email built from those facts."
    )


class CEOReportSettingsResponse(BaseModel):
    ceo_email: str
    ai_adoption_date: str
    schedule_enabled: bool
    schedule_frequency: str
    schedule_project_gid: Optional[str] = None
    last_sent_at: Optional[str] = None
    email_configured: bool
    cursor_configured: bool = False
    weekly_analysis: dict = Field(default_factory=dict)
    schedule_note: Optional[str] = None


class CEOReportSettingsUpdate(BaseModel):
    ceo_email: Optional[str] = None
    schedule_enabled: Optional[bool] = None
    schedule_frequency: Optional[str] = None
    schedule_project_gid: Optional[str] = None
