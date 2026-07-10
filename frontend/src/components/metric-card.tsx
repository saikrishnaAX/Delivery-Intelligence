import { type LucideIcon } from "lucide-react";
import { cn, formatNumber } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: { value: number; label: string };
  variant?: "default" | "success" | "warning" | "destructive";
}

const variantStyles = {
  default: "text-primary",
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
};

export function MetricCard({ title, value, subtitle, icon: Icon, trend, variant = "default" }: MetricCardProps) {
  const displayValue = typeof value === "number" ? formatNumber(value) : value;

  return (
    <div className="rounded-md border border-border/80 bg-card px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
          <p className={cn("text-lg font-semibold tabular-nums tracking-tight mt-0.5", variantStyles[variant])}>
            {displayValue}
          </p>
          {subtitle && <p className="text-[10px] text-muted-foreground mt-0.5">{subtitle}</p>}
          {trend && (
            <p className={cn("text-[10px] font-medium mt-0.5", trend.value >= 0 ? "text-success" : "text-destructive")}>
              {trend.value >= 0 ? "+" : ""}{trend.value}% {trend.label}
            </p>
          )}
        </div>
        <Icon className={cn("h-3.5 w-3.5 shrink-0 opacity-40", variantStyles[variant])} />
      </div>
    </div>
  );
}
