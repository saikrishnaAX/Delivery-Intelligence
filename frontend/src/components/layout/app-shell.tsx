import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./sidebar";
import { MobileNav } from "./mobile-nav";
import { ProjectBar } from "@/components/project-bar";
import { JiraBar } from "@/components/jira-bar";
import { isProjectScopedRoute } from "@/lib/constants";

export function AppShell() {
  const { pathname } = useLocation();
  const onJiraPage = pathname === "/jira";
  const showProjectBar = isProjectScopedRoute(pathname);

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="hidden lg:block">
        <Sidebar />
      </div>
      <div className="flex flex-col flex-1 min-w-0">
        <MobileNav />
        {onJiraPage ? <JiraBar /> : showProjectBar ? <ProjectBar /> : null}
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
