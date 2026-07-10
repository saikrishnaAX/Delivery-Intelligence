import { RefreshCw, ChevronDown, Circle } from "lucide-react";
import { useProject } from "@/hooks/use-project";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/date-picker";
import { cn } from "@/lib/utils";
import { DEFAULT_DATE_FROM } from "@/lib/constants";

export function ProjectBar() {
  const {
    projects,
    projectGid,
    setProjectGid,
    selectedProject,
    dateFrom,
    dateTo,
    setDateFrom,
    setDateTo,
    integrationStatus,
    syncing,
    syncError,
    syncProject,
    loadingProjects,
    apiError,
  } = useProject();

  const liveMode = integrationStatus && !integrationStatus.mock_mode && integrationStatus.asana_configured;

  return (
    <div className="border-b border-border/80 bg-card/50 px-4 md:px-5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[180px] flex-1 max-w-xs">
          <select
            value={projectGid ?? ""}
            onChange={(e) => setProjectGid(e.target.value)}
            disabled={loadingProjects || projects.length === 0}
            className={cn(
              "w-full appearance-none rounded-md border border-border/80 bg-background",
              "px-2.5 py-1.5 pr-7 text-xs font-medium",
              "focus:outline-none focus:ring-1 focus:ring-primary"
            )}
          >
            {projects.length === 0 ? (
              <option value="">
                {apiError ? "API offline — refresh after starting backend" : "No projects — sync or check API"}
              </option>
            ) : (
            projects.map((p) => (
                <option key={p.gid} value={p.gid}>
                  {p.name} ({p.last_synced_at ? p.ticket_count : "not synced"})
                </option>
              ))
            )}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
        </div>

        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <DatePicker
            value={dateFrom}
            onChange={setDateFrom}
            className="h-7 w-[128px] text-[10px]"
            placeholder="From"
          />
          <span>—</span>
          <DatePicker
            value={dateTo}
            onChange={setDateTo}
            className="h-7 w-[128px] text-[10px]"
            placeholder="To"
          />
          {dateFrom !== DEFAULT_DATE_FROM && (
            <button
              type="button"
              onClick={() => {
                setDateFrom(DEFAULT_DATE_FROM);
                setDateTo(new Date().toISOString().slice(0, 10));
              }}
              className="text-primary hover:underline ml-1"
            >
              Reset
            </button>
          )}
        </div>
        <p className="w-full text-[10px] text-muted-foreground mt-1.5 leading-relaxed">
          Date range filters closed-in-range metrics and analytics sections. Operational status and today&apos;s counts are always live (IST).
        </p>

        <Button
          size="sm"
          variant="outline"
          onClick={syncProject}
          disabled={!projectGid || syncing || !liveMode}
          className="h-7 text-[10px] gap-1.5"
          title={liveMode ? "Pull latest tickets from Asana" : "Set USE_MOCK_DATA=false and add Asana credentials"}
        >
          <RefreshCw className={cn("h-3 w-3", syncing && "animate-spin")} />
          {syncing ? "Syncing…" : "Sync"}
        </Button>

        <div className="flex items-center gap-3 ml-auto text-[10px] text-muted-foreground">
          {integrationStatus && (
            <>
              <span className="flex items-center gap-1">
                <Circle className={cn("h-2 w-2 fill-current", integrationStatus.asana_configured ? "text-success" : "text-muted-foreground/40")} />
                Asana
              </span>
              <span className="flex items-center gap-1">
                <Circle className={cn("h-2 w-2 fill-current", integrationStatus.jira_configured ? "text-success" : "text-muted-foreground/40")} />
                Jira
              </span>
            </>
          )}
          {integrationStatus?.auto_sync_enabled && integrationStatus.asana_configured && (
            <span className="hidden md:inline" title="Background sync of all Asana projects + Jira">
              Auto-sync {integrationStatus.auto_sync_interval_minutes ?? 10}m
              {integrationStatus.last_auto_sync_at && (
                <> · last {new Date(integrationStatus.last_auto_sync_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit", day: "numeric", month: "short" })}</>
              )}
            </span>
          )}
          {selectedProject?.last_synced_at && (
            <span className="hidden sm:inline" title="Last pull for selected project">
              Project synced {new Date(selectedProject.last_synced_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit", day: "numeric", month: "short" })}
            </span>
          )}
        </div>
      </div>
      {selectedProject && !selectedProject.last_synced_at && (
        <p className="text-[10px] text-warning mt-1.5">
          This project has not been synced yet. Select it and click <strong>Sync Asana</strong> to pull its tickets.
        </p>
      )}
      {apiError && (
        <p className="text-[10px] text-destructive mt-1.5">
          {apiError} — run backend on port <strong>8003</strong>, then refresh this page.
        </p>
      )}
      {syncError && (
        <p className="text-[10px] text-destructive mt-1.5">{syncError}</p>
      )}
    </div>
  );
}
