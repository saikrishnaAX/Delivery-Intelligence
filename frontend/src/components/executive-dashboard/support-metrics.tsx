import { TicketPlus, TicketCheck, FolderOpen, AlertTriangle, CheckCircle2 } from "lucide-react";
import { DrilldownMetricCard } from "@/components/drilldown-metric-card";
import type { ExecutiveMetrics } from "@/types";

export function SupportMetrics({ metrics }: { metrics: ExecutiveMetrics }) {
  const label = metrics.project_type === "bosch" ? "Bosch partner queue" : "Support queue";
  return (
    <div className="space-y-2">
      <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
      <p className="text-[10px] text-muted-foreground leading-relaxed">
        Today&apos;s metrics use IST calendar day. Date range applies to &quot;Closed in range&quot; only.
      </p>
      <div className="grid gap-2 grid-cols-2 lg:grid-cols-5">
        <DrilldownMetricCard id="exec-created-today" title="Created today" value={metrics.tickets_created_today} icon={TicketPlus} drilldownMetric="created_today" personMode="creator" />
        <DrilldownMetricCard title="Closed today" value={metrics.tickets_closed_today} icon={TicketCheck} variant="success" drilldownMetric="closed_today" personMode="assignee" />
        <DrilldownMetricCard id="exec-open-tickets" title="Open" value={metrics.open_tickets} icon={FolderOpen} drilldownMetric="open" personMode="assignee" />
        <DrilldownMetricCard title="Closed in range" value={metrics.total_closed} icon={CheckCircle2} variant="success" drilldownMetric="closed_range" ticketTotal={metrics.total_closed} personMode="assignee" />
        <DrilldownMetricCard id="exec-escalations" title="Escalations" value={metrics.escalations_count} icon={AlertTriangle} variant="destructive" drilldownMetric="escalations" subtitle="Open 7+ days" personMode="assignee" />
      </div>
    </div>
  );
}
