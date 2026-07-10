import { useState } from "react";
import { Download, TrendingUp } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useProjectApi } from "@/hooks/use-project-api";
import { useProject } from "@/hooks/use-project";
import { api } from "@/lib/api";

export default function ImpactPage() {
  const { projectGid, dateFrom, dateTo } = useProject();
  const { data, loading, error, refetch } = useProjectApi("impact", (gid, from, to) => api.getImpact(gid, from, to));
  const [exporting, setExporting] = useState(false);

  const onExport = async () => {
    setExporting(true);
    try {
      const blob = await api.downloadImpactCsv(projectGid, dateFrom, dateTo);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "impact_report.csv";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  if (loading && !data) {
    return (
      <>
        <Header title="My Impact" description="Measurable delivery productivity" />
        <div className="page-content"><LoadingState /></div>
      </>
    );
  }

  if (error && !data) {
    return (
      <>
        <Header title="My Impact" description="Measurable delivery productivity" />
        <div className="page-content">
          <ErrorState message={error} onRetry={() => void refetch()} />
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Header title="My Impact" description="Measurable delivery productivity" />
        <div className="page-content">
          <ErrorState message="No impact data available for this project." />
        </div>
      </>
    );
  }

  const isSprint = data.view_mode === "sprint";
  const itemsLabel = isSprint ? "Items released" : "Items closed";
  const avgLabel = isSprint ? "Avg days to release" : "Avg days to close";

  return (
    <PageLayout page="impact">
      <Header
        title="My Impact"
        description={
          isSprint
            ? "Sprint delivery — items and story points released in the selected window"
            : "Support delivery — closed tickets and workshops helped in the selected window"
        }
      />
      <div className="page-content space-y-3">
        <div className="flex justify-end">
          <Button variant="outline" size="sm" onClick={onExport} disabled={exporting}>
            <Download className="h-3.5 w-3.5 mr-1.5" />
            {exporting ? "Exporting…" : "Export CSV"}
          </Button>
        </div>

        <div className="grid gap-2 grid-cols-2 md:grid-cols-4">
          <MetricCard title={itemsLabel} value={data.items_released} icon={TrendingUp} />
          {isSprint ? (
            <MetricCard title="Points released" value={data.points_released} icon={TrendingUp} />
          ) : (
            <MetricCard title="Workshops helped" value={data.workshops_helped} icon={TrendingUp} />
          )}
          <MetricCard title="Support helped" value={data.support_people_helped} icon={TrendingUp} />
          <MetricCard title="Blockers cleared" value={data.blockers_cleared} icon={TrendingUp} />
          <MetricCard title="Release notes sent" value={data.release_notes_sent} icon={TrendingUp} />
          <MetricCard title="Follow-ups sent" value={data.followups_sent} icon={TrendingUp} />
          <MetricCard title="Cluster analyses" value={data.cluster_analyses_run} icon={TrendingUp} />
          <MetricCard title={avgLabel} value={data.avg_days_to_release ?? "—"} icon={TrendingUp} />
        </div>

        {!isSprint && data.top_workshops.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Workshops helped (closed tickets)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {data.top_workshops.map((w) => (
                <div key={w.name} className="flex justify-between text-xs gap-2">
                  <span className="truncate">{w.name}</span>
                  <Badge variant="secondary" className="text-[9px] shrink-0">{w.count}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {data.recent_activity.length > 0 && (
          <Card>
            <CardHeader><CardTitle>Recent activity</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {data.recent_activity.map((a) => (
                <div key={a.id} className="text-[10px] border-b border-border/40 pb-1.5 last:border-0">
                  <div className="flex gap-2">
                    <Badge variant="outline" className="text-[9px] px-1 py-0">{a.module}</Badge>
                    <span className="text-muted-foreground">{new Date(a.created_at).toLocaleDateString()}</span>
                  </div>
                  <p className="mt-0.5">{a.summary}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </PageLayout>
  );
}
