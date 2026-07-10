import { Layers, Archive, CheckCircle2, Rocket } from "lucide-react";
import { DrilldownMetricCard } from "@/components/drilldown-metric-card";
import type { ExecutiveMetrics } from "@/types";

export function SprintMetrics({ metrics }: { metrics: ExecutiveMetrics }) {
  const doneStage = metrics.pipeline_stages.find((s) => s.stage === "Done");
  const stageCards = metrics.pipeline_stages.filter((s) => s.stage !== "Done");
  return (
    <div className="space-y-2">
      <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Sprint pipeline</p>
      <p className="text-[10px] text-muted-foreground leading-relaxed">
        Live pipeline snapshot. Date range in the header does not change these counts.
      </p>
      <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
        <DrilldownMetricCard title="In pipeline" value={metrics.in_pipeline_count || metrics.open_tickets} icon={Layers} drilldownMetric="in_pipeline" personMode="assignee" />
        <DrilldownMetricCard title="Backlog" value={metrics.backlog_count} icon={Archive} drilldownMetric="backlog" personMode="assignee" />
        <DrilldownMetricCard title="Done" value={doneStage?.count ?? 0} icon={CheckCircle2} variant="success" drilldownMetric="pipeline" drilldownStage="Done" personMode="assignee" />
        <DrilldownMetricCard title="Released" value={metrics.released_count} icon={Rocket} variant="success" drilldownMetric="released" personMode="assignee" />
      </div>
      {stageCards.length > 0 && (
        <div className="grid gap-2 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4">
          {stageCards.map((stage) => (
            <DrilldownMetricCard
              key={stage.stage}
              title={stage.stage}
              value={stage.count}
              icon={Layers}
              drilldownMetric="pipeline"
              drilldownStage={stage.stage}
              personMode="assignee"
            />
          ))}
        </div>
      )}
    </div>
  );
}
