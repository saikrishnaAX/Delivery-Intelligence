import { Skeleton } from "@/components/ui/skeleton";

export function LoadingState({ rows = 2 }: { rows?: number }) {
  return (
    <div className="space-y-3 animate-fade-in">
      <div className="grid gap-2 grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 rounded-md" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-48 rounded-md" />
      ))}
    </div>
  );
}
