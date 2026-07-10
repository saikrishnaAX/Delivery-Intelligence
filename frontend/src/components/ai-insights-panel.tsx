import { Sparkles, AlertTriangle, Info, AlertCircle } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjectApi } from "@/hooks/use-project-api";
import { api } from "@/lib/api";
import { cn, severityColor } from "@/lib/utils";

const severityIcons = {
  critical: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

interface AIInsightsPanelProps {
  page: string;
  className?: string;
}

export function AIInsightsPanel({ page, className }: AIInsightsPanelProps) {
  const { data: insights, loading } = useProjectApi(
    `insights-${page}`,
    (gid, from, to) => api.getInsights(page, gid, from, to),
    [page]
  );

  return (
    <div className={cn("flex flex-col h-full", className)}>
      <div className="flex items-center gap-1.5 mb-2.5 px-0.5">
        <Sparkles className="h-3 w-3 text-primary" />
        <h3 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Data insights
          <span className="normal-case font-normal text-muted-foreground/80"> · rule-based</span>
        </h3>
      </div>

      <ScrollArea className="flex-1 max-h-48 xl:max-h-[calc(100vh-4rem)]">
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-md" />
            ))}
          </div>
        ) : insights && insights.length > 0 ? (
          <div className="space-y-2 pr-2">
            {insights.map((insight) => {
              const Icon = severityIcons[insight.severity as keyof typeof severityIcons] || Info;
              return (
                <div
                  key={insight.id}
                  className="rounded-md border border-border/60 bg-card px-2.5 py-2"
                >
                  <div className="flex items-start gap-1.5">
                    <Icon className={cn("h-3 w-3 mt-0.5 shrink-0", severityColor(insight.severity))} />
                    <div className="min-w-0">
                      <p className="text-[11px] font-medium leading-snug">{insight.title}</p>
                      <p className="text-[10px] text-muted-foreground leading-relaxed mt-0.5">{insight.content}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-[11px] text-muted-foreground text-center py-6">No insights yet.</p>
        )}
      </ScrollArea>
    </div>
  );
}
