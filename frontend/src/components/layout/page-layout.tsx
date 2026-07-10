import { type ReactNode } from "react";
import { AIInsightsPanel } from "@/components/ai-insights-panel";
import { Info } from "lucide-react";

interface PageInfo {
  title: string;
  description: string;
}

interface PageLayoutProps {
  page: string;
  children: ReactNode;
  /** Static info panel instead of AI insights */
  pageInfo?: PageInfo;
  /** Hide the right sidebar entirely */
  hideSidebar?: boolean;
}

export function PageLayout({ page, children, pageInfo, hideSidebar }: PageLayoutProps) {
  return (
    <div className="flex flex-col xl:flex-row min-h-full">
      <div className="flex-1 min-w-0">{children}</div>
      {!hideSidebar && (
        <aside className="w-full xl:w-64 border-t xl:border-t-0 xl:border-l border-border/80 p-3 xl:sticky xl:top-0 xl:h-screen shrink-0">
          {pageInfo ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                <Info className="h-3.5 w-3.5" />
                {pageInfo.title}
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">{pageInfo.description}</p>
            </div>
          ) : (
            <AIInsightsPanel page={page} />
          )}
        </aside>
      )}
    </div>
  );
}
