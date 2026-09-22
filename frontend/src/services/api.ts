import type {
  ApiResponse,
  PaginatedResponse,
  BudgetItem,
  BudgetSubjectL1,
  BudgetSubjectL2,
  BudgetSubjectL3,
  ExpenseReport,
  ApprovalRecord,
  AlertRecord,
  AlertClosure,
  AlertEscalation,
  GapAnalysis,
  ListAnalysis,
  ExecutionRate,
  QuadrantCompliance,
  PdcaRecord,
  ReportRecord,
  DashboardSummary,
  OntologyObject,
  OntologyRule,
  OntologyScene,
  Organization,
  B2AConversion,
} from '../types';
import type { AuthUser } from '../store';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function getToken(): string | null {
  return localStorage.getItem('auth_token');
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const token = getToken();
  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, config);

  if (response.status === 401) {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    window.location.href = '/login';
    throw new Error('登录已过期，请重新登录');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(
      error.message || error.detail || error.resultMsg || `HTTP ${response.status}`
    );
  }

  return response.json();
}

function buildQuery(params?: Record<string, unknown>): string {
  if (!params) return '';
  const filtered = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '');
  if (filtered.length === 0) return '';
  return '?' + new URLSearchParams(filtered.map(([k, v]) => [k, String(v)])).toString();
}

export const budgetApi = {
  getSubjects: (params?: { level?: string }) =>
    request<ApiResponse<(BudgetSubjectL1 | BudgetSubjectL2 | BudgetSubjectL3)[]>>(`/api/budget/subjects${buildQuery(params)}`),

  getItems: (params?: { org_id?: string; year?: number; page?: number; page_size?: number }) =>
    request<PaginatedResponse<BudgetItem>>(`/api/budget/items${buildQuery(params)}`),

  getItem: (budgetId: string) =>
    request<ApiResponse<BudgetItem>>(`/api/budget/items/${budgetId}`),

  createItem: (data: Partial<BudgetItem>) =>
    request<ApiResponse<BudgetItem>>('/api/budget/items', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateItem: (budgetId: string, data: Partial<BudgetItem>) =>
    request<ApiResponse<BudgetItem>>(`/api/budget/items/${budgetId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  grantA: (budgetId: string, data?: { amount?: number }) =>
    request<ApiResponse<BudgetItem>>(`/api/budget/items/${budgetId}/grant-a`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  grantB: (budgetId: string, data?: { amount?: number }) =>
    request<ApiResponse<BudgetItem>>(`/api/budget/items/${budgetId}/grant-b`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  b2aConvert: (budgetId: string, data: { milestone_evidence: string; amount: number }) =>
    request<ApiResponse<B2AConversion>>(`/api/budget/items/${budgetId}/b2a-convert`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  b2aPreview: (budgetId: string) =>
    request<ApiResponse<any>>(`/api/budget/items/${budgetId}/b2a-preview`),

  // v12.1: 阶段 4 — 经营分析 AI 智能引擎（5 大能力）
  aiRootCauseDrilldown: (data: { issue_type: string; period: string; l1_code?: string }) =>
    request<ApiResponse<any>>('/api/analysis/ai/root-cause-drilldown', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiSmartAttribution: (data: { center_id: string; period: string }) =>
    request<ApiResponse<any>>('/api/analysis/ai/smart-attribution', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiGenerateNarrative: (data: { center_id: string; period: string }) =>
    request<ApiResponse<any>>('/api/analysis/ai/generate-narrative', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiPredictHealth: (data: { center_id: string; period: string }) =>
    request<ApiResponse<any>>('/api/analysis/ai/predict-health', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiSmartRecommendations: (data: { center_id: string; period: string; top_n?: number }) =>
    request<ApiResponse<any>>('/api/analysis/ai/smart-recommendations', {
      method: 'POST', body: JSON.stringify(data),
    }),

  // v12.1: 阶段 3 — 费用报销 AI 智能路由（4 大能力）
  aiRecognizeL3: (data: { description: string; amount: number }) =>
    request<ApiResponse<any>>('/api/expenses/ai/recognize-l3', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiDetectAnomalies: (data: {
    applicant_id: string; amount: number; l3_code: string;
    invoice_number?: string; expense_date?: string;
  }) =>
    request<ApiResponse<any>>('/api/expenses/ai/detect-anomalies', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiSmartRoute: (data: {
    description: string; amount: number; applicant_id: string;
    l3_code?: string; invoice_number?: string; expense_date?: string;
  }) =>
    request<ApiResponse<any>>('/api/expenses/ai/smart-route', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiPreSubmitReview: (data: {
    description: string; amount: number; applicant_id: string;
    l3_code?: string; invoice_number?: string; expense_date?: string;
  }) =>
    request<ApiResponse<any>>('/api/expenses/ai/pre-submit-review', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiBatchAnomalyScan: (days: number = 7, topN: number = 20) =>
    request<ApiResponse<any>>(`/api/expenses/ai/batch-anomaly-scan?days=${days}&top_n=${topN}`),

  // v12.1: 阶段 5 — 实时预警 AI 智能引擎（5 大能力）
  aiFatigueDetect: (days: number = 7, threshold: number = 10) =>
    request<ApiResponse<any>>(`/api/alerts/ai/fatigue-detect?days=${days}&threshold=${threshold}`),

  aiAlertCluster: (days: number = 7) =>
    request<ApiResponse<any>>(`/api/alerts/ai/cluster?days=${days}`),

  aiSmartEscalation: (alertId: string) =>
    request<ApiResponse<any>>(`/api/alerts/ai/${alertId}/smart-escalation`),

  aiAlertPriority: (alertId: string) =>
    request<ApiResponse<any>>(`/api/alerts/ai/${alertId}/priority`),

  aiAlertDedup: (windowHours: number = 24) =>
    request<ApiResponse<any>>(`/api/alerts/ai/dedup?window_hours=${windowHours}`),

  // v12.1: 阶段 6 — PDCA 复盘 AI 智能引擎（5 大能力）
  aiGenerateReview: (data: { period: string; center_id?: string }) =>
    request<ApiResponse<any>>('/api/pdca/ai/generate-review', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiPersistRootCauses: () =>
    request<ApiResponse<any>>('/api/pdca/ai/persist-root-causes'),

  aiTrackRecommendations: () =>
    request<ApiResponse<any>>('/api/pdca/ai/track-recommendations'),

  aiExtractLessons: (data: { period: string }) =>
    request<ApiResponse<any>>('/api/pdca/ai/extract-lessons', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiNextCycleSuggestion: (data: { center_id?: string }) =>
    request<ApiResponse<any>>('/api/pdca/ai/next-cycle-suggestion', {
      method: 'POST', body: JSON.stringify(data),
    }),

  // v12.1: 阶段 7 — 报表出具 AI 智能引擎（5 大能力）
  aiReportAnomalies: (data: { period: string }) =>
    request<ApiResponse<any>>('/api/reports/ai/detect-anomalies', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiReportInterpret: (data: { center_id: string; period: string }) =>
    request<ApiResponse<any>>('/api/reports/ai/interpret', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiCrossPeriodCompare: (data: { center_id: string; current_period: string; previous_period: string }) =>
    request<ApiResponse<any>>('/api/reports/ai/cross-period-compare', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiGenerateReportTemplate: (data: { report_type: string; center_id?: string }) =>
    request<ApiResponse<any>>('/api/reports/ai/generate-template', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiHealthSummary: (data: { center_id?: string }) =>
    request<ApiResponse<any>>('/api/reports/ai/health-summary', {
      method: 'POST', body: JSON.stringify(data),
    }),

  // v12.1: 阶段 8 — 次年采集 AI 智能引擎（5 大能力）
  aiNextCycleBudgetSuggestion: (data: { center_id?: string }) =>
    request<ApiResponse<any>>('/api/next-cycle/ai/budget-suggestion', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiNextCycleStrategicAlignment: () =>
    request<ApiResponse<any>>('/api/next-cycle/ai/strategic-alignment'),

  aiNextCycleHarvestAnomalies: () =>
    request<ApiResponse<any>>('/api/next-cycle/ai/harvest-anomalies'),

  aiNextCycleHarvestTemplate: (data: { center_id?: string }) =>
    request<ApiResponse<any>>('/api/next-cycle/ai/harvest-template', {
      method: 'POST', body: JSON.stringify(data),
    }),

  aiNextCycleIntelligence: (data: { center_id?: string }) =>
    request<ApiResponse<any>>('/api/next-cycle/ai/intelligence', {
      method: 'POST', body: JSON.stringify(data),
    }),

  // v12.1: 阶段 2 — B→A 智能预判
  b2aPredict: (budgetId: string) =>
    request<ApiResponse<any>>(`/api/budget/items/${budgetId}/b2a-predict`),

  b2aRiskDashboard: (topN: number = 10) =>
    request<ApiResponse<any>>(`/api/budget/b2a-risk-dashboard?top_n=${topN}`),

  release: (budgetId: string, data: { amount: number; reason: string }) =>
    request<ApiResponse<BudgetItem>>(`/api/budget/items/${budgetId}/release`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getQuadrants: () =>
    request<ApiResponse<QuadrantCompliance[]>>('/api/dashboard/budget-by-quadrant'),

  adjust: (data: { budget_id: string; target_budget_id?: string; amount: number; reason: string }) =>
    request<ApiResponse<BudgetItem>>('/api/budget/adjustments', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  approve: (budgetId: string, data: { approver: string; comment?: string; role: string }) =>
    request<ApiResponse<BudgetItem>>(`/api/budget/items/${budgetId}/approve`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  reject: (budgetId: string, data: { approver: string; comment: string }) =>
    request<ApiResponse<BudgetItem>>(`/api/budget/items/${budgetId}/reject`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  startCycle: (data: { year: number; initiated_by: string }) =>
    request<ApiResponse<any>>('/api/budget/cycle/start', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getPendingItems: (params?: { year?: number }) =>
    request<ApiResponse<any[]>>(`/api/budget/cycle/pending-items${buildQuery(params)}`),

  createTransfer: (data: { from_budget_id: string; to_budget_id: string; amount: number }) =>
    request<ApiResponse<any>>('/api/budgets/transfers', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getTransfers: (params?: { status?: string }) =>
    request<ApiResponse<any[]>>(`/api/budgets/transfers${buildQuery(params)}`),

  approveTransfer: (transferId: string, data?: { approved_by?: string }) =>
    request<ApiResponse<any>>(`/api/budgets/transfers/${transferId}/approve`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  executeTransfer: (transferId: string, data?: { approved_by?: string }) =>
    request<ApiResponse<any>>(`/api/budgets/transfers/${transferId}/execute`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  getVersions: (budgetYear?: number) =>
    request<ApiResponse<any>>(`/api/budgets/versions${budgetYear ? `?budget_year=${budgetYear}` : ''}`),

  getVersion: (versionId: string) =>
    request<ApiResponse<any>>(`/api/budgets/versions/${versionId}`),

  snapshotVersion: (data?: { budget_year?: number; change_summary?: string; freeze?: boolean }) =>
    request<ApiResponse<any>>('/api/budgets/versions/snapshot', {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  freezeVersion: (versionId: string) =>
    request<ApiResponse<any>>(`/api/budgets/versions/${versionId}/freeze`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  getAdjustments: () =>
    request<ApiResponse<any>>('/api/budgets/adjustments'),

  applyAdjustment: (adjustmentId: string) =>
    request<ApiResponse<any>>(`/api/budgets/adjustments/${adjustmentId}/apply`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  getReasons: (targetId?: string) =>
    request<ApiResponse<any>>(`/api/budgets/reasons${targetId ? `?target_id=${targetId}` : ''}`),

  // ─── 预算健康度（v4.0 新增） ───────────────────────────
  getHealthScore: (period: string) =>
    request<ApiResponse<any>>(`/api/budget/health-score?period=${period}`),

  simulateTransfer: (fromId: string, toId: string, amount: number) =>
    request<ApiResponse<any>>('/api/budget/simulate-transfer', {
      method: 'POST',
      body: JSON.stringify({ from_id: fromId, to_id: toId, amount }),
    }),

  // ─── 预算认知深度（Module E.2：5 层根因下钻 + 主动建议 + 业务联动） ──
  getRootCause: (budgetId: string) =>
    request<ApiResponse<any>>(`/api/budget/cognitive/root-cause/${encodeURIComponent(budgetId)}`),

  getProactiveSuggestions: (period?: string) =>
    request<ApiResponse<any>>(`/api/budget/cognitive/suggestions${buildQuery({ period })}`),

  getBusinessLinkage: () =>
    request<ApiResponse<any>>('/api/budget/cognitive/business-linkage'),

  // v12.1: 阶段 1 — 战略主题自动分解
  autoDecompose: (data: { theme: string; year: number; total_budget: number; strategic_intent_l1?: string }) =>
    request<ApiResponse<any>>('/api/budget/auto-decompose', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  applyDecomposition: (data: { decomposition: any; year?: number }) =>
    request<ApiResponse<any>>('/api/budget/apply-decomposition', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

export const expenseApi = {
  getReports: (params?: { status?: string; org_id?: string; page?: number; page_size?: number }) =>
    request<PaginatedResponse<ExpenseReport>>(`/api/expenses${buildQuery(params)}`),

  getReport: (expenseId: string) =>
    request<ApiResponse<ExpenseReport>>(`/api/expenses/${expenseId}`),

  submit: (data: Partial<ExpenseReport>) =>
    request<ApiResponse<ExpenseReport>>('/api/expenses', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  cancel: (expenseId: string) =>
    request<ApiResponse<ExpenseReport>>(`/api/expenses/${expenseId}/cancel`, {
      method: 'POST',
    }),

  writeOff: (expenseId: string) =>
    request<ApiResponse<ExpenseReport>>(`/api/expenses/${expenseId}/write-off`, {
      method: 'POST',
    }),

  approve: (expenseId: string, data: { approver_id: string; comment?: string }) =>
    request<ApiResponse<any>>(`/api/expenses/${expenseId}/approve`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  reject: (expenseId: string, data: { approver_id: string; comment: string }) =>
    request<ApiResponse<any>>(`/api/expenses/${expenseId}/reject`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  checkInvoiceDuplicate: (invoiceNumber: string) =>
    request<ApiResponse<{ invoice_number: string; is_duplicate: boolean; duplicate_count: number; duplicate_records: any[] }>>('/api/expenses/check-invoice', {
      method: 'POST',
      body: JSON.stringify({ invoice_number: invoiceNumber }),
    }),

  evaluateEffect: (expenseId: string, data: { expected_outcome?: string; actual_outcome?: string; effect_score?: number; evaluator_id?: string; follow_up_required?: boolean }) =>
    request<ApiResponse<any>>(`/api/expenses/${expenseId}/evaluate-effect`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getEffectSummary: (params?: { l1_code?: string; budget_id?: string }) =>
    request<ApiResponse<any>>(`/api/expenses/effect-summary${buildQuery(params)}`),

  getExpenseEffectTracking: (expenseId: string) =>
    request<ApiResponse<any>>(`/api/expenses/${expenseId}/effect-tracking`),

  // v8.0: 异常检测 / 风险评分 / 预算消耗预测
  scanAnomalies: (params: { period: string; center_id?: string }) =>
    request<ApiResponse<any>>(`/api/expenses/anomalies${buildQuery(params)}`),

  getRiskScores: (params: { period: string; center_id?: string; top_n?: number }) =>
    request<ApiResponse<any>>(`/api/expenses/risk-scores${buildQuery(params)}`),

  getBudgetBurnPrediction: (params: { period: string; center_id?: string }) =>
    request<ApiResponse<any>>(`/api/expenses/budget-burn-prediction${buildQuery(params)}`),

  getSingleRiskScore: (expenseId: string) =>
    request<ApiResponse<any>>(`/api/expenses/${expenseId}/risk-score`),

  getApprovalStatus: (expenseId: string) =>
    request<ApiResponse<any>>(`/api/approvals/${expenseId}`),

  getOperational: (expenseId: string) =>
    request<ApiResponse<any>>(`/api/expenses/${expenseId}/operational`),

  checkThreeFlow: (expenseId: string, data?: Record<string, unknown>) =>
    request<ApiResponse<any>>(`/api/expenses/${expenseId}/three-flow/check`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  listThreeFlow: (status?: string) =>
    request<ApiResponse<any>>(`/api/expenses/three-flow${status ? `?status=${status}` : ''}`),
};

export const approvalApi = {
  getPending: (params?: { line?: string; page?: number; page_size?: number }) =>
    request<PaginatedResponse<ApprovalRecord>>(`/api/approvals/pending${buildQuery(params)}`),

  getChain: (expenseId: string) =>
    request<ApiResponse<ApprovalRecord[]>>(`/api/approvals/${expenseId}`),

  approve: (approvalId: string, data?: { comment?: string }) =>
    request<ApiResponse<ApprovalRecord>>(`/api/approvals/${approvalId}/approve`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  reject: (approvalId: string, data: { comment: string }) =>
    request<ApiResponse<ApprovalRecord>>(`/api/approvals/${approvalId}/reject`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getStats: () =>
    request<ApiResponse<any>>('/api/approvals/stats'),
};

export const alertApi = {
  getAlerts: (params?: { level?: string; status?: string; org_id?: string; page?: number; page_size?: number }) =>
    request<PaginatedResponse<AlertRecord>>(`/api/alerts${buildQuery(params)}`),

  getAlert: (alertId: string) =>
    request<ApiResponse<AlertRecord>>(`/api/alerts/${alertId}`),

  respond: (alertId: string, data: { action_description: string }) =>
    request<ApiResponse<AlertRecord>>(`/api/alerts/${alertId}/respond`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  confirmClosure: (alertId: string, data: { confirmer_id: string; comment?: string }) =>
    request<ApiResponse<AlertClosure>>(`/api/alerts/${alertId}/confirm`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  escalate: (alertId: string, data?: { reason?: string }) =>
    request<ApiResponse<AlertEscalation>>(`/api/alerts/${alertId}/escalate`, {
      method: 'POST',
      body: JSON.stringify(data || {}),
    }),

  getStats: () =>
    request<ApiResponse<any>>('/api/alerts/stats'),

  scan: () =>
    request<ApiResponse<any>>('/api/alerts/scan', {
      method: 'POST',
    }),

  getDashboard: () =>
    request<ApiResponse<any>>('/api/alerts/dashboard'),

  cascadeRiskAssess: (data: { l1_code: string }) =>
    request<ApiResponse<any>>('/api/alerts/cascade-risk', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  patternAnalysis: (data: { l1_code?: string; lookback_months?: number }) =>
    request<ApiResponse<any>>('/api/alerts/pattern-analysis', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ─── 5 层根因下钻 + 疲劳度（v4.0 新增） ───────────────────────────
  drillDownAlert: (alertId: string) =>
    request<ApiResponse<any>>(`/api/alerts/${alertId}/drill-down`),

  getAlertFatigue: (months: number = 3) =>
    request<ApiResponse<any>>(`/api/alerts/fatigue?months=${months}`),
};

export const analysisApi = {
  getExecutionRates: (params?: { org_id?: string; period?: string }) =>
    request<ApiResponse<ExecutionRate[]>>(`/api/analysis/execution-rates${buildQuery(params)}`),

  getQuadrantCompliance: (params?: { period?: string }) =>
    request<ApiResponse<QuadrantCompliance[]>>(`/api/analysis/quadrant-compliance${buildQuery(params)}`),

  analyze3Gap: (data: { org_id?: string; period?: string }) =>
    request<ApiResponse<GapAnalysis[]>>('/api/analysis/3gap', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  classify3List: (data: { org_id?: string; period?: string }) =>
    request<ApiResponse<ListAnalysis[]>>('/api/analysis/3list', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // v12.0: 全中心 3GAP+3List 自动批跑
  auto3Gap3List: (data: { period?: string; top_n?: number }) =>
    request<ApiResponse<any>>('/api/analysis/auto-3gap-3list', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getDashboard: () =>
    request<ApiResponse<any>>('/api/analysis/dashboard'),

  predictTrend: (data: { l1_code: string; months_ahead?: number }) =>
    request<ApiResponse<any>>('/api/analysis/predict-trend', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  detectAnomalies: (data: { period: string; z_threshold?: number; iqr_multiplier?: number }) =>
    request<ApiResponse<any>>('/api/analysis/detect-anomalies', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  rootCauseAnalysis: (data: { issue_type: string; period: string; l1_code?: string }) =>
    request<ApiResponse<any>>('/api/analysis/root-cause', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  comparePeriods: (data: { period1: string; period2: string; l1_code?: string }) =>
    request<ApiResponse<any>>('/api/analysis/compare-periods', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ─── 9 张诊断卡（v4.0 新增） ───────────────────────────
  diagnoseRevenueHealth: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnose/revenue-health', {
      method: 'POST', body: JSON.stringify({ period }),
    }),
  diagnoseGrossMargin: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnose/gross-margin', {
      method: 'POST', body: JSON.stringify({ period }),
    }),
  diagnoseExpensePacing: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnose/expense-pacing', {
      method: 'POST', body: JSON.stringify({ period }),
    }),
  diagnoseProductMix: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnose/product-mix', {
      method: 'POST', body: JSON.stringify({ period }),
    }),
  diagnoseChannelSplit: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnose/channel-split', {
      method: 'POST', body: JSON.stringify({ period }),
    }),
  diagnoseProfitAuthenticity: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnose/profit-authenticity', {
      method: 'POST', body: JSON.stringify({ period }),
    }),
  diagnoseCommercializationEff: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnose/commercialization-efficiency', {
      method: 'POST', body: JSON.stringify({ period }),
    }),
  diagnosePolicyRisk: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnose/policy-risk', {
      method: 'POST', body: JSON.stringify({ period }),
    }),
  diagnoseCashflowQuality: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnose/cashflow-quality', {
      method: 'POST', body: JSON.stringify({ period }),
    }),

  // ─── 4 个分析框架（v4.0 新增） ───────────────────────────
  getDupontFramework: (period: string) =>
    request<ApiResponse<any>>(`/api/analysis/framework/dupont?period=${period}`),
  getBridgeFramework: (period: string) =>
    request<ApiResponse<any>>(`/api/analysis/framework/bridge?period=${period}`),
  getBCGFramework: (period: string) =>
    request<ApiResponse<any>>(`/api/analysis/framework/bcg?period=${period}`),
  getSARFramework: (period: string) =>
    request<ApiResponse<any>>(`/api/analysis/framework/sar?period=${period}`),

  // ─── 报告组装（v4.0 新增） ───────────────────────────
  listDiagnosisCards: () =>
    request<ApiResponse<any>>('/api/analysis/diagnosis-cards'),
  generateDiagnosisReport: (period: string) =>
    request<ApiResponse<any>>('/api/analysis/diagnosis-report', {
      method: 'POST', body: JSON.stringify({ period }),
    }),
  getDiagnosisReport: (period: string) =>
    request<ApiResponse<any>>(`/api/analysis/diagnosis-report?period=${period}`),

  // ─── 信号灯规则（v4.0 新增） ───────────────────────────
  getSignalLightRules: (cardType?: string) =>
    request<ApiResponse<any>>(
      `/api/analysis/signal-light-rules${cardType ? `?card_type=${cardType}` : ''}`
    ),
  updateSignalLightRules: (rules: Record<string, any>) =>
    request<ApiResponse<any>>('/api/analysis/signal-light-rules', {
      method: 'PUT', body: JSON.stringify(rules),
    }),
};

// ─── 预算健康度（v4.0 新增） ───────────────────────────
declare module './api' {
  // (占位声明，TypeScript 实际不需要)
}

export const pdcaApi = {
  monthly: (data: { org_id?: string; period?: string }) =>
    request<ApiResponse<PdcaRecord>>('/api/pdca/monthly', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  quarterly: (data: { org_id?: string; period?: string }) =>
    request<ApiResponse<PdcaRecord>>('/api/pdca/quarterly', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  yearly: (data: { org_id?: string; period?: string }) =>
    request<ApiResponse<PdcaRecord>>('/api/pdca/yearly', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // v12.0: 阶段 8 — 次年采集反向输入
  harvestNextCycle: (data: { year: number; organization_id?: string }) =>
    request<ApiResponse<any>>('/api/pdca/harvest-next-cycle', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getHistory: (params?: { period_type?: string; org_id?: string }) =>
    request<ApiResponse<PdcaRecord[]>>(`/api/pdca/history${buildQuery(params)}`),

  updateSection: (pdcaId: string, data: { section: string; content: string }) =>
    request<ApiResponse<any>>(`/api/pdca/records/${pdcaId}/section`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getActions: (params?: { pdca_id?: string }) =>
    request<ApiResponse<any[]>>(`/api/pdca/actions${buildQuery(params)}`),

  createAction: (data: { pdca_id: string; description: string; assignee: string; due_date: string }) =>
    request<ApiResponse<any>>('/api/pdca/actions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateAction: (actionId: string, data: { status?: string; note?: string }) =>
    request<ApiResponse<any>>(`/api/pdca/actions/${actionId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
};

export const reportApi = {
  getReports: (params?: { report_type?: string; period?: string; page?: number; page_size?: number }) =>
    request<PaginatedResponse<ReportRecord>>(`/api/reports${buildQuery(params)}`),

  getReport: (reportId: string) =>
    request<ApiResponse<ReportRecord>>(`/api/reports/${reportId}`),

  monthlyFlash: (data: { period: string; org_id?: string }) =>
    request<ApiResponse<ReportRecord>>('/api/reports/monthly-flash', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  quarterly: (data: { period: string; org_id?: string }) =>
    request<ApiResponse<ReportRecord>>('/api/reports/quarterly', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  annualReview: (data: { period: string; org_id?: string }) =>
    request<ApiResponse<ReportRecord>>('/api/reports/annual-review', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  caliberComparison: (period: string) =>
    request<ApiResponse<any>>(`/api/reports/caliber-comparison?period=${period}`),

  caliberMappings: () =>
    request<ApiResponse<any[]>>('/api/reports/caliber-mappings'),

  trendAnalysis: (data: { months: number; l1_code?: string }) =>
    request<ApiResponse<any>>('/api/reports/trend-analysis', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  riskAssessment: (data: { period: string }) =>
    request<ApiResponse<any>>('/api/reports/risk-assessment', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  specialReport: (data: { report_type: string; target_code: string; period: string }) =>
    request<ApiResponse<any>>('/api/reports/special', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

export const dashboardApi = {
  getOverview: () =>
    request<ApiResponse<any>>('/api/dashboard/overview'),

  getBudgetByQuadrant: () =>
    request<ApiResponse<QuadrantCompliance[]>>('/api/dashboard/budget-by-quadrant'),

  getBudgetByL1: () =>
    request<ApiResponse<any>>('/api/dashboard/budget-by-l1'),

  getAlertTrend: () =>
    request<ApiResponse<any>>('/api/dashboard/alert-trend'),

  getExecutionTrend: () =>
    request<ApiResponse<ExecutionRate[]>>('/api/dashboard/execution-trend'),

  // v8.0 角色化 Dashboard
  getRoleDashboard: (params: {
    role: 'cfo' | 'center_lead' | 'product_manager';
    center_id?: string;
    l1_code?: string;
    period?: string;
  }) =>
    request<ApiResponse<any>>(
      `/api/dashboard/role/${params.role}${buildQuery({
        center_id: params.center_id,
        l1_code: params.l1_code,
        period: params.period,
      })}`
    ),

  getSupportedRoles: () =>
    request<ApiResponse<{ supported_roles: string[] }>>('/api/dashboard/role-supported'),

  getDecisionBrief: (period?: string) =>
    request<ApiResponse<{
      period: string;
      generated_at?: string;
      items: Array<{
        id: string;
        rank: number;
        source: string;
        severity: 'red' | 'yellow' | 'orange';
        title: string;
        money_label: string;
        money_value: number;
        action: string;
        why: string;
        href: string;
        secondary_href?: string;
      }>;
    }>>(`/api/dashboard/decision-brief${buildQuery({ period })}`),
};

export const settingsApi = {
  getSettings: () =>
    request<ApiResponse<any>>('/api/settings'),

  updateSettings: (data: Record<string, unknown>) =>
    request<ApiResponse<any>>('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getOrganization: () =>
    request<ApiResponse<Organization[]>>('/api/settings/organization'),

  getRoles: () =>
    request<ApiResponse<any[]>>('/api/settings/roles'),

  createDepartment: (data: { dept_id: string; dept_name: string; center_id?: string; parent_dept_id?: string }) =>
    request<ApiResponse<any>>('/api/settings/departments', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateDepartment: (deptId: string, data: Record<string, unknown>) =>
    request<ApiResponse<any>>(`/api/settings/departments/${deptId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteDepartment: (deptId: string) =>
    request<ApiResponse<any>>(`/api/settings/departments/${deptId}`, {
      method: 'DELETE',
    }),

  updateRolePermissions: (roleId: string, permissions: string[]) =>
    request<ApiResponse<any>>(`/api/settings/roles/${roleId}/permissions`, {
      method: 'PUT',
      body: JSON.stringify({ permissions }),
    }),

  getAuditLog: (limit?: number) =>
    request<ApiResponse<any[]>>(`/api/settings/audit-log${buildQuery({ limit })}`),

  getCaliberMappings: () =>
    request<ApiResponse<any[]>>('/api/settings/caliber-mappings'),

  updateCaliberMappings: (mappings: any[]) =>
    request<ApiResponse<any>>('/api/settings/caliber-mappings', {
      method: 'PUT',
      body: JSON.stringify({ mappings }),
    }),

  getAlertThresholds: () =>
    request<ApiResponse<any>>('/api/settings/alert-thresholds'),

  updateAlertThresholds: (thresholds: Record<string, any>) =>
    request<ApiResponse<any>>('/api/settings/alert-thresholds', {
      method: 'PUT',
      body: JSON.stringify(thresholds),
    }),
};

export const ontologyApi = {
  getObjects: (params?: { object_type?: string; category?: string }) =>
    request<ApiResponse<OntologyObject[]>>(`/api/ontology/objects${buildQuery(params)}`),

  getRelations: (params?: { scene_id?: string }) =>
    request<ApiResponse<any[]>>(`/api/ontology/relations${buildQuery(params)}`),

  getBehaviors: (params?: { scene_id?: string }) =>
    request<ApiResponse<any[]>>(`/api/ontology/behaviors${buildQuery(params)}`),

  getRules: (params?: { rule_type?: string }) =>
    request<ApiResponse<OntologyRule[]>>(`/api/ontology/rules${buildQuery(params)}`),

  updateSoftRuleParams: (ruleId: string, params: Record<string, any>) =>
    request<ApiResponse<any>>(`/api/ontology/rules/soft/${ruleId}/params`, {
      method: 'POST',
      body: JSON.stringify({ params }),
    }),

  getScenes: () =>
    request<ApiResponse<OntologyScene[]>>('/api/ontology/scenes'),

  getHealthScore: () =>
    request<ApiResponse<any>>('/api/ontology/health-score'),
};

// v11.0: 运行时仪表盘 API
export const ontologyRuntimeApi = {
  getStats: () => request<ApiResponse<any>>('/api/ontology/runtime/stats'),
  getScenes: () => request<ApiResponse<any>>('/api/ontology/runtime/scenes'),
  getRules: () => request<ApiResponse<any>>('/api/ontology/runtime/rules'),
  getCoverage: () => request<ApiResponse<any>>('/api/ontology/runtime/coverage'),
  getTraces: (limit = 10) =>
    request<ApiResponse<any>>(`/api/ontology/runtime/traces?limit=${limit}`),
  refresh: () =>
    request<ApiResponse<any>>('/api/ontology/runtime/refresh', { method: 'POST' }),
};

export const strategicApi = {
  getInitiatives: (params?: { strategic_intent_l1?: string; owner_center?: string; status?: string }) =>
    request<ApiResponse<any[]>>(`/api/strategic/initiatives${buildQuery(params)}`),

  createInitiative: (data: Record<string, unknown>) =>
    request<ApiResponse<any>>('/api/strategic/initiatives', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateInitiative: (id: string, data: Record<string, unknown>) =>
    request<ApiResponse<any>>(`/api/strategic/initiatives/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteInitiative: (id: string) =>
    request<ApiResponse<any>>(`/api/strategic/initiatives/${id}`, {
      method: 'DELETE',
    }),

  getAllocations: (params?: { budget_id?: string; quarter?: string }) =>
    request<ApiResponse<any[]>>(`/api/strategic/allocations${buildQuery(params)}`),

  createAllocation: (data: Record<string, unknown>) =>
    request<ApiResponse<any>>('/api/strategic/allocations', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getMatrix: () =>
    request<ApiResponse<any>>('/api/strategic/matrix'),

  // v9.0 E.1: 战略认知分析
  getRiskGauge: () =>
    request<ApiResponse<any>>('/api/strategic/risk-gauge'),

  getImpactChain: (initiativeId: string) =>
    request<ApiResponse<any>>(`/api/strategic/impact-chain/${encodeURIComponent(initiativeId)}`),

  getGapAnalysis: () =>
    request<ApiResponse<any>>('/api/strategic/gap-analysis'),
};

export const formApi = {
  getTemplates: (params?: { category?: string }) =>
    request<ApiResponse<any[]>>(`/api/forms/templates${buildQuery(params)}`),

  getTemplate: (formCode: string) =>
    request<ApiResponse<any>>(`/api/forms/templates/${formCode}`),

  submitForm: (data: Record<string, unknown>) =>
    request<ApiResponse<any>>('/api/forms/submissions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getSubmissions: (params?: { form_code?: string; status?: string; org_id?: string }) =>
    request<ApiResponse<any[]>>(`/api/forms/submissions${buildQuery(params)}`),

  getSubmission: (submissionId: string) =>
    request<ApiResponse<any>>(`/api/forms/submissions/${submissionId}`),
};

export const contractApi = {
  getContracts: (params?: { status?: string; department_id?: string; vendor_name?: string; page?: number; page_size?: number }) =>
    request<PaginatedResponse<any>>(`/api/contracts${buildQuery(params)}`),

  createContract: (data: Record<string, unknown>) =>
    request<ApiResponse<any>>('/api/contracts', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getContract: (contractId: string) =>
    request<ApiResponse<any>>(`/api/contracts/${contractId}`),

  updateContract: (contractId: string, data: Record<string, unknown>) =>
    request<ApiResponse<any>>(`/api/contracts/${contractId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteContract: (contractId: string) =>
    request<ApiResponse<any>>(`/api/contracts/${contractId}`, {
      method: 'DELETE',
    }),

  getPayments: (contractId: string) =>
    request<ApiResponse<any>>(`/api/contracts/${contractId}/payment`),

  addPayment: (contractId: string, data: Record<string, unknown>) =>
    request<ApiResponse<any>>(`/api/contracts/${contractId}/payment`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

export const healthApi = {
  check: () =>
    request<{ status: string; version: string }>('/api/health'),
};

export const authApi = {
  login: (username: string, password: string) =>
    request<ApiResponse<{ token: string; user: AuthUser }>>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  refreshToken: () =>
    request<ApiResponse<{ token: string }>>('/api/auth/refresh', {
      method: 'POST',
    }),

  getMe: () =>
    request<ApiResponse<AuthUser>>('/api/auth/me'),
};

// ── 现金流监控 ──────────────────────────────────────────

export const cashFlowApi = {
  forecast: (period: string, horizonMonths: number = 3) =>
    request<ApiResponse<any>>(`/api/cashflow/forecast?period=${period}&horizon_months=${horizonMonths}`),

  liquidityGap: (period: string) =>
    request<ApiResponse<any>>(`/api/cashflow/liquidity-gap?period=${period}`),

  profitCashGap: (period: string) =>
    request<ApiResponse<any>>(`/api/cashflow/profit-cash-gap?period=${period}`),

  receiptPaymentMatch: (period: string) =>
    request<ApiResponse<any>>(`/api/cashflow/receipt-payment-match?period=${period}`),
};

// ── 情景规划 ──────────────────────────────────────────

export const scenarioApi = {
  list: (params?: { scenario_type?: string; period?: string }) =>
    request<ApiResponse<any[]>>(`/api/scenarios${buildQuery(params)}`),

  create: (data: { name: string; scenario_type: string; assumptions: Record<string, any>; period?: string }) =>
    request<ApiResponse<any>>('/api/scenarios', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  compare: (scenarioIds: number[]) =>
    request<ApiResponse<any>>('/api/scenarios/compare', {
      method: 'POST',
      body: JSON.stringify({ scenario_ids: scenarioIds }),
    }),

  elasticAdjustment: (data: { budget_id: string; actual_volume: number }) =>
    request<ApiResponse<any>>('/api/scenarios/elastic-adjustment', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  stressTest: (data: { scenario_id: number }) =>
    request<ApiResponse<any>>('/api/scenarios/stress-test', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  emergencyAllocation: (data: { reserve_id: number; budget_id: string; amount: number; reason: string }) =>
    request<ApiResponse<any>>('/api/scenarios/emergency-allocation', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ── 影响评估 ──────────────────────────────────────────

export const impactApi = {
  budgetChange: (data: { budget_id: string; change_type: string; amount: number }) =>
    request<ApiResponse<any>>('/api/impact/budget-change', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  expenseOverrun: (data: { expense_id: string; overrun_amount: number }) =>
    request<ApiResponse<any>>('/api/impact/expense-overrun', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  strategicShift: (data: { initiative_id: string; new_direction: string }) =>
    request<ApiResponse<any>>('/api/impact/strategic-shift', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  trace: (chainId: number) =>
    request<ApiResponse<any>>(`/api/impact/trace/${chainId}`),

  mitigation: (chainId: number) =>
    request<ApiResponse<any>>(`/api/impact/mitigation/${chainId}`),

  // ── v8.0 Module I: 决策沙盘 / 影响归因 / Pareto ──

  simulateSandbox: (data: {
    scenario_name: string;
    operation_type: string;
    params: Record<string, any>;
  }) =>
    request<ApiResponse<any>>('/api/impact/sandbox', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  compareSandboxes: (data: { scenarios: any[] }) =>
    request<ApiResponse<any>>('/api/impact/sandbox/compare', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listSandboxes: (limit = 20) =>
    request<ApiResponse<any>>(`/api/impact/sandbox/list?limit=${limit}`),

  getSandbox: (sandboxId: number) =>
    request<ApiResponse<any>>(`/api/impact/sandbox/${sandboxId}`),

  attributeMetric: (data: {
    target_metric: string;
    target_period: string;
    observed_value: number;
  }) =>
    request<ApiResponse<any>>('/api/impact/attribute', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listAttributions: (limit = 20) =>
    request<ApiResponse<any>>(`/api/impact/attribute/list?limit=${limit}`),

  computePareto: (data: {
    candidates: any[];
    weights?: Record<string, number>;
  }) =>
    request<ApiResponse<any>>('/api/impact/pareto', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  autoPareto: (data: { budget_id: string; original_amount: number }) =>
    request<ApiResponse<any>>('/api/impact/pareto/auto', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  paretoHistory: (limit = 20) =>
    request<ApiResponse<any>>(`/api/impact/pareto/history?limit=${limit}`),
};

// ── 零基预算 ──────────────────────────────────────────

export const zbbApi = {
  initiateReview: (data: { period: string; total_budget_constraint: number }) =>
    request<ApiResponse<any>>('/api/zbb/reviews', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createDecisionUnit: (data: { review_id: number; name: string; owner: string; scope: string }) =>
    request<ApiResponse<any>>('/api/zbb/decision-units', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createDecisionPackage: (data: { unit_id: number; level: string; amount: number; justification: string }) =>
    request<ApiResponse<any>>('/api/zbb/decision-packages', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  rankPackages: (reviewId: number) =>
    request<ApiResponse<any>>(`/api/zbb/rank/${reviewId}`, {
      method: 'POST',
    }),

  synthesizeBudget: (reviewId: number, data: { total_budget: number }) =>
    request<ApiResponse<any>>(`/api/zbb/synthesize/${reviewId}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ── 成本中心 ──────────────────────────────────────────

export const costCenterApi = {
  setStandardCost: (data: { center_id: number; cost_item: string; quantity: number; price: number }) =>
    request<ApiResponse<any>>('/api/cost-centers/standard-costs', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  varianceAnalysis: (centerId: number, period: string) =>
    request<ApiResponse<any>>(`/api/cost-centers/${centerId}/variance?period=${period}`),

  allocateCost: (allocationId: number) =>
    request<ApiResponse<any>>(`/api/cost-centers/allocate/${allocationId}`, {
      method: 'POST',
    }),

  settleInternal: (data: { provider_id: number; consumer_id: number; volume: number; price: number }) =>
    request<ApiResponse<any>>('/api/cost-centers/settle', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ── HCP合规 ──────────────────────────────────────────

export const hcpApi = {
  verify: (data: { hcp_id: string }) =>
    request<ApiResponse<any>>('/api/hcp/verify', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  interactionCheck: (data: { interaction_id: number }) =>
    request<ApiResponse<any>>('/api/hcp/interaction-check', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  paymentLimitCheck: (data: { hcp_id: string; payment_amount: number }) =>
    request<ApiResponse<any>>('/api/hcp/payment-limit-check', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  riskAnalysis: (hcpId: string, period: string) =>
    request<ApiResponse<any>>(`/api/hcp/${hcpId}/risk?period=${period}`),

  getEvidence: (hcpId: string) =>
    request<ApiResponse<any>>(`/api/hcp/${hcpId}/evidence`),
};

// ── 管线管理 ──────────────────────────────────────────

export const pipelineApi = {
  advance: (pipelineId: string, data: { target_stage: string; go_nogo: string }) =>
    request<ApiResponse<any>>(`/api/pipelines/${pipelineId}/advance`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  terminate: (pipelineId: string, data: { action: string; reason: string }) =>
    request<ApiResponse<any>>(`/api/pipelines/${pipelineId}/terminate`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getStatus: (pipelineId: string) =>
    request<ApiResponse<any>>(`/api/pipelines/${pipelineId}/status`),

  list: (params?: { status?: string }) =>
    request<ApiResponse<any[]>>(`/api/pipelines${buildQuery(params)}`),

  // ─── Module E.3：管线认知深度（价值矩阵 + Go/No-Go） ──
  getValueMatrix: () =>
    request<ApiResponse<any>>('/api/pipelines/cognitive/value-matrix'),

  getValue: (pipelineId: string) =>
    request<ApiResponse<any>>(`/api/pipelines/cognitive/value/${encodeURIComponent(pipelineId)}`),

  getGoNoGo: (pipelineId: string) =>
    request<ApiResponse<any>>(`/api/pipelines/cognitive/go-nogo/${encodeURIComponent(pipelineId)}`),
};

// ── 经营分析会 ──────────────────────────────────────────

export const businessReviewApi = {
  generateAgenda: (data: { meeting_type: string; period: string }) =>
    request<ApiResponse<any>>('/api/business-review/agenda', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  recordResolution: (data: { meeting_id: number; content: string; owner: string; deadline: string }) =>
    request<ApiResponse<any>>('/api/business-review/resolutions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  trackResolution: (resolutionId: number, data: { progress: number; risk_flag: string }) =>
    request<ApiResponse<any>>(`/api/business-review/resolutions/${resolutionId}/track`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  crossCenterCompare: (data: { period: string; center_ids: string[] }) =>
    request<ApiResponse<any>>('/api/business-review/cross-center-compare', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
};

// ── 主动建议（v4.0 新增） ──────────────────────────────────────────

export interface ProactiveInsight {
  id: string;
  user_id?: string | null;
  period?: string | null;
  insight_type: string;
  priority: 'critical' | 'attention' | 'info';
  title: string;
  detail?: string | null;
  action_label?: string | null;
  action_url?: string | null;
  related_object?: string | null;
  is_read: boolean;
  is_dismissed: boolean;
  created_at: string;
}

export const insightsApi = {
  getActive: (userId?: string) =>
    request<ApiResponse<ProactiveInsight[]>>(
      `/api/insights/active${userId ? `?user_id=${userId}` : ''}`
    ),

  markRead: (insightId: string) =>
    request<ApiResponse<any>>(`/api/insights/${insightId}/read`, {
      method: 'POST',
    }),

  dismiss: (insightId: string) =>
    request<ApiResponse<any>>(`/api/insights/${insightId}/dismiss`, {
      method: 'POST',
    }),

  triggerScan: (data: { user_id?: string; period?: string } = {}) =>
    request<ApiResponse<{ count: number; insights: ProactiveInsight[] }>>(
      '/api/insights/scan',
      { method: 'POST', body: JSON.stringify(data) }
    ),
};

// v12.0: 血缘追踪 API（八阶段贯通）
export const lineageApi = {
  getExpenseLineage: (expenseId: string) =>
    request<ApiResponse<any>>(`/api/lineage/expense/${encodeURIComponent(expenseId)}`),
  getAlertLineage: (alertId: string) =>
    request<ApiResponse<any>>(`/api/lineage/alert/${encodeURIComponent(alertId)}`),
  getBudgetLineage: (budgetId: string) =>
    request<ApiResponse<any>>(`/api/lineage/budget/${encodeURIComponent(budgetId)}`),
};

// v12.0: 截点报告 API
export const cutoffApi = {
  getStatus: (period?: string) =>
    request<ApiResponse<any>>(`/api/reports/cutoff-status${period ? `?period=${period}` : ''}`),
  trigger: (day: number, period?: string) =>
    request<ApiResponse<any>>(`/api/reports/trigger-cutoff?day=${day}${period ? `&period=${period}` : ''}`, {
      method: 'POST',
    }),
};
