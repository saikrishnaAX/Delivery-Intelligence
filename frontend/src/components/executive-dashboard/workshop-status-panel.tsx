import { Building2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ExecutionBoardData } from "@/types";

export function WorkshopStatusPanel({
  workshops,
  healthyCount,
  showStopperWorkshops,
  hiddenCount = 0,
}: {
  workshops: ExecutionBoardData["workshop_statuses"];
  healthyCount: number;
  showStopperWorkshops: number;
  hiddenCount?: number;
}) {
  return (
    <Card className="border-border/80">
      <CardContent className="py-4 space-y-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold">Workshop status</h3>
          </div>
          <div className="flex gap-2 text-[10px]">
            {showStopperWorkshops > 0 && (
              <Badge variant="destructive" className="text-[9px]">
                {showStopperWorkshops} with show-stoppers
              </Badge>
            )}
            <Badge variant="secondary" className="text-[9px] text-emerald-600 dark:text-emerald-400" title="Workshops with open tickets but no blockers and low load">
              {healthyCount} low-risk
            </Badge>
          </div>
        </div>

        {workshops.length === 0 ? (
          <p className="text-xs text-muted-foreground py-2">
            No workshops in danger or caution — all monitored workshops are stable.
          </p>
        ) : (
          <ul className="space-y-1.5 max-h-[280px] overflow-y-auto pr-1">
            {workshops.map((w) => (
              <li
                key={w.name}
                className={cn(
                  "flex items-start gap-2.5 rounded-md border px-2.5 py-2 text-[11px]",
                  w.status === "red"
                    ? "border-red-500/30 bg-red-500/5"
                    : "border-amber-500/30 bg-amber-500/5"
                )}
              >
                <span
                  className={cn(
                    "mt-1 h-2 w-2 shrink-0 rounded-full",
                    w.status === "red" ? "bg-red-500 animate-pulse" : "bg-amber-500"
                  )}
                />
                <div className="min-w-0 flex-1">
                  <p className="font-medium truncate" title={w.name}>{w.name}</p>
                  <p className="text-muted-foreground text-[10px] mt-0.5">{w.headline}</p>
                </div>
                <div className="text-[9px] text-muted-foreground shrink-0 text-right tabular-nums">
                  {w.show_stoppers > 0 && <div className="text-red-500 font-medium">{w.show_stoppers} blocker{w.show_stoppers !== 1 ? "s" : ""}</div>}
                  <div>{w.open_tickets} open</div>
                </div>
              </li>
            ))}
          </ul>
        )}
        {hiddenCount > 0 && (
          <p className="text-[10px] text-muted-foreground pt-1 border-t border-border/40">
            +{hiddenCount} more workshop{hiddenCount !== 1 ? "s" : ""} at risk — not shown
          </p>
        )}
      </CardContent>
    </Card>
  );
}
