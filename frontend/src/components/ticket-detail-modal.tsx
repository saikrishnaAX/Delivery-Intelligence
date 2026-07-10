import { useEffect } from "react";
import { ExternalLink, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { priorityColor, cn } from "@/lib/utils";
import type { ExecutiveTicketItem } from "@/types";

export type TicketPersonMode = "creator" | "assignee";

interface TicketDetailModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  tickets: ExecutiveTicketItem[];
  totalCount?: number;
  loading?: boolean;
  /** Whose name to show — creator for "created today", assignee for open/escalations */
  personMode?: TicketPersonMode;
}

function personName(ticket: ExecutiveTicketItem, mode: TicketPersonMode): string | undefined {
  if (mode === "creator") {
    return ticket.created_by || ticket.ticket_owner || undefined;
  }
  return ticket.assignee || ticket.ticket_owner || undefined;
}

function personLabel(mode: TicketPersonMode): string {
  return mode === "creator" ? "Created by" : "Assigned to";
}

const thClass = "px-3 py-2 text-left text-[10px] font-medium text-muted-foreground";
const tdClass = "px-3 py-2 align-top text-[11px]";

export function TicketDetailModal({
  open,
  onClose,
  title,
  tickets,
  totalCount,
  loading = false,
  personMode = "creator",
}: TicketDetailModalProps) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  const whoLabel = personLabel(personMode);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-8">
      <button
        type="button"
        className="absolute inset-0 bg-black/60"
        aria-label="Close"
        onClick={onClose}
      />
      <div
        className="relative flex w-full max-w-3xl flex-col rounded-xl border border-border bg-card shadow-2xl"
        style={{ height: "min(85vh, 720px)" }}
      >
        <div className="flex items-center justify-between gap-4 border-b border-border/60 px-4 py-3 shrink-0">
          <div>
            <h3 className="text-sm font-semibold">{title}</h3>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {loading && tickets.length === 0
                ? "Loading tickets…"
                : totalCount != null && totalCount > tickets.length
                  ? `Showing ${tickets.length} of ${totalCount} tickets`
                  : `${tickets.length} ticket${tickets.length !== 1 ? "s" : ""}`}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 hover:bg-muted text-muted-foreground hover:text-foreground"
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-4 py-2 scrollbar-thin">
          {tickets.length === 0 ? (
            <p className="text-xs text-muted-foreground py-6 text-center">
              {loading ? "Loading tickets…" : "No tickets in this group."}
            </p>
          ) : (
            <div className="overflow-x-auto rounded-md border border-border/60">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className={thClass}>Ticket</th>
                    <th className={thClass}>{whoLabel}</th>
                    <th className={thClass}>Section</th>
                    <th className={cn(thClass, "w-16")}>Priority</th>
                    <th className={cn(thClass, "w-16")} />
                  </tr>
                </thead>
                <tbody>
                  {tickets.map((ticket) => {
                    const who = personName(ticket, personMode);
                    const section =
                      ticket.module_name && ticket.module_name.toLowerCase() !== "untitled section"
                        ? ticket.module_name
                        : ticket.workshop_name || "—";

                    return (
                      <tr key={ticket.id} className="border-t border-border/50 hover:bg-muted/15">
                        <td className={tdClass}>
                          <p className="font-medium leading-snug">{ticket.title}</p>
                          {ticket.days_open > 0 && personMode === "assignee" && (
                            <p className="text-[10px] text-muted-foreground mt-0.5">{ticket.days_open}d open</p>
                          )}
                          {ticket.jira_key && (
                            <Badge variant="outline" className="text-[9px] px-1 py-0 font-mono mt-1">
                              {ticket.jira_key}
                            </Badge>
                          )}
                        </td>
                        <td className={cn(tdClass, "text-muted-foreground whitespace-nowrap")}>
                          {who || "—"}
                        </td>
                        <td className={cn(tdClass, "text-muted-foreground")}>{section}</td>
                        <td className={tdClass}>
                          <span
                            className={`inline-flex rounded border px-1.5 py-0 text-[9px] font-medium capitalize ${priorityColor(ticket.priority)}`}
                          >
                            {ticket.priority}
                          </span>
                        </td>
                        <td className={tdClass}>
                          {ticket.asana_url ? (
                            <a
                              href={ticket.asana_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-0.5 text-[10px] font-medium text-primary hover:underline whitespace-nowrap"
                            >
                              Asana
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          ) : (
                            <span className="text-[10px] text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
