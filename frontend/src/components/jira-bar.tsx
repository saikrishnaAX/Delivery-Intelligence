import { RefreshCw, Circle } from "lucide-react";
import { useProject } from "@/hooks/use-project";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function JiraBar() {
  const {
    integrationStatus,
    syncing,
    syncError,
    syncJira,
  } = useProject();

  const jiraReady = integrationStatus?.jira_configured;
  const projectKey = integrationStatus?.jira_project_key ?? "AXP";

  return (
    <div className="border-b border-border/80 bg-card/50 px-4 md:px-5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="text-xs font-medium">
          Jira project <span className="font-mono text-primary">{projectKey}</span>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={syncJira}
          disabled={syncing || !jiraReady}
          className="h-7 text-[10px] gap-1.5"
          title={jiraReady ? "Pull latest issues from Jira" : "Add Jira credentials to backend/.env"}
        >
          <RefreshCw className={cn("h-3 w-3", syncing && "animate-spin")} />
          {syncing ? "Syncing…" : "Sync Jira"}
        </Button>

        <p className="text-[10px] text-muted-foreground hidden sm:block">
          Matched from Asana title, description, Jira URLs, or the native Jira Cloud connection on the task.
        </p>

        <div className="flex items-center gap-3 ml-auto text-[10px] text-muted-foreground">
          {integrationStatus && (
            <span className="flex items-center gap-1">
              <Circle
                className={cn(
                  "h-2 w-2 fill-current",
                  jiraReady ? "text-success" : "text-muted-foreground/40"
                )}
              />
              Jira
            </span>
          )}
        </div>
      </div>
      {syncError && (
        <p className="text-[10px] text-destructive mt-1.5">{syncError}</p>
      )}
    </div>
  );
}
