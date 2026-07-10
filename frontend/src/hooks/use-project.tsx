import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { api } from "@/lib/api";
import { DEFAULT_DATE_FROM } from "@/lib/constants";
import { readCache, writeCache, syncAtChanged } from "@/lib/data-cache";
import { prefetchProjectAnalytics } from "@/lib/prefetch-analytics";
import type { AsanaProject, IntegrationStatus } from "@/types";

interface ProjectContextValue {
  projects: AsanaProject[];
  projectGid: string | null;
  selectedProject: AsanaProject | null;
  setProjectGid: (gid: string) => void;
  dateFrom: string;
  dateTo: string;
  setDateFrom: (d: string) => void;
  setDateTo: (d: string) => void;
  integrationStatus: IntegrationStatus | null;
  syncing: boolean;
  syncError: string | null;
  /** Bumps when data should be refetched (manual sync or backend auto-sync). */
  cacheVersion: number;
  /** @deprecated use cacheVersion */
  syncVersion: number;
  refreshProjects: () => Promise<void>;
  syncProject: () => Promise<void>;
  syncJira: () => Promise<void>;
  loadingProjects: boolean;
  apiError: string | null;
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);
const STORAGE_KEY = "selected_project_gid";
const DATE_FROM_KEY = "date_from";
const DATE_TO_KEY = "date_to";
const PROJECTS_CACHE_KEY = "projects";
const INTEGRATION_CACHE_KEY = "integration_status";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function readBootstrapCache<T>(key: string): T | null {
  return readCache<T>(key, "global");
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<AsanaProject[]>(
    () => readBootstrapCache<AsanaProject[]>(PROJECTS_CACHE_KEY) ?? []
  );
  const [projectGid, setProjectGidState] = useState<string | null>(
    () => localStorage.getItem(STORAGE_KEY)
  );
  const [dateFrom, setDateFromState] = useState(
    () => localStorage.getItem(DATE_FROM_KEY) || DEFAULT_DATE_FROM
  );
  const [dateTo, setDateToState] = useState(
    () => localStorage.getItem(DATE_TO_KEY) || todayIso()
  );
  const [integrationStatus, setIntegrationStatus] = useState<IntegrationStatus | null>(
    () => readBootstrapCache<IntegrationStatus>(INTEGRATION_CACHE_KEY)
  );
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [cacheVersion, setCacheVersion] = useState(0);
  const [loadingProjects, setLoadingProjects] = useState(() => projects.length === 0);
  const [apiError, setApiError] = useState<string | null>(null);

  const setProjectGid = useCallback((gid: string) => {
    setProjectGidState(gid);
    localStorage.setItem(STORAGE_KEY, gid);
  }, []);

  const setDateFrom = useCallback((d: string) => {
    setDateFromState(d);
    localStorage.setItem(DATE_FROM_KEY, d);
    if (d > dateTo) {
      setDateToState(d);
      localStorage.setItem(DATE_TO_KEY, d);
    }
  }, [dateTo]);

  const setDateTo = useCallback((d: string) => {
    setDateToState(d);
    localStorage.setItem(DATE_TO_KEY, d);
    if (d < dateFrom) {
      setDateFromState(d);
      localStorage.setItem(DATE_FROM_KEY, d);
    }
  }, [dateFrom]);

  const bumpCache = useCallback(() => {
    setCacheVersion((v) => v + 1);
  }, []);

  const refreshProjects = useCallback(async () => {
    try {
      const [projs, status] = await Promise.all([
        api.getProjects(),
        api.getIntegrationStatus(),
      ]);
      setApiError(null);
      setProjects(projs);
      setIntegrationStatus(status);
      writeCache(PROJECTS_CACHE_KEY, "global", projs);
      writeCache(INTEGRATION_CACHE_KEY, "global", status);

      if (syncAtChanged(status.last_auto_sync_at ?? null)) {
        bumpCache();
      }

      if (projs.length > 0) {
        const stored = localStorage.getItem(STORAGE_KEY);
        const valid = projs.find((p) => p.gid === stored);
        if (valid) {
          setProjectGidState(stored);
        } else {
          setProjectGid(projs[0].gid);
        }
      }
    } catch (e) {
      console.error("Failed to load projects", e);
      setApiError(
        e instanceof Error
          ? e.message
          : "Cannot reach the API. Start the backend: uvicorn app.main:app --port 8003"
      );
    } finally {
      setLoadingProjects(false);
    }
  }, [bumpCache, setProjectGid]);

  const syncProject = useCallback(async () => {
    if (!projectGid) return;
    setSyncing(true);
    setSyncError(null);
    try {
      await api.syncProject(projectGid);
      await refreshProjects();
      bumpCache();
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }, [projectGid, refreshProjects, bumpCache]);

  const syncJira = useCallback(async () => {
    setSyncing(true);
    setSyncError(null);
    try {
      await api.syncJira();
      bumpCache();
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : "Jira sync failed");
    } finally {
      setSyncing(false);
    }
  }, [bumpCache]);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    if (!integrationStatus?.auto_sync_enabled) return;
    const pollMs = (integrationStatus.auto_sync_ui_poll_seconds ?? 60) * 1000;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") {
        refreshProjects();
      }
    }, pollMs);
    return () => clearInterval(id);
  }, [
    integrationStatus?.auto_sync_enabled,
    integrationStatus?.auto_sync_ui_poll_seconds,
    refreshProjects,
  ]);

  useEffect(() => {
    if (projectGid && !loadingProjects) {
      prefetchProjectAnalytics(projectGid, dateFrom, dateTo);
    }
  }, [projectGid, dateFrom, dateTo, loadingProjects, cacheVersion]);

  const selectedProject = projects.find((p) => p.gid === projectGid) ?? null;

  return (
    <ProjectContext.Provider
      value={{
        projects,
        projectGid,
        selectedProject,
        setProjectGid,
        dateFrom,
        dateTo,
        setDateFrom,
        setDateTo,
        integrationStatus,
        syncing,
        syncError,
        cacheVersion,
        syncVersion: cacheVersion,
        refreshProjects,
        syncProject,
        syncJira,
        loadingProjects,
        apiError,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used within ProjectProvider");
  return ctx;
}
