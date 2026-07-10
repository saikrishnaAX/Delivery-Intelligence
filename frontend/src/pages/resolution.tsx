import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  Bug,
  Calendar,
  Clock,
  Minus,
  RotateCcw,
  TicketCheck,
  TicketPlus,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { EmptyState } from "@/components/empty-state";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useProject } from "@/hooks/use-project";
import { readCache, writeCache, buildScope } from "@/lib/data-cache";
import { refreshCached } from "@/lib/fetch-with-cache";
import type { MonthlyProgressData, MonthlyProgressMonth } from "@/types";
import { cn, formatHours, formatPercent } from "@/lib/utils";

function DeltaBadge({
  value,
  pct,
  invert = false,
}: {
  value?: number | null;
  pct?: number | null;
  invert?: boolean;
}) {
  if (value == null && pct == null) return <span className="text-[9px] text-muted-foreground">—</span>;
  const v = value ?? 0;
  const good = invert ? v < 0 : v > 0;
  const bad = invert ? v > 0 : v < 0;
  const Icon = v > 0 ? ArrowUpRight : v < 0 ? ArrowDownRight : Minus;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-[9px] font-medium tabular-nums",
        good && "text-emerald-600 dark:text-emerald-400",
        bad && "text-amber-600 dark:text-amber-400",
        v === 0 && "text-muted-foreground"
      )}
    >
      <Icon className="h-2.5 w-2.5" />
      {v > 0 ? `+${v}` : v}
      {pct != null && <span className="opacity-70">({pct > 0 ? "+" : ""}{pct}%)</span>}
    </span>
  );
}

function MonthMetric({
  label,
  value,
  sub,
  delta,
  deltaPct,
  invertDelta,
}: {
  label: string;
  value: string | number;
  sub?: string;
  delta?: number | null;
  deltaPct?: number | null;
  invertDelta?: boolean;
}) {
  return (
    <div className="rounded-md border border-border/60 bg-card px-2.5 py-2 space-y-1">
      <p className="text-[9px] text-muted-foreground font-medium uppercase tracking-wide">{label}</p>
      <p className="text-sm font-semibold tabular-nums">{value}</p>
      <div className="flex items-center justify-between gap-1 min-h-[14px]">
        {sub ? <span className="text-[9px] text-muted-foreground">{sub}</span> : <span />}
        <DeltaBadge value={delta} pct={deltaPct} invert={invertDelta} />
      </div>
    </div>
  );
}

function MonthColumn({ month }: { month: MonthlyProgressMonth }) {
  return (
    <div
      className={cn(
        "flex flex-col min-w-[210px] max-w-[210px] shrink-0 rounded-lg border bg-muted/20",
        month.is_current_month ? "border-primary ring-1 ring-primary/30" : "border-border/70"
      )}
    >
      <div
        className={cn(
          "px-3 py-2 border-b border-border/60 rounded-t-lg",
          month.is_current_month ? "bg-primary/10" : "bg-muted/40"
        )}
      >
        <p className="text-xs font-semibold">{month.month_label}</p>
        {month.is_current_month && (
          <p className="text-[9px] text-primary font-medium">Current month</p>
        )}
        {month.insight && (
          <p className="text-[9px] text-muted-foreground mt-1 leading-snug">{month.insight}</p>
        )}
      </div>
      <div className="p-2 space-y-2 flex-1">
        <MonthMetric
          label="Created"
          value={month.tickets_created}
          delta={month.created_vs_prev}
          deltaPct={month.created_vs_prev_pct}
        />
        <MonthMetric
          label="Closed"
          value={month.tickets_closed}
          delta={month.closed_vs_prev}
          deltaPct={month.closed_vs_prev_pct}
        />
        <MonthMetric
          label="Reopened"
          value={month.reopened_count}
          invertDelta
        />
        <MonthMetric
          label="Avg close (opened)"
          value={month.avg_resolution_hours != null ? formatHours(month.avg_resolution_hours) : "—"}
          sub={
            month.median_resolution_hours != null
              ? `Median ${formatHours(month.median_resolution_hours)}`
              : "Tickets created this month"
          }
          delta={month.avg_resolution_vs_prev}
          invertDelta
        />
        <MonthMetric
          label="Bugs created"
          value={month.bugs_created}
          sub={`${month.bugs_closed} closed`}
          delta={month.bugs_vs_prev}
          deltaPct={month.bugs_vs_prev_pct}
          invertDelta
        />
        <div className="rounded-md border border-border/40 bg-background/50 px-2 py-1.5 text-[9px] text-muted-foreground">
          <span className="font-medium text-foreground">Net flow: </span>
          {month.net_flow > 0 ? (
            <span className="text-emerald-600">−{month.net_flow} backlog</span>
          ) : month.net_flow < 0 ? (
            <span className="text-amber-600">+{Math.abs(month.net_flow)} backlog</span>
          ) : (
            <span>balanced</span>
          )}
          {month.sla_compliance_rate != null && (
            <span className="block mt-0.5">SLA {formatPercent(month.sla_compliance_rate)}</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ResolutionPage() {
  const { projectGid, cacheVersion } = useProject();
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [data, setData] = useState<MonthlyProgressData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cacheScope = buildScope([projectGid, String(year)]);

  const yearOptions = useMemo(() => {
    const start = 2024;
    return Array.from({ length: currentYear - start + 1 }, (_, i) => currentYear - i);
  }, [currentYear]);

  const load = useCallback(() => {
    if (!projectGid) {
      setData(null);
      return;
    }
    const cached = readCache<MonthlyProgressData>("monthly-progress", cacheScope);
    if (cached) setData(cached);
    else setLoading(true);
    setError(null);
    void refreshCached(
      "monthly-progress",
      cacheScope,
      () => api.getMonthlyProgress(projectGid, year),
      setData
    ).catch((err) => {
      if (!readCache<MonthlyProgressData>("monthly-progress", cacheScope)) {
        setError(err instanceof Error ? err.message : "Failed to load monthly progress");
        setData(null);
      }
    }).finally(() => setLoading(false));
  }, [projectGid, year, cacheScope]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (cacheVersion === 0 || !projectGid) return;
    void refreshCached(
      "monthly-progress",
      cacheScope,
      () => api.getMonthlyProgress(projectGid, year),
      setData
    );
  }, [cacheVersion, projectGid, year, cacheScope]);

  return (
    <PageLayout page="resolution">
      <Header
        title="Monthly Progress"
        description="Month-by-month delivery trends — compare created, closed, bugs, and close time"
      />
      <div className="page-content space-y-3">
        <p className="text-[10px] text-muted-foreground rounded-md border border-border/60 bg-muted/20 px-3 py-2">
          Month-by-month trends use the <span className="font-medium text-foreground">calendar year</span> selector below — not the global date range in the header.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="rounded-md border border-border/80 bg-background px-2.5 py-1.5 text-xs font-medium"
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </div>
          {data?.project_name && (
            <span className="text-[10px] text-muted-foreground">
              Project: <span className="text-foreground font-medium">{data.project_name}</span>
            </span>
          )}
        </div>

        {!projectGid && (
          <EmptyState title="Select a project" description="Choose a project to see monthly ticket progress." />
        )}

        {error && (
          <Card className="border-destructive/30">
            <CardContent className="py-2 text-[11px] text-destructive">{error}</CardContent>
          </Card>
        )}

        {projectGid && loading && !data && <LoadingState />}

        {data && (
          <>
            <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
              <MetricCard title={`${year} created`} value={data.year_created} icon={TicketPlus} />
              <MetricCard title={`${year} closed`} value={data.year_closed} icon={TicketCheck} variant="success" />
              <MetricCard title="Bugs created" value={data.year_bugs_created} icon={Bug} />
              <MetricCard title="Reopened" value={data.year_reopened} icon={RotateCcw} variant="warning" />
            </div>

            {data.highlights.length > 0 && (
              <Card className="border-primary/20 bg-primary/5">
                <CardContent className="py-2.5 space-y-1">
                  <p className="text-[10px] font-semibold text-foreground">Month-over-month insights</p>
                  {data.highlights.map((h) => (
                    <p key={h} className="text-[10px] text-muted-foreground leading-snug">
                      {h}
                    </p>
                  ))}
                </CardContent>
              </Card>
            )}

            {data.months.length === 0 ? (
              <EmptyState title="No data for this year" description="Sync Asana to populate ticket history." />
            ) : (
              <div className="overflow-x-auto pb-2">
                <div className="flex gap-3 min-w-min">
                  {data.months.map((month) => (
                    <MonthColumn key={month.month} month={month} />
                  ))}
                </div>
              </div>
            )}

            <p className="text-[9px] text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Created/closed use ticket open and close dates. Avg close time uses only tickets opened that month.
            </p>
          </>
        )}
      </div>
    </PageLayout>
  );
}
