import { api } from "@/lib/api";
import { buildScope, readCache, writeCache } from "@/lib/data-cache";

const PREFETCH_ENDPOINTS: Array<{
  key: string;
  fetch: (gid: string, from: string, to: string) => Promise<unknown>;
}> = [
  { key: "execution-board-v3", fetch: (gid, from, to) => api.getExecutionBoard(gid, from, to) },
  { key: "classification", fetch: (gid, from, to) => api.getClassification(gid, from, to) },
  { key: "blockers-v2", fetch: (gid, from, to) => api.getBlockers(gid, from, to) },
  { key: "issue-intelligence", fetch: (gid, from, to) => api.getIssueIntelligence(gid, from, to) },
  { key: "customers", fetch: (gid, from, to) => api.getCustomers(gid, from, to) },
  { key: "support-team", fetch: (gid, from, to) => api.getSupportTeam(gid, from, to) },
];

let lastPrefetchKey = "";

/** Warm session cache for common analytics pages (skips keys already cached). */
export function prefetchProjectAnalytics(
  projectGid: string | null,
  dateFrom: string,
  dateTo: string
) {
  if (!projectGid) return;

  const scope = buildScope([projectGid, dateFrom, dateTo]);
  if (scope === lastPrefetchKey) return;
  lastPrefetchKey = scope;

  for (const { key, fetch } of PREFETCH_ENDPOINTS) {
    if (readCache(key, scope)) continue;
    fetch(projectGid, dateFrom, dateTo)
      .then((data) => writeCache(key, scope, data))
      .catch(() => {});
  }
}
