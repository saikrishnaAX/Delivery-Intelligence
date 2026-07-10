import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  hint?: string;
  className?: string;
  valueClassName?: string;
}

export function StatCard({ label, value, hint, className, valueClassName }: StatCardProps) {
  return (
    <div className={cn("rounded-md border bg-card px-3 py-2.5", className)}>
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={cn("text-lg font-semibold tabular-nums tracking-tight mt-0.5", valueClassName)}>
        {value}
      </p>
      {hint && <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{hint}</p>}
    </div>
  );
}
