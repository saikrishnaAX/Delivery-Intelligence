import { useMemo, useState } from "react";
import { format, parseISO, isValid } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type DatePickerProps = {
  value: string;
  onChange: (isoDate: string) => void;
  className?: string;
  placeholder?: string;
  disabled?: boolean;
};

function parseValue(value: string): Date | undefined {
  if (!value) return undefined;
  const d = parseISO(value);
  return isValid(d) ? d : undefined;
}

function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function DatePicker({
  value,
  onChange,
  className,
  placeholder = "Pick a date",
  disabled,
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const selected = useMemo(() => parseValue(value), [value]);
  const label = selected ? format(selected, "dd MMM yyyy") : placeholder;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn(
            "justify-start text-left font-normal gap-2 px-2.5",
            !selected && "text-muted-foreground",
            className
          )}
        >
          <CalendarIcon className="h-3.5 w-3.5 shrink-0 opacity-70" />
          <span className="truncate">{label}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selected}
          onSelect={(d) => {
            if (d) {
              onChange(toIsoDate(d));
              setOpen(false);
            }
          }}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}
