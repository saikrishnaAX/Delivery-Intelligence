import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { LoadingState } from "@/components/loading-state";
import { ErrorState } from "@/components/error-state";
import { TablePagination } from "@/components/table-pagination";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { buildScope, readCache } from "@/lib/data-cache";
import { refreshCached } from "@/lib/fetch-with-cache";
import { useProject } from "@/hooks/use-project";
import type { ActivityLogEntry } from "@/types";

const MODULES = ["", "release_notes", "workshops", "issue_intelligence", "org"];
const PAGE_SIZE = 50;

function formatWhen(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

type ActivityCache = {
  items: ActivityLogEntry[];
  total: number;
  page: number;
  page_size: number;
};

export default function ActivityPage() {
  const { cacheVersion, dateFrom, dateTo } = useProject();
  const [moduleFilter, setModuleFilter] = useState("");
  const [page, setPage] = useState(1);
  const cacheScope = buildScope([moduleFilter, dateFrom, dateTo, String(page)]);
  const cached = readCache<ActivityCache>("activity", cacheScope);

  const [items, setItems] = useState<ActivityLogEntry[]>(() => cached?.items ?? []);
  const [total, setTotal] = useState(() => cached?.total ?? 0);
  const [loading, setLoading] = useState(() => !cached);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((data: ActivityCache) => {
    setItems(data.items);
    setTotal(data.total);
    setError(null);
  }, []);

  const load = useCallback(async () => {
    const hit = readCache<ActivityCache>("activity", cacheScope);
    if (hit) apply(hit);
    else setLoading(true);
    setError(null);
    try {
      await refreshCached(
        "activity",
        cacheScope,
        () =>
          api.getActivity({
            module: moduleFilter || undefined,
            dateFrom,
            dateTo,
            page,
            pageSize: PAGE_SIZE,
          }),
        apply
      );
    } catch (err) {
      if (!readCache<ActivityCache>("activity", cacheScope)) {
        setError(err instanceof Error ? err.message : "Failed to load activity log");
      }
    } finally {
      setLoading(false);
    }
  }, [moduleFilter, dateFrom, dateTo, page, cacheScope, apply]);

  useEffect(() => {
    setPage(1);
  }, [moduleFilter, dateFrom, dateTo]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (cacheVersion === 0) return;
    void refreshCached(
      "activity",
      cacheScope,
      () =>
        api.getActivity({
          module: moduleFilter || undefined,
          dateFrom,
          dateTo,
          page,
          pageSize: PAGE_SIZE,
        }),
      apply
    );
  }, [cacheVersion, cacheScope, moduleFilter, dateFrom, dateTo, page, apply]);

  return (
    <PageLayout page="activity">
      <Header title="Activity Log" description="Audit trail across all modules" />
      <div className="page-content space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] text-muted-foreground">Module</span>
          <select
            className="h-7 text-xs rounded-md border border-border bg-background px-2"
            value={moduleFilter}
            onChange={(e) => setModuleFilter(e.target.value)}
          >
            {MODULES.map((m) => (
              <option key={m} value={m}>{m || "All"}</option>
            ))}
          </select>
          <span className="text-[10px] text-muted-foreground ml-auto">{total} entries</span>
        </div>

        {error && items.length === 0 && (
          <ErrorState message={error} onRetry={() => void load()} />
        )}

        {loading && items.length === 0 && !error ? (
          <LoadingState />
        ) : items.length === 0 && !error ? (
          <Card>
            <CardContent className="py-8 text-center text-xs text-muted-foreground">
              No activity logged yet.
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="space-y-1.5">
              {items.map((entry) => (
                <Card key={entry.id} className="border-border/60">
                  <CardContent className="py-2 flex items-start gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline" className="text-[9px] px-1.5 py-0">{entry.module}</Badge>
                        <Badge variant="secondary" className="text-[9px] px-1.5 py-0">{entry.action}</Badge>
                        <span className="text-[10px] text-muted-foreground">{formatWhen(entry.created_at)}</span>
                      </div>
                      <p className="text-xs mt-1">{entry.summary}</p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
            <TablePagination
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              onPageChange={setPage}
            />
          </>
        )}
      </div>
    </PageLayout>
  );
}
