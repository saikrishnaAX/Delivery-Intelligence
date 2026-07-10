import type { ExecutionBoardData, ExecutionTask, OperationalStatus } from "@/types";

export const EXECUTION_CACHE_KEY = "execution-board-v3";

export function isExecutionBoardData(value: unknown): value is ExecutionBoardData {
  if (!value || typeof value !== "object") return false;
  const v = value as ExecutionBoardData;
  return (
    typeof v.operational_status === "string" &&
    Array.isArray(v.today_tasks) &&
    v.metrics != null &&
    typeof v.metrics.project_type === "string" &&
    typeof v.workshops_hidden_count === "number"
  );
}

export const STATUS_THEME: Record<
  OperationalStatus,
  { ring: string; glow: string; core: string; label: string; pulse: boolean }
> = {
  red: {
    ring: "border-red-500/60",
    glow: "shadow-[0_0_48px_rgba(239,68,68,0.45)]",
    core: "bg-red-500",
    label: "DANGER",
    pulse: true,
  },
  amber: {
    ring: "border-amber-500/60",
    glow: "shadow-[0_0_40px_rgba(245,158,11,0.35)]",
    core: "bg-amber-500",
    label: "CAUTION",
    pulse: true,
  },
  green: {
    ring: "border-emerald-500/50",
    glow: "shadow-[0_0_32px_rgba(16,185,129,0.25)]",
    core: "bg-emerald-500",
    label: "NOMINAL",
    pulse: false,
  },
};

export const PRIORITY_STYLES: Record<ExecutionTask["priority"], string> = {
  critical: "border-l-red-500 bg-red-500/5",
  high: "border-l-amber-500 bg-amber-500/5",
  medium: "border-l-border bg-muted/20",
};
