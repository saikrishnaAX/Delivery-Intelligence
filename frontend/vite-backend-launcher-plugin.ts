import { spawn, execSync } from "node:child_process";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";

const BACKEND_PORT = 8003;
const BACKEND_HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/health`;

let launchInProgress = false;
let lastLaunchAt = 0;

function checkBackend(): Promise<{ running: boolean; detail?: string }> {
  return new Promise((resolve) => {
    const req = http.get(BACKEND_HEALTH_URL, { timeout: 2500 }, (res) => {
      res.resume();
      resolve({ running: res.statusCode === 200 });
    });
    req.on("timeout", () => {
      req.destroy();
      resolve({ running: false, detail: "timed out" });
    });
    req.on("error", (e) => {
      resolve({ running: false, detail: e.message });
    });
  });
}

function freePort(port: number) {
  if (process.platform === "win32") {
    try {
      execSync(
        `powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"`,
        { stdio: "ignore" }
      );
    } catch {
      // Port may already be free.
    }
    return;
  }

  try {
    execSync(`lsof -ti:${port} | xargs kill -9 2>/dev/null`, { stdio: "ignore", shell: true });
  } catch {
    // Port may already be free.
  }
}

function spawnBackend(backendDir: string): number | undefined {
  const python = process.platform === "win32" ? "python" : "python3";
  const child = spawn(
    python,
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    {
      cwd: backendDir,
      detached: true,
      stdio: "ignore",
      windowsHide: true,
      shell: process.platform === "win32",
      env: { ...process.env },
    }
  );
  child.unref();
  return child.pid;
}

function sendJson(res: import("http").ServerResponse, status: number, body: unknown) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(body));
}

/** Dev-only routes to start the FastAPI backend from the Vite dev server. */
export function backendLauncherPlugin(): Plugin {
  const repoRoot = path.resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
  const backendDir = path.join(repoRoot, "backend");

  return {
    name: "backend-launcher",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        const url = req.url?.split("?")[0] ?? "";
        if (!url.startsWith("/__dev/backend")) return next();

        if (req.method === "GET" && url === "/__dev/backend/status") {
          const status = await checkBackend();
          if (status.running) launchInProgress = false;
          sendJson(res, 200, { ...status, port: BACKEND_PORT });
          return;
        }

        if (req.method === "POST" && url === "/__dev/backend/start") {
          const now = Date.now();
          const current = await checkBackend();
          if (current.running) {
            launchInProgress = false;
            sendJson(res, 200, {
              ok: true,
              status: "running",
              message: "Backend is already running",
              port: BACKEND_PORT,
            });
            return;
          }

          if (launchInProgress && now - lastLaunchAt < 60_000) {
            sendJson(res, 200, {
              ok: true,
              status: "starting",
              message: "Backend launch already in progress",
              port: BACKEND_PORT,
            });
            return;
          }

          launchInProgress = true;
          lastLaunchAt = now;
          try {
            freePort(BACKEND_PORT);
            const pid = spawnBackend(backendDir);
            sendJson(res, 200, {
              ok: true,
              status: "starting",
              pid,
              port: BACKEND_PORT,
              message: "Backend process started",
            });
          } catch (e) {
            launchInProgress = false;
            sendJson(res, 500, {
              ok: false,
              error: e instanceof Error ? e.message : "Failed to start backend",
            });
          }
          return;
        }

        sendJson(res, 404, { ok: false, error: "Not found" });
      });
    },
  };
}
