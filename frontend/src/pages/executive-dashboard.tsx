import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { StaleDataBanner } from "@/components/stale-data-banner";
import { useProject } from "@/hooks/use-project";
import { useProjectApi, readProjectCache } from "@/hooks/use-project-api";
import { api } from "@/lib/api";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CEOIntelligenceView } from "@/components/ceo-intelligence/ceo-intelligence-view";
import {
  EXECUTION_CACHE_KEY,
  ExecutionTabContent,
  isExecutionBoardData,
} from "@/components/executive-dashboard";

export default function ExecutiveDashboard() {
  const { projectGid, dateFrom, dateTo } = useProject();
  const location = useLocation();
  const rawCached = readProjectCache(EXECUTION_CACHE_KEY, projectGid, dateFrom, dateTo);
  const cached = isExecutionBoardData(rawCached) ? rawCached : null;
  const { data: board, loading, error, stale, refetch } = useProjectApi(EXECUTION_CACHE_KEY, (gid, from, to) =>
    api.getExecutionBoard(gid, from, to)
  );
  const display = isExecutionBoardData(board) ? board : cached;

  const [activeTab, setActiveTab] = useState("execution");

  useEffect(() => {
    const scroll = new URLSearchParams(location.search).get("scroll");
    if (!scroll || !display) return;
    const el = document.getElementById(`exec-${scroll}`);
    if (el) {
      requestAnimationFrame(() => {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }
  }, [location.search, display]);

  if (loading && !display) {
    return (
      <>
        <Header title="Executive Dashboard" description="Your daily command center" />
        <div className="page-content"><LoadingState /></div>
      </>
    );
  }

  if (!display) {
    return (
      <>
        <Header title="Executive Dashboard" description="Your daily command center" />
        <div className="page-content">
          {error ? (
            <ErrorState
              message={`Could not load execution board: ${error}. Restart the backend if you recently updated the app.`}
              onRetry={() => void refetch()}
            />
          ) : (
            <ErrorState message="Select a project to view today's execution board." title="No project selected" />
          )}
        </div>
      </>
    );
  }

  const metrics = display.metrics;
  const isSprint = metrics.project_type === "sprint";
  const projectLabel = metrics.project_name ?? "Project";

  return (
    <PageLayout page="executive" hideSidebar>
      <Header
        title="Executive Dashboard"
        description={isSprint ? `${projectLabel} · Sprint execution` : `${projectLabel} · ${display.status_headline}`}
      />

      <Tabs value={activeTab} onValueChange={setActiveTab} className="page-content">
        {stale && (
          <StaleDataBanner
            className="mb-3"
            message="Showing cached execution board — live refresh failed."
            onRetry={() => void refetch()}
          />
        )}
        <TabsList className="mb-2 h-9">
          <TabsTrigger value="execution" className="text-xs px-4">Execution</TabsTrigger>
          <TabsTrigger value="ceo-intelligence" className="text-xs px-4">CEO Intelligence</TabsTrigger>
        </TabsList>

        <TabsContent value="execution" className="mt-0">
          <ExecutionTabContent display={display} />
        </TabsContent>

        <TabsContent value="ceo-intelligence" className="mt-0 w-full min-w-0">
          {activeTab === "ceo-intelligence" && <CEOIntelligenceView />}
        </TabsContent>
      </Tabs>
    </PageLayout>
  );
}
