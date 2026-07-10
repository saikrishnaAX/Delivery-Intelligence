import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat().format(n);
}

export function formatPercent(n: number): string {
  return `${n.toFixed(1)}%`;
}

export function formatHours(h: number): string {
  if (h < 24) return `${h.toFixed(1)}h`;
  return `${(h / 24).toFixed(1)}d`;
}

export function categoryLabel(cat: string): string {
  return cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function severityColor(severity: string): string {
  switch (severity) {
    case "critical": return "text-destructive";
    case "warning": return "text-warning";
    case "info": return "text-primary";
    default: return "text-muted-foreground";
  }
}

export function priorityColor(priority: string): string {
  switch (priority) {
    case "critical": return "bg-destructive/10 text-destructive border-destructive/20";
    case "high": return "bg-warning/10 text-warning border-warning/20";
    case "medium": return "bg-primary/10 text-primary border-primary/20";
    default: return "bg-muted text-muted-foreground border-border";
  }
}
