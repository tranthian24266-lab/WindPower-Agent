import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { StatusBanner } from "./components/StatusBanner";

const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const ModelLibraryPage = lazy(() =>
  import("./pages/ModelLibraryPage").then((module) => ({ default: module.ModelLibraryPage })),
);
const DiagnosisPage = lazy(() => import("./pages/DiagnosisPage").then((module) => ({ default: module.DiagnosisPage })));
const CasesPage = lazy(() => import("./pages/CasesPage").then((module) => ({ default: module.CasesPage })));
const CaseDetailPage = lazy(() =>
  import("./pages/CaseDetailPage").then((module) => ({ default: module.CaseDetailPage })),
);
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((module) => ({ default: module.ReportsPage })));
const ChatPage = lazy(() => import("./pages/ChatPage").then((module) => ({ default: module.ChatPage })));
const KnowledgePage = lazy(() => import("./pages/KnowledgePage").then((module) => ({ default: module.KnowledgePage })));
const EvalDashboardPage = lazy(() =>
  import("./pages/EvalDashboardPage").then((module) => ({ default: module.EvalDashboardPage })),
);
const ReviewQueuePage = lazy(() =>
  import("./pages/ReviewQueuePage").then((module) => ({ default: module.ReviewQueuePage })),
);
const RunDetailPage = lazy(() =>
  import("./pages/RunDetailPage").then((module) => ({ default: module.RunDetailPage })),
);
const AuditLogPage = lazy(() =>
  import("./pages/AuditLogPage").then((module) => ({ default: module.AuditLogPage })),
);
const SpecialistDashboardPage = lazy(() =>
  import("./pages/SpecialistDashboardPage").then((module) => ({ default: module.SpecialistDashboardPage })),
);

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<StatusBanner message="页面加载中..." />}>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/models" element={<ModelLibraryPage />} />
          <Route path="/diagnosis" element={<DiagnosisPage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/cases/:caseId" element={<CaseDetailPage />} />
          <Route path="/reports/:caseId" element={<ReportsPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="/reviews" element={<ReviewQueuePage />} />
          <Route path="/evals" element={<EvalDashboardPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/audit" element={<AuditLogPage />} />
          <Route path="/specialists" element={<SpecialistDashboardPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}
