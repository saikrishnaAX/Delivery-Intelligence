import type { CEOQuickView } from "@/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Brain, Layers, TrendingUp } from "lucide-react";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-border/50 bg-card px-4 py-4">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold tabular-nums mt-1">{value}</p>
      {sub && <p className="text-[10px] text-muted-foreground mt-1 leading-snug">{sub}</p>}
    </div>
  );
}

export function CEOQuickView({ data }: { data: CEOQuickView }) {
  const { bugs, modules, issues } = data;

  return (
    <article className="w-full min-w-0 space-y-6">
      <header className="rounded-xl border border-border/50 bg-gradient-to-r from-primary/5 to-transparent px-5 py-5">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-primary/10 p-2.5">
            <Brain className="h-5 w-5 text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-semibold tracking-tight">Engineering Quality — Facts at a Glance</h1>
            <p className="text-xs text-muted-foreground mt-1">{data.period_before}</p>
            <p className="text-xs text-muted-foreground">{data.period_after}</p>
          </div>
          <Badge variant="outline" className="text-[9px] shrink-0">
            AI from {data.ai_adoption_date}
          </Badge>
        </div>
      </header>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Bugs / month (pre-AI)" value={bugs.per_month_pre} sub={`${bugs.total_pre} total`} />
        <StatCard label="Bugs / month (post-AI)" value={bugs.per_month_post} sub={`${bugs.total_post} total`} />
        <StatCard label="Enhancements / mo (pre)" value={bugs.enhancements_per_month_pre} />
        <StatCard label="Enhancements / mo (post)" value={bugs.enhancements_per_month_post} />
      </div>

      <section className="rounded-xl border border-border/50 overflow-hidden">
        <div className="px-4 py-3 border-b border-border/40 bg-muted/20 flex items-center gap-2">
          <Layers className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-semibold">Bugs by product area</h2>
          <span className="text-[10px] text-muted-foreground ml-auto">
            {data.modules_existed_count} existed pre-AI · {data.modules_new_count} new post-AI
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border/30">
                <th className="text-left py-2.5 px-4 font-medium whitespace-nowrap">Area</th>
                <th className="text-right py-2.5 px-2 font-medium whitespace-nowrap">Pre/mo</th>
                <th className="text-right py-2.5 px-2 font-medium whitespace-nowrap">Post/mo</th>
                <th className="text-left py-2.5 px-4 font-medium min-w-[12rem]">What reports describe</th>
                <th className="text-left py-2.5 px-3 font-medium whitespace-nowrap">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/20">
              {modules.map((m) => (
                <tr key={m.area} className={cn(m.area.includes("Customer Concerns") && "bg-primary/5")}>
                  <td className="py-2.5 px-4 font-medium">{m.area}</td>
                  <td className="py-2.5 px-2 text-right tabular-nums">{m.per_month_pre}</td>
                  <td className="py-2.5 px-2 text-right tabular-nums">{m.per_month_post}</td>
                  <td className="py-2.5 px-4 text-muted-foreground leading-snug">{m.description}</td>
                  <td className="py-2.5 px-3">
                    <Badge
                      variant={m.status === "new_after_ai" ? "outline" : "secondary"}
                      className="text-[9px] font-normal"
                    >
                      {m.status === "new_after_ai" ? "New" : "Pre-AI"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border/50 px-4 py-4">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Recurring patterns before AI</h2>
            <Badge variant="secondary" className="text-[9px] ml-auto">{issues.clusters_existed_before_ai} patterns</Badge>
          </div>
          <p className="text-[10px] text-muted-foreground mb-2">From pre-AI bug history in the comparison window</p>
          <ul className="space-y-2">
            {(issues.existed_by_area || []).map((item) => (
              <li key={item.area} className="text-xs">
                <span className="font-medium">{item.area}</span>
                <span className="text-muted-foreground"> — {item.understanding}</span>
                <span className="text-[10px] text-muted-foreground block mt-0.5">
                  {item.clusters} clusters · {item.tickets} tickets
                </span>
              </li>
            ))}
            {!issues.existed_by_area?.length && (
              <li className="text-xs text-muted-foreground">No recurring clusters in this window.</li>
            )}
          </ul>
        </div>

        <div className="rounded-xl border border-border/50 px-4 py-4">
          <h2 className="text-sm font-semibold mb-3">
            New after AI
            <Badge variant="outline" className="text-[9px] ml-2">{issues.clusters_new_after_ai} clusters</Badge>
          </h2>
          {(issues.new_by_area || []).length > 0 ? (
            <ul className="space-y-2 mb-4">
              {issues.new_by_area.map((item) => (
                <li key={item.area} className="text-xs">
                  <span className="font-medium">{item.area}</span>
                  <span className="text-muted-foreground"> — {item.understanding}</span>
                  <span className="text-[10px] text-muted-foreground block">{item.clusters} clusters · {item.tickets} tickets</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground mb-4">No entirely new product areas after AI adoption.</p>
          )}
          {(issues.new_patterns_in_existing_modules || []).length > 0 && (
            <>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">New patterns in existing modules</p>
              <ul className="space-y-1.5">
                {issues.new_patterns_in_existing_modules.map((p, i) => (
                  <li key={i} className="text-xs text-foreground/85">
                    <span className="font-medium">{p.area}:</span> {p.understanding}
                    {p.first_seen && <span className="text-muted-foreground"> · from {p.first_seen}</span>}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </section>

      <p className="text-[10px] text-muted-foreground text-center px-4 leading-relaxed">
        {data.note} Detailed trends, charts, and ticket-level analysis are on the Executive Dashboard tab.
      </p>
    </article>
  );
}
