import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, Download, Plus, Upload, Users, Building2, Pencil, Trash2, Search, Cloud, Mail, Send } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import {
  isOrgCustomersHydrated,
  isOrgTeamsHydrated,
  markOrgCustomersStale,
  readOrgCustomers,
  readOrgTeams,
  writeOrgCustomers,
  writeOrgTeams,
} from "@/lib/org-store";
import { enqueueOrgSync, flushOrgSync, subscribeOrgSync } from "@/lib/org-sync";
import { useProject } from "@/hooks/use-project";
import { useNotifyHelpers } from "@/hooks/use-notify";
import { resolveSupportEmailFromTeams, resolveWorkshopSupportEmail } from "@/lib/support-email-resolve";
import { cn } from "@/lib/utils";
import type { TeamData, CustomerAccountData, TeamMemberData, WorkshopEmailDraft } from "@/types";

const thClass = "px-3 py-2 font-medium text-left text-[10px] text-muted-foreground";
const tdClass = "px-3 py-2 align-middle text-[11px]";

function TeamMemberRow({
  teamId,
  member,
  onMemberChange,
  onMemberRemove,
}: {
  teamId: number;
  member: TeamMemberData;
  onMemberChange: (member: TeamMemberData) => void;
  onMemberRemove: (personId: number) => void;
}) {
  const { confirm } = useNotifyHelpers();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(member.person.name);
  const [email, setEmail] = useState(member.person.email);
  const [designation, setDesignation] = useState(member.person.role || "");
  const [isLead, setIsLead] = useState(member.is_lead);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(member.person.name);
    setEmail(member.person.email);
    setDesignation(member.person.role || "");
    setIsLead(member.is_lead);
  }, [member]);

  const save = () => {
    if (!name.trim() || !email.trim()) {
      setError("Name and email are required");
      return;
    }
    setError(null);
    const updated: TeamMemberData = {
      is_lead: isLead,
      person: {
        ...member.person,
        name: name.trim(),
        email: email.trim(),
        role: designation.trim() || undefined,
      },
    };
    onMemberChange(updated);
    setEditing(false);

    enqueueOrgSync({
      key: `team-member-${teamId}-${member.person.id}`,
      type: "updateTeamMember",
      teamId,
      personId: member.person.id,
      body: {
        name: updated.person.name,
        email: updated.person.email,
        designation: updated.person.role,
        is_lead: isLead,
      },
    });
  };

  const remove = async () => {
    const ok = await confirm({
      title: `Remove ${member.person.name}?`,
      description: "They will be removed from this team only.",
      confirmLabel: "Remove",
      destructive: true,
    });
    if (!ok) return;
    onMemberRemove(member.person.id);
    enqueueOrgSync({
      key: `remove-member-${teamId}-${member.person.id}`,
      type: "removeTeamMember",
      teamId,
      personId: member.person.id,
    });
  };

  if (editing) {
    return (
      <tr className="border-t border-primary/30 bg-primary/5">
        <td className={tdClass}>
          <Input value={name} onChange={(e) => setName(e.target.value)} className="h-7 text-[11px]" />
        </td>
        <td className={tdClass}>
          <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" className="h-7 text-[11px]" />
        </td>
        <td className={tdClass}>
          <Input value={designation} onChange={(e) => setDesignation(e.target.value)} placeholder="Designation" className="h-7 text-[11px]" />
        </td>
        <td className={tdClass}>
          <label className="flex items-center gap-1 text-[10px] cursor-pointer">
            <input type="checkbox" checked={isLead} onChange={(e) => setIsLead(e.target.checked)} />
            Lead
          </label>
        </td>
        <td className={tdClass}>
          <div className="flex gap-1">
            <Button size="sm" className="h-7 text-[10px] px-2" onClick={save}>Save</Button>
            <Button size="sm" variant="ghost" className="h-7 text-[10px] px-2" onClick={() => { setEditing(false); setError(null); }}>Cancel</Button>
          </div>
          {error && <p className="text-[9px] text-destructive mt-1">{error}</p>}
        </td>
      </tr>
    );
  }

  return (
    <tr className="border-t border-border/50 hover:bg-muted/10">
      <td className={cn(tdClass, "font-medium")}>{member.person.name}</td>
      <td className={cn(tdClass, "text-muted-foreground")}>{member.person.email}</td>
      <td className={tdClass}>{member.person.role || "—"}</td>
      <td className={tdClass}>
        {member.is_lead ? (
          <Badge className="text-[9px] px-1.5 py-0">Lead</Badge>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className={tdClass}>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => setEditing(true)} title="Edit">
            <Pencil className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-destructive" onClick={remove} title="Remove from team">
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </td>
    </tr>
  );
}

function TeamPanel({
  team,
  onTeamChange,
  onTeamDelete,
}: {
  team: TeamData;
  onTeamChange: (team: TeamData) => void;
  onTeamDelete: (teamId: number) => void;
}) {
  const { confirm } = useNotifyHelpers();
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(team.name);
  const [editDesc, setEditDesc] = useState(team.description || "");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [designation, setDesignation] = useState("");
  const [isLead, setIsLead] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEditName(team.name);
    setEditDesc(team.description || "");
  }, [team.name, team.description]);

  const saveMember = () => {
    if (!name.trim() || !email.trim()) {
      setError("Name and email are required");
      return;
    }
    setError(null);
    const memberName = name.trim();
    const memberEmail = email.trim();
    const memberDesignation = designation.trim() || undefined;
    const tempPersonId = -Date.now();

    onTeamChange({
      ...team,
      members: [
        ...team.members,
        {
          person: {
            id: tempPersonId,
            name: memberName,
            email: memberEmail,
            role: memberDesignation,
          },
          is_lead: isLead,
        },
      ],
    });

    setName("");
    setEmail("");
    setDesignation("");
    setIsLead(false);
    setAdding(false);

    enqueueOrgSync({
      key: `team-member-${team.id}-${memberEmail}`,
      type: "addTeamMember",
      teamId: team.id,
      body: {
        name: memberName,
        email: memberEmail,
        designation: memberDesignation,
        is_lead: isLead,
      },
    });
  };

  const saveTeam = () => {
    if (!editName.trim()) {
      setError("Team name is required");
      return;
    }
    setError(null);
    const nextName = editName.trim();
    const nextDesc = editDesc.trim() || undefined;

    onTeamChange({ ...team, name: nextName, description: nextDesc });
    setEditing(false);

    enqueueOrgSync({
      key: `team-${team.id}`,
      type: "updateTeam",
      teamId: team.id,
      body: { name: nextName, description: nextDesc },
    });
  };

  const removeTeam = async () => {
    const ok = await confirm({
      title: `Delete team "${team.name}"?`,
      description: "Members are removed from this team only.",
      confirmLabel: "Delete team",
      destructive: true,
    });
    if (!ok) return;
    setError(null);
    onTeamDelete(team.id);
    enqueueOrgSync({ key: `delete-team-${team.id}`, type: "deleteTeam", teamId: team.id });
  };

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-muted/20 transition-colors"
      >
        <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform", open && "rotate-180")} />
        <span className="text-xs font-medium flex-1">{team.name}</span>
        <Badge variant="outline" className="text-[9px] px-1.5 py-0">
          {team.members.length} member{team.members.length !== 1 ? "s" : ""}
        </Badge>
      </button>

      {open && (
        <div className="border-t border-border/60 bg-card/50 px-3 py-3 space-y-2">
          {editing ? (
            <div className="space-y-2 rounded-md border border-primary/30 bg-primary/5 p-2">
              <Input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Team name" className="h-8 text-xs" />
              <Input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} placeholder="Description (optional)" className="h-8 text-xs" />
              <div className="flex gap-2">
                <Button size="sm" className="h-7 text-[10px]" onClick={saveTeam}>Save</Button>
                <Button size="sm" variant="ghost" className="h-7 text-[10px]" onClick={() => { setEditing(false); setError(null); }}>Cancel</Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {team.description && (
                <p className="text-[10px] text-muted-foreground flex-1">{team.description}</p>
              )}
              <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={() => setEditing(true)}>
                <Pencil className="h-3 w-3 mr-1" /> Rename
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-[10px] text-destructive hover:text-destructive" onClick={removeTeam}>
                <Trash2 className="h-3 w-3 mr-1" /> Delete team
              </Button>
            </div>
          )}

          <div className="overflow-x-auto rounded-md border border-border/60">
            <table className="w-full border-collapse">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className={thClass}>Name</th>
                  <th className={thClass}>Email</th>
                  <th className={thClass}>Designation</th>
                  <th className={thClass}>Lead</th>
                  <th className={cn(thClass, "w-20")} />
                </tr>
              </thead>
              <tbody>
                {team.members.length === 0 && !adding ? (
                  <tr>
                    <td colSpan={5} className="px-3 py-4 text-center text-[10px] text-muted-foreground">
                      No members yet.
                    </td>
                  </tr>
                ) : (
                  team.members.map((m) => (
                    <TeamMemberRow
                      key={m.person.id}
                      teamId={team.id}
                      member={m}
                      onMemberChange={(updated) =>
                        onTeamChange({
                          ...team,
                          members: team.members.map((x) =>
                            x.person.id === updated.person.id ? updated : x
                          ),
                        })
                      }
                      onMemberRemove={(personId) =>
                        onTeamChange({
                          ...team,
                          members: team.members.filter((x) => x.person.id !== personId),
                        })
                      }
                    />
                  ))
                )}
                {adding && (
                  <tr className="border-t border-primary/30 bg-primary/5">
                    <td className={tdClass}>
                      <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" className="h-7 text-[11px]" />
                    </td>
                    <td className={tdClass}>
                      <Input value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder="email@company.com" className="h-7 text-[11px]" />
                    </td>
                    <td className={tdClass}>
                      <Input value={designation} onChange={(e) => setDesignation(e.target.value)} placeholder="Designation" className="h-7 text-[11px]" />
                    </td>
                    <td className={tdClass}>
                      <label className="flex items-center gap-1 text-[10px] cursor-pointer">
                        <input type="checkbox" checked={isLead} onChange={(e) => setIsLead(e.target.checked)} />
                        Lead
                      </label>
                    </td>
                    <td className={tdClass} />
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {adding ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" className="h-7 text-[10px]" onClick={saveMember}>Save member</Button>
              <Button size="sm" variant="ghost" className="h-7 text-[10px]" onClick={() => { setAdding(false); setError(null); }}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button variant="outline" size="sm" className="h-7 text-[10px]" onClick={() => setAdding(true)}>
              <Plus className="h-3 w-3 mr-1" /> Add member
            </Button>
          )}
          {error && <p className="text-[10px] text-destructive">{error}</p>}
        </div>
      )}
    </div>
  );
}

const WORKSHOP_ROW_H = 37;
const WORKSHOP_OVERSCAN = 8;

const WorkshopRow = memo(function WorkshopRow({
  workshop,
  teams,
  onWorkshopChange,
  onWorkshopDelete,
}: {
  workshop: CustomerAccountData;
  teams: TeamData[];
  onWorkshopChange: (workshop: CustomerAccountData) => void;
  onWorkshopDelete: (id: number) => void;
}) {
  const { confirm } = useNotifyHelpers();
  const [editing, setEditing] = useState(false);
  const [workshopName, setWorkshopName] = useState(workshop.workshop_name);
  const [axId, setAxId] = useState(workshop.ax_id || "");
  const [supportName, setSupportName] = useState(workshop.support_person_name || "");
  const [workshopEmail, setWorkshopEmail] = useState(workshop.workshop_email || "");
  const [supportEmail, setSupportEmail] = useState(
    () => resolveWorkshopSupportEmail(workshop, teams) || ""
  );
  const [tier, setTier] = useState(workshop.tier);
  const [location, setLocation] = useState(workshop.industry || "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setWorkshopName(workshop.workshop_name);
    setAxId(workshop.ax_id || "");
    setSupportName(workshop.support_person_name || "");
    setWorkshopEmail(workshop.workshop_email || "");
    setSupportEmail(resolveWorkshopSupportEmail(workshop, teams) || "");
    setTier(workshop.tier);
    setLocation(workshop.industry || "");
  }, [workshop, teams]);

  const save = () => {
    if (!workshopName.trim()) {
      setError("Workshop name is required");
      return;
    }
    setError(null);
    const resolvedSupportEmail =
      supportEmail.trim() ||
      resolveSupportEmailFromTeams(supportName.trim(), teams) ||
      undefined;
    const updated: CustomerAccountData = {
      ...workshop,
      workshop_name: workshopName.trim(),
      name: workshopName.trim(),
      support_person_name: supportName.trim() || undefined,
      workshop_email: workshopEmail.trim() || undefined,
      support_contact_email: resolvedSupportEmail,
      support_person_email: resolvedSupportEmail,
      ax_id: axId.trim() || undefined,
      tier: tier.trim() || "standard",
      industry: location.trim() || undefined,
    };
    onWorkshopChange(updated);
    setEditing(false);

    enqueueOrgSync({
      key: `customer-${workshop.id}`,
      type: "updateCustomer",
      customerId: workshop.id,
      body: {
        workshop_name: updated.workshop_name,
        support_person_name: updated.support_person_name,
        support_person_email: updated.support_contact_email,
        workshop_email: updated.workshop_email,
        support_contact_email: updated.support_contact_email,
        ax_id: updated.ax_id,
        tier: updated.tier,
        location: updated.industry,
      },
    });
  };

  const remove = async () => {
    const ok = await confirm({
      title: `Delete workshop "${workshop.workshop_name}"?`,
      description: "This workshop will be removed from your org list.",
      confirmLabel: "Delete",
      destructive: true,
    });
    if (!ok) return;
    onWorkshopDelete(workshop.id);
    enqueueOrgSync({
      key: `delete-customer-${workshop.id}`,
      type: "deleteCustomer",
      customerId: workshop.id,
    });
  };

  if (editing) {
    return (
      <tr className="border-t border-primary/30 bg-primary/5">
        <td className={tdClass}>
          <Input value={workshopName} onChange={(e) => setWorkshopName(e.target.value)} className="h-7 text-[11px]" />
        </td>
        <td className={tdClass}>
          <Input value={axId} onChange={(e) => setAxId(e.target.value)} placeholder="AX1779430292280" className="h-7 text-[11px] font-mono" />
        </td>
        <td className={tdClass}>
          <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Location" className="h-7 text-[11px]" />
        </td>
        <td className={tdClass}>
          <select value={tier} onChange={(e) => setTier(e.target.value)} className="h-7 text-[11px] rounded-md border border-input bg-background px-2 w-full">
            <option value="standard">General</option>
            <option value="bosch">BOSCH</option>
          </select>
        </td>
        <td className={tdClass}>
          <Input
            value={supportName}
            onChange={(e) => {
              const next = e.target.value;
              setSupportName(next);
              const fromTeam = resolveSupportEmailFromTeams(next, teams);
              if (fromTeam) setSupportEmail(fromTeam);
            }}
            placeholder="Support agent"
            className="h-7 text-[11px]"
          />
        </td>
        <td className={tdClass}>
          <Input value={workshopEmail} onChange={(e) => setWorkshopEmail(e.target.value)} type="email" placeholder="workshop@garage.com" className="h-7 text-[11px]" />
        </td>
        <td className={tdClass}>
          <Input value={supportEmail} onChange={(e) => setSupportEmail(e.target.value)} type="email" placeholder="support@company.com" className="h-7 text-[11px]" />
        </td>
        <td className={tdClass}>
          <div className="flex gap-1">
            <Button size="sm" className="h-7 text-[10px] px-2" onClick={save}>Save</Button>
            <Button size="sm" variant="ghost" className="h-7 text-[10px] px-2" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
          {error && <p className="text-[9px] text-destructive mt-1">{error}</p>}
        </td>
      </tr>
    );
  }

  return (
    <tr className="border-t border-border/50 hover:bg-muted/10">
      <td className={cn(tdClass, "font-medium truncate max-w-0")} title={workshop.workshop_name}>
        {workshop.workshop_name}
      </td>
      <td className={cn(tdClass, "text-muted-foreground truncate max-w-0 font-mono text-[10px]")} title={workshop.ax_id}>
        {workshop.ax_id || "—"}
      </td>
      <td className={cn(tdClass, "text-muted-foreground truncate max-w-0")} title={workshop.industry || undefined}>
        {workshop.industry || "—"}
      </td>
      <td className={tdClass}>
        <Badge variant="outline" className="text-[9px] px-1.5 py-0 capitalize">
          {workshop.tier === "bosch" ? "BOSCH" : workshop.tier}
        </Badge>
      </td>
      <td className={tdClass}>{workshop.support_person_name || <span className="text-muted-foreground">—</span>}</td>
      <td className={cn(tdClass, "text-muted-foreground truncate max-w-0 text-[10px]")} title={workshop.workshop_email}>
        {workshop.workshop_email || "—"}
      </td>
      <td
        className={cn(tdClass, "text-muted-foreground truncate max-w-0 text-[10px]")}
        title={resolveWorkshopSupportEmail(workshop, teams)}
      >
        {resolveWorkshopSupportEmail(workshop, teams) || "—"}
      </td>
      <td className={tdClass}>
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => setEditing(true)} title="Edit">
            <Pencil className="h-3 w-3" />
          </Button>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-destructive" onClick={remove} title="Delete">
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </td>
    </tr>
  );
});

function VirtualWorkshopTable({
  workshops,
  teams,
  onWorkshopChange,
  onWorkshopDelete,
  matchLabel,
}: {
  workshops: CustomerAccountData[];
  teams: TeamData[];
  onWorkshopChange: (workshop: CustomerAccountData) => void;
  onWorkshopDelete: (id: number) => void;
  matchLabel?: string;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportH, setViewportH] = useState(560);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const update = () => setViewportH(el.clientHeight || 560);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    setScrollTop(0);
    scrollRef.current?.scrollTo({ top: 0 });
  }, [workshops]);

  const totalH = workshops.length * WORKSHOP_ROW_H;
  const start = Math.max(0, Math.floor(scrollTop / WORKSHOP_ROW_H) - WORKSHOP_OVERSCAN);
  const count = Math.ceil(viewportH / WORKSHOP_ROW_H) + WORKSHOP_OVERSCAN * 2;
  const end = Math.min(workshops.length, start + count);
  const visible = workshops.slice(start, end);
  const padTop = start * WORKSHOP_ROW_H;
  const padBottom = Math.max(0, totalH - end * WORKSHOP_ROW_H);

  return (
    <div className="rounded-md border border-border">
      {matchLabel && (
        <p className="px-3 py-2 text-[10px] text-muted-foreground border-b border-border bg-muted/30">
          {matchLabel}
        </p>
      )}
      <div
        ref={scrollRef}
        className="overflow-x-auto overflow-y-auto max-h-[560px]"
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      >
        <table className="w-full border-collapse table-fixed min-w-[1180px]">
          <colgroup>
            <col style={{ width: "18%" }} />
            <col style={{ width: "11%" }} />
            <col style={{ width: "10%" }} />
            <col style={{ width: "8%" }} />
            <col style={{ width: "12%" }} />
            <col style={{ width: "14%" }} />
            <col style={{ width: "14%" }} />
            <col style={{ width: "8%" }} />
          </colgroup>
          <thead className="sticky top-0 z-10">
            <tr className="border-b border-border bg-muted shadow-[0_1px_0_0_hsl(var(--border))]">
              <th className={thClass}>Workshop / garage</th>
              <th className={thClass}>AX ID</th>
              <th className={thClass}>Location</th>
              <th className={thClass}>Tier</th>
              <th className={thClass}>Support person</th>
              <th className={thClass}>Workshop mail</th>
              <th className={thClass}>Support mail</th>
              <th className={cn(thClass, "w-20")} />
            </tr>
          </thead>
        <tbody>
          {padTop > 0 && (
            <tr aria-hidden="true">
              <td colSpan={8} style={{ height: padTop, padding: 0, border: 0 }} />
            </tr>
          )}
          {visible.map((w) => (
            <WorkshopRow
              key={w.id}
              workshop={w}
              teams={teams}
              onWorkshopChange={onWorkshopChange}
              onWorkshopDelete={onWorkshopDelete}
            />
          ))}
          {padBottom > 0 && (
            <tr aria-hidden="true">
              <td colSpan={8} style={{ height: padBottom, padding: 0, border: 0 }} />
            </tr>
          )}
        </tbody>
      </table>
      </div>
    </div>
  );
}

type WorkshopSortKey = "workshop" | "ax_id" | "support" | "location" | "tier";

function workshopSortValue(c: CustomerAccountData, key: WorkshopSortKey): string {
  switch (key) {
    case "ax_id":
      return (c.ax_id || "zzz_unassigned").toLowerCase();
    case "support":
      return (c.support_person_name || "zzz_unassigned").toLowerCase();
    case "location":
      return (c.industry || "").toLowerCase();
    case "tier":
      return (c.tier || "").toLowerCase();
    default:
      return c.workshop_name.toLowerCase();
  }
}

function PendingWorkshopEmailsPanel() {
  const [open, setOpen] = useState(true);
  const [drafts, setDrafts] = useState<WorkshopEmailDraft[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setDrafts(await api.getWorkshopEmailDrafts("pending"));
    } catch {
      setDrafts([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading || drafts.length === 0) return null;

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-muted/20 transition-colors"
      >
        <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform", open && "rotate-180")} />
        <Mail className="h-3.5 w-3.5 shrink-0 text-primary" />
        <span className="text-xs font-medium flex-1">Pending release emails</span>
        <Badge variant="default" className="text-[9px] px-1.5 py-0">
          {drafts.length} to review
        </Badge>
      </button>

      {open && (
        <div className="border-t border-border/60 bg-card/50 px-3 py-3 space-y-2">
          <p className="text-[10px] text-muted-foreground">
            Release announcement drafts from sprint planning. Create them on Release Notes, then review and send here.
          </p>
          <ul className="space-y-1.5">
            {drafts.slice(0, 8).map((d) => {
              const snap = d.ticket_snapshot as { sprint_name?: string; release_date?: string };
              return (
                <li
                  key={d.id}
                  className="flex flex-wrap items-center gap-2 rounded-md border border-border/60 bg-background/50 px-2.5 py-2 text-[11px]"
                >
                  <Badge variant="outline" className="text-[9px] px-1.5 py-0 shrink-0">
                    Release
                  </Badge>
                  <span className="font-medium truncate min-w-0 flex-1" title={d.workshop_name}>
                    {d.workshop_name || "Workshop"}
                  </span>
                  <span className="text-muted-foreground truncate max-w-[200px]" title={d.subject}>
                    {snap.sprint_name ? `${snap.sprint_name} · ` : ""}
                    {d.subject}
                  </span>
                  <Link
                    to="/workshop-emails"
                    className="text-[10px] text-primary hover:underline inline-flex items-center gap-1 shrink-0"
                  >
                    <Send className="h-3 w-3" /> Review
                  </Link>
                </li>
              );
            })}
          </ul>
          {drafts.length > 8 && (
            <p className="text-[10px] text-muted-foreground">
              + {drafts.length - 8} more pending
            </p>
          )}
          <Link
            to="/workshop-emails"
            className="inline-flex items-center gap-1 text-[10px] text-primary hover:underline"
          >
            Open workshop release review →
          </Link>
        </div>
      )}
    </div>
  );
}

export default function PeopleWorkshopsPage() {
  const { cacheVersion } = useProject();
  const [teams, setTeams] = useState<TeamData[]>(() => readOrgTeams() ?? []);
  const [customers, setCustomers] = useState<CustomerAccountData[]>(() => readOrgCustomers() ?? []);
  const [initialLoad, setInitialLoad] = useState(
    () => !(readOrgTeams()?.length || readOrgCustomers()?.length)
  );
  const [message, setMessage] = useState<string | null>(null);
  const [messageIsError, setMessageIsError] = useState(false);
  const [importing, setImporting] = useState<"teams" | "customers" | null>(null);
  const [showNewTeam, setShowNewTeam] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamDesc, setNewTeamDesc] = useState("");
  const [showNewWorkshop, setShowNewWorkshop] = useState(false);
  const [workshopSearch, setWorkshopSearch] = useState("");
  const [workshopSort, setWorkshopSort] = useState<WorkshopSortKey>("workshop");
  const [newWorkshopName, setNewWorkshopName] = useState("");
  const [newWorkshopSupport, setNewWorkshopSupport] = useState("");
  const [newWorkshopEmail, setNewWorkshopEmail] = useState("");
  const [newWorkshopSupportEmail, setNewWorkshopSupportEmail] = useState("");
  const [newWorkshopTier, setNewWorkshopTier] = useState("standard");
  const [newWorkshopLocation, setNewWorkshopLocation] = useState("");
  const [newWorkshopAxId, setNewWorkshopAxId] = useState("");
  const [workshopsListOpen, setWorkshopsListOpen] = useState(false);
  const [syncStatus, setSyncStatus] = useState({ pending: 0, syncing: false, lastError: null as string | null });
  const supportEmailsReconciled = useRef(false);

  const persistTeams = useCallback((next: TeamData[]) => {
    setTeams(next);
    writeOrgTeams(next);
  }, []);

  const persistCustomers = useCallback((next: CustomerAccountData[] | ((prev: CustomerAccountData[]) => CustomerAccountData[])) => {
    setCustomers((prev) => {
      const resolved = typeof next === "function" ? next(prev) : next;
      writeOrgCustomers(resolved);
      return resolved;
    });
  }, []);

  const refreshTeams = useCallback(async () => {
    try {
      persistTeams(await api.getTeams());
    } catch {
      // teams are small — keep cached copy on failure
    }
  }, [persistTeams]);

  const refreshCustomers = useCallback(async (background = false) => {
    if (!background && !readOrgCustomers()?.length) {
      setInitialLoad(true);
    }
    try {
      persistCustomers(await api.getCustomerAccounts());
    } catch {
      if (!readOrgCustomers()?.length) {
        setMessage("Could not load workshops");
        setMessageIsError(true);
      }
    } finally {
      setInitialLoad(false);
    }
  }, [persistCustomers]);

  useEffect(() => {
    if (!isOrgTeamsHydrated()) void refreshTeams();
    if (!isOrgCustomersHydrated()) void refreshCustomers(true);
    else setInitialLoad(false);
  }, [refreshTeams, refreshCustomers]);

  useEffect(() => {
    if (!teams.length || supportEmailsReconciled.current) return;
    supportEmailsReconciled.current = true;
    void (async () => {
      try {
        await api.reconcileCustomerSupportEmails();
        markOrgCustomersStale();
        await refreshCustomers(true);
      } catch {
        // keep showing team-resolved emails in UI even if reconcile fails
      }
    })();
  }, [teams, refreshCustomers]);

  useEffect(() => {
    if (cacheVersion === 0) return;
    markOrgCustomersStale();
    void refreshCustomers(true);
    void refreshTeams();
  }, [cacheVersion, refreshCustomers, refreshTeams]);

  useEffect(() => subscribeOrgSync(setSyncStatus), []);

  useEffect(() => {
    const onReconciled = (e: Event) => {
      const detail = (e as CustomEvent<{
        teams?: Record<number, TeamData>;
        customers?: Record<number, CustomerAccountData>;
      }>).detail;
      if (detail.teams && Object.keys(detail.teams).length) {
        persistTeams(
          teams.map((t) => {
            const replaced = detail.teams![t.id] ?? detail.teams![-t.id];
            return replaced ?? t;
          }).filter((t) => t.id > 0 || detail.teams![-t.id])
        );
      }
      if (detail.customers && Object.keys(detail.customers).length) {
        persistCustomers((prev) =>
          prev
            .map((c) => detail.customers![c.id] ?? detail.customers![-c.id] ?? c)
            .filter((c) => c.id > 0 || detail.customers![-c.id])
        );
      }
    };
    window.addEventListener("org-sync-reconciled", onReconciled);
    return () => window.removeEventListener("org-sync-reconciled", onReconciled);
  }, [teams, persistTeams, persistCustomers]);

  const handleTeamChange = useCallback((team: TeamData) => {
    persistTeams(teams.map((t) => (t.id === team.id ? team : t)));
  }, [teams, persistTeams]);

  const handleTeamDelete = useCallback((teamId: number) => {
    persistTeams(teams.filter((t) => t.id !== teamId));
  }, [teams, persistTeams]);

  const handleWorkshopChange = useCallback((workshop: CustomerAccountData) => {
    persistCustomers((prev) => prev.map((c) => (c.id === workshop.id ? workshop : c)));
  }, [persistCustomers]);

  const handleWorkshopDelete = useCallback((id: number) => {
    persistCustomers((prev) => prev.filter((c) => c.id !== id));
  }, [persistCustomers]);

  const filteredWorkshops = useMemo(() => {
    const q = workshopSearch.trim().toLowerCase();
    if (!q) return customers;
    return customers.filter(
      (c) =>
        c.workshop_name.toLowerCase().includes(q) ||
        (c.ax_id || "").toLowerCase().includes(q) ||
        (c.support_person_name || "").toLowerCase().includes(q) ||
        (c.industry || "").toLowerCase().includes(q)
    );
  }, [customers, workshopSearch]);

  const sortedWorkshops = useMemo(() => {
    const list = [...filteredWorkshops];
    list.sort((a, b) => {
      const cmp = workshopSortValue(a, workshopSort).localeCompare(workshopSortValue(b, workshopSort));
      if (cmp !== 0) return cmp;
      return a.workshop_name.localeCompare(b.workshop_name);
    });
    return list;
  }, [filteredWorkshops, workshopSort]);

  const createTeam = () => {
    if (!newTeamName.trim()) return;
    const name = newTeamName.trim();
    const desc = newTeamDesc.trim() || undefined;
    const tempId = -Date.now();
    const optimistic: TeamData = { id: tempId, name, description: desc, members: [] };

    persistTeams([optimistic, ...teams]);
    setNewTeamName("");
    setNewTeamDesc("");
    setShowNewTeam(false);
    setMessage(`Team "${name}" saved`);
    setMessageIsError(false);

    enqueueOrgSync({
      key: `create-team-${tempId}`,
      type: "createTeam",
      tempId,
      body: { name, description: desc },
    });
  };

  const createWorkshop = () => {
    if (!newWorkshopName.trim()) return;
    const workshopName = newWorkshopName.trim();
    const tempId = -Date.now();
    const supportName = newWorkshopSupport.trim();
    const supportEmail =
      newWorkshopSupportEmail.trim() ||
      resolveSupportEmailFromTeams(supportName, teams) ||
      undefined;
    const optimistic: CustomerAccountData = {
      id: tempId,
      name: workshopName,
      workshop_name: workshopName,
      support_person_name: supportName || undefined,
      workshop_email: newWorkshopEmail.trim() || undefined,
      support_contact_email: supportEmail,
      support_person_email: supportEmail,
      tier: newWorkshopTier,
      industry: newWorkshopLocation.trim() || undefined,
      ax_id: newWorkshopAxId.trim() || undefined,
    };

    persistCustomers((prev) => [optimistic, ...prev]);
    setNewWorkshopName("");
    setNewWorkshopSupport("");
    setNewWorkshopEmail("");
    setNewWorkshopSupportEmail("");
    setNewWorkshopTier("standard");
    setNewWorkshopLocation("");
    setNewWorkshopAxId("");
    setShowNewWorkshop(false);
    setMessage(`Workshop "${workshopName}" saved`);
    setMessageIsError(false);

    enqueueOrgSync({
      key: `create-customer-${tempId}`,
      type: "createCustomer",
      tempId,
      body: {
        workshop_name: workshopName,
        support_person_name: optimistic.support_person_name,
        support_person_email: optimistic.support_contact_email,
        workshop_email: optimistic.workshop_email,
        support_contact_email: optimistic.support_contact_email,
        tier: newWorkshopTier,
        location: optimistic.industry,
        ax_id: optimistic.ax_id,
      },
    });
  };

  const onImport = (type: "teams" | "customers") => async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(type);
    setMessage(null);
    setMessageIsError(false);
    try {
      const result = type === "teams"
        ? await api.importTeamsCsv(file)
        : await api.importCustomersCsv(file);
      setMessage(
        type === "teams"
          ? `Imported ${result.rows_processed ?? 0} team row(s)`
          : `Imported ${result.imported ?? 0} workshop(s)`
      );
      if (type === "teams") {
        await refreshTeams();
      } else {
        markOrgCustomersStale();
        await refreshCustomers(true);
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Import failed");
      setMessageIsError(true);
    } finally {
      setImporting(null);
      e.target.value = "";
    }
  };

  if (initialLoad && teams.length === 0 && customers.length === 0) {
    return (
      <>
        <Header title="People & Workshops" description="Tech teams and support contacts for workshops" />
        <div className="page-content"><LoadingState /></div>
      </>
    );
  }

  return (
    <PageLayout page="people-workshops" hideSidebar>
      <Header
        title="People & Workshops"
        description="Manage delivery teams (with designations) and which support person owns each workshop"
      />
      <div className="page-content space-y-8">
        {(message || syncStatus.pending > 0 || syncStatus.syncing || syncStatus.lastError) && (
          <div className="flex flex-wrap items-center gap-2">
            {message && (
              <p className={cn("text-xs", messageIsError ? "text-destructive" : "text-muted-foreground")}>
                {message}
              </p>
            )}
            {syncStatus.syncing && (
              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                <Cloud className="h-3 w-3 animate-pulse" /> Syncing to server…
              </span>
            )}
            {!syncStatus.syncing && syncStatus.pending > 0 && (
              <button
                type="button"
                onClick={() => void flushOrgSync()}
                className="text-[10px] text-primary hover:underline"
              >
                {syncStatus.pending} change{syncStatus.pending !== 1 ? "s" : ""} saved locally · sync now
              </button>
            )}
            {syncStatus.lastError && (
              <p className="text-[10px] text-destructive">{syncStatus.lastError}</p>
            )}
          </div>
        )}

        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">Teams</h2>
              <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                {teams.length} team{teams.length !== 1 ? "s" : ""}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => api.downloadTeamsTemplate()}>
                <Download className="h-3.5 w-3.5 mr-1" /> CSV template
              </Button>
              <label>
                <Button variant="outline" size="sm" disabled={importing === "teams"} asChild>
                  <span><Upload className="h-3.5 w-3.5 mr-1" /> Import CSV</span>
                </Button>
                <input type="file" accept=".csv" className="hidden" onChange={onImport("teams")} />
              </label>
              <Button size="sm" onClick={() => setShowNewTeam((v) => !v)}>
                <Plus className="h-3.5 w-3.5 mr-1" /> Add team
              </Button>
            </div>
          </div>

          {showNewTeam && (
            <Card className="border-primary/30">
              <CardContent className="py-3 space-y-2">
                <Input placeholder="Team name (e.g. Platform Engineering)" value={newTeamName} onChange={(e) => setNewTeamName(e.target.value)} className="h-8 text-xs" />
                <Input placeholder="Description (optional)" value={newTeamDesc} onChange={(e) => setNewTeamDesc(e.target.value)} className="h-8 text-xs" />
                <div className="flex gap-2">
                  <Button size="sm" className="h-7 text-[10px]" onClick={createTeam}>Create team</Button>
                  <Button size="sm" variant="ghost" className="h-7 text-[10px]" onClick={() => setShowNewTeam(false)}>Cancel</Button>
                </div>
              </CardContent>
            </Card>
          )}

          {teams.length === 0 ? (
            <Card>
              <CardContent className="py-6 text-center text-xs text-muted-foreground">
                No teams yet. Click <strong>Add team</strong> or import a CSV.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {teams.map((team) => (
                <TeamPanel
                  key={team.id}
                  team={team}
                  onTeamChange={handleTeamChange}
                  onTeamDelete={handleTeamDelete}
                />
              ))}
            </div>
          )}
        </section>

        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold">Workshop assignments</h2>
              <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                {customers.length.toLocaleString()} workshop{customers.length !== 1 ? "s" : ""}
              </Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => api.downloadCustomersTemplate()}>
                <Download className="h-3.5 w-3.5 mr-1" /> CSV template
              </Button>
              <label>
                <Button variant="outline" size="sm" disabled={importing === "customers"} asChild>
                  <span><Upload className="h-3.5 w-3.5 mr-1" /> Bulk import CSV</span>
                </Button>
                <input type="file" accept=".csv" className="hidden" onChange={onImport("customers")} />
              </label>
              <Button size="sm" onClick={() => setShowNewWorkshop((v) => !v)}>
                <Plus className="h-3.5 w-3.5 mr-1" /> Add workshop
              </Button>
            </div>
          </div>
          <p className="text-[10px] text-muted-foreground">
            One row per workshop/garage with its support owner. AX ID is the stable key — tickets can be
            matched to the correct workshop even when the garage name is misspelled.
          </p>

          {showNewWorkshop && (
            <Card className="border-primary/30">
              <CardContent className="py-3 space-y-2">
                <Input placeholder="Workshop name *" value={newWorkshopName} onChange={(e) => setNewWorkshopName(e.target.value)} className="h-8 text-xs" />
                <div className="grid gap-2 sm:grid-cols-2">
                  <Input placeholder="AX ID (e.g. AX1779430292280)" value={newWorkshopAxId} onChange={(e) => setNewWorkshopAxId(e.target.value)} className="h-8 text-xs font-mono" />
                  <Input placeholder="Location (optional)" value={newWorkshopLocation} onChange={(e) => setNewWorkshopLocation(e.target.value)} className="h-8 text-xs" />
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Input
                    placeholder="Support person (e.g. Kavya)"
                    value={newWorkshopSupport}
                    onChange={(e) => {
                      const next = e.target.value;
                      setNewWorkshopSupport(next);
                      const fromTeam = resolveSupportEmailFromTeams(next, teams);
                      if (fromTeam) setNewWorkshopSupportEmail(fromTeam);
                    }}
                    className="h-8 text-xs"
                  />
                  <select value={newWorkshopTier} onChange={(e) => setNewWorkshopTier(e.target.value)} className="h-8 text-xs rounded-md border border-input bg-background px-2">
                    <option value="standard">General</option>
                    <option value="bosch">BOSCH</option>
                  </select>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Input placeholder="Workshop mail (for customer emails)" type="email" value={newWorkshopEmail} onChange={(e) => setNewWorkshopEmail(e.target.value)} className="h-8 text-xs" />
                  <Input placeholder="Support mail (CC on workshop emails)" type="email" value={newWorkshopSupportEmail} onChange={(e) => setNewWorkshopSupportEmail(e.target.value)} className="h-8 text-xs" />
                </div>
                <div className="flex gap-2">
                  <Button size="sm" className="h-7 text-[10px]" onClick={createWorkshop}>Save workshop</Button>
                  <Button size="sm" variant="ghost" className="h-7 text-[10px]" onClick={() => setShowNewWorkshop(false)}>Cancel</Button>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="rounded-md border border-border overflow-hidden">
            <button
              type="button"
              onClick={() => setWorkshopsListOpen((v) => !v)}
              className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-muted/20 transition-colors"
            >
              <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform", workshopsListOpen && "rotate-180")} />
              <span className="text-xs font-medium flex-1">Workshop list</span>
              <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                {workshopSearch.trim()
                  ? `${sortedWorkshops.length.toLocaleString()} match${sortedWorkshops.length !== 1 ? "es" : ""}`
                  : `${customers.length.toLocaleString()} workshop${customers.length !== 1 ? "s" : ""}`}
              </Badge>
            </button>

            {workshopsListOpen && (
              <div className="border-t border-border/60 bg-card/50 px-3 py-3 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative flex-1 min-w-[200px] max-w-sm">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                    <Input
                      value={workshopSearch}
                      onChange={(e) => setWorkshopSearch(e.target.value)}
                      placeholder="Search workshops, AX ID, support, location…"
                      className="h-8 pl-8 text-xs"
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-muted-foreground whitespace-nowrap">Sort by</span>
                    <select
                      value={workshopSort}
                      onChange={(e) => setWorkshopSort(e.target.value as WorkshopSortKey)}
                      className="h-8 text-xs rounded-md border border-input bg-background px-2 min-w-[140px]"
                    >
                      <option value="workshop">Workshop name</option>
                      <option value="ax_id">AX ID</option>
                      <option value="support">Support person</option>
                      <option value="location">Location</option>
                      <option value="tier">Tier</option>
                    </select>
                  </div>
                </div>

                {customers.length === 0 ? (
                  <Card>
                    <CardContent className="py-6 text-center text-xs text-muted-foreground">
                      No workshops yet. Click <strong>Add workshop</strong> or bulk import a CSV.
                    </CardContent>
                  </Card>
                ) : (
                  <VirtualWorkshopTable
                    workshops={sortedWorkshops}
                    teams={teams}
                    onWorkshopChange={handleWorkshopChange}
                    onWorkshopDelete={handleWorkshopDelete}
                    matchLabel={
                      workshopSearch.trim()
                        ? `${sortedWorkshops.length.toLocaleString()} match${sortedWorkshops.length !== 1 ? "es" : ""}`
                        : undefined
                    }
                  />
                )}
              </div>
            )}
          </div>

          <PendingWorkshopEmailsPanel />
        </section>
      </div>
    </PageLayout>
  );
}
