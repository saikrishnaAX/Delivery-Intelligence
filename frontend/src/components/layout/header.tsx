import { ThemeToggle } from "@/components/theme-toggle";

interface HeaderProps {
  title: string;
  description?: string;
}

export function Header({ title, description }: HeaderProps) {
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border/80 bg-background/90 backdrop-blur-sm px-4 md:px-5 py-2.5">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold tracking-tight truncate">{title}</h2>
        {description && (
          <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{description}</p>
        )}
      </div>
      <ThemeToggle />
    </header>
  );
}
