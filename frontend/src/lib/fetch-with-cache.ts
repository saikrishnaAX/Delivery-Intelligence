import { readCache, writeCache } from "@/lib/data-cache";

/** Apply cached data immediately, fetch fresh in background, swap when ready. */
export async function refreshCached<T>(
  cacheKey: string,
  cacheScope: string,
  fetcher: () => Promise<T>,
  apply: (data: T) => void,
): Promise<void> {
  const cached = readCache<T>(cacheKey, cacheScope);
  if (cached) apply(cached);

  try {
    const fresh = await fetcher();
    writeCache(cacheKey, cacheScope, fresh);
    apply(fresh);
  } catch (err) {
    if (!cached) throw err;
  }
}

export function hydrateFromCache<T>(cacheKey: string, cacheScope: string): T | null {
  return readCache<T>(cacheKey, cacheScope);
}
