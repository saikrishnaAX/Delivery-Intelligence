import { useState, useCallback, useEffect } from "react";
import { ChevronDown, History } from "lucide-react";
import { cn } from "@/lib/utils";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { StatCard } from "@/components/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BarChart } from "@/components/charts/bar-chart";
import { useProjectApi } from "@/hooks/use-project-api";
import { useProject } from "@/hooks/use-project";
import { api } from "@/lib/api";
import { buildScope, readCache } from "@/lib/data-cache";
import { refreshCached } from "@/lib/fetch-with-cache";
import type { CustomerPainItem, WorkshopHistoryItem } from "@/types";

type Tab = "pain" | "history";

function WorkshopRow({ customer }: { customer: CustomerPainItem }) {
  const [open, setOpen] = useState(false);

  return (
    <Card>
      <CardContent className="py-2.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="w-full flex items-start justify-between gap-3 text-left"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
                  open && "rotate-180"
                )}
              />
              <h4 className="text-xs font-medium">{customer.customer_name}</h4>
              <Badge variant="outline" className="text-[9px] px-1.5 py-0 capitalize">{customer.tier}</Badge>
            </div>
            <p className="text-[10px] text-muted-foreground mt-0.5 pl-5">
              {customer.ticket_count} total · {customer.open_tickets} open
              {customer.critical_tickets > 0 && (
                <span className="text-destructive"> · {customer.critical_tickets} blocked</span>
              )}
            </p>
            {(customer.support_person_name || customer.support_person_email) && (
              <p className="text-[10px] text-primary/80 mt-0.5 pl-5">
                Support: {customer.support_person_name ?? "—"}
                {customer.support_person_email ? ` (${customer.support_person_email})` : ""}
              </p>
            )}
          </div>
          <p className="text-base font-semibold tabular-nums shrink-0">{customer.pain_score}</p>
        </button>

        {open && (
          customer.tickets.length > 0 ? (
            <ul className="mt-2 pl-5 space-y-1 border-t border-border/40 pt-2 max-h-64 overflow-y-auto scrollbar-thin">
              {customer.tickets.map((ticket) => (
                <li key={ticket.id} className="flex items-start gap-2 py-0.5">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full shrink-0 bg-warning" />
                  <p className="text-[10px] leading-snug text-foreground/90 min-w-0 flex-1">{ticket.title}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 pl-5 pt-2 border-t border-border/40 text-[10px] text-muted-foreground">
              No open tickets for this workshop.
            </p>
          )
        )}
      </CardContent>
    </Card>
  );
}

function HistoryRow({ item }: { item: WorkshopHistoryItem }) {
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <CardContent className="py-2.5">
        <button type="button" onClick={() => setOpen((v) => !v)} className="w-full text-left">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h4 className="text-xs font-medium">{item.workshop_name}</h4>
              <p className="text-[10px] text-muted-foreground">
                {item.sprint_name} · {item.issues_released} released
                {item.release_date && ` · ${new Date(item.release_date).toLocaleDateString()}`}
              </p>
              {item.support_person_name && (
                <p className="text-[10px] text-muted-foreground">Support: {item.support_person_name}</p>
              )}
            </div>
            <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 transition-transform", open && "rotate-180")} />
          </div>
        </button>
        {open && item.tickets.length > 0 && (
          <ul className="mt-2 space-y-1 border-t border-border/40 pt-2">
            {item.tickets.map((t) => (
              <li key={t.id} className="text-[10px]">
                {t.asana_url ? (
                  <a href={t.asana_url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                    {t.title}
                  </a>
                ) : (
                  t.title
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default function CustomersPage() {
  const { projectGid, cacheVersion } = useProject();
  const [tab, setTab] = useState<Tab>("pain");
  const { data, loading, error, refetch } = useProjectApi("customers", (gid, from, to) =>
    api.getCustomers(gid, from, to)
  );
  const historyScope = buildScope([projectGid]);
  const historyCached = readCache<{ items: WorkshopHistoryItem[] }>("workshop-history", historyScope);
  const [history, setHistory] = useState<WorkshopHistoryItem[]>(() => historyCached?.items ?? []);
  const [historyLoading, setHistoryLoading] = useState(() => !historyCached);

  const loadHistory = useCallback(async () => {
    const hit = readCache<{ items: WorkshopHistoryItem[] }>("workshop-history", historyScope);
    if (hit) setHistory(hit.items);
    else setHistoryLoading(true);
    try {
      await refreshCached(
        "workshop-history",
        historyScope,
        async () => {
          const res = await api.getWorkshopHistory(projectGid);
          return { items: res.items };
        },
        (res) => setHistory(res.items)
      );
    } finally {
      setHistoryLoading(false);
    }
  }, [projectGid, historyScope]);

  useEffect(() => {
    if (tab === "history") void loadHistory();
  }, [tab, loadHistory]);

  useEffect(() => {
    if (cacheVersion === 0 || tab !== "history") return;
    void refreshCached(
      "workshop-history",
      historyScope,
      async () => {
        const res = await api.getWorkshopHistory(projectGid);
        return { items: res.items };
      },
      (res) => setHistory(res.items)
    );
  }, [cacheVersion, tab, projectGid, historyScope]);

  if (loading && !data) {
    return (
      <>
        <Header title="Workshops" description="Ticket volume by workshop / garage name" />
        <div className="page-content"><LoadingState /></div>
      </>
    );
  }

  if (error && !data) {
    return (
      <>
        <Header title="Workshops" description="Ticket volume by workshop / garage name" />
        <div className="page-content">
          <ErrorState message={error} onRetry={() => void refetch()} />
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Header title="Workshops" description="Ticket volume by workshop / garage name" />
        <div className="page-content">
          <ErrorState message="No workshop data for this project." />
        </div>
      </>
    );
  }

  return (
    <PageLayout page="customers">
      <Header title="Workshops" description="Ticket volume, support contacts, and sprint history" />
      <div className="page-content">
        <div className="flex gap-1 mb-3">
          <button
            type="button"
            onClick={() => setTab("pain")}
            className={cn(
              "px-3 py-1.5 text-xs rounded-md",
              tab === "pain" ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-muted"
            )}
          >
            Current pain
          </button>
          <button
            type="button"
            onClick={() => setTab("history")}
            className={cn(
              "px-3 py-1.5 text-xs rounded-md flex items-center gap-1",
              tab === "history" ? "bg-primary/15 text-primary" : "text-muted-foreground hover:bg-muted"
            )}
          >
            <History className="h-3 w-3" /> Sprint history
          </button>
        </div>

        {tab === "pain" ? (
          <>
            <div className="grid gap-2 grid-cols-2 mb-3">
              <StatCard label="Workshops" value={data.total_customers} />
              <StatCard label="Highest volume" value={data.top_pain_customer} valueClassName="text-destructive" />
            </div>
            <Card className="mb-3">
              <CardHeader><CardTitle>Workshop volume</CardTitle></CardHeader>
              <CardContent>
                <BarChart
                  data={data.customers.slice(0, 8).map((c) => ({
                    customer: c.customer_name.length > 10 ? c.customer_name.slice(0, 10) + "…" : c.customer_name,
                    pain_score: c.pain_score,
                  }))}
                  xKey="customer"
                  bars={[{ key: "pain_score", name: "Score" }]}
                  height={200}
                />
              </CardContent>
            </Card>
            <div className="space-y-2">
              {data.customers.map((customer) => (
                <WorkshopRow key={customer.customer_id} customer={customer} />
              ))}
            </div>
          </>
        ) : historyLoading && history.length === 0 ? (
          <LoadingState />
        ) : history.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-xs text-muted-foreground">
              No sprint release history yet. Mark a sprint as released from the Sprint Sheet page.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {history.map((item) => (
              <HistoryRow
                key={`${item.workshop_name}-${item.sprint_name}`}
                item={item}
              />
            ))}
          </div>
        )}
      </div>
    </PageLayout>
  );
}
