import type { ReleaseNoteArchive } from "@/types";

const STORAGE_PREFIX = "ax_archives_";
const memory = new Map<string, ReleaseNoteArchive[]>();
const hydrated = new Set<string>();

function storageKey(scope: string) {
  return `${STORAGE_PREFIX}${scope}`;
}

export function archiveScope(projectGid: string | null | undefined): string {
  return projectGid ?? "all";
}

/** Returns cached archives if this scope was already loaded this session (or restored from sessionStorage). */
export function readArchiveCache(scope: string): ReleaseNoteArchive[] | null {
  if (hydrated.has(scope)) {
    return memory.get(scope) ?? [];
  }
  try {
    const raw = sessionStorage.getItem(storageKey(scope));
    if (raw !== null) {
      const rows = JSON.parse(raw) as ReleaseNoteArchive[];
      memory.set(scope, rows);
      hydrated.add(scope);
      return rows;
    }
  } catch {
    // ignore
  }
  return null;
}

export function writeArchiveCache(scope: string, rows: ReleaseNoteArchive[]): void {
  const stable = rows.filter((r) => !r.pending && !r.uploadError);
  memory.set(scope, stable);
  hydrated.add(scope);
  try {
    sessionStorage.setItem(storageKey(scope), JSON.stringify(stable));
  } catch {
    // sessionStorage full — memory cache still works for this tab
  }
}

export function isArchiveScopeHydrated(scope: string): boolean {
  return hydrated.has(scope);
}

export function markArchiveScopeHydrated(scope: string, rows: ReleaseNoteArchive[] = []): void {
  memory.set(scope, rows);
  hydrated.add(scope);
  writeArchiveCache(scope, rows);
}
