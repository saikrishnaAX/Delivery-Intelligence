import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, ListChecks } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ExecutionTask } from "@/types";
import { PRIORITY_STYLES } from "./constants";

export function TodayTasksPanel({
  tasks,
  taskCount,
  itemCount,
}: {
  tasks: ExecutionTask[];
  taskCount: number;
  itemCount: number;
}) {
  if (tasks.length === 0) {
    return (
      <Card className="border-emerald-500/20 bg-emerald-500/5">
        <CardContent className="py-6 text-center">
          <CheckCircle2 className="h-8 w-8 mx-auto text-emerald-500 mb-2" />
          <p className="text-sm font-medium">Nothing urgent on your plate</p>
          <p className="text-xs text-muted-foreground mt-1">Use the metrics below for deeper review.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/80">
      <CardContent className="py-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ListChecks className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold">Today&apos;s focus</h3>
          </div>
          <Badge variant="secondary" className="text-[10px] tabular-nums">
            {taskCount} focus area{taskCount !== 1 ? "s" : ""}
            {itemCount > taskCount && ` · ${itemCount} items`}
          </Badge>
        </div>
        <ul className="space-y-2">
          {tasks.map((task) => (
            <li key={task.id}>
              <Link
                to={task.route}
                className={cn(
                  "flex items-start gap-3 rounded-lg border border-border/60 border-l-[3px] px-3 py-2.5",
                  "hover:bg-muted/30 transition-colors group",
                  PRIORITY_STYLES[task.priority]
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold">{task.title}</span>
                    <Badge variant="outline" className="text-[9px] px-1.5 py-0 tabular-nums">
                      {task.count}
                    </Badge>
                  </div>
                  {task.description && (
                    <p className="text-[10px] text-muted-foreground mt-0.5 leading-relaxed">{task.description}</p>
                  )}
                </div>
                <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground group-hover:text-primary mt-0.5" />
              </Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
