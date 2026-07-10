import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = "Could not load data",
  message,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-4 text-center rounded-lg border border-destructive/30 bg-destructive/5",
        className
      )}
    >
      <div className="rounded-full bg-destructive/10 p-3 mb-3">
        <AlertCircle className="h-6 w-6 text-destructive" />
      </div>
      <h3 className="text-sm font-semibold text-destructive">{title}</h3>
      <p className="text-xs text-muted-foreground mt-1.5 max-w-md leading-relaxed">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4 h-8 text-xs gap-1.5" onClick={onRetry}>
          <RefreshCw className="h-3 w-3" />
          Retry
        </Button>
      )}
    </div>
  );
}
