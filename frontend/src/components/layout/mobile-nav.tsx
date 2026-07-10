import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { Sidebar } from "./sidebar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setOpen(false);
  }, [location]);

  return (
    <div className="lg:hidden">
      <div className="flex items-center justify-between border-b border-border/80 px-3 py-2 bg-sidebar">
        <span className="text-xs font-semibold text-sidebar-foreground">Autorox AI</span>
        <Button variant="ghost" size="icon" onClick={() => setOpen(!open)} aria-label="Toggle menu" className="h-7 w-7 text-sidebar-foreground">
          {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </Button>
      </div>
      <div className={cn(
        "fixed inset-0 top-[41px] z-50 bg-sidebar transition-transform lg:hidden",
        open ? "translate-x-0" : "-translate-x-full"
      )}>
        <Sidebar />
      </div>
      {open && (
        <div className="fixed inset-0 top-[41px] z-40 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />
      )}
    </div>
  );
}
