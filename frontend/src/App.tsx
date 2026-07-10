import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "@/hooks/use-theme";
import { ProjectProvider } from "@/hooks/use-project";
import { NotifyProvider } from "@/hooks/use-notify";
import { IssueIntelligenceProvider } from "@/hooks/use-issue-intelligence-tracker";
import { AppShell } from "@/components/layout/app-shell";
import { LoadingState } from "@/components/loading-state";
import ExecutiveDashboard from "@/pages/executive-dashboard";

const SupportTeamPage = lazy(() => import("@/pages/support-team"));
const ClassificationPage = lazy(() => import("@/pages/classification"));
const IssueIntelligencePage = lazy(() => import("@/pages/issue-intelligence"));
const BlockersPage = lazy(() => import("@/pages/blockers"));
const CustomersPage = lazy(() => import("@/pages/customers"));
const ResolutionPage = lazy(() => import("@/pages/resolution"));
const ReleaseNotesPage = lazy(() => import("@/pages/release-notes"));
const SprintSheetPage = lazy(() => import("@/pages/sprint-sheet"));
const JiraPage = lazy(() => import("@/pages/jira"));
const AssistantPage = lazy(() => import("@/pages/assistant"));
const PeopleWorkshopsPage = lazy(() => import("@/pages/people-workshops"));
const WorkshopEmailsPage = lazy(() => import("@/pages/workshop-emails"));
const ActivityPage = lazy(() => import("@/pages/activity"));
const ImpactPage = lazy(() => import("@/pages/impact"));

function PageLoader() {
  return (
    <div className="page-content">
      <LoadingState />
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <NotifyProvider>
        <IssueIntelligenceProvider>
        <ProjectProvider>
          <BrowserRouter>
          <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<ExecutiveDashboard />} />
              <Route path="support-team" element={<SupportTeamPage />} />
              <Route path="classification" element={<ClassificationPage />} />
              <Route path="issue-intelligence" element={<IssueIntelligencePage />} />
              <Route path="clustering" element={<Navigate to="/issue-intelligence" replace />} />
              <Route path="blockers" element={<BlockersPage />} />
              <Route path="customers" element={<CustomersPage />} />
              <Route path="resolution" element={<ResolutionPage />} />
              <Route path="release-notes" element={<ReleaseNotesPage />} />
              <Route path="sprint-sheet" element={<SprintSheetPage />} />
              <Route path="jira" element={<JiraPage />} />
              <Route path="impact" element={<ImpactPage />} />
              <Route path="activity" element={<ActivityPage />} />
              <Route path="people-workshops" element={<PeopleWorkshopsPage />} />
              <Route path="workshop-emails" element={<WorkshopEmailsPage />} />
              <Route path="assistant" element={<AssistantPage />} />
            </Route>
          </Routes>
          </Suspense>
          </BrowserRouter>
        </ProjectProvider>
        </IssueIntelligenceProvider>
      </NotifyProvider>
    </ThemeProvider>
  );
}
