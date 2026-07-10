import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface StaleDataBannerProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function StaleDataBanner({
  message = "Showing cached data — live refresh failed.",
  onRetry,
  className,
}: StaleDataBannerProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2",
        className
      )}
      role="status"
    >
      <div className="flex items-center gap-2 min-w-0">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-500" />
        <p className="text-[11px] text-amber-600 dark:text-amber-400 leading-snug">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" className="h-7 text-[10px] gap-1 shrink-0" onClick={onRetry}>
          <RefreshCw className="h-3 w-3" />
          Retry
        </Button>
      )}
    </div>
  );
}
