import { useEffect, useRef } from "react";
import { useProjectApi } from "@/hooks/use-project-api";
import { useProject } from "@/hooks/use-project";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { StaleDataBanner } from "@/components/stale-data-banner";
import { api } from "@/lib/api";
import type { CEOIntelligenceData } from "@/types";
import { CEOReportPanel } from "@/components/ceo-intelligence/ceo-report-panel";
import { CEOQuickView } from "@/components/ceo-intelligence/ceo-quick-view";

const CEO_CACHE_KEY = "ceo-intelligence-v9";

function isCEOIntelligenceData(value: unknown): value is CEOIntelligenceData {
  if (!value || typeof value !== "object") return false;
  const v = value as CEOIntelligenceData;
  return Boolean(v.ceo_quick_view?.bugs);
}

export function CEOIntelligenceView() {
  const { projectGid } = useProject();
  const { data, loading, error, stale, refetch } = useProjectApi(
    CEO_CACHE_KEY,
    (gid, from, to) => api.getCEOIntelligence(gid, from, to)
  );
  const staleRefetchDone = useRef(false);

  useEffect(() => {
    if (data && !isCEOIntelligenceData(data) && !staleRefetchDone.current) {
      staleRefetchDone.current = true;
      void refetch();
    }
  }, [data, refetch]);

  if (!projectGid) {
    return (
      <ErrorState
        title="No project selected"
        message="Choose a project from the header dropdown to load CEO Intelligence."
      />
    );
  }

  if ((loading && !data) || (data && !isCEOIntelligenceData(data))) {
    return (
      <div className="space-y-3">
        <LoadingState rows={3} />
        <p className="text-xs text-muted-foreground text-center">Loading…</p>
      </div>
    );
  }

  if (error && !data) {
    const is404 = error.toLowerCase().includes("not found");
    return (
      <ErrorState
        title={is404 ? "CEO Intelligence API unavailable" : "Could not load CEO Intelligence"}
        message={
          is404
            ? "Restart the backend (port 8003), then retry."
            : error
        }
        onRetry={() => void refetch()}
      />
    );
  }

  if (!data || !isCEOIntelligenceData(data)) {
    return (
      <ErrorState
        message="Could not load CEO Intelligence. Click Retry or check that the backend is running on port 8003."
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <div className="w-full min-w-0 space-y-4">
      {stale && (
        <StaleDataBanner message="Showing cached data — live refresh failed." onRetry={() => void refetch()} />
      )}
      <CEOReportPanel />
      <CEOQuickView data={data.ceo_quick_view} />
    </div>
  );
}
