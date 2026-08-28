import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import BudgetPage from './pages/BudgetPage';
import ExpensePage from './pages/ExpensePage';
import ApprovalPage from './pages/ApprovalPage';
import AlertPage from './pages/AlertPage';
import AnalysisPage from './pages/AnalysisPage';
import PdcaPage from './pages/PdcaPage';
import ReportPage from './pages/ReportPage';
import OntologyPage from './pages/OntologyPage';
import SettingsPage from './pages/SettingsPage';
import ChatPage from './pages/ChatPage';
import StrategicPage from './pages/StrategicPage';
import FormCenterPage from './pages/FormCenterPage';
import ContractPage from './pages/ContractPage';
import CashFlowPage from './pages/CashFlowPage';
import ScenarioPage from './pages/ScenarioPage';
import HcpCompliancePage from './pages/HcpCompliancePage';
import PipelinePage from './pages/PipelinePage';
import BusinessReviewPage from './pages/BusinessReviewPage';
import ImpactAssessmentPage from './pages/ImpactAssessmentPage';
import ReasoningAuditorPage from './pages/ReasoningAuditorPage';
import LoginPage from './pages/LoginPage';
import ToastContainer from './components/ToastContainer';
import { CommandPalette, AIPeriodicScan } from './components/ai';
import { useAppStore } from './store';
import type { ReactNode } from 'react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
});

function ProtectedRoute({ children }: { children: ReactNode }) {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-center h-full min-h-[400px]">
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-brand-50 flex items-center justify-center">
          <span className="text-2xl">🏗️</span>
        </div>
        <h2 className="text-xl font-semibold text-surface-700 font-display">{title}</h2>
        <p className="text-sm text-surface-400 mt-2">页面开发中...</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/ai-agent" element={<ChatPage />} />
            <Route path="/budget" element={<BudgetPage />} />
            <Route path="/expense" element={<ExpensePage />} />
            <Route path="/approval" element={<ApprovalPage />} />
            <Route path="/alert" element={<AlertPage />} />
            <Route path="/analysis" element={<AnalysisPage />} />
            <Route path="/pdca" element={<PdcaPage />} />
            <Route path="/report" element={<ReportPage />} />
            <Route path="/ontology" element={<OntologyPage />} />
            <Route path="/strategic" element={<StrategicPage />} />
            <Route path="/forms" element={<FormCenterPage />} />
            <Route path="/contracts" element={<ContractPage />} />
            <Route path="/cashflow" element={<CashFlowPage />} />
            <Route path="/scenario" element={<ScenarioPage />} />
            <Route path="/hcp" element={<HcpCompliancePage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/business-review" element={<BusinessReviewPage />} />
            <Route path="/impact" element={<ImpactAssessmentPage />} />
            <Route path="/auditor" element={<ReasoningAuditorPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
        <ToastContainer />
        <CommandPalette />
        <AIPeriodicScan />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
