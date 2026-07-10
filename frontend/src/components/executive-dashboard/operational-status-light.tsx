import { cn } from "@/lib/utils";
import type { OperationalStatus } from "@/types";
import { STATUS_THEME } from "./constants";

export function OperationalStatusLight({ status }: { status: OperationalStatus }) {
  const theme = STATUS_THEME[status];
  return (
    <div className="flex flex-col items-center gap-3">
      <div
        className={cn(
          "relative flex h-28 w-28 sm:h-32 sm:w-32 items-center justify-center rounded-full border-4 bg-card",
          theme.ring,
          theme.glow
        )}
      >
        {theme.pulse && (
          <span
            className={cn(
              "absolute inset-0 rounded-full opacity-40 animate-ping",
              theme.core
            )}
          />
        )}
        <span className={cn("relative h-16 w-16 sm:h-[4.5rem] sm:w-[4.5rem] rounded-full", theme.core)} />
      </div>
      <span
        className={cn(
          "text-[11px] font-bold tracking-[0.2em]",
          status === "red" && "text-red-500",
          status === "amber" && "text-amber-500",
          status === "green" && "text-emerald-500"
        )}
      >
        {theme.label}
      </span>
    </div>
  );
}
