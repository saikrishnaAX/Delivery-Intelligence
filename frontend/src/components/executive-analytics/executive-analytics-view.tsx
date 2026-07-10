/**

 * Detailed engineering analytics — lives on Executive Dashboard tab, not CEO tab.

 */

import { useEffect, useRef, useState } from "react";

import {

  Activity, AlertTriangle, Brain, Building2, ChevronDown, ChevronRight, Gauge,

  LineChart, Target, TrendingDown, TrendingUp, Zap,

} from "lucide-react";

import { Badge } from "@/components/ui/badge";

import { AreaChart } from "@/components/charts/area-chart";

import { BarChart } from "@/components/charts/bar-chart";

import { useProject } from "@/hooks/use-project";

import { useProjectApi } from "@/hooks/use-project-api";

import { LoadingState } from "@/components/loading-state";

import { ErrorState } from "@/components/error-state";

import { StaleDataBanner } from "@/components/stale-data-banner";

import { api } from "@/lib/api";

import type { ExecutiveAnalyticsData, CEORecurringIssue } from "@/types";



// Slim analytics endpoint — avoids full CEO intelligence payload on Execution tab.
const EXEC_ANALYTICS_CACHE_KEY = "executive-analytics-v1";



function isExecutiveAnalyticsData(value: unknown): value is ExecutiveAnalyticsData {

  if (!value || typeof value !== "object") return false;

  const v = value as ExecutiveAnalyticsData;

  return Boolean(v.health_score && v.quality_trends?.windows && v.charts);

}



function trendIcon(trend: string) {

  if (trend === "up" || trend === "increasing") return <TrendingUp className="h-3 w-3 text-red-400" />;

  if (trend === "down" || trend === "decreasing") return <TrendingDown className="h-3 w-3 text-emerald-400" />;

  return null;

}



function RecurringRow({ ri }: { ri: CEORecurringIssue }) {

  const [open, setOpen] = useState(false);

  const detail = [ri.root_cause, ri.business_impact].filter(Boolean).join(" · ");

  return (

    <>

      <tr className="hover:bg-muted/20">

        <td className="py-2 pr-3">

          <button type="button" onClick={() => setOpen(!open)} className="flex gap-2 text-left w-full" title={ri.name}>

            {detail ? (open ? <ChevronDown className="h-3.5 w-3.5 shrink-0 mt-0.5" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 mt-0.5" />) : <span className="w-3.5" />}

            <span className="min-w-0">

              <p className="font-medium text-xs">{ri.name}</p>

              {!open && detail && <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">{detail}</p>}

            </span>

          </button>

        </td>

        <td className="py-2 px-2 text-right tabular-nums">{ri.ticket_count}</td>

        <td className="py-2 px-2 text-right tabular-nums">{ri.open_count}</td>

        <td className="py-2 px-2 capitalize">{ri.trend}{trendIcon(ri.trend)}</td>

        <td className="py-2 px-2">{ri.severity}</td>

      </tr>

      {open && detail && (

        <tr className="bg-muted/10">

          <td colSpan={5} className="px-4 py-2 text-xs text-muted-foreground">{detail}</td>

        </tr>

      )}

    </>

  );

}



function AnalyticsBody({ data }: { data: ExecutiveAnalyticsData }) {

  const w30 = data.quality_trends.windows.last_30d as Record<string, number>;

  const w90 = data.quality_trends.windows.last_90d as Record<string, number>;

  const w180 = data.quality_trends.windows.last_180d as Record<string, number>;

  const prod30 = data.engineering_productivity.last_30d as Record<string, number>;

  const complaints = data.customer_health.top_complaints ?? [];



  return (

    <div className="space-y-8 pt-4 border-t border-border/40">

      <p className="text-xs text-muted-foreground">

        Detailed trends for delivery managers. CEO tab shows the summary facts only.

        Date range in the header applies to this section.

      </p>



      <section>

        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><Gauge className="h-4 w-4" /> Engineering health</h3>

        <p className="text-2xl font-bold">{data.health_score.score}<span className="text-sm font-normal text-muted-foreground"> / 100 — {data.health_score.label}</span></p>

      </section>



      <section>

        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><LineChart className="h-4 w-4" /> Quality trends</h3>

        <div className="overflow-x-auto">

          <table className="w-full text-xs">

            <thead>

              <tr className="text-[10px] uppercase text-muted-foreground border-b">

                <th className="text-left py-2">Metric</th>

                <th className="text-right py-2 px-2">30d</th>

                <th className="text-right py-2 px-2">90d</th>

                <th className="text-right py-2">6mo</th>

              </tr>

            </thead>

            <tbody>

              {["bugs", "enhancements", "critical_bugs", "reopened"].map((k) => (

                <tr key={k} className="border-b border-border/20">

                  <td className="py-2 capitalize">{k.replace("_", " ")}</td>

                  <td className="py-2 px-2 text-right tabular-nums">{w30[k] ?? "—"}</td>

                  <td className="py-2 px-2 text-right tabular-nums">{w90[k] ?? "—"}</td>

                  <td className="py-2 text-right tabular-nums">{w180[k] ?? "—"}</td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

        <div className="mt-4 rounded-lg border p-3">

          <AreaChart

            data={data.charts.monthly_trends}

            xKey="month"

            areas={[

              { key: "bugs", name: "Bugs", color: "hsl(0 72% 55%)" },

              { key: "enhancements", name: "Enhancements", color: "hsl(160 60% 45%)" },

            ]}

            height={180}

          />

        </div>

      </section>



      <section id="exec-ai-impact">

        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2"><Brain className="h-4 w-4" /> AI period comparison</h3>

        <p className="text-[10px] text-muted-foreground mb-3">{data.ai_impact.note}</p>

        <BarChart

          data={data.charts.ai_comparison}

          xKey="metric"

          bars={[

            { key: "before", name: "Pre-AI", color: "hsl(220 10% 45%)" },

            { key: "after", name: "Post-AI", color: "hsl(160 60% 45%)" },

          ]}

          height={200}

        />

      </section>



      {data.post_ai_issue_nature && data.post_ai_issue_nature.total_bugs_created > 0 && (

        <section>

          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2"><AlertTriangle className="h-4 w-4" /> Post-AI defect themes</h3>

          <p className="text-xs text-muted-foreground mb-2">{data.post_ai_issue_nature.period} · {data.post_ai_issue_nature.total_bugs_created} bugs</p>

          <ul className="space-y-1">

            {data.post_ai_issue_nature.narrative_summary.map((s, i) => (

              <li key={i} className="text-xs text-foreground/85">· {s}</li>

            ))}

          </ul>

        </section>

      )}



      <section>

        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2"><Target className="h-4 w-4" /> Recurring product bugs</h3>

        {data.recurring_issues.length === 0 ? (

          <p className="text-xs text-muted-foreground">No recurring issues in this period.</p>

        ) : (

          <table className="w-full table-fixed text-xs">

            <thead>

              <tr className="text-[10px] uppercase text-muted-foreground border-b">

                <th className="text-left py-2 w-[50%]">Issue</th>

                <th className="text-right py-2">Tickets</th>

                <th className="text-right py-2">Open</th>

                <th className="text-left py-2">Trend</th>

                <th className="text-left py-2">Severity</th>

              </tr>

            </thead>

            <tbody className="divide-y divide-border/20">

              {data.recurring_issues.map((ri, i) => (

                <RecurringRow key={`${ri.name}-${i}`} ri={ri} />

              ))}

            </tbody>

          </table>

        )}

      </section>



      <section>

        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2"><Zap className="h-4 w-4" /> Productivity (30d)</h3>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">

          <div><span className="text-muted-foreground">Enhancements</span><p className="font-semibold text-lg">{prod30.enhancements ?? 0}</p></div>

          <div><span className="text-muted-foreground">Bugs</span><p className="font-semibold text-lg">{prod30.bugs ?? 0}</p></div>

          <div><span className="text-muted-foreground">Closed</span><p className="font-semibold text-lg">{prod30.closed ?? 0}</p></div>

          <div><span className="text-muted-foreground">Blocked</span><p className="font-semibold text-lg">{prod30.blocked ?? 0}</p></div>

        </div>

      </section>



      <section>

        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2"><Building2 className="h-4 w-4" /> Customer impact (90d)</h3>

        {complaints.length === 0 ? (

          <p className="text-xs text-muted-foreground">No customer complaints in the last 90 days.</p>

        ) : (

          <div className="flex flex-wrap gap-2">

            {complaints.map((c) => (

              <Badge key={c.category} variant="outline" className="text-[10px]">{c.category}: {c.count}</Badge>

            ))}

          </div>

        )}

      </section>



      <section>

        <h3 className="text-sm font-semibold mb-2 flex items-center gap-2"><Activity className="h-4 w-4" /> Delivery pipeline</h3>

        <p className="text-xs">Open pipeline: {data.delivery_intelligence.pipeline_open} · Jira open: {data.delivery_intelligence.jira_open}</p>

      </section>

    </div>

  );

}



export function ExecutiveAnalyticsView() {

  const { projectGid } = useProject();

  const { data, loading, error, stale, refetch } = useProjectApi(
    EXEC_ANALYTICS_CACHE_KEY,
    (gid, from, to) => api.getExecutiveAnalytics(gid, from, to)
  );

  const staleRefetchDone = useRef(false);



  useEffect(() => {

    if (data && !isExecutiveAnalyticsData(data) && !staleRefetchDone.current) {

      staleRefetchDone.current = true;

      void refetch();

    }

  }, [data, refetch]);



  if (!projectGid) return null;



  if ((loading && !data) || (data && !isExecutiveAnalyticsData(data))) {

    return <LoadingState rows={2} />;

  }



  if (error && !data) {

    return <ErrorState message={error} onRetry={() => void refetch()} />;

  }



  if (!data || !isExecutiveAnalyticsData(data)) {

    return (

      <ErrorState

        message="Could not load engineering analytics for this project."

        onRetry={() => void refetch()}

      />

    );

  }



  return (

    <div className="space-y-3">

      {stale && (

        <StaleDataBanner

          message="Showing cached analytics — live refresh failed."

          onRetry={() => void refetch()}

        />

      )}

      <AnalyticsBody data={data} />

    </div>

  );

}


