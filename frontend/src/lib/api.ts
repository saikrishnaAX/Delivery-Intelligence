const API_BASE = "/api/v1";
const READ_TIMEOUT_MS = 45_000;
const WRITE_TIMEOUT_MS = 120_000;

const inflightGets = new Map<string, Promise<unknown>>();

class ConcurrencyGate {
  private running = 0;
  private queue: Array<() => void> = [];

  constructor(private max: number) {}

  run<T>(fn: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      const start = () => {
        this.running++;
        fn()
          .then(resolve, reject)
          .finally(() => {
            this.running--;
            const next = this.queue.shift();
            if (next) next();
          });
      };
      if (this.running < this.max) start();
      else this.queue.push(start);
    });
  }
}

const analyticsGate = new ConcurrencyGate(3);

function formatApiDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) return String((item as { msg: string }).msg);
        return JSON.stringify(item);
      })
      .join("; ");
  }
  return fallback;
}

function withParams(
  endpoint: string,
  projectGid?: string | null,
  dateFrom?: string,
  dateTo?: string
): string {
  const params = new URLSearchParams();
  if (projectGid) params.set("project_gid", projectGid);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const qs = params.toString();
  return qs ? `${endpoint}?${qs}` : endpoint;
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
  timeoutMs = WRITE_TIMEOUT_MS
): Promise<T> {
  const method = (options?.method ?? "GET").toUpperCase();
  const isGet = method === "GET";
  const dedupeKey = isGet ? `${method}:${endpoint}` : null;

  const execute = async (): Promise<T> => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        headers: { "Content-Type": "application/json", ...options?.headers },
        signal: controller.signal,
        ...options,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail =
          typeof body.detail === "string"
            ? body.detail
            : formatApiDetail(body.detail, `API error: ${res.status}`);
        const err = new Error(detail) as Error & { status?: number };
        err.status = res.status;
        throw err;
      }
      return res.json();
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error("Request timed out — try again after auto-sync completes.");
      }
      throw err;
    } finally {
      clearTimeout(timeout);
    }
  };

  if (!dedupeKey) return execute();

  const existing = inflightGets.get(dedupeKey);
  if (existing) return existing as Promise<T>;

  const promise = execute();
  inflightGets.set(dedupeKey, promise);
  promise.finally(() => {
    if (inflightGets.get(dedupeKey) === promise) inflightGets.delete(dedupeKey);
  });
  return promise;
}

async function fetchApiRead<T>(endpoint: string): Promise<T> {
  return analyticsGate.run(() => fetchApiWithRetry<T>(endpoint, undefined, 4, READ_TIMEOUT_MS));
}

async function fetchApiWithRetry<T>(
  endpoint: string,
  options?: RequestInit,
  retries = 5,
  timeoutMs = WRITE_TIMEOUT_MS,
): Promise<T> {
  let lastErr: Error | undefined;
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      return await fetchApi<T>(endpoint, options, timeoutMs);
    } catch (err) {
      lastErr = err instanceof Error ? err : new Error(String(err));
      const status = (lastErr as Error & { status?: number }).status;
      const busy =
        status === 503 ||
        lastErr.message.toLowerCase().includes("database is busy") ||
        lastErr.message.toLowerCase().includes("database busy");
      if (!busy || attempt >= retries - 1) throw lastErr;
      await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
    }
  }
  throw lastErr ?? new Error("Request failed");
}

export const api = {
  getIntegrationStatus: () =>
    fetchApi<import("@/types").IntegrationStatus>("/integrations/status"),

  getProjects: () =>
    fetchApi<import("@/types").AsanaProject[]>("/projects"),

  syncProject: (projectGid: string) =>
    fetchApi<import("@/types").SyncResult>(`/sync/${projectGid}`, { method: "POST" }, 300_000),

  getExecutionBoard: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").ExecutionBoardData>(withParams("/execution", projectGid, dateFrom, dateTo)),

  getExecutionDrilldown: (
    projectGid: string | null | undefined,
    metric: string,
    dateFrom?: string,
    dateTo?: string,
    stage?: string,
    limit = 200,
    offset = 0,
  ) => {
    const params = new URLSearchParams();
    params.set("metric", metric);
    if (stage) params.set("stage", stage);
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    const base = `/execution/drilldown?${params.toString()}`;
    return fetchApiRead<import("@/types").ExecutiveDrilldownResponse>(
      withParams(base, projectGid, dateFrom, dateTo)
    );
  },

  getExecutiveAnalytics: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").ExecutiveAnalyticsData>(
      withParams("/executive/analytics", projectGid, dateFrom, dateTo)
    ),

  getCEOIntelligence: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").CEOIntelligenceData>(withParams("/ceo-intelligence", projectGid, dateFrom, dateTo)),

  getCEOReportSettings: () =>
    fetchApiRead<import("@/types").CEOReportSettings>("/ceo-intelligence/report-settings"),

  updateCEOReportSettings: (body: Partial<import("@/types").CEOReportSettings>) =>
    fetchApi<import("@/types").CEOReportSettings>("/ceo-intelligence/report-settings", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  sendCEOReport: (
    projectGid: string | null | undefined,
    body: { period: string; recipient_emails?: string[]; extra_emails?: string[] }
  ) =>
    fetchApi<import("@/types").CEOReportSendResult>(
      withParams("/ceo-intelligence/send-report", projectGid ?? null),
      { method: "POST", body: JSON.stringify(body) }
    ),

  previewCEOReport: (projectGid?: string | null, period = "weekly") => {
    const base = withParams("/ceo-intelligence/report-preview", projectGid ?? null);
    const sep = base.includes("?") ? "&" : "?";
    return fetchApi<import("@/types").CEOReportPreview>(
      `${base}${sep}period=${encodeURIComponent(period)}`
    );
  },

  runDailyCursorAnalysis: (projectGid?: string | null) =>
    fetchApi<{
      success: boolean;
      issues_found?: number;
      issues_cursor_enriched?: number;
      analysis_at?: string;
      schedule?: string;
    }>(withParams("/issue-intelligence/run-daily-cursor", projectGid ?? null), {
      method: "POST",
    }),

  runWeeklyCursorAnalysis: (projectGid?: string | null) =>
    fetchApi<{
      success: boolean;
      issues_found?: number;
      issues_cursor_enriched?: number;
      ceo_brief_overlay_saved?: boolean;
      analysis_at?: string;
    }>(withParams("/ceo-intelligence/run-weekly-analysis", projectGid ?? null), {
      method: "POST",
    }),

  getTickets: (projectGid?: string | null, dateFrom?: string, dateTo?: string, page = 1, pageSize = 20, status?: string, ticketType?: string) => {
    let ep = `/tickets?page=${page}&page_size=${pageSize}`;
    if (status) ep += `&status=${encodeURIComponent(status)}`;
    if (ticketType) ep += `&ticket_type=${encodeURIComponent(ticketType)}`;
    return fetchApiRead<import("@/types").TicketListResponse>(withParams(ep, projectGid, dateFrom, dateTo));
  },

  getClassification: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").ClassificationAnalytics>(withParams("/classification", projectGid, dateFrom, dateTo)),

  getIssueIntelligence: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").IssueIntelligenceDashboard>(
      withParams("/issue-intelligence", projectGid, dateFrom, dateTo)
    ),

  startIssueIntelligenceAnalysis: (projectGid: string, dateFrom?: string, dateTo?: string) =>
    fetchApi<import("@/types").IssueIntelligenceJobData>(
      withParams("/issue-intelligence/analyze", projectGid, dateFrom, dateTo),
      { method: "POST" }
    ),

  getIssueIntelligenceJob: (jobId: number) =>
    fetchApi<import("@/types").IssueIntelligenceJobData>(`/issue-intelligence/jobs/${jobId}`),

  getRecurringIssueDetail: (issueId: number) =>
    fetchApi<import("@/types").RecurringIssueDetail>(`/issue-intelligence/issues/${issueId}`),

  getBlockers: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").BlockerAnalytics>(withParams("/blockers", projectGid, dateFrom, dateTo)),

  getCustomers: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").CustomerPainAnalytics>(withParams("/customers", projectGid, dateFrom, dateTo)),

  getSupportTeam: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").SupportTeamAnalytics>(withParams("/support-team", projectGid, dateFrom, dateTo)),

  getJira: () => fetchApiRead<import("@/types").JiraAnalytics>("/jira"),

  syncJira: () =>
    fetchApi<import("@/types").SyncResult>("/jira/sync", { method: "POST" }),

  getResolution: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").ResolutionAnalytics>(withParams("/resolution", projectGid, dateFrom, dateTo)),

  getMonthlyProgress: (projectGid: string, year: number) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    params.set("year", String(year));
    return fetchApi<import("@/types").MonthlyProgressData>(`/resolution/monthly?${params}`);
  },

  getInsights: (page: string, projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApi<import("@/types").AIInsight[]>(withParams(`/insights/${page}`, projectGid, dateFrom, dateTo)),

  chat: (
    message: string,
    history: import("@/types").ChatMessage[],
    projectGid?: string | null,
    dateFrom?: string,
    dateTo?: string
  ) =>
    fetchApi<import("@/types").ChatResponse>(withParams("/assistant/chat", projectGid, dateFrom, dateTo), {
      method: "POST",
      body: JSON.stringify({ message, conversation_history: history }),
    }),

  getReleaseNotes: (
    projectGid: string,
    opts: { lookbackDays?: number; dateFrom?: string; dateTo?: string; sprintName?: string } = {}
  ) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    if (opts.dateFrom && opts.dateTo) {
      params.set("date_from", opts.dateFrom);
      params.set("date_to", opts.dateTo);
    } else {
      params.set("lookback_days", String(opts.lookbackDays ?? 2));
    }
    if (opts.sprintName) params.set("sprint_name", opts.sprintName);
    return fetchApi<import("@/types").ReleaseNotesData>(`/release-notes?${params}`);
  },

  downloadReleaseNotes: async (
    projectGid: string,
    opts: { lookbackDays?: number; dateFrom?: string; dateTo?: string; sprintName?: string } = {}
  ) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    if (opts.dateFrom && opts.dateTo) {
      params.set("date_from", opts.dateFrom);
      params.set("date_to", opts.dateTo);
    } else {
      params.set("lookback_days", String(opts.lookbackDays ?? 2));
    }
    if (opts.sprintName) params.set("sprint_name", opts.sprintName);
    const res = await fetch(`${API_BASE}/release-notes/download?${params}`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Download failed: ${res.status}`);
    }
    return res.blob();
  },

  getSprintSheet: (projectGid: string, sprintName: string, refresh = false) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    params.set("sprint_name", sprintName);
    if (refresh) params.set("refresh", "true");
    return fetchApi<import("@/types").SprintSheetData>(`/sprint-sheet?${params}`);
  },

  saveSprintSheet: (projectGid: string, payload: import("@/types").SprintSheetExportPayload) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    return fetchApi<import("@/types").SprintSheetData>(`/sprint-sheet/save?${params}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  downloadSprintSheet: async (
    projectGid: string,
    payload: import("@/types").SprintSheetExportPayload
  ) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    const res = await fetch(`${API_BASE}/sprint-sheet/download?${params}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Download failed: ${res.status}`);
    }
    return res.blob();
  },

  linkSprintGoogleSheet: (projectGid: string, sprintName: string, spreadsheetUrl: string) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    return fetchApi<import("@/types").SprintSheetData>(`/sprint-sheet/google/link?${params}`, {
      method: "POST",
      body: JSON.stringify({ sprint_name: sprintName, spreadsheet_url: spreadsheetUrl }),
    });
  },

  getTeams: () => fetchApi<import("@/types").TeamData[]>("/org/teams"),

  createTeam: (body: { name: string; description?: string }) =>
    fetchApiWithRetry<import("@/types").TeamData>("/org/teams", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  addTeamMember: (
    teamId: number,
    body: { name: string; email: string; designation?: string; is_lead?: boolean }
  ) =>
    fetchApiWithRetry<import("@/types").TeamData>(`/org/teams/${teamId}/members`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateTeamMember: (
    teamId: number,
    personId: number,
    body: { name?: string; email?: string; designation?: string; is_lead?: boolean }
  ) =>
    fetchApiWithRetry<import("@/types").TeamData>(`/org/teams/${teamId}/members/${personId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  removeTeamMember: (teamId: number, personId: number) =>
    fetchApiWithRetry<import("@/types").TeamData>(`/org/teams/${teamId}/members/${personId}`, {
      method: "DELETE",
    }),

  updateTeam: (teamId: number, body: { name?: string; description?: string }) =>
    fetchApiWithRetry<import("@/types").TeamData>(`/org/teams/${teamId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteTeam: (teamId: number) =>
    fetchApiWithRetry<{ success: boolean }>(`/org/teams/${teamId}`, { method: "DELETE" }),

  getPeople: () => fetchApi<import("@/types").PersonData[]>("/org/people"),
  getCustomerAccounts: () => fetchApi<import("@/types").CustomerAccountData[]>("/org/customers"),

  reconcileCustomerSupportEmails: () =>
    fetchApiWithRetry<{ updated: number; total: number }>("/org/customers/reconcile-support-emails", {
      method: "POST",
    }),

  createCustomerAccount: (body: {
    workshop_name: string;
    support_person_name?: string;
    support_person_email?: string;
    workshop_email?: string;
    support_contact_email?: string;
    ax_id?: string;
    tier?: string;
    location?: string;
  }) =>
    fetchApiWithRetry<import("@/types").CustomerAccountData>("/org/customers", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateCustomerAccount: (
    customerId: number,
    body: {
      workshop_name?: string;
      support_person_name?: string;
      support_person_email?: string;
      workshop_email?: string;
      support_contact_email?: string;
      ax_id?: string;
      tier?: string;
      location?: string;
    }
  ) =>
    fetchApiWithRetry<import("@/types").CustomerAccountData>(`/org/customers/${customerId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteCustomerAccount: (customerId: number) =>
    fetchApiWithRetry<{ success: boolean }>(`/org/customers/${customerId}`, { method: "DELETE" }),

  importTeamsCsv: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/org/import/teams`, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Import failed: ${res.status}`);
    }
    return res.json() as Promise<import("@/types").CsvImportResult>;
  },

  importCustomersCsv: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/org/import/customers`, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Import failed: ${res.status}`);
    }
    return res.json() as Promise<import("@/types").CsvImportResult>;
  },

  downloadTeamsTemplate: () => window.open(`${API_BASE}/org/templates/teams`, "_blank"),
  downloadCustomersTemplate: () => window.open(`${API_BASE}/org/templates/customers`, "_blank"),

  getWorkshopEmailDrafts: (status = "pending") =>
    fetchApi<import("@/types").WorkshopEmailDraft[]>(
      `/workshop-email-drafts?status=${encodeURIComponent(status)}`
    ),

  getWorkshopEmailDraftsSummary: () =>
    fetchApi<{ pending_count: number }>("/workshop-email-drafts/summary"),

  updateWorkshopEmailDraft: (
    draftId: number,
    body: {
      subject?: string;
      body_text?: string;
      to_emails?: string[];
      cc_emails?: string[];
    }
  ) =>
    fetchApiWithRetry<import("@/types").WorkshopEmailDraft>(`/workshop-email-drafts/${draftId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  sendWorkshopEmailDraft: (draftId: number) =>
    fetchApiWithRetry<import("@/types").WorkshopEmailDraft>(
      `/workshop-email-drafts/${draftId}/send`,
      { method: "POST" }
    ),

  cancelWorkshopEmailDraft: (draftId: number) =>
    fetchApiWithRetry<import("@/types").WorkshopEmailDraft>(
      `/workshop-email-drafts/${draftId}/cancel`,
      { method: "POST" }
    ),

  getWorkshopAudienceCounts: () =>
    fetchApi<Record<string, { total: number; with_email: number }>>("/release-notes/workshop-audience"),

  createWorkshopReleaseDrafts: (
    projectGid: string,
    body: {
      sprint_name: string;
      lookback_days?: number;
      date_from?: string;
      date_to?: string;
      audience?: string;
      workshop_ids?: number[];
    }
  ) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    return fetchApiWithRetry<{
      created: number;
      skipped_no_email: number;
      eligible: number;
      draft_ids: number[];
    }>(`/release-notes/workshop-announcement/drafts?${params}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  getActivity: (opts: {
    module?: string;
    dateFrom?: string;
    dateTo?: string;
    page?: number;
    pageSize?: number;
  } = {}) => {
    const params = new URLSearchParams();
    if (opts.module) params.set("module", opts.module);
    if (opts.dateFrom) params.set("date_from", opts.dateFrom);
    if (opts.dateTo) params.set("date_to", opts.dateTo);
    if (opts.page) params.set("page", String(opts.page));
    if (opts.pageSize) params.set("page_size", String(opts.pageSize));
    const qs = params.toString();
    return fetchApi<import("@/types").ActivityLogList>(`/activity${qs ? `?${qs}` : ""}`);
  },

  sendReleaseNotes: (
    projectGid: string,
    body: import("@/types").ReleaseNotesSendPayload
  ) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    return fetchApi<import("@/types").ReleaseNotesSendResult>(`/release-notes/send?${params}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  getWorkshopHistory: (projectGid?: string | null) => {
    const params = new URLSearchParams();
    if (projectGid) params.set("project_gid", projectGid);
    const qs = params.toString();
    return fetchApi<import("@/types").WorkshopHistoryData>(`/workshops/history${qs ? `?${qs}` : ""}`);
  },

  getReminders: (status?: string) => {
    const params = status ? `?status=${status}` : "";
    return fetchApi<import("@/types").ScheduledReminderData[]>(`/workshops/reminders${params}`);
  },

  markSprintReleased: (projectGid: string, sprintName: string, releaseDate?: string) => {
    const params = new URLSearchParams();
    params.set("project_gid", projectGid);
    return fetchApi<{ success: boolean; reminders_scheduled: number }>(
      `/sprint-sheet/mark-released?${params}`,
      {
        method: "POST",
        body: JSON.stringify({ sprint_name: sprintName, release_date: releaseDate }),
      }
    );
  },

  getClusterTickets: (clusterId: number, status = "open") =>
    fetchApi<import("@/types").ClusterTicketData[]>(`/clusters/${clusterId}/tickets?status=${status}`),

  startClusterAnalysis: (clusterId: number) =>
    fetchApi<import("@/types").ClusterAnalysisJobData>(`/clusters/${clusterId}/analyze`, { method: "POST" }),

  getClusterAnalysisJob: (jobId: number) =>
    fetchApi<import("@/types").ClusterAnalysisJobData>(`/cluster-analysis/${jobId}`),

  getLatestClusterAnalysis: (clusterId: number) =>
    fetchApi<import("@/types").ClusterAnalysisJobData>(`/clusters/${clusterId}/analysis/latest`),

  dismissClusterAnalysis: (clusterId: number) =>
    fetchApi<{ success: boolean; job_id: number }>(`/clusters/${clusterId}/analysis/dismiss`, {
      method: "POST",
    }),

  getImpact: (projectGid?: string | null, dateFrom?: string, dateTo?: string) =>
    fetchApiRead<import("@/types").ImpactMetrics>(withParams("/impact", projectGid, dateFrom, dateTo)),

  downloadImpactCsv: async (projectGid?: string | null, dateFrom?: string, dateTo?: string) => {
    const res = await fetch(`${API_BASE}${withParams("/impact/export", projectGid, dateFrom, dateTo)}`);
    if (!res.ok) throw new Error("Export failed");
    return res.blob();
  },

  getReleaseNoteArchives: (projectGid?: string | null) => {
    const params = new URLSearchParams();
    if (projectGid) params.set("project_gid", projectGid);
    const qs = params.toString();
    return fetchApi<import("@/types").ReleaseNoteArchive[]>(`/release-notes/archive${qs ? `?${qs}` : ""}`);
  },

  uploadReleaseNoteArchive: async (
    projectGid: string | null | undefined,
    releaseDate: string,
    file: File,
    opts: { title?: string; sprintName?: string } = {}
  ) => {
    const params = new URLSearchParams();
    if (projectGid) params.set("project_gid", projectGid);
    params.set("release_date", releaseDate);
    if (opts.title) params.set("title", opts.title);
    if (opts.sprintName) params.set("sprint_name", opts.sprintName);

    let lastErr: Error | undefined;
    for (let attempt = 0; attempt < 2; attempt++) {
      const form = new FormData();
      form.append("file", file);
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60_000);
      try {
        const res = await fetch(`${API_BASE}/release-notes/archive?${params}`, {
          method: "POST",
          body: form,
          signal: controller.signal,
        });
        clearTimeout(timeout);
        if (res.ok) {
          return res.json() as Promise<import("@/types").ReleaseNoteArchive>;
        }
        const body = await res.json().catch(() => ({}));
        const detail = formatApiDetail(body.detail, `Upload failed: ${res.status}`);
        lastErr = new Error(detail);
        const busy = res.status === 503 || detail.toLowerCase().includes("database busy");
        if (!busy || attempt >= 1) throw lastErr;
        await new Promise((r) => setTimeout(r, 800));
      } catch (err) {
        clearTimeout(timeout);
        if (err instanceof Error && err.name === "AbortError") {
          throw new Error("Upload timed out — try a smaller file or try again");
        }
        throw err;
      }
    }
    throw lastErr ?? new Error("Upload failed");
  },

  sendReleaseNoteArchive: (
    archiveId: number,
    body: import("@/types").ReleaseNoteArchiveSendPayload
  ) =>
    fetchApi<import("@/types").ReleaseNotesSendResult>(`/release-notes/archive/${archiveId}/send`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  downloadReleaseNoteArchive: async (archiveId: number) => {
    const res = await fetch(`${API_BASE}/release-notes/archive/${archiveId}/download`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Download failed: ${res.status}`);
    }
    return res.blob();
  },
};
