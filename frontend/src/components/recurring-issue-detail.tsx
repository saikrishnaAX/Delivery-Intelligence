import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { RecurringIssueDetail } from "@/types";
import { cn } from "@/lib/utils";
import {
  AlertTriangle, Building2, Calendar, CheckCircle2, ClipboardCheck,
  ExternalLink, GitBranch, Lightbulb, Shield, TrendingDown, TrendingUp,
  Wrench, X,
} from "lucide-react";

function TrendBadge({ trend }: { trend: string }) {
  const t = trend.toLowerCase();
  if (t === "increasing") {
    return (
      <Badge variant="destructive" className="text-[8px] gap-0.5">
        <TrendingUp className="h-2.5 w-2.5" /> Increasing
      </Badge>
    );
  }
  if (t === "decreasing") {
    return (
      <Badge variant="default" className="text-[8px] gap-0.5 bg-emerald-600">
        <TrendingDown className="h-2.5 w-2.5" /> Decreasing
      </Badge>
    );
  }
  return <Badge variant="secondary" className="text-[8px]">Stable</Badge>;
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon?: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  if (!children) return null;
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
        {Icon && <Icon className="h-3 w-3" />}
        {title}
      </h4>
      <div className="text-xs leading-relaxed">{children}</div>
    </div>
  );
}

interface RecurringIssueDetailPanelProps {
  issue: RecurringIssueDetail;
  onClose: () => void;
}

export function RecurringIssueDetailPanel({ issue, onClose }: RecurringIssueDetailPanelProps) {
  const resolutionUnknown =
    !issue.developer_resolution ||
    issue.developer_resolution === "Resolution Unknown." ||
    issue.developer_resolution.toLowerCase().includes("resolution unknown");

  const regressionTests = resolutionUnknown ? [] : issue.regression_test_cases;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl border-l border-border bg-background shadow-2xl flex flex-col">
      <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3 shrink-0">
        <div className="min-w-0 space-y-1">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Recurring Issue</p>
          <h2 className="text-sm font-semibold leading-snug">{issue.issue_name}</h2>
          <div className="flex flex-wrap gap-1">
            <Badge variant="outline" className="text-[8px] capitalize">{issue.issue_type.replace(/_/g, " ")}</Badge>
            <Badge variant={issue.severity === "critical" ? "destructive" : "secondary"} className="text-[8px] capitalize">
              {issue.severity}
            </Badge>
            <TrendBadge trend={issue.trend} />
            <Badge variant="outline" className="text-[8px]">
              {Math.round((issue.confidence ?? 0) * 100)}% confidence
            </Badge>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="h-8 w-8 p-0 shrink-0" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-5">
          {/* Overview */}
          <Section title="Executive summary" icon={Shield}>
            <p className="text-muted-foreground">{issue.overview?.executive_summary || issue.executive_summary}</p>
          </Section>

          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <Card className="border-border/60">
              <CardContent className="py-2 px-3">
                <p className="text-muted-foreground">Tickets</p>
                <p className="text-lg font-semibold tabular-nums">{issue.ticket_count}</p>
                <p className="text-muted-foreground">{issue.open_count} open</p>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="py-2 px-3">
                <p className="text-muted-foreground">Workshops</p>
                <p className="text-lg font-semibold tabular-nums">{issue.workshop_count}</p>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="py-2 px-3">
                <p className="text-muted-foreground">Recurring since</p>
                <p className="font-medium">{issue.recurring_since ?? "—"}</p>
              </CardContent>
            </Card>
            <Card className="border-border/60">
              <CardContent className="py-2 px-3">
                <p className="text-muted-foreground">Latest occurrence</p>
                <p className="font-medium">{issue.latest_occurrence ?? "—"}</p>
              </CardContent>
            </Card>
          </div>

          {issue.overview?.engineering_fix_hypothesis && (
            <Section title="Engineering fix hypothesis" icon={Wrench}>
              <p className="text-muted-foreground italic">{issue.overview.engineering_fix_hypothesis}</p>
              {issue.engineering_fix_label && (
                <Badge variant="outline" className="mt-1 text-[8px]">{issue.engineering_fix_label}</Badge>
              )}
            </Section>
          )}

          <Separator />

          {/* Evidence */}
          <Section title="Evidence from tickets" icon={Shield}>
            <p className="text-muted-foreground text-[10px] mb-2">{issue.evidence_summary}</p>
            <p className="text-[10px] font-medium mb-1">
              Sample tickets ({issue.evidence.length} of {issue.evidence_total})
            </p>
            <ul className="space-y-2">
              {issue.evidence.map((t) => (
                <li key={t.id} className="rounded-md border border-border/50 p-2 text-[10px]">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium leading-snug">{t.title}</span>
                    {t.asana_url && (
                      <a href={t.asana_url} target="_blank" rel="noreferrer" className="text-primary shrink-0">
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1 text-muted-foreground">
                    <Badge variant="outline" className="text-[7px] px-1">{t.status}</Badge>
                    {t.workshop_name && <span>{t.workshop_name}</span>}
                    {t.created_at && <span>· {t.created_at.slice(0, 10)}</span>}
                  </div>
                  {t.description_excerpt && (
                    <p className="mt-1 text-muted-foreground line-clamp-2">{t.description_excerpt}</p>
                  )}
                </li>
              ))}
            </ul>
          </Section>

          <Separator />

          {/* Impact */}
          <div className="grid gap-3 sm:grid-cols-2">
            <Section title="Affected workshops" icon={Building2}>
              <p className="text-[10px] text-muted-foreground">
                {(issue.all_workshops ?? []).slice(0, 12).join(", ")}
                {(issue.all_workshops?.length ?? 0) > 12 && ` +${issue.all_workshops!.length - 12} more`}
              </p>
            </Section>
            <Section title="Affected modules" icon={GitBranch}>
              <div className="flex flex-wrap gap-1">
                {(issue.all_modules ?? []).map((m) => (
                  <Badge key={m} variant="outline" className="text-[8px]">{m}</Badge>
                ))}
              </div>
            </Section>
          </div>

          {(issue.all_releases?.length ?? 0) > 0 && (
            <Section title="Affected releases" icon={Calendar}>
              <p className="text-[10px]">{issue.all_releases!.join(" · ")}</p>
            </Section>
          )}

          {issue.timeline.length > 0 && (
            <Section title="Timeline" icon={Calendar}>
              <div className="flex flex-wrap gap-2">
                {issue.timeline.map((t) => (
                  <Badge key={t.month} variant="secondary" className="text-[8px]">
                    {t.month}: {t.count}
                  </Badge>
                ))}
              </div>
            </Section>
          )}

          <Separator />

          {/* Root cause & resolution */}
          <Section title="Root cause" icon={Wrench}>
            <p>{issue.root_cause}</p>
          </Section>

          <Section title="Developer resolution" icon={CheckCircle2}>
            <p className={cn(resolutionUnknown && "text-muted-foreground italic")}>
              {issue.developer_resolution || "Resolution Unknown."}
            </p>
          </Section>

          <Section title="Business impact" icon={AlertTriangle}>
            <p>{issue.business_impact}</p>
          </Section>

          <Section title="Customer impact" icon={Building2}>
            <p>{issue.customer_impact}</p>
          </Section>

          {issue.suggested_permanent_fix && (
            <Section title="Suggested permanent fix" icon={Wrench}>
              <p>{issue.suggested_permanent_fix}</p>
            </Section>
          )}

          {issue.suggested_product_improvement && (
            <Section title="Suggested product improvement" icon={Lightbulb}>
              <p>{issue.suggested_product_improvement}</p>
            </Section>
          )}

          {/* Regression */}
          <div className="rounded-lg border border-border/60 p-3 space-y-2">
            <p className="text-[10px] font-semibold flex items-center gap-1">
              <ClipboardCheck className="h-3.5 w-3.5" />
              Regression test cases
            </p>
            {regressionTests.length > 0 ? (
              <ol className="list-decimal pl-4 space-y-1 text-[10px] text-muted-foreground">
                {regressionTests.map((tc, i) => (
                  <li key={i}>{tc}</li>
                ))}
              </ol>
            ) : (
              <p className="text-[10px] text-muted-foreground italic">
                No regression tests generated — resolution not verified in ticket evidence.
              </p>
            )}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
