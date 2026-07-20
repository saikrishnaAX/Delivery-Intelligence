import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Eye, Mail, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useProject } from "@/hooks/use-project";
import { useNotifyHelpers } from "@/hooks/use-notify";
import { api } from "@/lib/api";
import type { CEOReportPreview, CEOReportSettings } from "@/types";
import { cn } from "@/lib/utils";

const PERIODS = [
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "6months", label: "6 Months" },
] as const;

export function CEOReportPanel() {
  const { projectGid } = useProject();
  const { success, error } = useNotifyHelpers();
  const [settings, setSettings] = useState<CEOReportSettings | null>(null);
  const [period, setPeriod] = useState<string>("weekly");
  const [email, setEmail] = useState("vijay@autorox.co");
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleFreq, setScheduleFreq] = useState<string>("weekly");
  const [sending, setSending] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<CEOReportPreview | null>(null);
  const [savingSchedule, setSavingSchedule] = useState(false);

  useEffect(() => {
    api.getCEOReportSettings().then((s) => {
      setSettings(s);
      setEmail(s.ceo_email || "vijay@autorox.co");
      setScheduleEnabled(s.schedule_enabled);
      setScheduleFreq(s.schedule_frequency || "weekly");
    }).catch(() => {});
  }, []);

  const sendReport = useCallback(async () => {
    if (!projectGid) {
      error("Select a project", "Choose an Asana project before sending the CEO report.");
      return;
    }
    setSending(true);
    try {
      const result = await api.sendCEOReport(projectGid, {
        period,
        recipient_emails: email.trim() ? [email.trim()] : [],
      });
      success(
        "Report sent",
        `Delivered to ${result.sent_to.join(", ")}`
      );
      setSettings((prev) => (prev ? { ...prev, last_sent_at: result.sent_at } : prev));
    } catch (err) {
      error("Send failed", err instanceof Error ? err.message : "Could not send CEO report.");
    } finally {
      setSending(false);
    }
  }, [projectGid, period, email, success, error]);

  const loadPreview = useCallback(async () => {
    if (!projectGid) {
      error("Select a project", "Choose an Asana project before previewing the CEO report.");
      return;
    }
    setPreviewing(true);
    setPreview(null);
    try {
      const result = await api.previewCEOReport(projectGid, period);
      setPreview(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not load email preview.";
      const status = err && typeof err === "object" && "status" in err ? (err as { status?: number }).status : undefined;
      const is404 = status === 404 || message.toLowerCase().includes("not found");
      error(
        "Preview failed",
        is404
          ? "Email preview API is unavailable. Restart the backend on port 8003, then try again."
          : message
      );
    } finally {
      setPreviewing(false);
    }
  }, [projectGid, period, error]);

  const saveSchedule = useCallback(async () => {
    setSavingSchedule(true);
    try {
      const updated = await api.updateCEOReportSettings({
        ceo_email: email.trim(),
        schedule_enabled: scheduleEnabled,
        schedule_frequency: scheduleFreq,
        schedule_project_gid: projectGid ?? undefined,
      });
      setSettings(updated);
      success(
        scheduleEnabled ? "Schedule saved" : "Schedule disabled",
        scheduleEnabled
          ? `Auto-send ${scheduleFreq} to ${updated.ceo_email}`
          : "Manual send only"
      );
    } catch (err) {
      error("Save failed", err instanceof Error ? err.message : "Could not update schedule.");
    } finally {
      setSavingSchedule(false);
    }
  }, [email, scheduleEnabled, scheduleFreq, projectGid, success, error]);

  const emailReady = settings?.email_configured !== false;
  const lastSent = settings?.last_sent_at
    ? new Date(settings.last_sent_at).toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "numeric",
        month: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : null;

  return (
    <div className="rounded-lg border border-border/50 bg-muted/10 px-4 py-3 mb-4 w-full">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-center gap-2 min-w-0 shrink-0">
          <Mail className="h-4 w-4 text-primary shrink-0" />
          <div>
            <p className="text-xs font-medium">Executive Brief</p>
            <p className="text-[10px] text-muted-foreground">
              Issue Intelligence: daily 5 PM IST (Cursor) · CEO email Tuesday when schedule on
              {settings?.cursor_configured ? " · Cursor AI" : " · add CURSOR_API_KEY for AI wording"}
            </p>
            <p className="text-[10px] text-muted-foreground mt-1">
              Dashboard below = raw facts · Email = interpreted brief (use Preview before send)
            </p>
          </div>
        </div>
        {lastSent && (
          <Badge variant="outline" className="text-[9px] font-normal w-fit lg:ml-auto">
            Last sent {lastSent}
          </Badge>
        )}
      </div>

      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPeriod(p.id)}
              className={cn(
                "text-[10px] px-2.5 py-1 rounded-md border transition-colors",
                period === p.id
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border/60 text-muted-foreground hover:text-foreground"
              )}
            >
              {p.label}
            </button>
          ))}
        </div>

        <Input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="CEO email"
          className="h-8 text-xs w-full sm:w-52 sm:max-w-xs"
        />

        <Button
          variant="outline"
          size="sm"
          className="h-8 text-xs gap-1.5"
          onClick={loadPreview}
          disabled={previewing || !projectGid}
        >
          <Eye className="h-3 w-3" />
          {previewing ? "Loading…" : "Preview email"}
        </Button>

        <Button
          size="sm"
          className="h-8 text-xs gap-1.5"
          onClick={sendReport}
          disabled={sending || !emailReady}
        >
          <Send className="h-3 w-3" />
          {sending ? "Sending…" : "Send Executive Brief"}
        </Button>
      </div>

      {preview && (
        <div className="mt-4 rounded-lg border border-border/60 overflow-hidden bg-background">
          <div className="px-3 py-2.5 border-b border-border/40 bg-muted/30 flex flex-wrap items-center gap-2 text-[10px]">
            <span className="font-medium text-foreground">Preview: {preview.subject}</span>
            <Badge variant="outline" className="text-[9px] font-normal">
              {preview.period_label} · {preview.date_from} → {preview.date_to}
            </Badge>
            <Badge variant="secondary" className="text-[9px] font-normal">
              {preview.narrative_source === "cursor_weekly" ? "Cursor AI narrative" : "Rules-based narrative"}
            </Badge>
            <span className="text-muted-foreground ml-auto">Health {preview.health_score}/100</span>
          </div>
          <p className="px-3 py-2 text-[10px] text-muted-foreground border-b border-border/30">
            {preview.dashboard_note}
          </p>
          <iframe
            title="CEO executive brief email preview"
            srcDoc={preview.html}
            className="w-full h-[min(70vh,720px)] border-0 bg-white"
            sandbox=""
          />
        </div>
      )}

      {!emailReady && (
        <p className="text-[10px] text-amber-500 mt-2">
          Gmail not configured — set GMAIL_USER and GMAIL_APP_PASSWORD in .env to enable email.
        </p>
      )}

      <div className="mt-3 pt-3 border-t border-border/30 flex flex-wrap items-center gap-3">
        <CalendarClock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={scheduleEnabled}
            onChange={(e) => setScheduleEnabled(e.target.checked)}
            className="rounded border-border"
          />
          Auto-send
        </label>
        <select
          value={scheduleFreq}
          onChange={(e) => setScheduleFreq(e.target.value)}
          disabled={!scheduleEnabled}
          className="h-7 text-[10px] rounded-md border border-border/60 bg-background px-2 disabled:opacity-50"
        >
          <option value="weekly">Every Tuesday</option>
          <option value="monthly">1st of each month</option>
          <option value="6months">Jan 1 & Jul 1</option>
        </select>
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-[10px]"
          onClick={saveSchedule}
          disabled={savingSchedule}
        >
          {savingSchedule ? "Saving…" : "Save schedule"}
        </Button>
      </div>
    </div>
  );
}
