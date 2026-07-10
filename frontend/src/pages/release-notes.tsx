import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Download, RefreshCw, Mail, X, Info, Archive, Upload } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { EmptyState } from "@/components/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useProject } from "@/hooks/use-project";
import { readCache, buildScope } from "@/lib/data-cache";
import { refreshCached } from "@/lib/fetch-with-cache";
import {
  archiveScope,
  isArchiveScopeHydrated,
  markArchiveScopeHydrated,
  readArchiveCache,
  writeArchiveCache,
} from "@/lib/archive-store";
import type { ReleaseNoteItem, ReleaseNotesData, TeamData, ReleaseNoteArchive } from "@/types";
import { cn } from "@/lib/utils";
import { DatePicker } from "@/components/date-picker";

const LOOKBACK_OPTIONS = [
  { value: 1, label: "Today" },
  { value: 2, label: "Last 2 days" },
  { value: 7, label: "Last 7 days" },
] as const;

const SECTION_ORDER = ["enhancement", "security", "performance", "bug"] as const;

const SECTION_META: Record<string, { label: string; accent: string }> = {
  enhancement: { label: "Product improvements", accent: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  security: { label: "Security", accent: "bg-violet-500/15 text-violet-700 dark:text-violet-300" },
  performance: { label: "Performance", accent: "bg-sky-500/15 text-sky-700 dark:text-sky-300" },
  bug: { label: "Issues resolved", accent: "bg-amber-500/15 text-amber-800 dark:text-amber-200" },
};

function ExecutiveReleaseView({ data }: { data: ReleaseNotesData }) {
  const summary = data.executive_summary;
  const docTitle = data.document_title ?? `Product Release — ${data.release_date}`;

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden border-border/80 bg-gradient-to-br from-card via-card to-primary/5">
        <CardContent className="py-6 px-5 sm:px-8 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2 max-w-2xl">
              <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground font-medium">
                Executive release brief
              </p>
              <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight leading-tight">{docTitle}</h2>
              <p className="text-sm text-muted-foreground">
                {summary?.headline ?? `${data.total_items} items`} · {data.release_date}
              </p>
              {summary?.subheadline && (
                <p className="text-sm text-foreground/90 leading-relaxed">{summary.subheadline}</p>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 min-w-[240px]">
              {SECTION_ORDER.map((key) => {
                const count = data.sections[key]?.length ?? 0;
                if (!count) return null;
                const meta = SECTION_META[key];
                return (
                  <div key={key} className="rounded-lg border border-border/60 bg-background/70 px-3 py-2.5">
                    <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{meta.label}</p>
                    <p className="text-xl font-semibold mt-0.5">{count}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {summary?.highlights && summary.highlights.length > 0 && (
            <div className="rounded-lg border border-border/60 bg-background/50 p-4">
              <p className="text-xs font-semibold mb-3">Key highlights</p>
              <ul className="space-y-2">
                {summary.highlights.map((h, i) => (
                  <li key={i} className="text-sm leading-snug">
                    <span className={cn("inline-block text-[10px] font-medium px-1.5 py-0.5 rounded mr-2", SECTION_META[h.category || "enhancement"]?.accent)}>
                      {SECTION_META[h.category || "enhancement"]?.label}
                    </span>
                    <span className="font-medium">{h.title}</span>
                    {h.benefit && <span className="text-muted-foreground"> — {h.benefit}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {SECTION_ORDER.map((key) => {
        const items = data.sections[key] ?? [];
        if (items.length === 0) return null;
        const meta = SECTION_META[key];
        return (
          <Card key={key} className="border-border/70">
            <CardContent className="py-4 px-4 sm:px-5 space-y-3">
              <div className="flex items-center gap-2">
                <span className={cn("text-[10px] font-semibold uppercase tracking-wide px-2 py-1 rounded", meta.accent)}>
                  {meta.label}
                </span>
                <span className="text-xs text-muted-foreground">{items.length} item{items.length !== 1 ? "s" : ""}</span>
              </div>
              <div className="space-y-3">
                {items.map((item) => (
                  <ReleaseItemCard key={item.ticket_id} item={item} isBug={key === "bug"} />
                ))}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function ReleaseItemCard({ item, isBug }: { item: ReleaseNoteItem; isBug: boolean }) {
  const benefit = item.impact_benefit || item.impact || item.summary;
  return (
    <div className="rounded-lg border border-border/50 bg-muted/10 px-4 py-3">
      <p className="text-sm font-semibold leading-snug">{item.title}</p>
      {isBug ? (
        <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
          <span className="font-medium text-foreground">Resolution: </span>
          {item.fix || item.summary}
        </p>
      ) : (
        <>
          {benefit && (
            <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
              <span className="font-medium text-foreground">Impact: </span>
              {benefit}
            </p>
          )}
          {(item.whats_new?.length ?? 0) > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-muted-foreground list-disc pl-4">
              {item.whats_new.slice(0, 4).map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

function WorkshopAnnouncementPanel({
  projectGid,
  sprintName,
  queryOpts,
  canSend,
  totalItems,
}: {
  projectGid: string | null;
  sprintName: string;
  queryOpts: () => { lookbackDays?: number; dateFrom?: string; dateTo?: string; sprintName: string };
  canSend: boolean;
  totalItems: number;
}) {
  const [audience, setAudience] = useState<"all" | "bosch" | "standard">("all");
  const [counts, setCounts] = useState<Record<string, { total: number; with_email: number }>>({});
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.getWorkshopAudienceCounts().then(setCounts).catch(() => setCounts({}));
  }, []);

  const selected = counts[audience] ?? { total: 0, with_email: 0 };

  const createDrafts = async () => {
    if (!projectGid) return;
    setCreating(true);
    setMessage(null);
    setError(null);
    try {
      const opts = queryOpts();
      const result = await api.createWorkshopReleaseDrafts(projectGid, {
        sprint_name: sprintName,
        lookback_days: opts.lookbackDays,
        date_from: opts.dateFrom,
        date_to: opts.dateTo,
        audience,
      });
      setMessage(
        `Created ${result.created} workshop email draft${result.created !== 1 ? "s" : ""}` +
          (result.skipped_no_email ? ` (${result.skipped_no_email} skipped — no workshop mail on file)` : "")
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create drafts");
    } finally {
      setCreating(false);
    }
  };

  return (
    <Card className="border-primary/25 bg-primary/[0.03]">
      <CardContent className="py-4 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Workshop release announcements</h3>
            <p className="text-[11px] text-muted-foreground mt-1 max-w-xl">
              Send this release to workshops after sprint planning — all garages, Bosch network only, or general workshops.
              Drafts are created for human review; nothing is sent automatically.
            </p>
          </div>
          <Link to="/workshop-emails" className="text-[11px] text-primary hover:underline shrink-0">
            Review drafts →
          </Link>
        </div>

        <div className="flex flex-wrap gap-2">
          {(["all", "bosch", "standard"] as const).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setAudience(key)}
              className={cn(
                "rounded-md border px-3 py-2 text-left min-w-[140px] transition-colors",
                audience === key ? "border-primary bg-primary/10" : "border-border hover:bg-muted/30"
              )}
            >
              <p className="text-xs font-medium capitalize">{key === "all" ? "All workshops" : key === "bosch" ? "Bosch network" : "General workshops"}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {(counts[key]?.with_email ?? 0).toLocaleString()} with email · {(counts[key]?.total ?? 0).toLocaleString()} total
              </p>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            className="h-8 text-xs"
            disabled={!canSend || !projectGid || creating || selected.with_email === 0}
            onClick={() => void createDrafts()}
          >
            <Mail className="h-3.5 w-3.5 mr-1" />
            {creating ? "Creating drafts…" : `Create ${selected.with_email.toLocaleString()} draft${selected.with_email !== 1 ? "s" : ""}`}
          </Button>
          {!canSend && (
            <span className="text-[10px] text-muted-foreground">Load release items first ({totalItems} in window).</span>
          )}
        </div>

        {message && <p className="text-[11px] text-emerald-600 dark:text-emerald-400">{message}</p>}
        {error && <p className="text-[11px] text-destructive">{error}</p>}
      </CardContent>
    </Card>
  );
}

function isoDate(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function yesterdayIso() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return isoDate(d);
}

function SendEmailModal({
  open,
  onClose,
  teams,
  emailConfigured,
  sending,
  onSend,
  title = "Send release notes email",
  description = "The same Word document shown in the preview will be attached to the email.",
}: {
  open: boolean;
  onClose: () => void;
  teams: TeamData[];
  emailConfigured: boolean;
  sending: boolean;
  onSend: (personIds: number[], teamIds: number[], excludedPersonIds: number[]) => void;
  title?: string;
  description?: string;
}) {
  const [selectedTeamIds, setSelectedTeamIds] = useState<number[]>([]);
  const [checkedPersonIds, setCheckedPersonIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!open) {
      setSelectedTeamIds([]);
      setCheckedPersonIds(new Set());
    }
  }, [open]);

  const toggleTeam = (team: TeamData) => {
    const isSelected = selectedTeamIds.includes(team.id);
    if (isSelected) {
      setSelectedTeamIds((prev) => prev.filter((id) => id !== team.id));
      setCheckedPersonIds((prev) => {
        const next = new Set(prev);
        team.members.forEach((m) => next.delete(m.person.id));
        return next;
      });
    } else {
      setSelectedTeamIds((prev) => [...prev, team.id]);
      setCheckedPersonIds((prev) => {
        const next = new Set(prev);
        team.members.forEach((m) => next.add(m.person.id));
        return next;
      });
    }
  };

  const togglePerson = (personId: number) => {
    setCheckedPersonIds((prev) => {
      const next = new Set(prev);
      if (next.has(personId)) next.delete(personId);
      else next.add(personId);
      return next;
    });
  };

  const selectedTeams = teams.filter((t) => selectedTeamIds.includes(t.id));
  const recipientCount = checkedPersonIds.size;

  const handleSend = () => {
    const excluded: number[] = [];
    selectedTeams.forEach((team) => {
      team.members.forEach((m) => {
        if (!checkedPersonIds.has(m.person.id)) excluded.push(m.person.id);
      });
    });
    onSend(Array.from(checkedPersonIds), selectedTeamIds, excluded);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button type="button" className="absolute inset-0 bg-black/60" aria-label="Close" onClick={onClose} />
      <div className="relative w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button type="button" onClick={onClose} className="p-1 rounded hover:bg-muted">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          <p className="text-[10px] text-muted-foreground">{description}</p>

          {!emailConfigured && (
            <Card className="border-warning/40 bg-warning/5">
              <CardContent className="py-2.5 text-[10px] space-y-1">
                <p className="font-medium flex items-center gap-1">
                  <Info className="h-3.5 w-3.5" /> Gmail not configured
                </p>
                <p className="text-muted-foreground">
                  Add <code className="text-[9px]">GMAIL_USER</code> and{" "}
                  <code className="text-[9px]">GMAIL_APP_PASSWORD</code> to your backend{" "}
                  <code className="text-[9px]">.env</code> file. Use a Google App Password
                  (not your login password) for the account that should send mail.
                </p>
              </CardContent>
            </Card>
          )}

          {teams.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No teams found. Add teams under People & Workshops first.
            </p>
          ) : (
            <div className="space-y-2">
              <p className="text-[10px] font-medium">Select teams</p>
              {teams.map((team) => {
                const teamOn = selectedTeamIds.includes(team.id);
                return (
                  <div key={team.id} className="rounded-md border border-border/60">
                    <label className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-muted/20">
                      <input
                        type="checkbox"
                        checked={teamOn}
                        onChange={() => toggleTeam(team)}
                        className="rounded"
                      />
                      <span className="text-[11px] font-medium">{team.name}</span>
                      <Badge variant="outline" className="text-[9px] ml-auto">
                        {team.members.length} member{team.members.length !== 1 ? "s" : ""}
                      </Badge>
                    </label>
                    {teamOn && team.members.length > 0 && (
                      <div className="border-t border-border/40 px-3 py-2 space-y-1.5 bg-muted/10">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-wide">
                          Uncheck anyone to exclude
                        </p>
                        {team.members.map((m) => (
                          <label
                            key={m.person.id}
                            className="flex items-center gap-2 text-[10px] cursor-pointer pl-2"
                          >
                            <input
                              type="checkbox"
                              checked={checkedPersonIds.has(m.person.id)}
                              onChange={() => togglePerson(m.person.id)}
                              className="rounded"
                            />
                            <span>{m.person.name}</span>
                            {m.person.role && (
                              <span className="text-muted-foreground">· {m.person.role}</span>
                            )}
                            {m.is_lead && (
                              <Badge className="text-[8px] px-1 py-0">Lead</Badge>
                            )}
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="border-t border-border/60 px-4 py-3 flex items-center justify-between gap-2">
          <p className="text-[10px] text-muted-foreground">
            {recipientCount} recipient{recipientCount !== 1 ? "s" : ""} selected
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={onClose} className="h-8 text-[10px]">
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSend}
              disabled={sending || !emailConfigured || recipientCount === 0}
              className="h-8 text-[10px]"
            >
              {sending ? "Sending…" : "Send email"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ReleaseNotesHistory({
  projectGid,
  teams,
  emailConfigured,
}: {
  projectGid: string | null;
  teams: TeamData[];
  emailConfigured: boolean;
}) {
  const scope = archiveScope(projectGid);
  const [archives, setArchives] = useState<ReleaseNoteArchive[]>(
    () => readArchiveCache(scope) ?? []
  );
  const [uploadDate, setUploadDate] = useState(isoDate(new Date()));
  const [uploadTitle, setUploadTitle] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [messageIsError, setMessageIsError] = useState(false);
  const [sendArchive, setSendArchive] = useState<ReleaseNoteArchive | null>(null);
  const [sendingArchive, setSendingArchive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isArchiveScopeHydrated(scope)) {
      setArchives(readArchiveCache(scope) ?? []);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const rows = await api.getReleaseNoteArchives(projectGid);
        if (cancelled) return;
        markArchiveScopeHydrated(scope, rows);
        setArchives(rows);
      } catch {
        if (!cancelled) markArchiveScopeHydrated(scope, []);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scope, projectGid]);

  const onUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!uploadDate) {
      setMessage("Select a release date first");
      setMessageIsError(true);
      e.target.value = "";
      return;
    }

    const tempId = -Date.now();
    const title = uploadTitle.trim() || file.name.replace(/\.[^.]+$/, "");
    const optimistic: ReleaseNoteArchive = {
      id: tempId,
      release_date: uploadDate,
      title,
      original_filename: file.name,
      file_size: file.size,
      source: "upload",
      created_at: new Date().toISOString(),
      pending: true,
    };

    setArchives((prev) => {
      const next = [optimistic, ...prev];
      writeArchiveCache(scope, next);
      return next;
    });
    setMessage(`"${file.name}" saved — uploading in background`);
    setMessageIsError(false);
    setUploadTitle("");

    void (async () => {
      try {
        const saved = await api.uploadReleaseNoteArchive(projectGid, uploadDate, file, { title });
        setArchives((prev) => {
          const next = [saved, ...prev.filter((r) => r.id !== tempId)];
          writeArchiveCache(scope, next);
          return next;
        });
        setMessage(`"${file.name}" uploaded`);
        setMessageIsError(false);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : "Upload failed";
        setArchives((prev) =>
          prev.map((r) =>
            r.id === tempId ? { ...r, pending: false, uploadError: errMsg } : r
          )
        );
        setMessage(errMsg);
        setMessageIsError(true);
      }
    })();

    e.target.value = "";
  };

  const sendArchiveEmail = async (
    personIds: number[],
    teamIds: number[],
    excludedPersonIds: number[]
  ) => {
    if (!sendArchive || sendArchive.id < 0) return;
    setSendingArchive(true);
    setMessage(null);
    try {
      const result = await api.sendReleaseNoteArchive(sendArchive.id, {
        team_ids: teamIds,
        person_ids: personIds,
        excluded_person_ids: excludedPersonIds,
      });
      setMessage(`Emailed to ${result.recipient_count} recipient(s)`);
      setMessageIsError(false);
      setSendArchive(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Send failed");
      setMessageIsError(true);
    } finally {
      setSendingArchive(false);
    }
  };

  const downloadArchive = async (row: ReleaseNoteArchive) => {
    const blob = await api.downloadReleaseNoteArchive(row.id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = row.original_filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
    } catch {
      return iso;
    }
  };

  return (
    <section className="space-y-3 pt-4 border-t border-border">
      <div className="flex items-center gap-2">
        <Archive className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">Release notes history</h2>
      </div>
      <p className="text-[10px] text-muted-foreground">
        Upload past release notes (.docx or .pdf) to keep a searchable archive and re-share from here.
      </p>

      <Card>
        <CardContent className="py-3 space-y-2">
          <div className="flex flex-wrap items-end gap-2">
            <div className="space-y-1">
              <label className="text-[10px] text-muted-foreground font-medium">Release date</label>
              <DatePicker
                value={uploadDate}
                onChange={setUploadDate}
                className="h-8 w-[160px] text-xs"
              />
            </div>
            <div className="space-y-1 flex-1 min-w-[160px]">
              <label className="text-[10px] text-muted-foreground font-medium">Title (optional)</label>
              <Input value={uploadTitle} onChange={(e) => setUploadTitle(e.target.value)} placeholder="e.g. June 2026 release" className="h-8 text-xs" />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[10px] text-transparent select-none">.</span>
              <input
                ref={fileInputRef}
                type="file"
                accept=".docx,.doc,.pdf,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                onChange={onUpload}
              />
              <Button
                type="button"
                size="sm"
                className="h-8 text-[10px]"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-3 w-3 mr-1" />
                Upload document
              </Button>
            </div>
          </div>
          {message && (
            <p className={cn("text-[10px]", messageIsError ? "text-destructive" : "text-success")}>
              {message}
            </p>
          )}
        </CardContent>
      </Card>

      {archives.length === 0 ? (
        <p className="text-[10px] text-muted-foreground">No archived documents yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full border-collapse text-[11px]">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="px-3 py-2 text-left text-[10px] font-medium text-muted-foreground">Release date</th>
                <th className="px-3 py-2 text-left text-[10px] font-medium text-muted-foreground">Title</th>
                <th className="px-3 py-2 text-left text-[10px] font-medium text-muted-foreground">File</th>
                <th className="px-3 py-2 text-left text-[10px] font-medium text-muted-foreground w-44" />
              </tr>
            </thead>
            <tbody>
              {archives.map((row) => (
                <tr key={row.id} className="border-t border-border/50 hover:bg-muted/15">
                  <td className="px-3 py-2">{formatDate(row.release_date)}</td>
                  <td className="px-3 py-2 font-medium">
                    {row.title || "—"}
                    {row.pending && (
                      <Badge variant="outline" className="ml-1.5 text-[8px] px-1 py-0">Uploading…</Badge>
                    )}
                    {row.uploadError && (
                      <span className="block text-[9px] text-destructive mt-0.5">{row.uploadError}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{row.original_filename}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-[10px]"
                        disabled={row.pending || !!row.uploadError || row.id < 0}
                        onClick={() => downloadArchive(row)}
                      >
                        <Download className="h-3 w-3 mr-1" /> Download
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-[10px]"
                        disabled={row.pending || !!row.uploadError || row.id < 0 || !emailConfigured}
                        onClick={() => setSendArchive(row)}
                      >
                        <Mail className="h-3 w-3 mr-1" /> Send email
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <SendEmailModal
        open={!!sendArchive}
        onClose={() => setSendArchive(null)}
        teams={teams}
        emailConfigured={emailConfigured}
        sending={sendingArchive}
        onSend={sendArchiveEmail}
        title="Email archived release notes"
        description={`The saved document "${sendArchive?.title || sendArchive?.original_filename || ""}" will be attached.`}
      />
    </section>
  );
}

export default function ReleaseNotesPage() {
  const { projectGid, projects, cacheVersion, integrationStatus } = useProject();
  const [filterMode, setFilterMode] = useState<"lookback" | "custom">("lookback");
  const [lookbackDays, setLookbackDays] = useState(2);
  const [dateFrom, setDateFrom] = useState(yesterdayIso);
  const [dateTo, setDateTo] = useState(yesterdayIso);
  const [sprintName, setSprintName] = useState(
    () => `${new Date().toLocaleString("en-US", { month: "long" })} Sprint`
  );
  const [data, setData] = useState<ReleaseNotesData | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendMessage, setSendMessage] = useState<string | null>(null);
  const [teams, setTeams] = useState<TeamData[]>([]);
  const [sendModalOpen, setSendModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailConfigured = integrationStatus?.email_configured ?? false;

  useEffect(() => {
    api.getTeams().then(setTeams).catch(() => setTeams([]));
  }, [cacheVersion]);

  const queryOpts = useCallback(() => {
    if (filterMode === "custom" && dateFrom && dateTo) {
      return { dateFrom, dateTo, sprintName };
    }
    return { lookbackDays, sprintName };
  }, [filterMode, dateFrom, dateTo, lookbackDays, sprintName]);

  const cacheScope = buildScope([
    projectGid,
    filterMode,
    String(lookbackDays),
    dateFrom,
    dateTo,
    sprintName,
  ]);

  const loadNotes = useCallback(() => {
    if (!projectGid) {
      setData(null);
      return;
    }
    if (filterMode === "custom" && dateFrom && dateTo && dateFrom > dateTo) {
      setError("Start date must be on or before end date.");
      setData(null);
      return;
    }
    const cached = readCache<ReleaseNotesData>("release-notes", cacheScope);
    if (cached) setData(cached);
    else setLoading(true);
    setError(null);
    void refreshCached(
      "release-notes",
      cacheScope,
      () => api.getReleaseNotes(projectGid, queryOpts()),
      setData
    ).catch((err) => {
      if (!readCache<ReleaseNotesData>("release-notes", cacheScope)) {
        setError(err instanceof Error ? err.message : "Failed to load release notes");
        setData(null);
      }
    }).finally(() => setLoading(false));
  }, [projectGid, queryOpts, cacheScope, filterMode, dateFrom, dateTo]);

  useEffect(() => {
    void loadNotes();
  }, [loadNotes]);

  useEffect(() => {
    if (cacheVersion === 0 || !projectGid) return;
    void refreshCached(
      "release-notes",
      cacheScope,
      () => api.getReleaseNotes(projectGid, queryOpts()),
      setData
    );
  }, [cacheVersion, projectGid, queryOpts, cacheScope]);

  const canSendOrDownload = Boolean(data && data.total_items > 0);

  const handleDownload = async () => {
    if (!projectGid || !data) return;
    setDownloading(true);
    try {
      const blob = await api.downloadReleaseNotes(projectGid, queryOpts());
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${data.document_title ?? `Release Notes ${data.release_date}`}.docx`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  };

  const handleSend = async (
    personIds: number[],
    teamIds: number[],
    excludedPersonIds: number[]
  ) => {
    if (!projectGid || !data) return;
    if (data.total_items === 0) {
      setError("No release items in the selected window — adjust the date range or sync from Asana.");
      return;
    }
    setSending(true);
    setSendMessage(null);
    setError(null);
    try {
      const opts = queryOpts();
      const result = await api.sendReleaseNotes(projectGid, {
        sprint_name: sprintName,
        lookback_days: opts.lookbackDays,
        date_from: opts.dateFrom,
        date_to: opts.dateTo,
        team_ids: teamIds,
        person_ids: personIds,
        excluded_person_ids: excludedPersonIds,
      });
      setSendMessage(
        `Release notes sent to ${result.recipient_count} recipient${result.recipient_count !== 1 ? "s" : ""} (${result.item_count} items in document)`
      );
      setSendModalOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Send failed");
    } finally {
      setSending(false);
    }
  };

  return (
    <PageLayout page="release-notes">
      <Header
        title="Release Notes"
        description="Executive-ready release briefs and workshop announcements for sprint planning"
      />
      <div className="page-content space-y-3">
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <label className="text-[10px] text-muted-foreground font-medium">Sprint label</label>
            <Input
              value={sprintName}
              onChange={(e) => setSprintName(e.target.value)}
              className="h-8 w-40 text-xs"
              title="Used in email subject and sprint sheet enrichment"
            />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-muted-foreground font-medium">Released window</label>
            <div className="flex rounded-md border border-border overflow-hidden">
              {LOOKBACK_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => {
                    setFilterMode("lookback");
                    setLookbackDays(opt.value);
                  }}
                  className={cn(
                    "px-2.5 py-1.5 text-[10px] font-medium transition-colors",
                    filterMode === "lookback" && lookbackDays === opt.value
                      ? "bg-primary text-primary-foreground"
                      : "bg-card text-muted-foreground hover:text-foreground"
                  )}
                >
                  {opt.label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setFilterMode("custom")}
                className={cn(
                  "px-2.5 py-1.5 text-[10px] font-medium transition-colors border-l border-border",
                  filterMode === "custom"
                    ? "bg-primary text-primary-foreground"
                    : "bg-card text-muted-foreground hover:text-foreground"
                )}
              >
                Custom dates
              </button>
            </div>
          </div>
          {filterMode === "custom" && (
            <div className="flex flex-wrap items-end gap-2">
              <div className="space-y-1">
                <label className="text-[10px] text-muted-foreground font-medium">From</label>
                <DatePicker value={dateFrom} onChange={setDateFrom} className="h-8 w-[150px] text-xs" placeholder="From date" />
              </div>
              <div className="space-y-1">
                <label className="text-[10px] text-muted-foreground font-medium">To</label>
                <DatePicker value={dateTo} onChange={setDateTo} className="h-8 w-[150px] text-xs" placeholder="To date" />
              </div>
              <Button variant="outline" size="sm" className="h-8 text-[10px]" onClick={() => { const y = yesterdayIso(); setDateFrom(y); setDateTo(y); }}>
                Yesterday
              </Button>
            </div>
          )}
          <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={() => loadNotes()} disabled={loading || !projectGid}>
            <RefreshCw className={cn("h-3 w-3 mr-1", loading && "animate-spin")} />
            Refresh
          </Button>
          <Button size="sm" className="h-7 text-[10px]" onClick={handleDownload} disabled={downloading || !canSendOrDownload}>
            <Download className="h-3 w-3 mr-1" />
            {downloading ? "Preparing…" : "Save Word doc"}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="h-7 text-[10px]"
            onClick={() => setSendModalOpen(true)}
            disabled={!canSendOrDownload}
          >
            <Mail className="h-3 w-3 mr-1" />
            Send email
          </Button>
        </div>

        {sendMessage && (
          <Card className="border-success/30">
            <CardContent className="py-2 text-[11px] text-success">{sendMessage}</CardContent>
          </Card>
        )}

        {!projectGid && (
          <EmptyState title="Select a project" description="Choose Sprint planning from the top bar to generate release notes." />
        )}

        {error && (
          <Card className="border-destructive/30">
            <CardContent className="py-2 text-[11px] text-destructive">{error}</CardContent>
          </Card>
        )}

        {projectGid && loading && !data && <LoadingState />}

        {data && (
          <>
            {data.total_items === 0 ? (
              <EmptyState
                title="No releases in this window"
                description={`No tickets were moved to "${data.released_section}" during the selected period.`}
              />
            ) : (
              <>
                <ExecutiveReleaseView data={data} />
                <WorkshopAnnouncementPanel
                  projectGid={projectGid}
                  sprintName={sprintName}
                  queryOpts={queryOpts}
                  canSend={canSendOrDownload}
                  totalItems={data.total_items}
                />
              </>
            )}
          </>
        )}
      </div>

      <ReleaseNotesHistory projectGid={projectGid} teams={teams} emailConfigured={emailConfigured} />

      <SendEmailModal
        open={sendModalOpen}
        onClose={() => setSendModalOpen(false)}
        teams={teams}
        emailConfigured={emailConfigured}
        sending={sending}
        onSend={handleSend}
      />
    </PageLayout>
  );
}
