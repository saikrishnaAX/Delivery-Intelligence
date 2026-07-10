import { cn } from "@/lib/utils";
import type { ModuleHeatMapItem } from "@/types";

interface HeatmapGridProps {
  modules: ModuleHeatMapItem[];
}

export function HeatmapGrid({ modules }: HeatmapGridProps) {
  return (
    <div className="rounded-md border border-border/80 overflow-hidden">
      <div className="hidden sm:grid grid-cols-[1fr_5rem_4rem_4rem_4rem_5rem] gap-2 px-3 py-2 bg-muted/40 text-[10px] font-medium uppercase tracking-wider text-muted-foreground border-b">
        <span>Module</span>
        <span className="text-right">Total</span>
        <span className="text-right">Open</span>
        <span className="text-right">Crit.</span>
        <span className="text-right">Avg h</span>
        <span className="text-right">Heat</span>
      </div>

      <div className="divide-y divide-border/60">
        {modules.map((m) => (
          <div
            key={m.module}
            className="grid grid-cols-1 sm:grid-cols-[1fr_5rem_4rem_4rem_4rem_5rem] gap-1 sm:gap-2 items-center px-3 py-2 hover:bg-muted/30 transition-colors"
          >
            <div className="min-w-0">
              <p className="text-xs font-medium truncate">{m.module}</p>
              <p className="text-[10px] text-muted-foreground truncate">{m.product_area}</p>
            </div>

            <div className="flex sm:contents items-center justify-between sm:justify-end text-[11px] tabular-nums">
              <span className="sm:hidden text-muted-foreground">Total</span>
              <span className="sm:text-right font-medium">{m.ticket_count}</span>
            </div>

            <div className="flex sm:contents items-center justify-between sm:justify-end text-[11px] tabular-nums text-muted-foreground">
              <span className="sm:hidden">Open</span>
              <span className="sm:text-right">{m.open_count}</span>
            </div>

            <div className="flex sm:contents items-center justify-between sm:justify-end text-[11px] tabular-nums">
              <span className="sm:hidden">Critical</span>
              <span className={cn("sm:text-right", m.critical_count > 0 ? "text-destructive font-medium" : "text-muted-foreground")}>
                {m.critical_count}
              </span>
            </div>

            <div className="flex sm:contents items-center justify-between sm:justify-end text-[11px] tabular-nums text-muted-foreground">
              <span className="sm:hidden">Avg resolution</span>
              <span className="sm:text-right">{m.avg_resolution_hours}h</span>
            </div>

            <div className="flex sm:contents items-center gap-2 sm:justify-end">
              <span className="sm:hidden text-[10px] text-muted-foreground">Intensity</span>
              <div className="flex-1 sm:flex-none sm:w-full h-1 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.max(m.intensity * 100, 4)}%`, opacity: 0.35 + m.intensity * 0.65 }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
