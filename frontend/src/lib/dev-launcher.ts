export interface BackendDevStatus {
  running: boolean;
  port?: number;
  detail?: string;
  unavailable?: boolean;
}

export interface BackendStartResult {
  ok: boolean;
  status?: "running" | "starting";
  message?: string;
  error?: string;
  port?: number;
}

const DEV_BASE = "/__dev/backend";

export async function getBackendDevStatus(): Promise<BackendDevStatus> {
  if (!import.meta.env.DEV) return { running: false, unavailable: true };
  try {
    const res = await fetch(`${DEV_BASE}/status`);
    return (await res.json()) as BackendDevStatus;
  } catch {
    return { running: false, unavailable: true };
  }
}

export async function startBackendDev(): Promise<BackendStartResult> {
  if (!import.meta.env.DEV) {
    throw new Error("Backend launcher is only available in local dev mode.");
  }
  const res = await fetch(`${DEV_BASE}/start`, { method: "POST" });
  const body = (await res.json()) as BackendStartResult;
  if (!res.ok || !body.ok) {
    throw new Error(body.error || "Failed to start backend");
  }
  return body;
}

export async function waitForBackend(maxMs = 90_000, intervalMs = 1_500): Promise<boolean> {
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    const status = await getBackendDevStatus();
    if (status.running) return true;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return false;
}
