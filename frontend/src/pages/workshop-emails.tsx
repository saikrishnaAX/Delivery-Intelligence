import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Mail, Send, X } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { EmptyState } from "@/components/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useNotifyHelpers } from "@/hooks/use-notify";
import type { WorkshopEmailDraft } from "@/types";
import { cn } from "@/lib/utils";

function releaseSnapshot(draft: WorkshopEmailDraft) {
  const snap = draft.ticket_snapshot as {
    sprint_name?: string;
    release_date?: string;
    total_items?: number;
    audience?: string;
  };
  return snap;
}

export default function WorkshopEmailsPage() {
  const { success, error: notifyError } = useNotifyHelpers();
  const [drafts, setDrafts] = useState<WorkshopEmailDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<WorkshopEmailDraft | null>(null);
  const [subject, setSubject] = useState("");
  const [bodyText, setBodyText] = useState("");
  const [toEmails, setToEmails] = useState("");
  const [ccEmails, setCcEmails] = useState("");
  const [sending, setSending] = useState(false);
  const [filter, setFilter] = useState<"pending" | "sent" | "cancelled">("pending");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDrafts(await api.getWorkshopEmailDrafts(filter));
    } catch (err) {
      notifyError("Could not load drafts", err instanceof Error ? err.message : "Try again");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- notifyError is stable via useNotifyHelpers
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  const openDraft = (draft: WorkshopEmailDraft) => {
    setSelected(draft);
    setSubject(draft.subject);
    setBodyText(draft.body_text);
    setToEmails((draft.to_emails || []).join(", "));
    setCcEmails((draft.cc_emails || []).join(", "));
  };

  const saveEdits = async () => {
    if (!selected) return;
    try {
      const updated = await api.updateWorkshopEmailDraft(selected.id, {
        subject,
        body_text: bodyText,
        to_emails: toEmails.split(/[,;]/).map((e) => e.trim()).filter(Boolean),
        cc_emails: ccEmails.split(/[,;]/).map((e) => e.trim()).filter(Boolean),
      });
      setSelected(updated);
      setDrafts((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
      success("Draft updated", "Review and send when ready.");
    } catch (err) {
      notifyError("Save failed", err instanceof Error ? err.message : "Could not update draft");
    }
  };

  const sendDraft = async () => {
    if (!selected) return;
    setSending(true);
    try {
      await saveEdits();
      const sent = await api.sendWorkshopEmailDraft(selected.id);
      success("Email sent", `Delivered to ${sent.workshop_name || "workshop"}`);
      setSelected(null);
      await load();
    } catch (err) {
      notifyError("Send failed", err instanceof Error ? err.message : "Could not send email");
    } finally {
      setSending(false);
    }
  };

  const cancelDraft = async () => {
    if (!selected) return;
    try {
      await api.cancelWorkshopEmailDraft(selected.id);
      setSelected(null);
      await load();
      success("Draft dismissed", "This email will not be sent.");
    } catch (err) {
      notifyError("Cancel failed", err instanceof Error ? err.message : "Could not cancel draft");
    }
  };

  const snapshot = selected ? releaseSnapshot(selected) : undefined;

  return (
    <PageLayout
      page="workshop-emails"
      pageInfo={{
        title: "Workshop Releases",
        description:
          "Release announcement drafts for workshops. Create them from Release Notes at sprint planning, " +
          "then review and send here. Support person and support head are CC'd.",
      }}
    >
      <Header
        title="Workshop Releases"
        description="Sprint release emails to workshops — human review required before send"
      />

      <div className="page-content space-y-4">
        <Card className="border-border/70 bg-muted/10">
          <CardContent className="py-3 text-[11px] text-muted-foreground">
            Ticket open/close emails are handled outside this app. Use{" "}
            <Link to="/release-notes" className="text-primary hover:underline font-medium">
              Release Notes
            </Link>{" "}
            to build a release brief and create workshop drafts for all workshops, Bosch network, or general tier.
          </CardContent>
        </Card>

        <div className="flex flex-wrap gap-2">
          {(["pending", "sent", "cancelled"] as const).map((key) => (
            <Button
              key={key}
              size="sm"
              variant={filter === key ? "default" : "outline"}
              className="h-7 text-[10px] capitalize"
              onClick={() => { setFilter(key); setSelected(null); }}
            >
              {key}
            </Button>
          ))}
        </div>

        {loading ? (
          <LoadingState />
        ) : drafts.length === 0 ? (
          <EmptyState
            title={filter === "pending" ? "No pending release drafts" : `No ${filter} release emails`}
            description={
              filter === "pending"
                ? "Create release announcement drafts from Release Notes when you are ready to communicate a sprint release to workshops."
                : undefined
            }
          />
        ) : (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <div className="space-y-2">
              {drafts.map((draft) => {
                const snap = releaseSnapshot(draft);
                return (
                  <button
                    key={draft.id}
                    type="button"
                    onClick={() => openDraft(draft)}
                    className={cn(
                      "w-full text-left rounded-lg border px-3 py-2.5 transition-colors",
                      selected?.id === draft.id
                        ? "border-primary/50 bg-primary/5"
                        : "border-border/60 hover:bg-muted/30"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold truncate">{draft.workshop_name}</p>
                        <p className="text-[10px] text-muted-foreground line-clamp-1 mt-0.5">{draft.subject}</p>
                      </div>
                      <Badge variant="secondary" className="text-[8px] shrink-0">
                        Release
                      </Badge>
                    </div>
                    <p className="text-[9px] text-muted-foreground mt-1">
                      {snap.sprint_name && <span>{snap.sprint_name} · </span>}
                      {new Date(draft.created_at).toLocaleString()}
                    </p>
                  </button>
                );
              })}
            </div>

            {selected ? (
              <Card className="border-primary/20">
                <CardContent className="py-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold">{selected.workshop_name}</p>
                      <Badge variant="outline" className="text-[9px] mt-1">
                        Release announcement
                      </Badge>
                    </div>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setSelected(null)}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>

                  {(snapshot?.sprint_name || snapshot?.release_date) && (
                    <p className="text-[10px] text-muted-foreground">
                      {snapshot.sprint_name && (
                        <span>
                          Sprint: <span className="text-foreground font-medium">{snapshot.sprint_name}</span>
                        </span>
                      )}
                      {snapshot.release_date && (
                        <span className={snapshot.sprint_name ? " ml-2" : ""}>
                          Release date: <span className="text-foreground font-medium">{snapshot.release_date}</span>
                        </span>
                      )}
                      {typeof snapshot.total_items === "number" && (
                        <span className="ml-2">
                          · {snapshot.total_items} item{snapshot.total_items !== 1 ? "s" : ""}
                        </span>
                      )}
                    </p>
                  )}

                  <div className="space-y-1.5">
                    <label className="text-[10px] font-medium text-muted-foreground">To (workshop)</label>
                    <Input value={toEmails} onChange={(e) => setToEmails(e.target.value)} className="h-8 text-xs" />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-medium text-muted-foreground">CC (support person + support head)</label>
                    <Input value={ccEmails} onChange={(e) => setCcEmails(e.target.value)} className="h-8 text-xs" />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-medium text-muted-foreground">Subject</label>
                    <Input value={subject} onChange={(e) => setSubject(e.target.value)} className="h-8 text-xs" />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-medium text-muted-foreground">Message</label>
                    <textarea
                      value={bodyText}
                      onChange={(e) => setBodyText(e.target.value)}
                      rows={12}
                      className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  </div>

                  {selected.status === "pending" && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      <Button size="sm" className="h-8 text-xs" onClick={sendDraft} disabled={sending}>
                        <Send className="h-3.5 w-3.5 mr-1" />
                        {sending ? "Sending…" : "Send email"}
                      </Button>
                      <Button size="sm" variant="outline" className="h-8 text-xs" onClick={saveEdits}>
                        Save edits
                      </Button>
                      <Button size="sm" variant="ghost" className="h-8 text-xs text-destructive" onClick={cancelDraft}>
                        Dismiss draft
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card className="border-dashed">
                <CardContent className="py-12 text-center text-xs text-muted-foreground">
                  <Mail className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  Select a release draft to review before sending
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </PageLayout>
  );
}
