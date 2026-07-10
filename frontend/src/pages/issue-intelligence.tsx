import { useCallback, useEffect, useMemo, useState } from "react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { EmptyState } from "@/components/empty-state";
import { RecurringIssueDetailPanel } from "@/components/recurring-issue-detail";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useProjectApi } from "@/hooks/use-project-api";
import { useProject } from "@/hooks/use-project";
import { api } from "@/lib/api";
import { buildScope, invalidateCache } from "@/lib/data-cache";
import { cn } from "@/lib/utils";
import type { RecurringIssueDetail, RecurringIssueSummary } from "@/types";
import { useNotifyHelpers } from "@/hooks/use-notify";
import {
  useIssueIntelligenceTracker,
  ISSUE_INTELLIGENCE_DONE_EVENT,
} from "@/hooks/use-issue-intelligence-tracker";
import {
  AlertTriangle, ArrowRight, Brain, ChevronRight, Loader2,
  Sparkles, TrendingUp, Wrench,
} from "lucide-react";

type FilterTab = "all" | "product_bug" | "increasing" | "has_fix" | "open";

const severityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function TrendIndicator({ trend }: { trend: string }) {
  const t = trend.toLowerCase();
  if (t === "increasing") return <span className="text-destructive text-[10px] font-medium">↑ Increasing</span>;
  if (t === "decreasing") return <span className="text-emerald-600 text-[10px] font-medium">↓ Decreasing</span>;
  return <span className="text-muted-foreground text-[10px]">→ Stable</span>;
}

function IssueRow({
  issue,
  onSelect,
  selected,
}: {
  issue: RecurringIssueSummary;
  onSelect: () => void;
  selected: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full text-left rounded-lg border px-3 py-2.5 transition-colors",
        "hover:bg-muted/40 hover:border-primary/30",
        selected ? "border-primary/50 bg-primary/5" : "border-border/60 bg-card/50"
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-xs font-semibold leading-snug">{issue.issue_name}</h3>
            {issue.severity === "critical" && (
              <Badge variant="destructive" className="text-[7px] px-1">Critical</Badge>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground line-clamp-1">
            {issue.executive_summary || issue.business_impact}
          </p>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[9px] text-muted-foreground">
            <span className="tabular-nums font-medium text-foreground">{issue.ticket_count} tickets</span>
            <span>{issue.open_count} open</span>
            <span>{issue.workshop_count} workshops</span>
            <TrendIndicator trend={issue.trend} />
            {issue.affected_modules.slice(0, 2).map((m) => (
              <Badge key={m} variant="outline" className="text-[7px] px-1 py-0">{m}</Badge>
            ))}
          </div>
        </div>
        <div className="shrink-0 flex flex-col items-end gap-1">
          <Badge variant="outline" className="text-[8px] tabular-nums">
            {Math.round((issue.confidence ?? 0) * 100)}%
          </Badge>
          {issue.developer_resolution_available ? (
            <Badge variant="default" className="text-[7px] bg-emerald-700">Fix documented</Badge>
          ) : issue.fix_status === "open" ? (
            <Badge variant="destructive" className="text-[7px]">Needs fix</Badge>
          ) : null}
          <ChevronRight className="h-4 w-4 text-muted-foreground mt-1" />
        </div>
      </div>
    </button>
  );
}

function analysisPhase(job: { tickets_processed: number; tickets_total: number; issues_found: number } | null | undefined): string {
  if (!job || job.tickets_total <= 0) return "Starting analysis…";
  const pct = job.tickets_processed / job.tickets_total;
  if (pct < 0.2) return "Loading ticket history…";
  if (pct < 0.6) return "Grouping by engineering fix (not keywords)…";
  if (job.issues_found > 0) return `Building intelligence for ${job.issues_found} recurring issue${job.issues_found !== 1 ? "s" : ""}…`;
  return "Identifying recurring product issues…";
}

export default function IssueIntelligencePage() {
  const { projectGid, dateFrom, dateTo } = useProject();
  const { success, error: notifyError } = useNotifyHelpers();
  const { trackJob, activeJob, isAnalyzing, dismissAnalysis } = useIssueIntelligenceTracker();
  const scope = buildScope([projectGid, dateFrom, dateTo]);

  const { data, loading, error, refetch } = useProjectApi(
    "issue-intelligence",
    (gid, from, to) => api.getIssueIntelligence(gid, from, to)
  );

  const [filter, setFilter] = useState<FilterTab>("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RecurringIssueDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    const onDone = () => {
      invalidateCache("issue-intelligence", scope);
      void refetch();
    };
    window.addEventListener(ISSUE_INTELLIGENCE_DONE_EVENT, onDone);
    return () => window.removeEventListener(ISSUE_INTELLIGENCE_DONE_EVENT, onDone);
  }, [refetch, scope]);

  // Resume tracking only for a genuinely in-flight job on this project
  useEffect(() => {
    const job = data?.active_job;
    if (!projectGid || !job?.id) return;
    if (job.status !== "pending" && job.status !== "running") return;
    trackJob(job.id, projectGid, job as import("@/types").IssueIntelligenceJobData);
  }, [data?.active_job?.id, data?.active_job?.status, projectGid, trackJob]);

  const filteredIssues = useMemo(() => {
    if (!data?.issues) return [];
    let list = [...data.issues];
    if (filter === "product_bug") list = list.filter((i) => i.issue_type === "product_bug");
    if (filter === "increasing") list = list.filter((i) => i.trend === "increasing");
    if (filter === "has_fix") list = list.filter((i) => i.developer_resolution_available);
    if (filter === "open") list = list.filter((i) => i.open_count > 0);
    return list.sort((a, b) => {
      const sev = (severityOrder[a.severity] ?? 9) - (severityOrder[b.severity] ?? 9);
      if (sev !== 0) return sev;
      return b.priority_score - a.priority_score;
    });
  }, [data?.issues, filter]);

  const openIssue = useCallback(async (id: number) => {
    setSelectedId(id);
    setDetailLoading(true);
    try {
      setDetail(await api.getRecurringIssueDetail(id));
    } catch {
      notifyError("Could not load issue", "Try again in a moment.");
      setSelectedId(null);
    } finally {
      setDetailLoading(false);
    }
  }, [notifyError]);

  const startAnalysis = async () => {
    if (!projectGid || isAnalyzing) return;
    setStarting(true);
    try {
      const job = await api.startIssueIntelligenceAnalysis(projectGid, dateFrom, dateTo);
      trackJob(job.id, projectGid, job);
      if (job.status === "completed") {
        invalidateCache("issue-intelligence", scope);
        await refetch();
        success("Analysis complete", `${job.issues_found} recurring issues found.`);
      }
    } catch (err) {
      notifyError(
        "Analysis failed",
        err instanceof Error ? err.message : "Could not analyse ticket history."
      );
    } finally {
      setStarting(false);
    }
  };

  const job = activeJob ?? data?.active_job;
  const analyzing = isAnalyzing || starting || job?.status === "pending" || job?.status === "running";
  const progressPct =
    job && job.tickets_total > 0
      ? Math.min(99, Math.max(3, Math.round((job.tickets_processed / job.tickets_total) * 100)))
      : analyzing ? 3 : 0;
  const phaseLabel = analysisPhase(job ?? undefined);

  const hasResults = (data?.recurring_issues_found ?? 0) > 0;
  const ticketsInRange = data?.insights?.tickets_in_range ?? 0;

  if (loading && !data) {
    return (
      <>
        <Header title="Issue Intelligence" description="Recurring product issues from ticket history" />
        <div className="page-content"><LoadingState /></div>
      </>
    );
  }

  if (error && !data) {
    return (
      <>
        <Header title="Issue Intelligence" description="Recurring product issues from ticket history" />
        <div className="page-content space-y-4">
          <EmptyState title="Could not load issue intelligence" description={error} />
          <div className="flex justify-center">
            <Button size="sm" onClick={() => void refetch()}>Retry</Button>
          </div>
        </div>
      </>
    );
  }

  return (
    <PageLayout
      page="issue-intelligence"
      pageInfo={{
        title: "Issue Intelligence",
        description:
          "AI analyses your ticket history and groups issues by engineering fix — not keywords. " +
          "Cursor refresh runs daily at 5 PM IST so urgent issues stay current.",
      }}
    >
      <Header
        title="Issue Intelligence"
        description="What recurring product problems should engineering fix first?"
      />

      <div className="page-content space-y-4">
        {/* Hero stats */}
        <div className="grid gap-3 sm:grid-cols-3">
          <Card className="border-border/60 bg-gradient-to-br from-card to-muted/20">
            <CardContent className="py-3">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Tickets in range</p>
              <p className="text-2xl font-bold tabular-nums mt-0.5">{ticketsInRange}</p>
              {data?.last_analyzed_at && (
                <p className="text-[9px] text-muted-foreground mt-1">
                  Last analysed {new Date(data.last_analyzed_at).toLocaleString()}
                </p>
              )}
            </CardContent>
          </Card>
          <Card className="border-primary/20 bg-primary/5">
            <CardContent className="py-3">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <Brain className="h-3 w-3" /> Recurring issues found
              </p>
              <p className="text-2xl font-bold tabular-nums mt-0.5 text-primary">
                {data?.recurring_issues_found ?? 0}
              </p>
              <p className="text-[9px] text-muted-foreground mt-1">
                {data?.product_defects_found ?? 0} product defects
              </p>
            </CardContent>
          </Card>
          <Card className="border-border/60">
            <CardContent className="py-3 flex flex-col justify-between h-full">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Analyse ticket history</p>
              <Button
                className="mt-2 h-9 text-xs w-full"
                onClick={startAnalysis}
                disabled={analyzing || starting || !projectGid}
              >
                {analyzing || starting ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                )}
                {analyzing ? "Analysing…" : hasResults ? "Re-analyse tickets" : "Analyse ticket history"}
              </Button>
              <p className="text-[8px] text-muted-foreground mt-1.5">
                Groups by engineering fix · Cursor enrich daily 5 PM IST
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Progress */}
        {analyzing && (
          <Card className="border-primary/40 bg-primary/5 overflow-hidden relative">
            <div className="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/10 to-primary/0 animate-analysis-shimmer pointer-events-none" />
            <CardContent className="py-4 space-y-3 relative">
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
                  {phaseLabel}
                </p>
                <Badge variant="outline" className="text-[10px] tabular-nums shrink-0">
                  {progressPct}%
                </Badge>
              </div>
              <div className="h-2.5 rounded-full bg-muted/80 overflow-hidden shadow-inner">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-primary via-orange-400 to-primary bg-[length:200%_100%] animate-analysis-bar transition-all duration-700 ease-out"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted-foreground">
                <span>
                  {job && job.tickets_total > 0
                    ? `${job.tickets_processed} / ${job.tickets_total} tickets`
                    : "Preparing ticket batch…"}
                  {job && job.issues_found > 0 && (
                    <span className="text-primary font-medium">
                      {" "}· {job.issues_found} issue{job.issues_found !== 1 ? "s" : ""} found so far
                    </span>
                  )}
                </span>
                <div className="flex items-center gap-2">
                  <span className="hidden sm:inline">Runs in background — leave this page if needed</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[9px] px-2"
                    onClick={dismissAnalysis}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Insights strip */}
        {hasResults && data?.insights && (
          <div className="grid gap-2 sm:grid-cols-3">
            {data.insights.top_priority_issues.slice(0, 1).map((name) => (
              <Card key={name} className="border-destructive/20 bg-destructive/5 sm:col-span-1">
                <CardContent className="py-2 px-3">
                  <p className="text-[9px] text-muted-foreground flex items-center gap-1">
                    <Wrench className="h-3 w-3" /> Fix first
                  </p>
                  <p className="text-[10px] font-medium leading-snug mt-0.5 line-clamp-2">{name}</p>
                </CardContent>
              </Card>
            ))}
            <Card className="border-border/60">
              <CardContent className="py-2 px-3">
                <p className="text-[9px] text-muted-foreground flex items-center gap-1">
                  <TrendingUp className="h-3 w-3" /> Increasing issues
                </p>
                <p className="text-lg font-semibold tabular-nums">{data.insights.increasing_issues_count}</p>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="py-2 px-3">
                <p className="text-[9px] text-muted-foreground flex items-center gap-1">
                  <AlertTriangle className="h-3 w-3" /> Unstable modules
                </p>
                <p className="text-[10px] font-medium mt-0.5 line-clamp-2">
                  {data.insights.unstable_modules.slice(0, 3).map((m) => m.module).join(", ") || "—"}
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Empty state — no analysis yet */}
        {!hasResults && !analyzing && (
          <div className="space-y-4">
            <EmptyState
              title="No recurring issues identified yet"
              description={
                ticketsInRange > 0
                  ? `${ticketsInRange} tickets available. Run analysis to discover recurring product problems grouped by engineering fix.`
                  : "Sync tickets from Asana first, then analyse ticket history."
              }
            />
            {projectGid && ticketsInRange > 0 && (
              <div className="flex justify-center">
                <Button onClick={startAnalysis} disabled={starting}>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Analyse {ticketsInRange} tickets
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Issue list */}
        {hasResults && (
          <>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex gap-1 flex-wrap">
                {(
                  [
                    ["all", "All issues"],
                    ["product_bug", "Product bugs"],
                    ["increasing", "Increasing"],
                    ["open", "Open tickets"],
                    ["has_fix", "Fix documented"],
                  ] as const
                ).map(([key, label]) => (
                  <Button
                    key={key}
                    variant={filter === key ? "default" : "outline"}
                    size="sm"
                    className="h-7 text-[10px]"
                    onClick={() => setFilter(key)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground">
                {filteredIssues.length} issue{filteredIssues.length !== 1 ? "s" : ""} · sorted by priority
              </p>
            </div>

            <div className="space-y-1.5">
              {filteredIssues.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4 text-center">No issues match this filter.</p>
              ) : (
                filteredIssues.map((issue) => (
                  <IssueRow
                    key={issue.id}
                    issue={issue}
                    selected={selectedId === issue.id}
                    onSelect={() => void openIssue(issue.id)}
                  />
                ))
              )}
            </div>

            <p className="text-[9px] text-muted-foreground flex items-center gap-1">
              <ArrowRight className="h-3 w-3" />
              Click an issue to view evidence, root cause, and regression insights
            </p>
          </>
        )}
      </div>

      {/* Detail panel */}
      {selectedId && (
        <>
          <div
            className="fixed inset-0 z-40 bg-background/60 backdrop-blur-sm"
            onClick={() => { setSelectedId(null); setDetail(null); }}
            aria-hidden
          />
          {detailLoading && !detail ? (
            <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl border-l bg-background flex items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : detail ? (
            <RecurringIssueDetailPanel
              issue={detail}
              onClose={() => { setSelectedId(null); setDetail(null); }}
            />
          ) : null}
        </>
      )}
    </PageLayout>
  );
}
