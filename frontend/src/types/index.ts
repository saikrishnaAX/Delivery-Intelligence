// ── Executive Dashboard ─────────────────────────────────────────────────────

export interface ExecutiveMetrics {
  project_type: "support" | "bosch" | "sprint";
  project_name?: string;
  dashboard_description?: string;
  tickets_created_today: number;
  tickets_closed_today: number;
  open_tickets: number;
  total_closed: number;
  escalations_count: number;
  backlog_count: number;
  released_count: number;
  in_pipeline_count: number;
  testing_stuck_count?: number;
  avg_resolution_hours: number;
  critical_open_issues: number;
  sla_compliance_rate: number;
  reopened_tickets: number;
  overdue_count: number;
  created_today_tickets: ExecutiveTicketItem[];
  closed_today_tickets: ExecutiveTicketItem[];
  open_tickets_list: ExecutiveTicketItem[];
  total_closed_tickets: ExecutiveTicketItem[];
  escalation_tickets: ExecutiveTicketItem[];
  backlog_tickets: ExecutiveTicketItem[];
  released_tickets: ExecutiveTicketItem[];
  pipeline_stages: ExecutivePipelineStage[];
  reopened_tickets_list: ExecutiveTicketItem[];
  urgent_blockers: ExecutiveTicketItem[];
  overdue_tickets: ExecutiveTicketItem[];
  workshop_alerts: ExecutiveWorkshopAlert[];
  team_pulse: ExecutiveTeamPulse;
  workflow_hotspots: ExecutiveWorkflowHotspot[];
}

export interface ExecutivePipelineStage {
  stage: string;
  count: number;
  tickets: ExecutiveTicketItem[];
}

export interface ExecutiveTicketItem {
  id: number;
  title: string;
  workshop_name?: string;
  assignee?: string;
  ticket_owner?: string;
  created_by?: string;
  created_at?: string;
  days_open: number;
  priority: string;
  detail?: string;
  asana_url?: string;
  module_name?: string;
  jira_key?: string;
}

export interface ExecutiveWorkshopAlert {
  name: string;
  open_tickets: number;
  blockers: number;
}

export interface ExecutiveTeamPulse {
  top_creator?: string;
  top_creator_count: number;
  top_closer?: string;
  top_closer_count: number;
  highest_open_load?: string;
  highest_open_count: number;
}

export interface ExecutiveWorkflowHotspot {
  area: string;
  open_count: number;
}

export interface ExecutiveSummary {
  id: number;
  summary: string;
  key_metrics: Record<string, number>;
  recommendations: string[];
  generated_at: string;
}

// ── Execution Board ───────────────────────────────────────────────────────────

export type OperationalStatus = "red" | "amber" | "green";

export interface ExecutionTask {
  id: string;
  title: string;
  description?: string;
  count: number;
  priority: "critical" | "high" | "medium";
  route: string;
  category: string;
}

export interface WorkshopOperationalStatus {
  name: string;
  status: OperationalStatus;
  open_tickets: number;
  show_stoppers: number;
  escalations: number;
  headline: string;
}

export interface ExecutionBoardData {
  operational_status: OperationalStatus;
  status_headline: string;
  status_detail: string;
  show_stopper_count: number;
  workshops_with_show_stoppers: number;
  workshops_at_risk: number;
  workshops_healthy: number;
  today_task_count: number;
  today_item_count: number;
  today_tasks: ExecutionTask[];
  workshop_statuses: WorkshopOperationalStatus[];
  workshops_hidden_count?: number;
  metrics: ExecutiveMetrics;
}

export interface ExecutiveDrilldownResponse {
  metric: string;
  stage?: string | null;
  total: number;
  tickets: ExecutiveTicketItem[];
  limit: number;
  offset: number;
}

export interface ExecutiveAnalyticsData {
  health_score: { score: number; label: string; components?: Record<string, number> };
  quality_trends: {
    windows: Record<string, Record<string, unknown>>;
    monthly: { month: string; bugs: number; enhancements: number; total: number }[];
    bug_feature_ratio_30d: number;
  };
  ai_impact: {
    before: Record<string, number | null>;
    after: Record<string, number | null>;
    adoption_date?: string;
    note: string;
  };
  post_ai_issue_nature?: PostAiIssueNature;
  recurring_issues: CEORecurringIssue[];
  engineering_productivity: Record<string, unknown>;
  customer_health: {
    top_complaints: { category: string; count: number }[];
  };
  delivery_intelligence: {
    blocked_tickets: { title: string; assignee?: string; days_open: number }[];
    pipeline_open: number;
    jira_open: number;
    upcoming_risks: string[];
  };
  charts: {
    monthly_trends: { month: string; bugs: number; enhancements: number; total: number }[];
    ai_comparison: { metric: string; before: number | null; after: number | null }[];
  };
}

// ── CEO Intelligence ────────────────────────────────────────────────────────

export interface CEOIntelligenceRisk {
  risk: string;
  score: number;
  trend: string;
  impact: string;
  recommendation: string;
}

export interface CEORecurringIssue {
  name: string;
  issue_type?: string;
  ticket_count: number;
  open_count: number;
  trend: string;
  severity: string;
  workshops: number;
  business_impact: string;
  root_cause: string;
  status: string;
  affected_modules: string[];
}

export interface CEOMorningBriefing {
  greeting: string;
  narrative: string;
  engineering_summary: Record<string, number>;
  quality_summary: Record<string, number | string>;
  customer_summary: Record<string, number>;
  ai_summary: string;
  wins: string[];
  watch_next_week: string[];
  recommendations: string[];
  meeting_questions: string[];
  generated_at: string;
}

export interface CEOExecutiveBriefCard {
  title: string;
  subtitle: string;
  period_before: string;
  period_after: string;
  verdict: string;
  verdict_detail?: string;
  scorecard: { kpi: string; status: string; label: string; detail: string }[];
  highlights: { label: string; value: string; sub?: string; section?: string }[];
  watch: string[];
  actions: string[];
  decision: string;
  ceo_verdict: string;
  engineering_health: {
    label: string;
    score_10: number;
    subscores: {
      delivery_velocity: number;
      product_quality: number;
      release_stability: number;
      ai_effectiveness: number;
    };
    risk_level: string;
  };
}

export interface PostAiIssueNature {
  period: string;
  total_tickets_created: number;
  total_bugs_created: number;
  bugs_still_open: number;
  high_critical_count: number;
  narrative_summary: string[];
  root_cause_themes: { theme: string; count: number }[];
  product_modules_affected: { module: string; count: number }[];
  engineering_fix_groups: {
    issue_name: string;
    engineering_fix: string;
    bug_count: number;
    sample_titles: string[];
  }[];
  priority_breakdown: { priority: string; count: number }[];
  recommended_focus: string[];
}

export interface CEOQuickView {
  period_before: string;
  period_after: string;
  ai_adoption_date: string;
  bugs: {
    total_pre: number;
    total_post: number;
    per_month_pre: number;
    per_month_post: number;
    enhancements_per_month_pre: number;
    enhancements_per_month_post: number;
  };
  modules: {
    area: string;
    description: string;
    bugs_pre: number;
    bugs_post: number;
    per_month_pre: number;
    per_month_post: number;
    status: "existed_before_ai" | "new_after_ai";
  }[];
  modules_new_count: number;
  modules_existed_count: number;
  issues: {
    clusters_existed_before_ai: number;
    clusters_new_after_ai: number;
    existed_by_area: { area: string; understanding: string; clusters: number; tickets: number }[];
    new_by_area: { area: string; understanding: string; clusters: number; tickets: number }[];
    new_patterns_in_existing_modules: {
      area: string;
      understanding: string;
      ticket_count: number;
      first_seen: string | null;
    }[];
  };
  note: string;
}

export interface CEOIntelligenceData {
  meta: {
    generated_at: string;
    project_gid?: string;
    ai_adoption_date?: string;
    data_confidence: { score: number; gaps: string[] };
  };
  ceo_quick_view: CEOQuickView;
  morning_briefing: CEOMorningBriefing;
  executive_brief_card?: CEOExecutiveBriefCard;
  executive_summary: string;
  health_score: { score: number; label: string; components: Record<string, number> };
  quality_trends: {
    windows: Record<string, Record<string, unknown>>;
    monthly: { month: string; bugs: number; enhancements: number; total: number }[];
    bug_feature_ratio_30d: number;
  };
  ai_impact: {
    before: Record<string, number | null>;
    after: Record<string, number | null>;
    before_dec_apr?: Record<string, number | null>;
    after_may_jun?: Record<string, number | null>;
    adoption_date?: string;
    confidence: string;
    note: string;
  };
  post_ai_issue_nature?: PostAiIssueNature;
  top_risks: CEOIntelligenceRisk[];
  recurring_issues: CEORecurringIssue[];
  release_intelligence: Record<string, unknown>;
  engineering_productivity: Record<string, unknown>;
  customer_health: {
    top_workshops: { name: string; count: number }[];
    top_modules: { module: string; count: number }[];
    top_complaints: { category: string; count: number }[];
  };
  delivery_intelligence: {
    blocked_tickets: { title: string; assignee?: string; days_open: number }[];
    pipeline_open: number;
    jira_open: number;
    upcoming_risks: string[];
  };
  financial_impact: { available: boolean; note: string; estimated_support_hours_30d?: number };
  leadership_recommendations: string[];
  charts: {
    monthly_trends: { month: string; bugs: number; enhancements: number; total: number }[];
    health_components: { name: string; score: number }[];
    ai_comparison: { metric: string; before: number | null; after: number | null }[];
    workshop_heatmap: { name: string; count: number }[];
    module_stability: { module: string; count: number }[];
  };
}

export interface CEOReportSettings {
  ceo_email: string;
  ai_adoption_date: string;
  schedule_enabled: boolean;
  schedule_frequency: "weekly" | "monthly" | "6months";
  schedule_project_gid?: string | null;
  last_sent_at?: string | null;
  email_configured: boolean;
  cursor_configured?: boolean;
  weekly_analysis?: {
    cursor_configured?: boolean;
    last_analysis_at?: string | null;
    last_run_at?: string | null;
    status?: string;
    ceo_brief_ready?: boolean;
    daily_hour_ist?: number;
    schedule?: string;
  };
  schedule_note?: string;
}

export interface CEOReportSendResult {
  success: boolean;
  recipient_count: number;
  sent_to: string[];
  period: string;
  date_from: string;
  date_to: string;
  health_score: number;
  sent_at: string;
}

export interface CEOReportPreview {
  subject: string;
  period: string;
  period_label: string;
  date_from: string;
  date_to: string;
  health_score: number;
  narrative_source: string;
  cursor_generated_at?: string | null;
  html: string;
  text: string;
  brief: Record<string, unknown>;
  dashboard_note: string;
}

// ── Tickets ─────────────────────────────────────────────────────────────────

export interface Ticket {
  id: number;
  asana_gid?: string;
  title: string;
  description?: string;
  status: string;
  support_category?: string;
  ai_category?: string;
  priority: string;
  module_name?: string;
  customer_name?: string;
  workshop_name?: string;
  assignee?: string;
  reporter?: string;
  ticket_owner?: string;
  is_critical_blocker: boolean;
  is_reopened: boolean;
  sla_met?: boolean;
  resolution_hours?: number;
  cluster_name?: string;
  jira_key?: string;
  asana_type_raw?: string;
  asana_url?: string;
  tags: string[];
  created_at: string;
  closed_at?: string;
}

export interface TicketListResponse {
  tickets: Ticket[];
  total: number;
  page: number;
  page_size: number;
}

// ── Classification ──────────────────────────────────────────────────────────

export interface CategoryBreakdown {
  category: string;
  count: number;
  open_count: number;
  percentage: number;
  trend: { date?: string; count?: number }[];
}

export interface ClassificationAnalytics {
  support_breakdown: CategoryBreakdown[];
  ai_breakdown: CategoryBreakdown[];
  total_tickets: number;
  most_common_category: string;
}

// ── Issue Intelligence (Recurring Issues) ───────────────────────────────────

export interface IssueIntelligenceJobData {
  id: number;
  status: string;
  tickets_total: number;
  tickets_processed: number;
  issues_found: number;
  analysis_mode: string;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
}

export interface RecurringIssueSummary {
  id: number;
  issue_name: string;
  issue_type: string;
  severity: string;
  ticket_count: number;
  open_count: number;
  workshop_count: number;
  trend: "increasing" | "stable" | "decreasing" | string;
  confidence: number;
  priority_score: number;
  recurring_since?: string;
  latest_occurrence?: string;
  affected_modules: string[];
  affected_workshops: string[];
  affected_releases: string[];
  fix_status: string;
  developer_resolution_available: boolean;
  regression_tests_available: boolean;
  business_impact?: string;
  customer_impact?: string;
  executive_summary?: string;
}

export interface IssueIntelligenceDashboard {
  tickets_analyzed: number;
  recurring_issues_found: number;
  product_defects_found: number;
  last_analyzed_at?: string;
  active_job?: IssueIntelligenceJobData;
  analysis_mode: string;
  issues: RecurringIssueSummary[];
  insights: {
    top_priority_issues: string[];
    increasing_issues_count: number;
    unstable_modules: { module: string; open_tickets: number }[];
    tickets_in_range: number;
  };
}

export interface IssueEvidenceTicket {
  id: number;
  title: string;
  status: string;
  workshop_name?: string;
  created_at?: string;
  asana_url?: string;
  description_excerpt?: string;
}

export interface RecurringIssueDetail extends RecurringIssueSummary {
  engineering_fix_key?: string;
  engineering_fix_label?: string;
  ticket_ids: number[];
  overview: {
    executive_summary?: string;
    issue_type?: string;
    engineering_fix_hypothesis?: string;
  };
  evidence: IssueEvidenceTicket[];
  evidence_total: number;
  timeline: { month: string; count: number }[];
  root_cause?: string;
  developer_resolution: string;
  related_issues: string[];
  regression_test_cases: string[];
  suggested_permanent_fix?: string;
  suggested_product_improvement?: string;
  release_version_introduced?: string;
  release_version_fixed?: string;
  sample_tickets: string[];
  all_workshops: string[];
  all_modules: string[];
  all_releases: string[];
  issue_history: Record<string, unknown>[];
  evidence_summary?: string;
}

// ── Clustering (legacy API — internal only) ─────────────────────────────────

export interface Cluster {
  id: number;
  name: string;
  description?: string;
  ai_summary?: string;
  ticket_count: number;
  open_ticket_count: number;
  severity: string;
  module_name?: string;
  sample_tickets: string[];
  analysis_job_id?: number;
  analysis_defect_count?: number;
  analysis_dismissed?: boolean;
  analysis_open_snapshot?: number;
  can_reanalyze?: boolean;
  active_analysis_job_id?: number;
  analysis_in_progress?: boolean;
}

export interface ClusteringAnalytics {
  clusters: Cluster[];
  total_clusters: number;
  unclustered_tickets: number;
}

export interface ClusterTicketData {
  id: number;
  title: string;
  status: string;
  workshop_name?: string;
  assignee?: string;
  asana_url?: string;
}

export interface IssueIntelligence {
  issue_name: string;
  affected_module?: string;
  ticket_count: number;
  ticket_percentage?: number;
  first_seen?: string;
  last_seen?: string;
  open_count?: number;
  closed_count?: number;
  workshops_affected?: string[];
  business_impact?: string;
  root_cause?: string;
  fix_status?: string;
  developer_resolution_summary?: string;
  regression_test_cases?: string[];
  recurring?: boolean;
  suggested_permanent_fix?: string;
  suggested_product_improvement?: string;
  estimated_engineering_hours_saved?: number;
  top_customer_complaints?: string[];
  top_keywords?: string[];
  related_issues?: string[];
  release_version_introduced?: string;
  release_version_fixed?: string;
  evidence_summary?: string;
  confidence?: number;
  ticket_ids?: number[];
}

export interface ClusterAnalysisResultData {
  id: number;
  theme_title: string;
  one_line_issue?: string;
  ticket_ids: number[];
  suggested_test_cases: string[];
  confidence?: number;
  topic_module?: string;
  ticket_percentage?: number;
  intelligence?: IssueIntelligence;
}

export interface ClusterAnalysisJobData {
  id: number;
  cluster_id: number;
  status: string;
  batch_size: number;
  tickets_total: number;
  tickets_processed: number;
  open_ticket_count_snapshot?: number;
  dismissed_at?: string;
  can_reanalyze?: boolean;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  results: ClusterAnalysisResultData[];
}

// ── Heat Map ────────────────────────────────────────────────────────────────

export interface ModuleHeatMapItem {
  module: string;
  product_area: string;
  ticket_count: number;
  open_count: number;
  critical_count: number;
  avg_resolution_hours: number;
  intensity: number;
}

export interface HeatMapAnalytics {
  modules: ModuleHeatMapItem[];
  hottest_module: string;
  total_modules: number;
}

// ── Blockers ────────────────────────────────────────────────────────────────

export interface Blocker {
  id: number;
  title: string;
  priority: string;
  module_name?: string;
  customer_name?: string;
  days_open: number;
  assignee?: string;
  impact_summary: string;
  asana_url?: string;
}

export interface BlockerAnalytics {
  blockers: Blocker[];
  total_blockers: number;
  avg_days_blocked: number;
  affected_customers: number;
}

// ── Customer Pain ───────────────────────────────────────────────────────────

export interface WorkshopTicketSummary {
  id: number;
  title: string;
  status: string;
  is_open: boolean;
}

export interface CustomerPainItem {
  customer_id: number;
  customer_name: string;
  tier: string;
  ticket_count: number;
  open_tickets: number;
  critical_tickets: number;
  recurring_issues: string[];
  pain_score: number;
  tickets: WorkshopTicketSummary[];
  support_person_name?: string;
  support_person_email?: string;
}

export interface CustomerPainAnalytics {
  customers: CustomerPainItem[];
  top_pain_customer: string;
  total_customers: number;
}

// ── Support Team ────────────────────────────────────────────────────────────

export interface SupportTeamMember {
  name: string;
  tickets_created: number;
  tickets_closed: number;
  open_assigned: number;
  avg_resolution_hours: number;
  open_tickets: WorkshopTicketSummary[];
}

export interface SupportTeamAnalytics {
  members: SupportTeamMember[];
  top_creator?: string;
  top_closer?: string;
  total_members: number;
}

// ── Jira ────────────────────────────────────────────────────────────────────

export interface JiraIssue {
  id: number;
  jira_key: string;
  summary?: string;
  status?: string;
  issue_type?: string;
  sprint_name?: string;
  sprint_state?: string;
  story_points?: number;
  assignee?: string;
  ticket_title?: string;
  jira_url?: string;
  is_open: boolean;
  linked: boolean;
  asana_url?: string;
  asana_project_name?: string;
  asana_section?: string;
}

export interface JiraAnalytics {
  issues: JiraIssue[];
  open_issues: JiraIssue[];
  active_sprints: Record<string, unknown>[];
  total_linked: number;
  total_open: number;
  sprint_velocity: Record<string, unknown>[];
}

// ── Resolution ──────────────────────────────────────────────────────────────

export interface ResolutionAnalytics {
  avg_resolution_hours: number;
  median_resolution_hours: number;
  sla_compliance_rate: number;
  reopened_count: number;
  reopened_rate: number;
  total_resolved: number;
  sla_met_count: number;
  sla_missed_count: number;
  under_48h_count: number;
  over_7d_count: number;
  resolution_by_priority: Record<string, unknown>[];
  sla_by_module: Record<string, unknown>[];
}

export interface MonthlyProgressMonth {
  month: number;
  month_label: string;
  is_current_month: boolean;
  tickets_created: number;
  tickets_closed: number;
  reopened_count: number;
  avg_resolution_hours?: number;
  median_resolution_hours?: number;
  sla_compliance_rate?: number;
  bugs_created: number;
  bugs_closed: number;
  enhancements_created: number;
  net_flow: number;
  created_vs_prev?: number;
  created_vs_prev_pct?: number;
  closed_vs_prev?: number;
  closed_vs_prev_pct?: number;
  bugs_vs_prev?: number;
  bugs_vs_prev_pct?: number;
  avg_resolution_vs_prev?: number;
  insight?: string;
}

export interface MonthlyProgressData {
  year: number;
  project_name?: string;
  months: MonthlyProgressMonth[];
  year_created: number;
  year_closed: number;
  year_bugs_created: number;
  year_reopened: number;
  highlights: string[];
}

// ── AI Assistant ────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatResponse {
  response: string;
  sources: Record<string, unknown>[];
  suggested_followups: string[];
}

export interface AIInsight {
  id: number;
  page: string;
  insight_type: string;
  title: string;
  content: string;
  severity: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

// ── Projects & Sync ─────────────────────────────────────────────────────────

export interface AsanaProject {
  id: number;
  gid: string;
  name: string;
  ticket_count: number;
  last_synced_at?: string;
  jira_project_key?: string;
}

export interface IntegrationStatus {
  asana_configured: boolean;
  jira_configured: boolean;
  google_sheets_configured: boolean;
  google_service_account_email?: string;
  mock_mode: boolean;
  asana_workspace_gid?: string;
  jira_project_key?: string;
  type_field_name: string;
  auto_sync_enabled: boolean;
  auto_sync_interval_minutes: number;
  auto_sync_ui_poll_seconds: number;
  asana_webhooks_enabled: boolean;
  email_configured: boolean;
  last_auto_sync_at?: string;
}

export interface SyncResult {
  success: boolean;
  error?: string;
  project_gid?: string;
  project_name?: string;
  tasks_synced?: number;
  issues_synced?: number;
  asana?: Record<string, unknown>;
  jira?: Record<string, unknown>;
}

// ── Release Notes ─────────────────────────────────────────────────────────────

export interface ReleaseNoteItem {
  ticket_id: number;
  asana_gid?: string;
  title: string;
  category: string;
  release_category: string;
  module_affected: string;
  summary: string;
  whats_new: string[];
  impact: string;
  impact_benefit?: string;
  fix?: string;
  note?: string;
  emoji: string;
  moved_at: string;
  assignee?: string;
  asana_url?: string;
}

export interface ReleaseNotesData {
  project_name?: string;
  project_gid?: string;
  released_section: string;
  window_start: string;
  window_end: string;
  lookback_days: number;
  release_date: string;
  document_title?: string;
  total_items: number;
  sections: Record<string, ReleaseNoteItem[]>;
  items: ReleaseNoteItem[];
  asana_live: boolean;
  source: string;
  executive_summary?: {
    headline?: string;
    subheadline?: string;
    counts?: Record<string, number>;
    total?: number;
    highlights?: { title?: string; category?: string; benefit?: string }[];
    release_month?: string;
  };
}

export interface ReleaseNotesSendPayload {
  sprint_name?: string;
  lookback_days?: number;
  date_from?: string;
  date_to?: string;
  team_ids?: number[];
  person_ids?: number[];
  excluded_person_ids?: number[];
  extra_emails?: string[];
}

export interface ReleaseNotesSendResult {
  success: boolean;
  recipient_count: number;
  sent_to?: string[];
  item_count: number;
  activity_log_id?: number;
  release_note_send_id?: number;
}

export interface ReleaseNoteArchive {
  id: number;
  project_id?: number;
  project_name?: string;
  release_date: string;
  title?: string;
  sprint_name?: string;
  original_filename: string;
  file_size: number;
  source: string;
  created_at: string;
  pending?: boolean;
  uploadError?: string;
}

export interface ReleaseNoteArchiveSendPayload {
  team_ids?: number[];
  person_ids?: number[];
  excluded_person_ids?: number[];
  extra_emails?: string[];
}

// ── Sprint Sheet ──────────────────────────────────────────────────────────────

export interface SprintSheetRow {
  ticket_id: number;
  asana_gid?: string;
  sheet_row_id?: number;
  title: string;
  team?: string;
  dev_estimate?: number | null;
  qa_estimate?: number | null;
  total_estimate?: number | null;
  status: string;
  priority?: string;
  doc_link?: string;
  jira_status?: string;
  asana_link?: string;
  dev_assigned?: string | null;
  qa_assigned?: string | null;
  ticket_type?: string;
  work_type?: "bug" | "requirement" | "other";
  product_stage?: string;
  build_in?: string;
  dor?: string;
  release?: string;
  sheet_status?: string;
  section_name?: string;
  asana_board_index?: number | null;
}

export interface SprintSheetTotals {
  ticket_count: number;
  prioritized: number;
  prioritized_bugs: number;
  prioritized_requirements: number;
  prioritized_other: number;
  prioritized_bug_hours: number;
  prioritized_requirement_hours: number;
  prioritized_bug_dev_hours: number;
  prioritized_requirement_dev_hours: number;
  prioritized_bug_qa_hours: number;
  prioritized_requirement_qa_hours: number;
  in_progress: number;
  done: number;
  removed: number;
  dev_hours: number;
  qa_hours: number;
  total_hours: number;
  in_sprint: number;
  released: number;
}

export interface SprintSheetData {
  sheet_id?: number;
  sprint_name: string;
  project_name?: string;
  project_gid?: string;
  section: string;
  generated_at: string;
  rows: SprintSheetRow[];
  prioritized_rows?: SprintSheetRow[];
  requirement_rows?: SprintSheetRow[];
  bug_rows?: SprintSheetRow[];
  totals: SprintSheetTotals;
  asana_live: boolean;
  persisted: boolean;
  google_sheet_url?: string;
  google_synced_at?: string;
  google_sheets_configured: boolean;
  google_service_account_email?: string;
  google_sync_error?: string;
  sync_mode?: string;
}

export interface SprintSheetExportPayload {
  sprint_name: string;
  section?: string;
  rows: SprintSheetRow[];
}

// ── Organization ────────────────────────────────────────────────────────────

export interface PersonData {
  id: number;
  name: string;
  email: string;
  role?: string;
  is_active: boolean;
}

export interface TeamMemberData {
  person: PersonData;
  is_lead: boolean;
}

export interface TeamData {
  id: number;
  name: string;
  description?: string;
  members: TeamMemberData[];
}

export interface CustomerAccountData {
  id: number;
  name: string;
  workshop_name: string;
  tier: string;
  industry?: string;
  workshop_email?: string;
  support_person_name?: string;
  support_person_email?: string;
  support_contact_email?: string;
  ax_id?: string;
  notes?: string;
}

export interface CsvImportResult {
  success: boolean;
  errors: Record<string, unknown>[];
  rows_processed: number;
  imported: number;
}

export interface WorkshopEmailDraft {
  id: number;
  ticket_id?: number | null;
  project_id?: number;
  draft_type: "release_announcement";
  status: "pending" | "sent" | "cancelled";
  workshop_name?: string;
  to_emails: string[];
  cc_emails: string[];
  subject: string;
  body_text: string;
  body_html?: string;
  ticket_snapshot: Record<string, unknown>;
  created_at: string;
  sent_at?: string;
  cancelled_at?: string;
}

// ── Activity Log ──────────────────────────────────────────────────────────────

export interface ActivityLogEntry {
  id: number;
  module: string;
  action: string;
  entity_type?: string;
  entity_id?: string;
  summary: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ActivityLogList {
  items: ActivityLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

// ── Workshop History ──────────────────────────────────────────────────────────

export interface WorkshopHistoryTicket {
  id: number;
  title: string;
  asana_url?: string;
}

export interface WorkshopHistoryItem {
  workshop_name: string;
  sprint_name: string;
  issues_released: number;
  support_person_name?: string;
  support_person_email?: string;
  release_date?: string;
  sprint_sheet_id?: number;
  tickets: WorkshopHistoryTicket[];
}

export interface WorkshopHistoryData {
  items: WorkshopHistoryItem[];
}

export interface ScheduledReminderData {
  id: number;
  workshop_name: string;
  sprint_name?: string;
  support_person_name?: string;
  due_at: string;
  status: string;
  sent_at?: string;
}

// ── Impact ────────────────────────────────────────────────────────────────────

export interface ImpactTopWorkshop {
  name: string;
  count: number;
}

export interface ImpactMetrics {
  view_mode: string;
  project_name?: string;
  items_released: number;
  points_released: number;
  workshops_helped: number;
  support_people_helped: number;
  blockers_cleared: number;
  avg_days_to_release?: number;
  release_notes_sent: number;
  last_release_note_at?: string;
  followups_sent: number;
  cluster_analyses_run: number;
  active_sprint_sheets: number;
  sprint_sheet_rows: number;
  top_workshops: ImpactTopWorkshop[];
  recent_activity: { id: number; module: string; summary: string; created_at: string }[];
}
