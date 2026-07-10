import { useState } from "react";
import { ExternalLink, Link2, ListTodo, Unlink, Zap } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { TablePagination } from "@/components/table-pagination";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useProject } from "@/hooks/use-project";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import type { JiraIssue } from "@/types";

const PAGE_SIZE = 50;

function IssueTable({
  issues,
  showLinkedColumn = true,
}: {
  issues: JiraIssue[];
  showLinkedColumn?: boolean;
}) {
  if (issues.length === 0) return null;

  return (
    <div className="overflow-x-auto rounded-md border border-border max-h-[480px] overflow-y-auto">
      <table className="w-full text-[10px] table-fixed">
        <thead className="sticky top-0 z-10 bg-muted/95 backdrop-blur-sm">
          <tr className="text-left">
            <th className="px-2 py-2 font-medium w-24">Key</th>
            <th className="px-2 py-2 font-medium min-w-[180px]">Summary</th>
            <th className="px-2 py-2 font-medium w-24">Status</th>
            <th className="px-2 py-2 font-medium w-20">Type</th>
            <th className="px-2 py-2 font-medium w-16">Pts</th>
            <th className="px-2 py-2 font-medium w-28">Assignee</th>
            {showLinkedColumn && (
              <th className="px-2 py-2 font-medium min-w-[200px]">Linked Asana</th>
            )}
            <th className="px-2 py-2 font-medium w-12">Jira</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((issue) => (
            <tr key={issue.id} className="border-t border-border/60 align-top">
              <td className="px-2 py-1.5 font-mono text-primary">{issue.jira_key}</td>
              <td className="px-2 py-1.5 leading-snug">{issue.summary ?? "—"}</td>
              <td className="px-2 py-1.5">
                <Badge variant="outline" className="text-[9px]">
                  {issue.status ?? "—"}
                </Badge>
              </td>
              <td className="px-2 py-1.5 text-muted-foreground">{issue.issue_type ?? "—"}</td>
              <td className="px-2 py-1.5 tabular-nums">{issue.story_points ?? "—"}</td>
              <td className="px-2 py-1.5 text-muted-foreground">{issue.assignee ?? "—"}</td>
              {showLinkedColumn && (
                <td className="px-2 py-1.5">
                  {issue.linked && issue.ticket_title ? (
                    <div className="space-y-0.5">
                      <div className="flex items-start gap-1">
                        <Link2 className="h-3 w-3 text-success shrink-0 mt-0.5" />
                        <span className="leading-snug">{issue.ticket_title}</span>
                      </div>
                      {(issue.asana_project_name || issue.asana_section) && (
                        <p className="text-[9px] text-muted-foreground pl-4">
                          {[issue.asana_project_name, issue.asana_section].filter(Boolean).join(" · ")}
                        </p>
                      )}
                      {issue.asana_url && (
                        <a
                          href={issue.asana_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-0.5 text-primary hover:underline pl-4 text-[9px]"
                        >
                          Open in Asana <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      )}
                    </div>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-muted-foreground">
                      <Unlink className="h-3 w-3" />
                      No match
                    </span>
                  )}
                </td>
              )}
              <td className="px-2 py-1.5">
                {issue.jira_url ? (
                  <a
                    href={issue.jira_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-0.5 text-primary hover:underline"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function JiraPage() {
  const { integrationStatus, cacheVersion } = useProject();
  const [openPage, setOpenPage] = useState(1);
  const [closedPage, setClosedPage] = useState(1);
  const jiraReady = integrationStatus?.jira_configured;
  const projectKey = integrationStatus?.jira_project_key ?? "AXP";

  const { data, loading, error, refetch } = useApi(
    () => api.getJira(),
    [],
    { cacheKey: "jira", cacheScope: "global", refreshToken: cacheVersion }
  );

  if (!jiraReady) {
    return (
      <PageLayout page="jira">
        <Header
          title="Jira"
          description="AXP project issues from Atlassian"
        />
        <div className="page-content">
          <EmptyState
            title="Jira not connected"
            description="Add JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, and JIRA_PROJECT_KEY to backend/.env, then restart the backend and click Sync Jira."
          />
        </div>
      </PageLayout>
    );
  }

  if (loading && !data) {
    return (
      <PageLayout page="jira">
        <Header title="Jira" description={`${projectKey} — synced from Jira Cloud`} />
        <div className="page-content">
          <LoadingState />
        </div>
      </PageLayout>
    );
  }

  if (error && !data) {
    return (
      <PageLayout page="jira">
        <Header title="Jira" description={`${projectKey} — synced from Jira Cloud`} />
        <div className="page-content">
          <ErrorState message={error} onRetry={() => void refetch()} />
        </div>
      </PageLayout>
    );
  }

  if (!data) {
    return (
      <PageLayout page="jira">
        <Header title="Jira" description={`${projectKey} — synced from Jira Cloud`} />
        <div className="page-content">
          <ErrorState message="Could not load Jira data." onRetry={() => void refetch()} />
        </div>
      </PageLayout>
    );
  }

  const closedCount = data.issues.length - data.total_open;
  const totalPoints = data.open_issues.reduce((s, i) => s + (i.story_points ?? 0), 0);
  const closedIssues = data.issues.filter((i) => !i.is_open);
  const openSlice = data.open_issues.slice((openPage - 1) * PAGE_SIZE, openPage * PAGE_SIZE);
  const closedSlice = closedIssues.slice((closedPage - 1) * PAGE_SIZE, closedPage * PAGE_SIZE);

  return (
    <PageLayout page="jira">
      <Header
        title="Jira"
        description={`${projectKey} — open issues first; linked from Asana title, description, URL, or Jira Cloud connection`}
      />
      <div className="page-content space-y-3">
        <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
          <MetricCard title="Open issues" value={data.total_open} icon={ListTodo} />
          <MetricCard title="Linked to Asana" value={data.total_linked} icon={Link2} />
          <MetricCard title="Open story points" value={totalPoints} icon={Zap} />
          <MetricCard title="Closed / other" value={closedCount} icon={ListTodo} />
        </div>

        {data.open_issues.length === 0 ? (
          <EmptyState
            title="No open Jira issues"
            description={`Click Sync Jira in the top bar to pull issues from project ${projectKey}.`}
          />
        ) : (
          <Card>
            <CardHeader className="py-2">
              <CardTitle className="text-sm">
                Open issues ({data.total_open})
              </CardTitle>
            </CardHeader>
            <CardContent className="py-2 px-3">
              <IssueTable issues={openSlice} />
              <TablePagination
                page={openPage}
                pageSize={PAGE_SIZE}
                total={data.open_issues.length}
                onPageChange={setOpenPage}
              />
            </CardContent>
          </Card>
        )}

        {closedCount > 0 && (
          <Card>
            <CardHeader className="py-2">
              <CardTitle className="text-sm text-muted-foreground">
                Done / closed ({closedCount})
              </CardTitle>
            </CardHeader>
            <CardContent className="py-2 px-3">
              <IssueTable issues={closedSlice} showLinkedColumn={false} />
              <TablePagination
                page={closedPage}
                pageSize={PAGE_SIZE}
                total={closedIssues.length}
                onPageChange={setClosedPage}
              />
            </CardContent>
          </Card>
        )}
      </div>
    </PageLayout>
  );
}
