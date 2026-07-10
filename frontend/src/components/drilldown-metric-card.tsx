import { useState } from "react";
import { type LucideIcon } from "lucide-react";
import { cn, formatNumber } from "@/lib/utils";
import { TicketDetailModal, type TicketPersonMode } from "@/components/ticket-detail-modal";
import { useProject } from "@/hooks/use-project";
import { api } from "@/lib/api";
import type { ExecutiveTicketItem } from "@/types";

interface DrilldownMetricCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  variant?: "default" | "success" | "warning" | "destructive";
  tickets?: ExecutiveTicketItem[];
  ticketTotal?: number;
  drilldownMetric?: string;
  drilldownStage?: string;
  subtitle?: string;
  personMode?: TicketPersonMode;
  id?: string;
}

const variantStyles = {
  default: "text-primary",
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
};

export function DrilldownMetricCard({
  title,
  value,
  icon: Icon,
  variant = "default",
  tickets,
  ticketTotal,
  drilldownMetric,
  drilldownStage,
  subtitle,
  personMode = "creator",
  id,
}: DrilldownMetricCardProps) {
  const { projectGid, dateFrom, dateTo } = useProject();
  const [modalOpen, setModalOpen] = useState(false);
  const [loadedTickets, setLoadedTickets] = useState<ExecutiveTicketItem[] | null>(null);
  const [loadedTotal, setLoadedTotal] = useState<number | null>(null);
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const displayValue = typeof value === "number" ? formatNumber(value) : value;
  const clickable = tickets !== undefined || Boolean(drilldownMetric);
  const total = ticketTotal ?? loadedTotal ?? tickets?.length ?? (typeof value === "number" ? value : 0);
  const displayTickets = tickets ?? loadedTickets ?? [];
  const truncated = clickable && total > displayTickets.length;
  const clickHint =
    subtitle ??
    (fetching
      ? "Loading tickets…"
      : truncated
        ? `Showing ${displayTickets.length} of ${total} — click to view`
        : "Click to view tickets");

  const openModal = async () => {
    if (!clickable) return;
    setModalOpen(true);
    if (tickets !== undefined || !drilldownMetric || !projectGid) return;
    if (loadedTickets !== null) return;

    setFetching(true);
    setFetchError(null);
    try {
      const res = await api.getExecutionDrilldown(
        projectGid,
        drilldownMetric,
        dateFrom,
        dateTo,
        drilldownStage
      );
      setLoadedTickets(res.tickets);
      setLoadedTotal(res.total);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : "Could not load tickets");
    } finally {
      setFetching(false);
    }
  };

  return (
    <>
      <button
        id={id}
        type="button"
        onClick={() => void openModal()}
        disabled={!clickable}
        className={cn(
          "w-full rounded-md border border-border/80 bg-card px-3 py-2.5 text-left transition-colors",
          clickable && "hover:bg-muted/30 hover:border-primary/30 cursor-pointer",
          !clickable && "cursor-default"
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
            <p className={cn("text-lg font-semibold tabular-nums tracking-tight mt-0.5", variantStyles[variant])}>
              {displayValue}
            </p>
            {clickable && (
              <p className={cn("text-[9px] mt-0.5", fetchError ? "text-destructive" : "text-primary")}>
                {fetchError ?? clickHint}
              </p>
            )}
          </div>
          <Icon className={cn("h-3.5 w-3.5 shrink-0 opacity-40", variantStyles[variant])} />
        </div>
      </button>

      {clickable && (
        <TicketDetailModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          title={title}
          tickets={displayTickets}
          totalCount={truncated ? total : undefined}
          personMode={personMode}
          loading={fetching && displayTickets.length === 0}
        />
      )}
    </>
  );
}
