import { Button } from "@/components/ui/button";

interface TablePaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function TablePagination({ page, pageSize, total, onPageChange }: TablePaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between pt-2 gap-2 flex-wrap">
      <Button
        variant="outline"
        size="sm"
        className="h-7 text-[10px]"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      >
        Previous
      </Button>
      <span className="text-[10px] text-muted-foreground tabular-nums">
        {from}–{to} of {total} · page {page}/{totalPages}
      </span>
      <Button
        variant="outline"
        size="sm"
        className="h-7 text-[10px]"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </Button>
    </div>
  );
}
