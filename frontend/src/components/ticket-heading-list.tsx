import { Badge } from "@/components/ui/badge";
import { priorityColor } from "@/lib/utils";

export interface TicketHeading {
  id: number;
  title: string;
  workshop_name?: string | null;
  assignee?: string | null;
  ticket_owner?: string | null;
  priority?: string;
  detail?: string | null;
  days_open?: number;
}

interface TicketHeadingListProps {
  tickets: TicketHeading[];
  emptyMessage?: string;
  showDays?: boolean;
  dayLabel?: string;
}

export function TicketHeadingList({
  tickets,
  emptyMessage = "No tickets.",
  showDays = false,
  dayLabel = "days",
}: TicketHeadingListProps) {
  if (tickets.length === 0) {
    return <p className="text-[10px] text-muted-foreground py-1">{emptyMessage}</p>;
  }

  return (
    <ul className="space-y-1 max-h-56 overflow-y-auto scrollbar-thin">
      {tickets.map((ticket) => (
        <li
          key={ticket.id}
          className="flex items-start justify-between gap-2 py-1.5 border-b border-border/30 last:border-0"
        >
          <div className="min-w-0 flex-1">
            <p className="text-[10px] leading-snug font-medium">{ticket.title}</p>
            <div className="flex flex-wrap gap-1 mt-0.5">
              {ticket.workshop_name && (
                <Badge variant="outline" className="text-[8px] px-1 py-0 max-w-[120px] truncate">
                  {ticket.workshop_name}
                </Badge>
              )}
              {(ticket.assignee || ticket.ticket_owner) && (
                <Badge variant="secondary" className="text-[8px] px-1 py-0">
                  {ticket.assignee || ticket.ticket_owner}
                </Badge>
              )}
              {ticket.priority && (
                <span className={`inline-flex rounded border px-1 py-0 text-[8px] font-medium ${priorityColor(ticket.priority)}`}>
                  {ticket.priority}
                </span>
              )}
              {ticket.detail && (
                <span className="text-[8px] text-muted-foreground">{ticket.detail}</span>
              )}
            </div>
          </div>
          {showDays && ticket.days_open !== undefined && (
            <div className="text-right shrink-0">
              <p className="text-xs font-semibold tabular-nums">{ticket.days_open}</p>
              <p className="text-[8px] text-muted-foreground">{dayLabel}</p>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
