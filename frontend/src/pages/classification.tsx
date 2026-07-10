import { useCallback, useEffect, useState } from "react";
import { ExternalLink } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PieChart } from "@/components/charts/pie-chart";
import { BarChart } from "@/components/charts/bar-chart";
import { useProjectApi } from "@/hooks/use-project-api";
import { useProject } from "@/hooks/use-project";
import { api } from "@/lib/api";
import { buildScope, readCache, writeCache } from "@/lib/data-cache";
import { categoryLabel, cn } from "@/lib/utils";
import { CATEGORY_COLORS, TICKET_TYPES, type TicketTypeKey } from "@/lib/constants";
import type { Ticket } from "@/types";

const thClass = "px-3 py-2 font-medium text-left text-[10px] text-muted-foreground";
const tdClass = "px-3 py-2 align-middle text-[11px]";

type StatusFilter = "open" | "all" | "closed";

export default function ClassificationPage() {
  const { projectGid, dateFrom, dateTo, cacheVersion } = useProject();
  const { data, loading, error, refetch } = useProjectApi("classification", (gid, from, to) =>
    api.getClassification(gid, from, to)
  );

  const [selectedType, setSelectedType] = useState<TicketTypeKey>("enhancement");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("open");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [ticketTotal, setTicketTotal] = useState(0);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const ticketCacheScope = buildScope([
    projectGid,
    dateFrom,
    dateTo,
    selectedType,
    statusFilter,
    String(page),
  ]);

  const loadTickets = useCallback(async () => {
    if (!projectGid) return;
    const cached = readCache<{ tickets: Ticket[]; total: number }>(
      "classification-tickets",
      ticketCacheScope
    );
    if (cached) {
      setTickets(cached.tickets);
      setTicketTotal(cached.total);
    } else {
      setTicketsLoading(true);
    }
    try {
      const status = statusFilter === "all" ? undefined : statusFilter;
      const result = await api.getTickets(
        projectGid,
        dateFrom,
        dateTo,
        page,
        pageSize,
        status,
        selectedType
      );
      setTickets(result.tickets);
      setTicketTotal(result.total);
      writeCache("classification-tickets", ticketCacheScope, {
        tickets: result.tickets,
        total: result.total,
      });
    } finally {
      setTicketsLoading(false);
    }
  }, [projectGid, dateFrom, dateTo, page, statusFilter, selectedType, ticketCacheScope]);

  useEffect(() => {
    if (cacheVersion === 0) return;
    void loadTickets();
  }, [cacheVersion]);

  useEffect(() => {
    setPage(1);
  }, [selectedType, statusFilter, projectGid, dateFrom, dateTo]);

  useEffect(() => {
    loadTickets();
  }, [loadTickets]);

  if (loading && !data) {
    return (
      <>
        <Header title="Ticket Types" description="Task, Requirement, Enhancement, Bug" />
        <div className="page-content"><LoadingState /></div>
      </>
    );
  }

  if (error && !data) {
    return (
      <>
        <Header title="Ticket Types" description="Task, Requirement, Enhancement, Bug" />
        <div className="page-content">
          <ErrorState message={error} onRetry={() => void refetch()} />
        </div>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <Header title="Ticket Types" description="Task, Requirement, Enhancement, Bug" />
        <div className="page-content">
          <ErrorState message="Select a project to view ticket types." />
        </div>
      </>
    );
  }

  const pieData = data.support_breakdown.map((c) => ({
    name: c.category,
    value: c.open_count,
  }));

  const typeRow = (key: TicketTypeKey) =>
    data.support_breakdown.find((c) => c.category === key) ?? {
      category: key,
      count: 0,
      open_count: 0,
      percentage: 0,
      trend: [],
    };

  const totalPages = Math.max(1, Math.ceil(ticketTotal / pageSize));

  return (
    <PageLayout page="classification">
      <Header
        title="Ticket Types"
        description="Asana Type field — Task, Requirement, Enhancement, Bug. Select a type to see matching tickets."
      />
      <div className="page-content space-y-4">
        <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
          {TICKET_TYPES.map((typ) => {
            const row = typeRow(typ);
            const active = selectedType === typ;
            return (
              <button
                key={typ}
                type="button"
                onClick={() => setSelectedType(typ)}
                className={cn(
                  "rounded-lg border p-3 text-left transition-colors",
                  active
                    ? "border-primary bg-primary/10 ring-1 ring-primary/40"
                    : "border-border bg-card hover:bg-muted/30"
                )}
              >
                <p className="text-[10px] text-muted-foreground uppercase tracking-wide">
                  {categoryLabel(typ)}
                </p>
                <p className="text-xl font-semibold mt-1">{row.open_count}</p>
                <p className="text-[10px] text-muted-foreground">
                  open · {row.count} total in range
                </p>
              </button>
            );
          })}
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>Open by type</CardTitle></CardHeader>
            <CardContent>
              <PieChart data={pieData} useCategoryColors />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Total in date range</CardTitle></CardHeader>
            <CardContent>
              <BarChart
                data={data.support_breakdown.map((c) => ({
                  category: categoryLabel(c.category),
                  count: c.count,
                }))}
                xKey="category"
                bars={[{ key: "count", name: "Tickets" }]}
                colors={data.support_breakdown.map(
                  (c) => CATEGORY_COLORS[c.category] || "#737373"
                )}
              />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-sm">
                {categoryLabel(selectedType)} tickets
              </CardTitle>
              <div className="flex rounded-md border border-border overflow-hidden">
                {(["open", "all", "closed"] as StatusFilter[]).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStatusFilter(s)}
                    className={cn(
                      "px-2.5 py-1 text-[10px] font-medium capitalize transition-colors",
                      statusFilter === s
                        ? "bg-primary text-primary-foreground"
                        : "bg-card text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {ticketsLoading && tickets.length === 0 ? (
              <LoadingState />
            ) : tickets.length === 0 ? (
              <p className="text-xs text-muted-foreground py-6 text-center">
                No {statusFilter !== "all" ? statusFilter : ""} {categoryLabel(selectedType)} tickets
                in this date range.
              </p>
            ) : (
              <>
                <p className="text-[10px] text-muted-foreground">
                  Showing {tickets.length} of {ticketTotal} ticket{ticketTotal !== 1 ? "s" : ""}
                </p>
                <div className="overflow-x-auto rounded-md border border-border max-h-[480px] overflow-y-auto">
                  <table className="w-full border-collapse table-fixed min-w-[900px]">
                    <colgroup>
                      <col style={{ width: "34%" }} />
                      <col style={{ width: "18%" }} />
                      <col style={{ width: "14%" }} />
                      <col style={{ width: "12%" }} />
                      <col style={{ width: "14%" }} />
                      <col style={{ width: "8%" }} />
                    </colgroup>
                    <thead className="sticky top-0 z-10">
                      <tr className="border-b border-border bg-muted shadow-[0_1px_0_0_hsl(var(--border))]">
                        <th className={thClass}>Title</th>
                        <th className={thClass}>Workshop</th>
                        <th className={thClass}>Asana type</th>
                        <th className={thClass}>Status</th>
                        <th className={thClass}>Assignee</th>
                        <th className={cn(thClass, "w-10")} />
                      </tr>
                    </thead>
                    <tbody>
                      {tickets.map((t) => (
                        <tr key={t.id} className="border-t border-border/50 hover:bg-muted/10">
                          <td className={cn(tdClass, "font-medium max-w-0 align-top")}>
                            <span className="line-clamp-2" title={t.title}>{t.title}</span>
                          </td>
                          <td className={cn(tdClass, "text-muted-foreground truncate max-w-0")} title={t.workshop_name || t.customer_name || undefined}>
                            {t.workshop_name || t.customer_name || "—"}
                          </td>
                          <td className={tdClass}>
                            <Badge variant="outline" className="text-[9px] capitalize">
                              {t.asana_type_raw || categoryLabel(selectedType)}
                            </Badge>
                          </td>
                          <td className={tdClass}>
                            <Badge variant="outline" className="text-[9px] capitalize">
                              {t.status.replace(/_/g, " ")}
                            </Badge>
                          </td>
                          <td className={tdClass}>{t.assignee || "—"}</td>
                          <td className={tdClass}>
                            {t.asana_url ? (
                              <a
                                href={t.asana_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex text-primary hover:text-primary/80"
                                title="Open in Asana"
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                              </a>
                            ) : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {totalPages > 1 && (
                  <div className="flex items-center justify-between pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-[10px]"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      Previous
                    </Button>
                    <span className="text-[10px] text-muted-foreground">
                      Page {page} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-[10px]"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  );
}
