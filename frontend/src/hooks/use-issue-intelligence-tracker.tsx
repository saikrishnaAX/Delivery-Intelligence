import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import { useNotifyHelpers } from "@/hooks/use-notify";
import type { IssueIntelligenceJobData } from "@/types";

export const ISSUE_INTELLIGENCE_DONE_EVENT = "autorox:issue-intelligence-done";

type TrackedJob = { jobId: number; projectGid: string };

const STORAGE_KEY = "autorox_issue_intelligence_jobs";
const MAX_POLL_FAILURES = 8;

function loadTracked(): TrackedJob[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as TrackedJob[]) : [];
  } catch {
    return [];
  }
}

function saveTracked(jobs: TrackedJob[]) {
  if (jobs.length === 0) sessionStorage.removeItem(STORAGE_KEY);
  else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(jobs));
}

interface IssueIntelligenceContextValue {
  trackJob: (jobId: number, projectGid: string, initial?: IssueIntelligenceJobData) => void;
  untrackJob: (jobId: number) => void;
  dismissAnalysis: () => void;
  activeJob: IssueIntelligenceJobData | null;
  isAnalyzing: boolean;
}

const IssueIntelligenceContext = createContext<IssueIntelligenceContextValue | null>(null);

export function IssueIntelligenceProvider({ children }: { children: ReactNode }) {
  const { success, error: notifyError } = useNotifyHelpers();
  const [tracked, setTracked] = useState<TrackedJob[]>(loadTracked);
  const [activeJob, setActiveJob] = useState<IssueIntelligenceJobData | null>(null);
  const failCounts = useRef<Record<number, number>>({});

  const untrackJob = useCallback((jobId: number) => {
    setTracked([]);
    saveTracked([]);
    setActiveJob(null);
    delete failCounts.current[jobId];
  }, []);

  const dismissAnalysis = useCallback(() => {
    const current = loadTracked();
    if (current[0]) untrackJob(current[0].jobId);
    else setActiveJob(null);
  }, [untrackJob]);

  const trackJob = useCallback((jobId: number, projectGid: string, initial?: IssueIntelligenceJobData) => {
    setTracked([{ jobId, projectGid }]);
    saveTracked([{ jobId, projectGid }]);
    failCounts.current[jobId] = 0;
    if (initial) setActiveJob(initial);
    else {
      setActiveJob({
        id: jobId,
        status: "pending",
        tickets_total: 0,
        tickets_processed: 0,
        issues_found: 0,
        analysis_mode: "engineering_fix (rule-based)",
      });
    }
  }, []);

  const finishJob = useCallback(
    (job: IssueIntelligenceJobData, jobId: number) => {
      if (job.status === "completed") {
        success(
          "Analysis complete",
          `${job.tickets_total} tickets analysed — ${job.issues_found} recurring product issue${job.issues_found !== 1 ? "s" : ""} found.`
        );
        untrackJob(jobId);
        window.dispatchEvent(new CustomEvent(ISSUE_INTELLIGENCE_DONE_EVENT));
      } else if (job.status === "failed") {
        notifyError(
          "Analysis failed",
          job.error_message ?? "Could not complete issue intelligence analysis."
        );
        untrackJob(jobId);
        window.dispatchEvent(new CustomEvent(ISSUE_INTELLIGENCE_DONE_EVENT));
      }
    },
    [success, notifyError, untrackJob]
  );

  // On load, reconcile any job left in sessionStorage (e.g. after overnight / server restart)
  useEffect(() => {
    const stored = loadTracked();
    if (stored.length === 0) return;

    let cancelled = false;
    void (async () => {
      for (const t of stored) {
        try {
          const j = await api.getIssueIntelligenceJob(t.jobId);
          if (cancelled) return;
          setActiveJob(j);
          if (j.status === "completed" || j.status === "failed") {
            finishJob(j, t.jobId);
          }
        } catch {
          if (!cancelled) untrackJob(t.jobId);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [finishJob, untrackJob]);

  useEffect(() => {
    if (tracked.length === 0) return;

    let cancelled = false;

    const poll = async () => {
      const current = loadTracked();
      for (const t of current) {
        if (cancelled) return;
        try {
          const j = await api.getIssueIntelligenceJob(t.jobId);
          failCounts.current[t.jobId] = 0;
          setActiveJob(j);

          if (j.status === "completed" || j.status === "failed") {
            finishJob(j, t.jobId);
          }
        } catch {
          const n = (failCounts.current[t.jobId] ?? 0) + 1;
          failCounts.current[t.jobId] = n;
          if (n >= MAX_POLL_FAILURES) {
            notifyError(
              "Analysis status unknown",
              "Could not reach the server. Dismiss and run analysis again."
            );
            untrackJob(t.jobId);
          }
        }
      }
    };

    void poll();
    const id = window.setInterval(poll, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [tracked, finishJob, notifyError, untrackJob]);

  const isAnalyzing =
    activeJob?.status === "pending" || activeJob?.status === "running";

  return (
    <IssueIntelligenceContext.Provider
      value={{ trackJob, untrackJob, dismissAnalysis, activeJob, isAnalyzing }}
    >
      {children}
    </IssueIntelligenceContext.Provider>
  );
}

export function useIssueIntelligenceTracker() {
  const ctx = useContext(IssueIntelligenceContext);
  if (!ctx) throw new Error("useIssueIntelligenceTracker must be used within IssueIntelligenceProvider");
  return ctx;
}
