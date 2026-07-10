export const NAV_ITEMS = [
  { path: "/", label: "Execution", icon: "LayoutDashboard", page: "executive" },
  { path: "/blockers", label: "Blockers", icon: "AlertOctagon", page: "blockers" },
  { path: "/customers", label: "Workshops", icon: "Building2", page: "customers" },
  { path: "/support-team", label: "Support Team", icon: "UserCheck", page: "support-team" },
  { path: "/classification", label: "Ticket Types", icon: "Tags", page: "classification" },
  { path: "/resolution", label: "Monthly Progress", icon: "Clock", page: "resolution" },
  { path: "/impact", label: "My Impact", icon: "TrendingUp", page: "impact" },
  { path: "/jira", label: "Jira", icon: "Ticket", page: "jira" },
  { path: "/issue-intelligence", label: "Issue Intelligence", icon: "Brain", page: "issue-intelligence" },
  { path: "/release-notes", label: "Release Notes", icon: "FileText", page: "release-notes" },
  { path: "/sprint-sheet", label: "Sprint Sheet", icon: "Sheet", page: "sprint-sheet" },
  { path: "/workshop-emails", label: "Workshop Releases", icon: "Mail", page: "workshop-emails" },
  { path: "/people-workshops", label: "People & Workshops", icon: "Users", page: "people-workshops" },
  { path: "/activity", label: "Activity Log", icon: "History", page: "activity" },
  { path: "/assistant", label: "Assistant", icon: "Bot", page: "assistant" },
] as const;

/** Sidebar sections — operational items first, then analytics and delivery tools. */
export const NAV_GROUPS: { label: string; paths: string[] }[] = [
  { label: "Daily ops", paths: ["/", "/blockers", "/customers", "/support-team"] },
  { label: "Analytics", paths: ["/classification", "/resolution", "/impact", "/jira"] },
  { label: "Intelligence", paths: ["/issue-intelligence"] },
  { label: "Delivery", paths: ["/release-notes", "/sprint-sheet", "/workshop-emails"] },
  { label: "Admin", paths: ["/people-workshops", "/activity", "/assistant"] },
];

/** Routes where the project picker and date range filter the page data. */
export const PROJECT_SCOPED_ROUTES = [
  "/",
  "/support-team",
  "/classification",
  "/issue-intelligence",
  "/customers",
  "/blockers",
  "/resolution",
  "/release-notes",
  "/sprint-sheet",
  "/impact",
  "/assistant",
  "/activity",
] as const;

export function isProjectScopedRoute(pathname: string): boolean {
  if (pathname === "/") return true;
  return PROJECT_SCOPED_ROUTES.some((route) => route !== "/" && pathname.startsWith(route));
}

export const DEFAULT_DATE_FROM = "2026-02-01";

export const CATEGORY_COLORS: Record<string, string> = {
  bug: "#ef4444",
  enhancement: "#f97316",
  task: "#3b82f6",
  requirement: "#a78bfa",
  configuration: "#a78bfa",
  knowledge_gap: "#fbbf24",
  duplicate: "#737373",
};

export const TICKET_TYPES = ["task", "requirement", "enhancement", "bug"] as const;
export type TicketTypeKey = (typeof TICKET_TYPES)[number];

export const CHART_COLORS = {
  primary: "#f97316",
  secondary: "#fb923c",
  tertiary: "#fdba74",
  danger: "#ef4444",
  success: "#22c55e",
  muted: "#737373",
};

export const CHART_PALETTE = [
  "#f97316", "#fb923c", "#fbbf24", "#ef4444", "#22c55e",
  "#a78bfa", "#fdba74", "#525252", "#ea580c", "#d97706",
];
