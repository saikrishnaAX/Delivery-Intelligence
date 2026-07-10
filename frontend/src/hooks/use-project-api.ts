import { useCallback } from "react";
import { useProject } from "./use-project";
import { useApi } from "./use-api";
import { buildScope, readCache } from "@/lib/data-cache";

/** Fetch API data scoped to the currently selected Asana project and date range. */
export function useProjectApi<T>(
  cacheKey: string,
  fetcher: (
    projectGid: string | null,
    dateFrom: string,
    dateTo: string
  ) => Promise<T>,
  extraDeps: unknown[] = []
) {
  const { projectGid, cacheVersion, dateFrom, dateTo } = useProject();
  const cacheScope = buildScope([projectGid, dateFrom, dateTo, ...extraDeps.map(String)]);

  const stableFetcher = useCallback(
    () => fetcher(projectGid, dateFrom, dateTo),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projectGid, dateFrom, dateTo, ...extraDeps]
  );

  return useApi(stableFetcher, [projectGid, dateFrom, dateTo, ...extraDeps], {
    cacheKey,
    cacheScope,
    refreshToken: cacheVersion,
  });
}

/** Read cached project-scoped data synchronously (for instant first paint). */
export function readProjectCache<T>(
  cacheKey: string,
  projectGid: string | null,
  dateFrom: string,
  dateTo: string,
  extraScope: (string | null | undefined)[] = []
): T | null {
  return readCache<T>(cacheKey, buildScope([projectGid, dateFrom, dateTo, ...extraScope.map(String)]));
}
