/** Session-scoped display cache — show last synced data instantly; refresh silently after sync. */

const CACHE_STORAGE_KEY = "ax_data_cache";
const LAST_SYNC_KEY = "ax_last_auto_sync_at";

export interface CacheEntry<T = unknown> {
  data: T;
  syncAt: string;
  scope: string;
}

const memory: Record<string, CacheEntry> = {};

function entryId(key: string, scope: string): string {
  return `${key}\0${scope}`;
}

function readStore(): Record<string, CacheEntry> {
  try {
    const raw = sessionStorage.getItem(CACHE_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, CacheEntry>) : {};
  } catch {
    return {};
  }
}

function writeStore(store: Record<string, CacheEntry>) {
  try {
    sessionStorage.setItem(CACHE_STORAGE_KEY, JSON.stringify(store));
  } catch {
    // sessionStorage full — memory cache still works for this tab
  }
}

export function invalidateCache(key: string, scope: string): void {
  const id = entryId(key, scope);
  delete memory[id];
  const store = readStore();
  delete store[id];
  writeStore(store);
}

export function buildScope(parts: (string | null | undefined)[]): string {
  return parts.map((p) => p ?? "").join("|");
}

export function currentSyncStamp(): string {
  return sessionStorage.getItem(LAST_SYNC_KEY) ?? "init";
}

/** Read last known data for this key+scope (ignores sync stamp — stale-while-revalidate). */
export function readCache<T>(key: string, scope: string): T | null {
  const id = entryId(key, scope);
  const mem = memory[id];
  if (mem) return mem.data as T;
  const store = readStore();
  const entry = store[id];
  if (entry) {
    memory[id] = entry;
    return entry.data as T;
  }
  return null;
}

export function writeCache<T>(key: string, scope: string, data: T): void {
  const id = entryId(key, scope);
  const entry: CacheEntry<T> = { data, syncAt: currentSyncStamp(), scope };
  memory[id] = entry;
  const store = readStore();
  store[id] = entry;
  writeStore(store);
}

export function syncAtChanged(at: string | null): boolean {
  if (!at) return false;
  const prev = sessionStorage.getItem(LAST_SYNC_KEY);
  if (!prev) {
    sessionStorage.setItem(LAST_SYNC_KEY, at);
    return false;
  }
  if (prev !== at) {
    sessionStorage.setItem(LAST_SYNC_KEY, at);
    return true;
  }
  return false;
}
