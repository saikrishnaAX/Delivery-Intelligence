import { useCallback, useState } from "react";
import { getBackendDevStatus, startBackendDev, waitForBackend } from "@/lib/dev-launcher";

export type BackendLauncherState = "idle" | "starting" | "running" | "failed";

export function useBackendLauncher(onReady?: () => void | Promise<void>) {
  const devAvailable = import.meta.env.DEV;
  const [state, setState] = useState<BackendLauncherState>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const start = useCallback(async () => {
    if (!devAvailable) return;

    setState("starting");
    setMessage("Starting backend on port 8003…");

    try {
      const status = await getBackendDevStatus();
      if (!status.running) {
        await startBackendDev();
      }

      const ready = await waitForBackend();
      if (!ready) {
        setState("failed");
        setMessage(
          "Backend did not respond in time. Check that Python is installed, then try again or run scripts/run-backend.cmd."
        );
        return;
      }

      setState("running");
      setMessage(null);
      await onReady?.();
    } catch (e) {
      setState("failed");
      setMessage(e instanceof Error ? e.message : "Failed to start backend");
    }
  }, [devAvailable, onReady]);

  return {
    devAvailable,
    state,
    message,
    start,
    isStarting: state === "starting",
  };
}
