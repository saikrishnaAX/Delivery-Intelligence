import { useState } from "react";
import { ChevronDown, UserPlus, UserCheck, Users, Clock } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { MetricCard } from "@/components/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProjectApi } from "@/hooks/use-project-api";
import { api } from "@/lib/api";
import { cn, formatHours } from "@/lib/utils";
import type { SupportTeamMember } from "@/types";

function SupportMemberRow({ member }: { member: SupportTeamMember }) {
  const [open, setOpen] = useState(false);
  const canExpand = member.open_assigned > 0;

  return (
    <>
      <tr className="border-b border-border/30">
        <td className="py-2">
          <button
            type="button"
            onClick={() => canExpand && setOpen((v) => !v)}
            disabled={!canExpand}
            className={cn(
              "flex items-center gap-1.5 text-left font-medium",
              canExpand && "hover:text-primary cursor-pointer"
            )}
          >
            {canExpand && (
              <ChevronDown
                className={cn(
                  "h-3 w-3 shrink-0 text-muted-foreground transition-transform",
                  open && "rotate-180"
                )}
              />
            )}
            <span>{member.name}</span>
          </button>
          {canExpand && !open && (
            <p className="text-[9px] text-primary mt-0.5 pl-5">Click to view open tickets</p>
          )}
        </td>
        <td className="text-right tabular-nums py-2">{member.tickets_created}</td>
        <td className="text-right tabular-nums py-2">{member.tickets_closed}</td>
        <td className="text-right tabular-nums py-2">{member.open_assigned}</td>
        <td className="text-right tabular-nums py-2">
          {member.avg_resolution_hours ? formatHours(member.avg_resolution_hours) : "—"}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={5} className="pb-2 pt-0">
            <ul className="ml-4 space-y-1 border-l border-border/40 pl-3 max-h-48 overflow-y-auto scrollbar-thin">
              {member.open_tickets.map((ticket) => (
                <li key={ticket.id} className="flex items-start gap-2 py-0.5">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full shrink-0 bg-warning" />
                  <p className="text-[10px] leading-snug text-foreground/90">{ticket.title}</p>
                </li>
              ))}
            </ul>
          </td>
        </tr>
      )}
    </>
  );
}

export default function SupportTeamPage() {
  const { data, loading, error, refetch } = useProjectApi("support-team", (gid, from, to) =>
    api.getSupportTeam(gid, from, to)
  );

  if (loading && !data) {
    return (
      <>
        <Header title="Support Team" description="Who creates, closes, and owns tickets" />
        <div className="page-content"><LoadingState /></div>
      </>
    );
  }

  if (error && !data) {
    return (
      <>
        <Header title="Support Team" description="Who creates, closes, and owns tickets" />
        <div className="page-content">
          <ErrorState message={error} onRetry={() => void refetch()} />
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Header title="Support Team" description="Who creates, closes, and owns tickets" />
        <div className="page-content">
          <ErrorState message="No support team data for this project." />
        </div>
      </>
    );
  }

  const topCreators = [...data.members].sort((a, b) => b.tickets_created - a.tickets_created).slice(0, 5);
  const topClosers = [...data.members].sort((a, b) => b.tickets_closed - a.tickets_closed).slice(0, 5);
  const topOpenLoad = [...data.members].sort((a, b) => b.open_assigned - a.open_assigned).filter((m) => m.open_assigned > 0).slice(0, 5);

  return (
    <PageLayout page="support-team">
      <Header title="Support Team" description="Who creates, closes, and owns tickets" />
      <div className="page-content">
        <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
          <MetricCard title="Team members" value={data.total_members} icon={Users} />
          <MetricCard title="Top creator" value={data.top_creator ?? "—"} icon={UserPlus} />
          <MetricCard title="Top closer" value={data.top_closer ?? "—"} icon={UserCheck} variant="success" />
          <MetricCard
            title="Highest open load"
            value={topOpenLoad[0]?.name?.split(" ")[0] ?? "—"}
            icon={Clock}
          />
        </div>

        <div className="grid gap-3 lg:grid-cols-3">
          <Card>
            <CardHeader className="pb-2"><CardTitle>Most created</CardTitle></CardHeader>
            <CardContent className="space-y-1.5">
              {topCreators.map((m) => (
                <div key={m.name} className="flex justify-between text-[10px] py-1 border-b border-border/30 last:border-0">
                  <span className="font-medium truncate">{m.name}</span>
                  <span className="tabular-nums text-muted-foreground">{m.tickets_created}</span>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle>Most closed</CardTitle></CardHeader>
            <CardContent className="space-y-1.5">
              {topClosers.filter((m) => m.tickets_closed > 0).map((m) => (
                <div key={m.name} className="flex justify-between text-[10px] py-1 border-b border-border/30 last:border-0">
                  <span className="font-medium truncate">{m.name}</span>
                  <span className="tabular-nums text-muted-foreground">{m.tickets_closed}</span>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle>Highest open load</CardTitle></CardHeader>
            <CardContent className="space-y-1.5">
              {topOpenLoad.map((m) => (
                <div key={m.name} className="flex justify-between text-[10px] py-1 border-b border-border/30 last:border-0">
                  <span className="font-medium truncate">{m.name}</span>
                  <span className="tabular-nums text-warning">{m.open_assigned} open</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader><CardTitle>Full team breakdown</CardTitle></CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="text-muted-foreground border-b border-border/60">
                    <th className="text-left py-1.5 font-medium">Name</th>
                    <th className="text-right py-1.5 font-medium">Created</th>
                    <th className="text-right py-1.5 font-medium">Closed</th>
                    <th className="text-right py-1.5 font-medium">Open</th>
                    <th className="text-right py-1.5 font-medium">Avg close</th>
                  </tr>
                </thead>
                <tbody>
                  {data.members.map((m) => (
                    <SupportMemberRow key={m.name} member={m} />
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  );
}
