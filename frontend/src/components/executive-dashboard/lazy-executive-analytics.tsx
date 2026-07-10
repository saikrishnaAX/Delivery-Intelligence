import { useEffect, useRef, useState } from "react";
import { LoadingState } from "@/components/loading-state";
import { ExecutiveAnalyticsView } from "@/components/executive-analytics/executive-analytics-view";

export function LazyExecutiveAnalytics() {
  const anchorRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = anchorRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setVisible(true);
      },
      { rootMargin: "240px 0px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={anchorRef}>
      {visible ? <ExecutiveAnalyticsView /> : <LoadingState rows={2} />}
    </div>
  );
}
