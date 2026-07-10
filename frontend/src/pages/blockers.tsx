import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useProjectApi } from "@/hooks/use-project-api";
import { api } from "@/lib/api";
import { priorityColor } from "@/lib/utils";
import { AlertOctagon, Clock, Users, ExternalLink } from "lucide-react";

export default function BlockersPage() {
  const { data, loading, error, refetch } = useProjectApi("blockers-v2", (gid, from, to) =>
    api.getBlockers(gid, from, to)
  );

  if (loading && !data) {
    return (
      <>
        <Header title="Workflow Blockers" description="Critical business-stopping issues" />
        <div className="page-content"><LoadingState /></div>
      </>
    );
  }

  if (error && !data) {
    return (
      <>
        <Header title="Workflow Blockers" description="Critical business-stopping issues" />
        <div className="page-content">
          <ErrorState message={error} onRetry={() => void refetch()} />
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Header title="Workflow Blockers" description="Critical business-stopping issues" />
        <div className="page-content">
          <ErrorState message="Could not load blockers." onRetry={() => void refetch()} />
        </div>
      </>
    );
  }

  return (
    <PageLayout page="blockers">
      <Header title="Workflow Blockers" description="Critical business-stopping issues" />
      <div className="page-content">
        <div className="grid gap-2 grid-cols-3">
          <MetricCard title="Active" value={data.total_blockers} icon={AlertOctagon} variant="destructive" />
          <MetricCard title="Avg days" value={data.avg_days_blocked} icon={Clock} variant="warning" />
          <MetricCard title="Workshops" value={data.affected_customers} icon={Users} />
        </div>

        {data.blockers.length === 0 ? (
          <EmptyState title="No blockers" description="All critical blockers resolved." />
        ) : (
          <div className="space-y-2">
            {data.blockers.map((blocker) => (
              <Card key={blocker.id} className="border-destructive/15">
                <CardContent className="py-2.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        {blocker.asana_url ? (
                          <a
                            href={blocker.asana_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs font-medium hover:underline"
                          >
                            {blocker.title}
                          </a>
                        ) : (
                          <h4 className="text-xs font-medium">{blocker.title}</h4>
                        )}
                        <span className={`inline-flex rounded border px-1.5 py-0 text-[9px] font-medium ${priorityColor(blocker.priority)}`}>
                          {blocker.priority}
                        </span>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">{blocker.impact_summary}</p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {blocker.module_name && <Badge variant="outline" className="text-[9px] px-1.5 py-0">{blocker.module_name}</Badge>}
                        {blocker.customer_name && <Badge variant="outline" className="text-[9px] px-1.5 py-0">{blocker.customer_name}</Badge>}
                      </div>
                    </div>
                    <div className="text-right shrink-0 flex flex-col items-end">
                      <p className="text-base font-semibold text-destructive tabular-nums">{blocker.days_open}</p>
                      <p className="text-[9px] text-muted-foreground">days</p>
                      {blocker.asana_url && (
                        <a
                          href={blocker.asana_url}
                          target="_blank"
                          rel="noreferrer"
                          title="Open in Asana"
                          className="mt-1 text-muted-foreground/50 hover:text-muted-foreground"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </PageLayout>
  );
}
