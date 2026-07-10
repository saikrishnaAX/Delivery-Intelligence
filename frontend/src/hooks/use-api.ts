import { useState, useEffect, useCallback, useRef } from "react";
import { readCache, writeCache } from "@/lib/data-cache";

export interface UseApiOptions {
  cacheKey?: string;
  cacheScope?: string;
  refreshToken?: number;
}

const inflight = new Map<string, Promise<unknown>>();

function inflightKey(cacheKey: string, cacheScope: string) {
  return `${cacheKey}\0${cacheScope}`;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: UseApiOptions = {}
) {
  const { cacheKey, cacheScope = "", refreshToken = 0 } = options;

  const readCached = useCallback((): T | null => {
    if (!cacheKey) return null;
    return readCache<T>(cacheKey, cacheScope);
  }, [cacheKey, cacheScope]);

  const [data, setData] = useState<T | null>(() =>
    cacheKey ? readCache<T>(cacheKey, cacheScope) : null
  );
  const [loading, setLoading] = useState(
    () => !(cacheKey && readCache<T>(cacheKey, cacheScope))
  );
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const fetchGen = useRef(0);
  const lastRefreshToken = useRef(refreshToken);
  const dataRef = useRef(data);
  dataRef.current = data;

  // Hydrate instantly when scope changes (e.g. project switch).
  useEffect(() => {
    const cached = readCached();
    if (cached) {
      setData(cached);
      setLoading(false);
    }
  }, [cacheScope, readCached]);

  const runFetch = useCallback(
    async (background: boolean) => {
      const gen = ++fetchGen.current;
      const cached = readCached();
      const hasDisplay = !!(cached ?? dataRef.current);

      if (hasDisplay) {
        if (cached) setData(cached);
        setLoading(false);
      } else if (!background) {
        setLoading(true);
      }

      setError(null);
      if (!background) setStale(false);

      const dedupeKey = cacheKey ? inflightKey(cacheKey, cacheScope) : null;
      let promise: Promise<T>;
      if (dedupeKey && inflight.has(dedupeKey)) {
        promise = inflight.get(dedupeKey) as Promise<T>;
      } else {
        promise = fetcher();
        if (dedupeKey) {
          inflight.set(dedupeKey, promise);
          promise.finally(() => {
            if (inflight.get(dedupeKey) === promise) inflight.delete(dedupeKey);
          });
        }
      }

      try {
        const result = await promise;
        if (gen !== fetchGen.current) return;
        setData(result);
        if (cacheKey) writeCache(cacheKey, cacheScope, result);
        setStale(false);
      } catch (e) {
        if (gen !== fetchGen.current) return;
        if (hasDisplay) {
          setStale(true);
          setError(e instanceof Error ? e.message : String(e));
        } else {
          setError(e instanceof Error ? e.message : String(e));
        }
      } finally {
        if (gen === fetchGen.current) setLoading(false);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [cacheKey, cacheScope, fetcher, ...deps]
  );

  // Initial load + dependency changes (project, dates, etc.)
  useEffect(() => {
    const cached = readCached();
    void runFetch(!!cached);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey, cacheScope, ...deps]);

  // Silent background refresh after sync completes.
  useEffect(() => {
    const bumped = refreshToken !== lastRefreshToken.current && refreshToken > 0;
    lastRefreshToken.current = refreshToken;
    if (bumped) void runFetch(true);
  }, [refreshToken, runFetch]);

  return {
    data,
    loading,
    error,
    stale,
    refetch: () => runFetch(false),
  };
}
