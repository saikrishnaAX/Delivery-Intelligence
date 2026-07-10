import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Tags, Brain, AlertOctagon,
  Building2, Clock, Bot, Zap, UserCheck, FileText, Sheet, Ticket,
  Users, History, TrendingUp, Mail,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, NAV_GROUPS } from "@/lib/constants";

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  LayoutDashboard, Tags, Brain, AlertOctagon,
  Building2, Clock, Bot, UserCheck, FileText, Sheet, Ticket,
  Users, History, TrendingUp, Mail,
};

const navByPath = Object.fromEntries(NAV_ITEMS.map((item) => [item.path, item]));

interface SidebarProps {
  collapsed?: boolean;
}

export function Sidebar({ collapsed }: SidebarProps) {
  return (
    <aside
      className={cn(
        "flex flex-col border-r border-sidebar-border bg-sidebar h-full transition-all",
        collapsed ? "w-14" : "w-52"
      )}
    >
      <div className="flex items-center gap-2.5 px-3 py-3.5 border-b border-sidebar-border">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground shrink-0">
          <Zap className="h-3.5 w-3.5" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <h1 className="text-xs font-semibold truncate text-sidebar-foreground">Autorox AI</h1>
            <p className="text-[10px] text-sidebar-foreground/50 truncate">Delivery Intel</p>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto scrollbar-thin py-2 px-1.5 space-y-3">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <p className="px-2.5 mb-1 text-[9px] font-semibold uppercase tracking-wider text-sidebar-foreground/35">
                {group.label}
              </p>
            )}
            <div className="space-y-0.5">
              {group.paths.map((path) => {
                const item = navByPath[path];
                if (!item) return null;
                const Icon = iconMap[item.icon];
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === "/"}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-xs font-medium transition-colors",
                        isActive
                          ? "bg-primary/15 text-primary"
                          : "text-sidebar-foreground/60 hover:bg-white/5 hover:text-sidebar-foreground"
                      )
                    }
                  >
                    {Icon && <Icon className="h-3.5 w-3.5 shrink-0" />}
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
