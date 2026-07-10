import { ShieldAlert } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ExecutionBoardData } from "@/types";
import { OperationalStatusLight } from "./operational-status-light";
import { TodayTasksPanel } from "./today-tasks-panel";
import { WorkshopStatusPanel } from "./workshop-status-panel";
import { SupportMetrics } from "./support-metrics";
import { SprintMetrics } from "./sprint-metrics";
import { LazyExecutiveAnalytics } from "./lazy-executive-analytics";

export function ExecutionTabContent({ display }: { display: ExecutionBoardData }) {
  const metrics = display.metrics;
  const isSprint = metrics.project_type === "sprint";

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden border-border/80">
        <CardContent className="py-5 px-4 sm:px-6">
          <div className="flex flex-col lg:flex-row items-center gap-6 lg:gap-10">
            <OperationalStatusLight status={display.operational_status} />
            <div className="flex-1 text-center lg:text-left space-y-3 min-w-0">
              <div>
                <p className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground font-medium">
                  Operational status
                </p>
                <h2 className="text-xl sm:text-2xl font-semibold tracking-tight mt-1">
                  {display.status_headline}
                </h2>
                <p className="text-sm text-muted-foreground mt-1.5 leading-relaxed max-w-xl">
                  {display.status_detail}
                </p>
              </div>
              <div className="flex flex-wrap justify-center lg:justify-start gap-2">
                <Badge
                  variant={display.show_stopper_count > 0 ? "destructive" : "secondary"}
                  className="text-[10px] gap-1"
                >
                  <ShieldAlert className="h-3 w-3" />
                  {display.show_stopper_count} show-stopper{display.show_stopper_count !== 1 ? "s" : ""}
                </Badge>
                {display.workshops_with_show_stoppers > 0 && (
                  <Badge variant="outline" className="text-[10px]">
                    {display.workshops_with_show_stoppers} workshop{display.workshops_with_show_stoppers !== 1 ? "s" : ""} affected
                  </Badge>
                )}
                {display.workshops_at_risk > 0 && (
                  <Badge variant="outline" className="text-[10px] text-amber-600 dark:text-amber-400 border-amber-500/30">
                    {display.workshops_at_risk} at risk
                  </Badge>
                )}
                <Badge variant="outline" className="text-[10px] text-emerald-600 dark:text-emerald-400 border-emerald-500/30" title="Workshops with open tickets, no blockers, and fewer than 3 open">
                  {display.workshops_healthy} low-risk
                </Badge>
              </div>
            </div>
            <div className="shrink-0 text-center rounded-xl border border-primary/20 bg-primary/5 px-6 py-4 min-w-[120px]">
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">Today</p>
              <p className="text-4xl font-bold tabular-nums text-primary mt-1">{display.today_task_count}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                focus area{display.today_task_count !== 1 ? "s" : ""}
                {display.today_item_count > display.today_task_count && (
                  <> · {display.today_item_count} items</>
                )}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <TodayTasksPanel
          tasks={display.today_tasks}
          taskCount={display.today_task_count}
          itemCount={display.today_item_count}
        />
        <WorkshopStatusPanel
          workshops={display.workshop_statuses}
          healthyCount={display.workshops_healthy}
          showStopperWorkshops={display.workshops_with_show_stoppers}
          hiddenCount={display.workshops_hidden_count ?? 0}
        />
      </div>

      {isSprint ? <SprintMetrics metrics={metrics} /> : <SupportMetrics metrics={metrics} />}

      <LazyExecutiveAnalytics />
    </div>
  );
}
