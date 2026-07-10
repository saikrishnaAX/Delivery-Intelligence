import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, ExternalLink, Link2, RefreshCw, Save, Sheet, Users, Bell } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useProject } from "@/hooks/use-project";
import { readCache, writeCache, buildScope, invalidateCache } from "@/lib/data-cache";
import { refreshCached } from "@/lib/fetch-with-cache";
import type { SprintSheetData, SprintSheetRow } from "@/types";
import { cn } from "@/lib/utils";

function defaultSprintName() {
  const d = new Date();
  return `${d.toLocaleString("en-US", { month: "long" })} ${d.getFullYear()}`;
}

function recalcTotal(row: SprintSheetRow): SprintSheetRow {
  const dev = row.dev_estimate ?? 0;
  const qa = row.qa_estimate ?? 0;
  const hasEst = row.dev_estimate != null || row.qa_estimate != null;
  return {
    ...row,
    total_estimate: hasEst ? dev + qa : row.total_estimate,
  };
}

type EditableKey = "qa_estimate" | "dev_assigned" | "qa_assigned" | "status";

const EDITABLE: { key: EditableKey; label: string; width: string }[] = [
  { key: "qa_estimate", label: "QA Est", width: "min-w-[72px]" },
  { key: "dev_assigned", label: "Dev Assigned", width: "min-w-[100px]" },
  { key: "qa_assigned", label: "QA Assigned", width: "min-w-[100px]" },
  { key: "status", label: "Status", width: "min-w-[120px]" },
];

function typeBadgeVariant(type?: string | null): "destructive" | "default" | "outline" {
  const t = (type ?? "").toLowerCase();
  if (t.includes("bug")) return "destructive";
  if (t.includes("enhance") || t.includes("requirement") || t.includes("feature")) return "default";
  return "outline";
}

function normalizeSection(name: string): string {
  return name.toLowerCase().replace(/[\s\-_]+/g, "");
}

const PIPELINE_SECTIONS = [
  "Prioritized",
  "Design/Spec- in progress",
  "Design/Spec - in progress",
  "Developing",
  "PR Raised",
  "Build in UAT",
  "Testing (UAT)",
  "Testing(UAT)",
  "Build in Pre Prod",
  "Build in Pre-Prod",
  "Testing(Pre-Prod)",
  "Testing (Pre-Prod)",
  "Done",
];

function pipelineStageRank(sectionName?: string | null): number {
  const norm = normalizeSection(sectionName || "");
  for (let i = 0; i < PIPELINE_SECTIONS.length; i++) {
    if (normalizeSection(PIPELINE_SECTIONS[i]) === norm) return i;
  }
  return -1;
}

function sortRowsForDisplay(rows: SprintSheetRow[]): SprintSheetRow[] {
  return [...rows]
    .filter((r) => r.sheet_status !== "removed")
    .sort((a, b) => {
      const stageA = pipelineStageRank(a.section_name);
      const stageB = pipelineStageRank(b.section_name);
      if (stageA !== stageB) return stageB - stageA;
      return (a.asana_board_index ?? 999999) - (b.asana_board_index ?? 999999);
    });
}

function priorityBadgeVariant(priority?: string | null): "destructive" | "default" | "secondary" | "outline" {
  const p = (priority ?? "").toLowerCase();
  if (p.includes("high") || p.includes("critical") || p.includes("urgent")) return "destructive";
  if (p.includes("medium")) return "default";
  if (p.includes("low")) return "secondary";
  return "outline";
}

interface SprintSheetTableProps {
  tableRows: SprintSheetRow[];
  onUpdateRow: (ticketId: number, key: EditableKey, value: string) => void;
}

function SprintSheetTable({ tableRows, onUpdateRow }: SprintSheetTableProps) {
  if (tableRows.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-[10px] table-fixed min-w-[1260px]">
        <colgroup>
          <col style={{ width: "240px" }} />
          <col style={{ width: "96px" }} />
          <col style={{ width: "72px" }} />
          <col style={{ width: "64px" }} />
          <col style={{ width: "64px" }} />
          <col style={{ width: "96px" }} />
          <col style={{ width: "64px" }} />
          <col style={{ width: "80px" }} />
          <col style={{ width: "108px" }} />
          <col style={{ width: "108px" }} />
          <col style={{ width: "120px" }} />
          <col style={{ width: "64px" }} />
        </colgroup>
        <thead>
          <tr className="bg-muted/50 text-left">
            <th className="px-2 py-2 font-medium">Ticket</th>
            <th className="px-2 py-2 font-medium">Type</th>
            <th className="px-2 py-2 font-medium">Priority</th>
            <th className="px-2 py-2 font-medium">Asana</th>
            <th className="px-2 py-2 font-medium">Jira</th>
            <th className="px-2 py-2 font-medium">Jira Status</th>
            <th className="px-2 py-2 font-medium">Dev Est</th>
            {EDITABLE.map((col) => (
              <th key={col.key} className="px-2 py-2 font-medium">
                {col.label}
              </th>
            ))}
            <th className="px-2 py-2 font-medium">Total</th>
          </tr>
        </thead>
        <tbody>
          {tableRows.map((row) => (
            <tr
              key={row.ticket_id}
              className={cn(
                "border-t border-border/60 align-top",
                row.sheet_status === "removed" && "opacity-50"
              )}
            >
              <td className="px-2 py-1.5 align-top max-w-0">
                <p className="font-medium leading-snug text-foreground line-clamp-3" title={row.title?.trim() || "Untitled ticket"}>
                  {row.title?.trim() || "Untitled ticket"}
                </p>
                {row.asana_link && (
                  <a
                    href={row.asana_link}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[9px] text-primary hover:underline inline-flex items-center gap-0.5 mt-0.5"
                  >
                    View in Asana
                  </a>
                )}
              </td>
              <td className="px-2 py-1.5 align-top whitespace-nowrap">
                <Badge variant={typeBadgeVariant(row.ticket_type)} className="text-[9px] whitespace-nowrap">
                  {row.ticket_type ?? "—"}
                </Badge>
              </td>
              <td className="px-2 py-1.5 align-top whitespace-nowrap">
                {row.priority ? (
                  <Badge variant={priorityBadgeVariant(row.priority)} className="text-[9px] whitespace-nowrap">
                    {row.priority}
                  </Badge>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-2 py-1.5">
                {row.asana_link ? (
                  <a href={row.asana_link} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                    Open
                  </a>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-2 py-1.5">
                {row.doc_link ? (
                  <a href={row.doc_link} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                    Open
                  </a>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-2 py-1.5 text-muted-foreground">{row.jira_status ?? "—"}</td>
              <td className="px-2 py-1.5 text-muted-foreground">{row.dev_estimate ?? "—"}</td>
              {EDITABLE.map((col) => (
                <td key={col.key} className="px-1 py-1">
                  {col.key === "status" ? (
                    <Input
                      value={row.status ?? ""}
                      onChange={(e) => onUpdateRow(row.ticket_id, col.key, e.target.value)}
                      className="h-7 text-[10px] bg-amber-500/5 border-amber-500/20"
                    />
                  ) : (
                    <Input
                      value={
                        col.key === "qa_estimate"
                          ? row.qa_estimate ?? ""
                          : (row[col.key] as string | null) ?? ""
                      }
                      onChange={(e) => onUpdateRow(row.ticket_id, col.key, e.target.value)}
                      className="h-7 text-[10px] bg-amber-500/5 border-amber-500/20"
                      placeholder={col.key === "dev_assigned" || col.key === "qa_assigned" ? "—" : undefined}
                    />
                  )}
                </td>
              ))}
              <td className="px-2 py-1.5 font-medium">{row.total_estimate ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SprintSheetPage() {
  const { projectGid, selectedProject, cacheVersion, integrationStatus } = useProject();
  const [sprintName, setSprintName] = useState(defaultSprintName);
  const [data, setData] = useState<SprintSheetData | null>(null);
  const [rows, setRows] = useState<SprintSheetRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveHint, setSaveHint] = useState<string | null>(null);
  const [googleUrl, setGoogleUrl] = useState("");
  const [showSetup, setShowSetup] = useState(true);
  const [linkingGoogle, setLinkingGoogle] = useState(false);
  const [markingReleased, setMarkingReleased] = useState(false);
  const [releaseHint, setReleaseHint] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rowsRef = useRef(rows);
  rowsRef.current = rows;

  const totals = useMemo(() => {
    if (data?.totals) return data.totals;
    const active = rows.filter((r) => r.sheet_status !== "removed");
    const dev = active.reduce((s, r) => s + (r.dev_estimate ?? 0), 0);
    const qa = active.reduce((s, r) => s + (r.qa_estimate ?? 0), 0);
    const total = active.reduce((s, r) => s + (r.total_estimate ?? 0), 0);
    const norm = (v: string) => v.toLowerCase().replace(/[\s\-_]+/g, "");
    const prioritized = active.filter((r) => norm(r.status || "").includes("prioritized")).length;
    const done = active.filter((r) => norm(r.status || "") === "done").length;
    return {
      ticket_count: active.length,
      prioritized,
      prioritized_bugs: 0,
      prioritized_requirements: 0,
      prioritized_other: 0,
      prioritized_bug_hours: 0,
      prioritized_requirement_hours: 0,
      prioritized_bug_dev_hours: 0,
      prioritized_requirement_dev_hours: 0,
      prioritized_bug_qa_hours: 0,
      prioritized_requirement_qa_hours: 0,
      in_progress: Math.max(active.length - prioritized - done, 0),
      done,
      removed: rows.filter((r) => r.sheet_status === "removed").length,
      dev_hours: dev,
      qa_hours: qa,
      total_hours: total,
      in_sprint: active.length,
      released: 0,
    };
  }, [data?.totals, rows]);

  const cacheScope = buildScope(["v6", projectGid, sprintName]);

  const applySheet = useCallback((result: SprintSheetData) => {
    setData(result);
    setRows(result.rows.map(recalcTotal));
    writeCache("sprint-sheet", cacheScope, result);
  }, [cacheScope]);

  const loadSheet = useCallback(async (refresh = false) => {
    if (!projectGid) {
      setData(null);
      setRows([]);
      return;
    }
    if (refresh) {
      invalidateCache("sprint-sheet", cacheScope);
    }
    const cached = refresh ? null : readCache<SprintSheetData>("sprint-sheet", cacheScope);
    if (cached) {
      applySheet(cached);
    }
    if (!cached) setLoading(true);
    setError(null);
    try {
      const result = await api.getSprintSheet(projectGid, sprintName, refresh);
      applySheet(result);
    } catch (err) {
      if (!cached) {
        setError(err instanceof Error ? err.message : "Failed to load sprint sheet");
        setData(null);
        setRows([]);
      }
    } finally {
      setLoading(false);
    }
  }, [projectGid, sprintName, cacheScope, applySheet]);

  useEffect(() => {
    void loadSheet(false);
  }, [projectGid, sprintName, loadSheet]);

  useEffect(() => {
    if (cacheVersion === 0) return;
    void loadSheet(true);
  }, [cacheVersion, loadSheet]);

  const syncFromAsana = useCallback(async () => {
    if (!projectGid) return;
    setLoading(true);
    setError(null);
    invalidateCache("sprint-sheet", cacheScope);
    try {
      await api.syncProject(projectGid);
      const result = await api.getSprintSheet(projectGid, sprintName, true);
      applySheet(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Asana sync failed");
    } finally {
      setLoading(false);
    }
  }, [projectGid, sprintName, cacheScope, applySheet]);

  const persistSheet = useCallback(
    async (rowsToSave: SprintSheetRow[]) => {
      if (!projectGid || rowsToSave.length === 0) return;
      setSaving(true);
      setSaveHint(null);
      try {
        const result = await api.saveSprintSheet(projectGid, {
          sprint_name: sprintName,
          section: data?.section,
          rows: rowsToSave,
        });
        setData(result);
        setRows(result.rows.map(recalcTotal));
        writeCache("sprint-sheet", cacheScope, result);
        setSaveHint("Saved");
      } catch (err) {
        setSaveHint(err instanceof Error ? err.message : "Save failed");
      } finally {
        setSaving(false);
      }
    },
    [projectGid, sprintName, data?.section, cacheScope]
  );

  const scheduleSave = useCallback(
    (nextRows: SprintSheetRow[]) => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => {
        persistSheet(nextRows);
      }, 1500);
    },
    [persistSheet]
  );

  const updateRow = (ticketId: number, key: EditableKey, value: string) => {
    setRows((prev) => {
      const next = prev.map((row) => {
        if (row.ticket_id !== ticketId) return row;
        const updated = { ...row };
        if (key === "qa_estimate") {
          const num = value === "" ? null : Number(value);
          updated.qa_estimate = Number.isFinite(num) ? num : null;
        } else if (key === "status") {
          updated.status = value;
        } else {
          updated[key] = value || null;
        }
        return recalcTotal(updated);
      });
      scheduleSave(next);
      return next;
    });
    setSaveHint("Saving…");
  };

  const displayRows = useMemo(() => sortRowsForDisplay(rows), [rows]);

  const handleDownload = async () => {
    if (!projectGid || displayRows.length === 0) return;
    setDownloading(true);
    try {
      const blob = await api.downloadSprintSheet(projectGid, {
        sprint_name: sprintName,
        section: data?.section,
        rows: displayRows,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${sprintName} Sheet.xlsx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  };

  const handleLinkGoogle = async () => {
    if (!projectGid || !googleUrl.trim()) return;
    setLinkingGoogle(true);
    setError(null);
    try {
      const result = await api.linkSprintGoogleSheet(projectGid, sprintName, googleUrl.trim());
      setData(result);
      setRows(result.rows.map(recalcTotal));
      setSaveHint("Linked to Google Sheet");
      setShowSetup(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to link Google Sheet");
    } finally {
      setLinkingGoogle(false);
    }
  };

  const handleMarkReleased = async () => {
    if (!projectGid) return;
    setMarkingReleased(true);
    setReleaseHint(null);
    setError(null);
    try {
      const result = await api.markSprintReleased(projectGid, sprintName);
      setReleaseHint(
        `Sprint marked released — ${result.reminders_scheduled} feedback reminder(s) scheduled for 1 week from now`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark sprint released");
    } finally {
      setMarkingReleased(false);
    }
  };

  const isSheetLinked = Boolean(data?.google_sheet_url && data?.sync_mode === "service_account");

  return (
    <PageLayout page="sprint-sheet">
      <Header
        title="Sprint Sheet"
        description="Live sheet synced with Asana and Google Sheets via Google Cloud API"
      />
      <div className="page-content space-y-3">
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <label className="text-[10px] text-muted-foreground font-medium">Sprint name</label>
            <Input
              value={sprintName}
              onChange={(e) => setSprintName(e.target.value)}
              className="h-8 w-44 text-xs"
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-[10px]"
            onClick={() => void syncFromAsana()}
            disabled={loading || !projectGid}
          >
            <RefreshCw className={cn("h-3 w-3 mr-1", loading && "animate-spin")} />
            Sync from Asana
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 text-[10px]"
            onClick={() => persistSheet(rowsRef.current)}
            disabled={saving || rows.length === 0}
          >
            <Save className={cn("h-3 w-3 mr-1", saving && "animate-pulse")} />
            Save now
          </Button>
          <Button
            size="sm"
            className="h-8 text-[10px]"
            onClick={handleDownload}
            disabled={downloading || rows.length === 0}
          >
            <Download className="h-3 w-3 mr-1" />
            {downloading ? "Exporting…" : "Download Excel"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            className="h-8 text-[10px]"
            onClick={handleMarkReleased}
            disabled={markingReleased || !projectGid}
          >
            <Bell className="h-3 w-3 mr-1" />
            {markingReleased ? "Scheduling…" : "Mark sprint released"}
          </Button>
          {saveHint && (
            <span className="text-[10px] text-muted-foreground self-center">{saveHint}</span>
          )}
          {releaseHint && (
            <span className="text-[10px] text-primary self-center">{releaseHint}</span>
          )}
        </div>

        {!projectGid && (
          <EmptyState
            title="Select Sprint planning"
            description="Choose Sprint planning, put sprint tickets in Prioritized, then open this sheet."
          />
        )}

        {error && (
          <Card className="border-destructive/30">
            <CardContent className="py-2 text-[11px] text-destructive">{error}</CardContent>
          </Card>
        )}

        {projectGid && loading && !data && <LoadingState />}

        {data && (
          <>
            <div className="grid gap-2 grid-cols-2 lg:grid-cols-5">
              <MetricCard title="Prioritized" value={totals.prioritized ?? 0} icon={Sheet} />
              <MetricCard title="In progress" value={totals.in_progress ?? 0} icon={Sheet} />
              <MetricCard title="Done" value={totals.done ?? 0} icon={Sheet} variant="success" />
              <MetricCard title="Dev hours" value={(totals.dev_hours ?? 0).toFixed(0)} icon={Users} />
              <MetricCard title="QA hours" value={(totals.qa_hours ?? 0).toFixed(0)} icon={Users} />
            </div>

            {(totals.prioritized ?? 0) > 0 && (
              <Card>
                <CardContent className="py-2.5">
                  <p className="text-[10px] font-medium mb-2">Prioritized breakdown (bugs vs requirements)</p>
                  <div className="grid gap-2 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 text-[10px]">
                    <div className="rounded-md border border-destructive/20 bg-destructive/5 px-2.5 py-2">
                      <p className="text-muted-foreground">Bugs</p>
                      <p className="font-semibold text-sm">{totals.prioritized_bugs ?? 0} tickets</p>
                      <p className="text-muted-foreground mt-0.5">
                        {(totals.prioritized_bug_hours ?? 0).toFixed(0)} hrs total
                        {" · "}
                        dev {(totals.prioritized_bug_dev_hours ?? 0).toFixed(0)} / qa{" "}
                        {(totals.prioritized_bug_qa_hours ?? 0).toFixed(0)}
                      </p>
                    </div>
                    <div className="rounded-md border border-primary/20 bg-primary/5 px-2.5 py-2">
                      <p className="text-muted-foreground">Requirements / enhancements</p>
                      <p className="font-semibold text-sm">{totals.prioritized_requirements ?? 0} tickets</p>
                      <p className="text-muted-foreground mt-0.5">
                        {(totals.prioritized_requirement_hours ?? 0).toFixed(0)} hrs total
                        {" · "}
                        dev {(totals.prioritized_requirement_dev_hours ?? 0).toFixed(0)} / qa{" "}
                        {(totals.prioritized_requirement_qa_hours ?? 0).toFixed(0)}
                      </p>
                    </div>
                    {(totals.prioritized_other ?? 0) > 0 && (
                      <div className="rounded-md border border-border px-2.5 py-2">
                        <p className="text-muted-foreground">Unclassified</p>
                        <p className="font-semibold text-sm">{totals.prioritized_other} tickets</p>
                        <p className="text-muted-foreground mt-0.5">Set Asana Type to Bug or Requirement</p>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            <Card className="border-primary/20 bg-primary/5">
              <CardContent className="py-2.5 text-[10px] text-muted-foreground space-y-2">
                <p>
                  <span className="font-medium text-foreground">Project:</span>{" "}
                  {data.project_name ?? selectedProject?.name ?? "—"}
                </p>
                <p>
                  Tickets are listed <strong>Done and in-progress first</strong>, counting down to
                  Prioritized at the bottom — so you see what is finished or actively moving before
                  what is still queued. Within each stage, order follows the Asana board.
                </p>

                <div className="pt-1 border-t border-border/40 space-y-2">
                  {isSheetLinked ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <a
                        href={data.google_sheet_url!}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-primary font-medium hover:underline"
                      >
                        <ExternalLink className="h-3 w-3" />
                        Open Google Sheet
                      </a>
                      {data.google_synced_at && (
                        <span className="text-muted-foreground">
                          Last synced: {new Date(data.google_synced_at).toLocaleString()}
                        </span>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-[9px]"
                        onClick={() => setShowSetup((v) => !v)}
                      >
                        {showSetup ? "Hide link settings" : "Change sheet link"}
                      </Button>
                    </div>
                  ) : null}

                  {(!isSheetLinked || showSetup) && (
                    <div className="space-y-2 rounded-md border border-border/60 bg-background/60 p-2.5">
                      <p className="text-[10px] font-semibold text-foreground">Link Google Sheet</p>
                      {data.google_sheets_configured ? (
                        <>
                          <p className="text-[9px] leading-relaxed">
                            Share your spreadsheet with{" "}
                            <span className="font-medium text-foreground">
                              {data.google_service_account_email}
                            </span>{" "}
                            as <strong>Editor</strong>, then paste the sheet URL below.
                          </p>
                          <div className="space-y-1">
                            <label className="text-[9px] font-medium text-foreground">Google Sheet URL</label>
                            <Input
                              value={googleUrl}
                              onChange={(e) => setGoogleUrl(e.target.value)}
                              placeholder="https://docs.google.com/spreadsheets/d/..."
                              className="h-8 text-[10px]"
                            />
                          </div>
                          <Button
                            size="sm"
                            className="h-8 text-[10px]"
                            onClick={handleLinkGoogle}
                            disabled={linkingGoogle || !googleUrl.trim()}
                          >
                            <Link2 className={cn("h-3 w-3 mr-1", linkingGoogle && "animate-pulse")} />
                            {linkingGoogle ? "Linking & syncing…" : "Link & sync now"}
                          </Button>
                        </>
                      ) : (
                        <p className="text-[9px] leading-relaxed">
                          Add your service account JSON path to{" "}
                          <code className="bg-muted px-0.5 rounded">backend/.env</code>:
                          <br />
                          <code className="text-[8px]">GOOGLE_SERVICE_ACCOUNT_FILE=secrets/your-key.json</code>
                          <br />
                          Restart the backend, share the sheet with the service account email, then refresh this page.
                        </p>
                      )}
                    </div>
                  )}
                  {data.google_sync_error && (
                    <p className="text-destructive w-full text-[9px]">{data.google_sync_error}</p>
                  )}
                </div>
              </CardContent>
            </Card>

            {rows.length === 0 ? (
              <EmptyState
                title="No sprint tickets yet"
                description={`Move tickets to "${data.section}" in Asana. Auto-sync refreshes all projects and sprint sheets every ${integrationStatus?.auto_sync_interval_minutes ?? 15} minutes.`}
              />
            ) : (
              <div className="space-y-4">
                <Card className="border-primary/30">
                  <CardContent className="py-3 space-y-2">
                    <p className="text-sm font-medium">Sprint board ({displayRows.length})</p>
                    <p className="text-[10px] text-muted-foreground">
                      Top = Done / furthest along (Testing Pre-Prod, Build in Pre-Prod, …). Bottom =
                      Prioritized (not started yet). Priority column from Asana when set.
                    </p>
                    <SprintSheetTable tableRows={displayRows} onUpdateRow={updateRow} />
                  </CardContent>
                </Card>
              </div>
            )}
          </>
        )}
      </div>
    </PageLayout>
  );
}
