import { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Receipt,
  Search,
  FileCheck,
  AlertCircle,
  Check,
  X,
  Filter,
  Target,
  TrendingUp,
  ShieldAlert,
  Shield,
  RefreshCw,
  Brain,
  Loader2,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Route as RouteIcon,
  ChevronRight,
  Zap,
} from 'lucide-react';
import { clsx } from 'clsx';
import { expenseApi, budgetApi, approvalApi } from '../services/api';
import { useAppStore } from '../store';
import Pagination from '../components/Pagination';
import RuleBadge from '../components/common/RuleBadge';
import { AIViewPanel, ViewToggle } from '../components/ai';

const TABS = ['报销单列表', '发票查重', '效果追踪', '异常检测', '预算消耗预测', 'AI智能预审'] as const;

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  draft: { label: '编制中', cls: 'badge-blue' },
  submitted: { label: '审批中', cls: 'badge-amber' },
  org_approved: { label: '已通过', cls: 'badge-green' },
  legal_approved: { label: '法人已批', cls: 'badge-green' },
  rejected: { label: '已驳回', cls: 'badge-red' },
  written_off: { label: '已核销', cls: 'badge-purple' },
};

const CONTROL_MAP: Record<string, { label: string; cls: string }> = {
  strong: { label: '强管控', cls: 'badge-red' },
  weak: { label: '中心弱管控', cls: 'badge-amber' },
  combo: { label: '组合管控', cls: 'badge-blue' },
  none: { label: '不管控', cls: 'badge-green' },
};

function formatAmount(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '¥ 0';
  if (n >= 10000) return `¥ ${(n / 10000).toFixed(1)}万`;
  return `¥ ${n.toLocaleString()}`;
}

export default function ExpensePage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('报销单列表');
  const [invoiceSearch, setInvoiceSearch] = useState('');
  const [expenses, setExpenses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedExpense, setSelectedExpense] = useState<any | null>(null);
  const addToast = useAppStore((s) => s.addToast);
  const location = useLocation();
  const aiContext = useAppStore((s) => s.aiContext);
  const currentUser = useAppStore((s) => s.user);
  const [invoiceCheckResult, setInvoiceCheckResult] = useState<any>(null);
  const [invoiceCheckLoading, setInvoiceCheckLoading] = useState(false);
  const [budgetOptions, setBudgetOptions] = useState<{ value: string; label: string }[]>([]);
  const [l2Options, setL2Options] = useState<{ value: string; label: string }[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize] = useState(10);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterStartDate, setFilterStartDate] = useState<string>('');
  const [filterEndDate, setFilterEndDate] = useState<string>('');
  const [strategicScores, setStrategicScores] = useState<Record<string, { alignment: number; rationality: number; details: string[] }>>({});
  const [effectForm, setEffectForm] = useState({ expected_outcome: '', actual_outcome: '', effect_score: 3, follow_up_required: false });
  const [showEffectModal, setShowEffectModal] = useState(false);
  const [effectExpenseId, setEffectExpenseId] = useState<string>('');
  const [effectTrackings, setEffectTrackings] = useState<any[]>([]);
  const [approvalStatus, setApprovalStatus] = useState<any>(null);
  const [detailTab, setDetailTab] = useState<'info' | 'effect'>('info');
  const [viewMode, setViewMode] = useState<'ai' | 'data'>('ai');
  // v9.0: v8.0 引擎接入
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [anomaliesLoading, setAnomaliesLoading] = useState(false);
  const [riskScores, setRiskScores] = useState<any[]>([]);
  const [riskScoresLoading, setRiskScoresLoading] = useState(false);
  const [burnPrediction, setBurnPrediction] = useState<any>(null);
  const [burnPredictionLoading, setBurnPredictionLoading] = useState(false);
  const [defaultPeriod] = useState(() => new Date().toISOString().slice(0, 7));

  // v9.0: 加载异常检测
  const loadAnomalies = async () => {
    setAnomaliesLoading(true);
    try {
      const res = await expenseApi.scanAnomalies({ period: defaultPeriod });
      const data = Array.isArray(res.data) ? res.data : (res.data?.anomalies || []);
      setAnomalies(data);
    } catch (e: any) {
      addToast({ type: 'error', title: '异常检测失败', message: e.message });
    } finally {
      setAnomaliesLoading(false);
    }
  };

  // v9.0: 加载风险评分
  const loadRiskScores = async () => {
    setRiskScoresLoading(true);
    try {
      const res = await expenseApi.getRiskScores({ period: defaultPeriod, top_n: 20 });
      const data = Array.isArray(res.data) ? res.data : (res.data?.scores || []);
      setRiskScores(data);
    } catch (e: any) {
      addToast({ type: 'error', title: '风险评分失败', message: e.message });
    } finally {
      setRiskScoresLoading(false);
    }
  };

  // v9.0: 加载预算消耗预测
  const loadBurnPrediction = async () => {
    setBurnPredictionLoading(true);
    try {
      const res = await expenseApi.getBudgetBurnPrediction({ period: defaultPeriod });
      setBurnPrediction(res.data);
    } catch (e: any) {
      addToast({ type: 'error', title: '预算消耗预测失败', message: e.message });
    } finally {
      setBurnPredictionLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === '异常检测' && anomalies.length === 0) loadAnomalies();
    if (activeTab === '异常检测' && riskScores.length === 0) loadRiskScores();
    if (activeTab === '预算消耗预测' && !burnPrediction) loadBurnPrediction();
  }, [activeTab]);

  // v12.1: 阶段 3 — AI 智能预审
  const [aiReviewForm, setAiReviewForm] = useState({
    description: '',
    amount: 0,
    applicant_id: '',
    l3_code: '',
    invoice_number: '',
    expense_date: new Date().toISOString().slice(0, 10),
  });
  const [aiReviewResult, setAiReviewResult] = useState<any>(null);
  const [aiReviewLoading, setAiReviewLoading] = useState(false);
  const [batchScan, setBatchScan] = useState<any>(null);
  const [batchScanLoading, setBatchScanLoading] = useState(false);

  const handleAiReview = async () => {
    if (!aiReviewForm.description.trim() || aiReviewForm.amount <= 0) return;
    setAiReviewLoading(true);
    setAiReviewResult(null);
    try {
      const res = await expenseApi.aiPreSubmitReview(aiReviewForm);
      if (res.success) setAiReviewResult(res.data);
    } catch (error) {
      console.error('AI review failed:', error);
      alert(`AI 预审失败：${(error as Error).message}`);
    } finally {
      setAiReviewLoading(false);
    }
  };

  const loadBatchScan = async () => {
    setBatchScanLoading(true);
    try {
      const res = await expenseApi.aiBatchAnomalyScan(7, 20);
      if (res.success) setBatchScan(res.data);
    } catch (error) {
      console.error('Batch scan failed:', error);
    } finally {
      setBatchScanLoading(false);
    }
  };

  const fetchExpenses = async () => {
    try {
      const response = await expenseApi.getReports({
        status: filterStatus || undefined,
        page: currentPage,
        page_size: pageSize,
      });
      const data = Array.isArray(response.data) ? response.data : [];
      setExpenses(data);
      if (response.total !== undefined) {
        setTotalPages(Math.max(1, Math.ceil(response.total / pageSize)));
      }
    } catch (error: any) {
      addToast({ type: 'error', title: '获取报销单失败', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExpenses();
  }, [currentPage, filterStatus, filterStartDate, filterEndDate]);

  useEffect(() => {
    budgetApi.getItems().then(res => {
      const opts = (res.data || []).map((item: any) => ({
        value: item.budget_id,
        label: `${item.budget_id} ${item.description || ''}`,
      }));
      setBudgetOptions(opts);
    }).catch(() => {});
    budgetApi.getSubjects({ level: 'L2' }).then(res => {
      const opts = (res.data || []).map((item: any) => ({
        value: item.l2_code || item.code,
        label: item.l2_name || item.name,
      }));
      setL2Options(opts);
    }).catch(() => {});
    // v9.0: 页面加载即预取 v8.0 引擎数据
    loadRiskScores();
    loadBurnPrediction();
  }, []);

  const handleWriteOff = async (expenseId: string) => {
    try {
      await expenseApi.writeOff(expenseId);
      addToast({ type: 'success', title: '操作成功', message: '报销单已核销' });
      fetchExpenses();
    } catch (error: any) {
      addToast({ type: 'error', title: '核销失败', message: error.message });
    }
  };

  const handleApprove = async (expenseId: string) => {
    try {
      await expenseApi.approve(expenseId, { approver_id: currentUser?.user_id || '' });
      addToast({ type: 'success', title: '操作成功', message: '报销单已通过' });
      fetchExpenses();
    } catch (error: any) {
      addToast({ type: 'error', title: '审批失败', message: error.message });
    }
  };

  const handleReject = async (expenseId: string) => {
    try {
      await expenseApi.reject(expenseId, { approver_id: currentUser?.user_id || '', comment: '驳回' });
      addToast({ type: 'success', title: '操作成功', message: '报销单已驳回' });
      fetchExpenses();
    } catch (error: any) {
      addToast({ type: 'error', title: '驳回失败', message: error.message });
    }
  };

  const handleEvaluateEffect = async () => {
    try {
      await expenseApi.evaluateEffect(effectExpenseId, {
        expected_outcome: effectForm.expected_outcome,
        actual_outcome: effectForm.actual_outcome,
        effect_score: effectForm.effect_score,
        evaluator_id: currentUser?.user_id || '',
        follow_up_required: effectForm.follow_up_required,
      });
      addToast({ type: 'success', title: '操作成功', message: '效果评估已提交' });
      setShowEffectModal(false);
      setEffectForm({ expected_outcome: '', actual_outcome: '', effect_score: 3, follow_up_required: false });
    } catch (error: any) {
      addToast({ type: 'error', title: '提交评估失败', message: error.message });
    }
  };

  const draftCount = expenses.filter(e => e.status === 'draft').length;
  const submittedCount = expenses.filter(e => e.status === 'submitted').length;
  const writtenOffCount = expenses.filter(e => e.status === 'written_off').length;
  const monthlyTotal = expenses.reduce((s, e) => s + (e.amount || 0), 0);

  // v9.0 B.2: 风险分查表（expense_id → risk_score），用于表格行内显示
  const riskScoresMap = useMemo<Record<string, number>>(() => {
    const m: Record<string, number> = {};
    riskScores.forEach((r: any) => {
      if (r.expense_id != null) m[r.expense_id] = r.risk_score || 0;
    });
    return m;
  }, [riskScores]);

  // AI pre-review insights from expense data
  const expenseAIInsights = useMemo(() => {
    const insights: { priority: 'critical' | 'attention' | 'info'; title: string; analysis: string; suggestion: string }[] = [];
    let autoApproved = 0;
    let needsReview = 0;

    expenses.forEach((exp: any) => {
      const amount = exp.amount || 0;
      let risk = 'low';
      let riskReasons: string[] = [];

      // Risk scoring based on amount thresholds
      if (amount > 50000) { risk = 'high'; riskReasons.push('大额支出（超过5万）'); }
      else if (amount > 10000) { risk = 'medium'; riskReasons.push('中等金额（超过1万）'); }

      // Control tag risk
      if (exp.control_tag === 'strong') { risk = risk === 'low' ? 'medium' : 'high'; riskReasons.push('强管控类别'); }

      // Status risk
      if (exp.status === 'rejected') { risk = 'high'; riskReasons.push('曾被驳回'); }

      // Amount vs budget ratio
      if (amount > 20000) { riskReasons.push('单笔金额较高'); risk = risk === 'low' ? 'medium' : risk; }

      if (risk === 'low') { autoApproved++; }
      else {
        needsReview++;
        const priority = risk === 'high' ? 'critical' : 'attention';
        const applicant = exp.applicant_name || exp.applicant_id || '未知';
        insights.push({
          priority,
          title: `${applicant} - ${formatAmount(amount)} ${riskReasons[0]}`,
          analysis: `报销单 ${exp.expense_id} 风险等级：${risk === 'high' ? '高风险' : '中等风险'}。${riskReasons.join('；')}。审批状态：${STATUS_MAP[exp.status]?.label || exp.status}。`,
          suggestion: risk === 'high'
            ? '建议人工审核该报销单，重点关注支出合理性和预算充足性。必要时可要求补充证明材料。'
            : '建议关注该报销单，确认支出事由和金额是否合理。',
        });
      }
    });

    return { insights, autoApproved, needsReview };
  }, [expenses]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-finance-800 font-display">费用报销</h1>
          <p className="text-sm text-surface-400 mt-1">报销申请、审批跟踪与发票查重</p>
        </div>
        <ViewToggle mode={viewMode} onToggle={setViewMode} />
      </div>

      {/* AI View */}
      <AnimatePresence>
        {viewMode === 'ai' && (
          <motion.div
            key="expense-ai-view"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2 }}
          >
            <div className="glass-card p-6">
              {aiContext && (
                <div className="flex items-center gap-2 mb-3 pb-3 border-b border-surface-100">
                  <div className="flex items-center gap-1.5 text-[10px] text-surface-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-finance-400" />
                    此分析基于你的 Dashboard 工作清单 · 最后更新于 {new Date(aiContext.lastUpdate).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              )}
              <AIViewPanel
                title="报销 AI 预审"
                summary={`自动通过 ${expenseAIInsights.autoApproved} 笔，需人工审核 ${expenseAIInsights.needsReview} 笔`}
                score={{ value: expenses.length > 0 ? Math.round((expenseAIInsights.autoApproved / expenses.length) * 100) : 0, label: '自动通过率', max: 100 }}
                insights={expenseAIInsights.insights}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
        {[
          { label: '待提交', value: draftCount, gradient: 'from-brand-500 to-finance-600' },
          { label: '审批中', value: submittedCount, gradient: 'from-warning-500 to-alert-500' },
          { label: '已核销', value: writtenOffCount, gradient: 'from-compliance-500 to-health-600' },
          { label: '本月报销额', value: formatAmount(monthlyTotal), gradient: 'from-finance-500 to-finance-700' },
          {
            label: '高风险报销单',
            value: riskScores.filter((r) => (r.risk_score || 0) >= 70).length,
            gradient: 'from-alert-500 to-rose-700',
            suffix: '笔',
          },
          {
            label: '预算预计燃尽',
            value: burnPrediction?.runway_months != null
              ? `${burnPrediction.runway_months.toFixed(1)}月`
              : '计算中…',
            gradient: 'from-amber-500 to-orange-600',
          },
        ].map(card => (
          <div key={card.label} className="glass-card p-5">
            <p className="metric-label mb-2">{card.label}</p>
            <p className="metric-value">
              <span className={`bg-gradient-to-r ${card.gradient} bg-clip-text text-transparent`}>
                {card.value}{card.suffix || ''}
              </span>
            </p>
          </div>
        ))}
      </div>

      <div className="glass-card">
        <div className="flex border-b border-surface-200/60">
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={clsx(
                'px-5 py-3 text-sm font-medium transition-colors relative',
                activeTab === tab ? 'text-finance-700' : 'text-surface-400 hover:text-surface-600'
              )}
            >
              {tab}
              {activeTab === tab && (
                <motion.div
                  layoutId="expenseTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === '报销单列表' && (
              <motion.div
                key="list"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="flex flex-wrap items-center gap-3 mb-4 p-3 rounded-xl bg-surface-50/50 border border-surface-200/60">
                  <Filter size={14} className="text-surface-400" />
                  <select
                    value={filterStatus}
                    onChange={e => { setFilterStatus(e.target.value); setCurrentPage(1); }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value="">全部状态</option>
                    <option value="draft">草稿</option>
                    <option value="submitted">已提交</option>
                    <option value="org_approved">审批中</option>
                    <option value="legal_approved">已审批</option>
                    <option value="written_off">已核销</option>
                    <option value="rejected">已驳回</option>
                  </select>
                  <input
                    type="date"
                    value={filterStartDate}
                    onChange={e => { setFilterStartDate(e.target.value); setCurrentPage(1); }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    placeholder="开始日期"
                  />
                  <span className="text-xs text-surface-400">至</span>
                  <input
                    type="date"
                    value={filterEndDate}
                    onChange={e => { setFilterEndDate(e.target.value); setCurrentPage(1); }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    placeholder="结束日期"
                  />
                </div>
                {loading ? (
                  <div className="text-center py-10 text-surface-300">
                    <p className="text-sm">加载中...</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-surface-200/60">
                          <th className="text-left py-3 px-3 metric-label">报销单号</th>
                          <th className="text-left py-3 px-3 metric-label">申请人</th>
                          <th className="text-left py-3 px-3 metric-label">预算ID</th>
                          <th className="text-right py-3 px-3 metric-label">金额</th>
                          <th className="text-left py-3 px-3 metric-label">L2费用类别</th>
                          <th className="text-center py-3 px-3 metric-label">管控级别</th>
                          <th className="text-center py-3 px-3 metric-label">风险分</th>
                          <th className="text-left py-3 px-3 metric-label">规则依据</th>
                          <th className="text-center py-3 px-3 metric-label">审批状态</th>
                          <th className="text-center py-3 px-3 metric-label">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {expenses.map(exp => (
                          <tr
                            key={exp.expense_id}
                            className={clsx(
                              'border-b border-surface-100 hover:bg-finance-50/30 transition-colors cursor-pointer',
                              selectedExpense?.expense_id === exp.expense_id && 'bg-finance-50/50'
                            )}
                            onClick={() => {
                              setSelectedExpense(exp);
                              setDetailTab('info');
                              // Fetch approval status
                              approvalApi.getChain(exp.expense_id).then(res => {
                                const records = Array.isArray(res.data) ? res.data : [];
                                // Group by approval_line
                                const grouped: any = { org_line: [], legal_line: [] };
                                records.forEach((r: any) => {
                                  if (r.approval_line === 'legal' || r.approval_line === '法人线') {
                                    grouped.legal_line.push(r);
                                  } else {
                                    grouped.org_line.push(r);
                                  }
                                });
                                setApprovalStatus(grouped);
                              }).catch(() => setApprovalStatus(null));
                              // Fetch effect tracking
                              expenseApi.getExpenseEffectTracking(exp.expense_id).then(res => {
                                setEffectTrackings(Array.isArray(res.data) ? res.data : []);
                              }).catch(() => setEffectTrackings([]));
                            }}
                          >
                            <td className="py-3 px-3 font-mono text-xs text-finance-700">{exp.expense_id}</td>
                            <td className="py-3 px-3 font-medium text-surface-800">{exp.applicant_name || exp.applicant_id}</td>
                            <td className="py-3 px-3 text-surface-500 font-mono text-xs">{exp.budget_id}</td>
                            <td className="py-3 px-3 text-right font-mono">{formatAmount(exp.amount)}</td>
                            <td className="py-3 px-3 text-surface-600">{exp.l2_name || exp.l3_code || '-'}</td>
                            <td className="py-3 px-3 text-center">
                              <span className={CONTROL_MAP[exp.control_tag]?.cls || 'badge-green'}>
                                {CONTROL_MAP[exp.control_tag]?.label || '不管控'}
                              </span>
                            </td>
                            <td className="py-3 px-3 text-center">
                              {(() => {
                                const score = riskScoresMap[exp.expense_id] ?? 0;
                                return (
                                  <div className="inline-flex items-center gap-1.5">
                                    <span className={clsx(
                                      'text-xs font-bold font-mono',
                                      score >= 70 ? 'text-rose-600' :
                                      score >= 40 ? 'text-amber-600' :
                                      'text-emerald-600'
                                    )}>
                                      {score.toFixed(0)}
                                    </span>
                                    <div className="w-10 h-1 bg-surface-100 rounded-full overflow-hidden">
                                      <div
                                        className={clsx(
                                          'h-full rounded-full',
                                          score >= 70 ? 'bg-rose-500' :
                                          score >= 40 ? 'bg-amber-500' :
                                          'bg-emerald-500'
                                        )}
                                        style={{ width: `${Math.min(100, score)}%` }}
                                      />
                                    </div>
                                  </div>
                                );
                              })()}
                            </td>
                            <td className="py-3 px-3">
                              {exp.rule_ids && exp.rule_ids.length > 0 ? (
                                <div className="flex flex-wrap gap-1">
                                  {exp.rule_ids.slice(0, 2).map((rid: string) => (
                                    <RuleBadge key={rid} rule_id={rid} size="xs" />
                                  ))}
                                </div>
                              ) : (
                                <span className="text-[10px] text-surface-400">-</span>
                              )}
                            </td>
                            <td className="py-3 px-3 text-center">
                              <span className={STATUS_MAP[exp.status]?.cls || 'badge-blue'}>
                                {STATUS_MAP[exp.status]?.label || exp.status}
                              </span>
                            </td>
                            <td className="py-3 px-3 text-center" onClick={e => e.stopPropagation()}>
                              <div className="flex gap-1 justify-center">
                                {exp.status === 'submitted' && (
                                  <>
                                    <button
                                      onClick={() => handleApprove(exp.expense_id)}
                                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-compliance-50 text-compliance-700 border border-compliance-200 hover:bg-compliance-100 transition-colors"
                                    >
                                      <Check size={10} /> 通过
                                    </button>
                                    <button
                                      onClick={() => handleReject(exp.expense_id)}
                                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-alert-50 text-alert-700 border border-alert-200 hover:bg-alert-100 transition-colors"
                                    >
                                      <X size={10} /> 驳回
                                    </button>
                                  </>
                                )}
                                {(exp.status === 'org_approved' || exp.status === 'legal_approved') && (
                                  <>
                                    <button
                                      onClick={() => handleWriteOff(exp.expense_id)}
                                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100 transition-colors"
                                    >
                                      <FileCheck size={10} /> 核销
                                    </button>
                                    <button
                                      onClick={() => { setEffectExpenseId(exp.expense_id); setShowEffectModal(true); }}
                                      className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors"
                                    >
                                      <TrendingUp size={10} /> 效果评估
                                    </button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {selectedExpense && strategicScores[selectedExpense.expense_id] && (
                      <motion.div
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-3 p-4 rounded-xl border border-amber-100 bg-amber-50/30"
                      >
                        <div className="flex items-center gap-2 mb-3">
                          <Target size={14} className="text-amber-600" />
                          <span className="text-sm font-medium text-amber-700">战略对齐评估</span>
                          {strategicScores[selectedExpense.expense_id].alignment < 30 && (
                            <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-red-100 text-red-700 border border-red-300">强制审核</span>
                          )}
                          {strategicScores[selectedExpense.expense_id].alignment >= 30 && strategicScores[selectedExpense.expense_id].alignment < 40 && (
                            <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700 border border-amber-300">建议审核</span>
                          )}
                        </div>
                        {/* 4-dimension progress bars */}
                        <div className="space-y-2 mb-3">
                          {(() => {
                            const score = strategicScores[selectedExpense.expense_id];
                            const details = score.details || [];
                            // Parse dimension scores from details
                            const intentScore = details.some(d => d.includes('对齐') && !d.includes('不对齐')) ? 90 : details.some(d => d.includes('不对齐')) ? 35 : 70;
                            const quadrantScore = details.some(d => d.includes('收缩')) ? 30 : details.some(d => d.includes('发展')) ? 85 : details.some(d => d.includes('探索')) ? 55 : 70;
                            const trendScore = details.some(d => d.includes('增长') && d.includes('超过')) ? 30 : details.some(d => d.includes('下降趋势')) ? 85 : 70;
                            const budgetRatioScore = details.some(d => d.includes('比例偏高')) ? 40 : details.some(d => d.includes('比例合理')) ? 85 : 70;
                            const dimensions = [
                              { label: '战略意图对齐', value: intentScore },
                              { label: '象限归属', value: quadrantScore },
                              { label: '趋势检测', value: trendScore },
                              { label: '预算占比', value: budgetRatioScore },
                            ];
                            return dimensions.map(dim => (
                              <div key={dim.label} className="flex items-center gap-2">
                                <span className="text-xs text-surface-500 w-20 shrink-0">{dim.label}</span>
                                <div className="flex-1 h-2 bg-surface-100 rounded-full overflow-hidden">
                                  <div
                                    className={clsx(
                                      'h-full rounded-full transition-all',
                                      dim.value >= 70 ? 'bg-green-500' : dim.value >= 40 ? 'bg-amber-500' : 'bg-red-500'
                                    )}
                                    style={{ width: `${dim.value}%` }}
                                  />
                                </div>
                                <span className={clsx(
                                  'text-xs font-mono w-8 text-right',
                                  dim.value >= 70 ? 'text-green-600' : dim.value >= 40 ? 'text-amber-600' : 'text-red-600'
                                )}>{dim.value}</span>
                              </div>
                            ));
                          })()}
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <p className="text-xs text-surface-500">战略对齐度</p>
                            <p className={clsx(
                              'text-lg font-bold',
                              strategicScores[selectedExpense.expense_id].alignment < 40 ? 'text-red-600' :
                              strategicScores[selectedExpense.expense_id].alignment < 70 ? 'text-amber-600' : 'text-green-600'
                            )}>
                              {strategicScores[selectedExpense.expense_id].alignment}
                              <span className="text-xs font-normal text-surface-400">/100</span>
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-surface-500">资源合理性</p>
                            <p className={clsx(
                              'text-lg font-bold',
                              strategicScores[selectedExpense.expense_id].rationality < 40 ? 'text-red-600' :
                              strategicScores[selectedExpense.expense_id].rationality < 70 ? 'text-amber-600' : 'text-green-600'
                            )}>
                              {strategicScores[selectedExpense.expense_id].rationality}
                              <span className="text-xs font-normal text-surface-400">/100</span>
                            </p>
                          </div>
                        </div>
                        {strategicScores[selectedExpense.expense_id].alignment < 40 && (
                          <div className="mt-2 px-2 py-1 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
                            ⚠️ 战略对齐度低于40%，将触发战略审核步骤
                          </div>
                        )}
                        {strategicScores[selectedExpense.expense_id].details.length > 0 && (
                          <div className="mt-2 text-xs text-surface-500">
                            {strategicScores[selectedExpense.expense_id].details.map((d, i) => (
                              <p key={i}>• {d}</p>
                            ))}
                          </div>
                        )}
                      </motion.div>
                    )}

                    {/* Approval steps with mandatory indicator */}
                    {selectedExpense && approvalStatus && (approvalStatus.org_line?.length > 0 || approvalStatus.legal_line?.length > 0) && (
                      <motion.div
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-3 p-4 rounded-xl border border-finance-100 bg-finance-50/30"
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <FileCheck size={14} className="text-finance-600" />
                          <span className="text-sm font-medium text-finance-700">审批步骤</span>
                        </div>
                        <div className="space-y-1.5">
                          {[
                            ...(approvalStatus.org_line || []).map((s: any) => ({ ...s, line: '组织线' })),
                            ...(approvalStatus.legal_line || []).map((s: any) => ({ ...s, line: '法人线' })),
                          ].sort((a: any, b: any) => a.step - b.step).map((step: any, idx: number) => (
                            <div key={idx} className="flex items-center gap-2 text-xs">
                              <span className={clsx(
                                'px-1.5 py-0.5 rounded font-medium',
                                step.action === '通过' ? 'bg-green-50 text-green-700' :
                                step.action === '驳回' ? 'bg-red-50 text-red-700' :
                                'bg-amber-50 text-amber-700'
                              )}>
                                {step.action}
                              </span>
                              <span className="text-surface-500">{step.line} Step {step.step}</span>
                              <span className="font-medium text-surface-700">{step.role}</span>
                              {step.role === '战略审核' && step.is_mandatory && (
                                <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-red-100 text-red-700 border border-red-300">不可跳过</span>
                              )}
                              {step.role === '战略审核' && !step.is_mandatory && (
                                <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-600 border border-amber-300">可跳过</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </div>
                )}
                <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} pageSize={pageSize} />
              </motion.div>
            )}

            {activeTab === '发票查重' && (
              <motion.div
                key="invoice"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="max-w-lg">
                  <div className="flex gap-3 mb-4">
                    <input
                      type="text"
                      value={invoiceSearch}
                      onChange={e => { setInvoiceSearch(e.target.value); setInvoiceCheckResult(null); }}
                      placeholder="请输入发票号码"
                      className="flex-1 px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    />
                    <button
                      className="btn-primary"
                      disabled={!invoiceSearch || invoiceCheckLoading}
                      onClick={async () => {
                        setInvoiceCheckLoading(true);
                        setInvoiceCheckResult(null);
                        try {
                          const response = await expenseApi.checkInvoiceDuplicate(invoiceSearch);
                          setInvoiceCheckResult(response.data);
                        } catch (error: any) {
                          addToast({ type: 'error', title: '发票查重失败', message: error.message });
                        } finally {
                          setInvoiceCheckLoading(false);
                        }
                      }}
                    >
                      <Search size={14} /> {invoiceCheckLoading ? '查询中...' : '查询'}
                    </button>
                  </div>
                  {invoiceCheckResult && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className={invoiceCheckResult.is_duplicate
                        ? 'p-4 rounded-xl border border-alert-200 bg-alert-50/30'
                        : 'p-4 rounded-xl border border-compliance-200 bg-compliance-50/30'
                      }
                    >
                      {invoiceCheckResult.is_duplicate ? (
                        <>
                          <div className="flex items-center gap-2 mb-2">
                            <AlertCircle size={16} className="text-alert-600" />
                            <span className="text-sm font-medium text-alert-700">
                              发现重复发票 (共{invoiceCheckResult.duplicate_count}条)
                            </span>
                          </div>
                          {invoiceCheckResult.duplicate_records?.map((rec: any, idx: number) => (
                            <div key={idx} className="text-sm text-surface-600 ml-6 mb-1">
                              发票号: {rec.invoice_number} | 金额: {rec.amount ?? rec.invoice_amount ?? '-'} | 状态: {rec.upload_status ?? rec.is_duplicate ? '重复' : '正常'}
                            </div>
                          ))}
                        </>
                      ) : (
                        <div className="flex items-center gap-2">
                          <FileCheck size={16} className="text-compliance-600" />
                          <span className="text-sm font-medium text-compliance-700">该发票号码未发现重复记录</span>
                        </div>
                      )}
                    </motion.div>
                  )}
                  {!invoiceCheckResult && !invoiceSearch && (
                    <div className="text-center py-10 text-surface-300">
                      <Receipt size={40} className="mx-auto mb-3 opacity-30" />
                      <p className="text-sm">输入发票号码进行查重</p>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === '效果追踪' && (
              <motion.div
                key="effect-tracking"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="max-w-3xl">
                  {!selectedExpense ? (
                    <div className="text-center py-10 text-surface-300">
                      <TrendingUp size={40} className="mx-auto mb-3 opacity-30" />
                      <p className="text-sm">请先在报销单列表中选择一个报销单查看效果追踪</p>
                    </div>
                  ) : effectTrackings.length === 0 ? (
                    <div className="text-center py-10 text-surface-300">
                      <TrendingUp size={40} className="mx-auto mb-3 opacity-30" />
                      <p className="text-sm">该报销单暂无效果追踪记录</p>
                      <p className="text-xs mt-1">报销单号: {selectedExpense.expense_id}</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 mb-2">
                        <TrendingUp size={14} className="text-finance-600" />
                        <span className="text-sm font-medium text-finance-700">
                          {selectedExpense.expense_id} 效果追踪
                        </span>
                      </div>
                      {effectTrackings.map((tracking: any) => (
                        <div key={tracking.tracking_id} className="p-4 rounded-xl border border-surface-200/60 bg-white">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-mono text-xs text-finance-600">{tracking.tracking_id}</span>
                            <span className={clsx(
                              'px-2 py-0.5 rounded text-xs font-medium',
                              tracking.status === '待评估' ? 'bg-amber-50 text-amber-700 border border-amber-200' :
                              tracking.status === '已评估' ? 'bg-green-50 text-green-700 border border-green-200' :
                              'bg-red-50 text-red-700 border border-red-200'
                            )}>
                              {tracking.status || '待评估'}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <span className="text-surface-400">预期效果:</span>
                              <span className="text-surface-700 ml-1">{tracking.expected_outcome || '待填写'}</span>
                            </div>
                            <div>
                              <span className="text-surface-400">实际效果:</span>
                              <span className="text-surface-700 ml-1">{tracking.actual_outcome || '待填写'}</span>
                            </div>
                            <div>
                              <span className="text-surface-400">效果评分:</span>
                              <span className="text-surface-700 ml-1">{tracking.effect_score ? `${tracking.effect_score}/5` : '未评分'}</span>
                            </div>
                            <div>
                              <span className="text-surface-400">评估截止:</span>
                              <span className="text-surface-700 ml-1">{tracking.evaluation_deadline || '未设置'}</span>
                            </div>
                            {tracking.follow_up_required && (
                              <div className="col-span-2">
                                <span className="px-1.5 py-0.5 rounded text-xs bg-blue-50 text-blue-700 border border-blue-200">需要跟进</span>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* v9.0: 异常检测 Tab（接 v8.0 expense_anomaly + expense_risk_score 引擎） */}
            {activeTab === '异常检测' && (
              <motion.div
                key="anomalies"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-finance-800">异常检测报告（v8.0 引擎）</h3>
                      <p className="text-xs text-surface-500 mt-0.5">
                        基于 z-score 异常检测 + 5 维风险评分（金额/品类/频次/时段/历史）
                      </p>
                    </div>
                    <button
                      className="btn-secondary text-xs"
                      onClick={() => { loadAnomalies(); loadRiskScores(); }}
                      disabled={anomaliesLoading || riskScoresLoading}
                    >
                      <RefreshCw size={12} className={anomaliesLoading ? 'animate-spin' : ''} /> 重新扫描
                    </button>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {/* 左：异常列表 */}
                    <div className="p-4 rounded-xl border border-surface-200 bg-white">
                      <div className="flex items-center gap-2 mb-3">
                        <ShieldAlert size={14} className="text-alert-600" />
                        <span className="text-sm font-semibold text-finance-800">异常报销单</span>
                        <span className="ml-auto px-2 py-0.5 rounded-full text-[10px] font-bold bg-alert-50 text-alert-700 border border-alert-200">
                          {anomalies.length}
                        </span>
                      </div>
                      {anomaliesLoading ? (
                        <div className="text-center py-8 text-surface-400 text-sm">扫描中...</div>
                      ) : anomalies.length === 0 ? (
                        <div className="text-center py-8 text-surface-400 text-sm">未发现异常报销单</div>
                      ) : (
                        <ul className="space-y-2 max-h-96 overflow-y-auto">
                          {anomalies.slice(0, 20).map((a, idx) => (
                            <li key={a.expense_id || idx} className="p-3 rounded-lg border border-alert-100 bg-alert-50/30">
                              <div className="flex items-center justify-between mb-1.5">
                                <span className="font-mono text-xs text-finance-700">{a.expense_id}</span>
                                <span className={clsx(
                                  'px-1.5 py-0.5 rounded text-[10px] font-bold',
                                  a.severity === 'high' ? 'bg-rose-100 text-rose-700' :
                                  a.severity === 'medium' ? 'bg-amber-100 text-amber-700' :
                                  'bg-blue-100 text-blue-700'
                                )}>
                                  {a.severity === 'high' ? '高' : a.severity === 'medium' ? '中' : '低'}
                                </span>
                              </div>
                              <p className="text-xs text-surface-700">
                                {a.applicant_name || a.applicant_id || '未知'} · {formatAmount(a.amount)}
                              </p>
                              <p className="text-[11px] text-surface-500 mt-1">
                                {a.anomaly_type || a.reason || '金额/品类/时段异常'}
                              </p>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    {/* 右：风险评分 Top */}
                    <div className="p-4 rounded-xl border border-surface-200 bg-white">
                      <div className="flex items-center gap-2 mb-3">
                        <Target size={14} className="text-amber-600" />
                        <span className="text-sm font-semibold text-finance-800">风险评分 Top 20</span>
                      </div>
                      {riskScoresLoading ? (
                        <div className="text-center py-8 text-surface-400 text-sm">加载中...</div>
                      ) : riskScores.length === 0 ? (
                        <div className="text-center py-8 text-surface-400 text-sm">无风险数据</div>
                      ) : (
                        <ul className="space-y-2 max-h-96 overflow-y-auto">
                          {riskScores.slice(0, 20).map((r, idx) => (
                            <li key={r.expense_id || idx} className="flex items-center gap-3">
                              <span className="text-[10px] font-mono text-surface-400 w-6 shrink-0">#{idx + 1}</span>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-xs text-surface-700 truncate">
                                    {r.applicant_name || r.expense_id}
                                  </span>
                                  <span className={clsx(
                                    'text-xs font-bold ml-2',
                                    r.risk_score >= 70 ? 'text-rose-600' :
                                    r.risk_score >= 40 ? 'text-amber-600' :
                                    'text-emerald-600'
                                  )}>
                                    {r.risk_score?.toFixed(0) ?? 0}
                                  </span>
                                </div>
                                <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden">
                                  <div
                                    className={clsx(
                                      'h-full rounded-full',
                                      r.risk_score >= 70 ? 'bg-rose-500' :
                                      r.risk_score >= 40 ? 'bg-amber-500' :
                                      'bg-emerald-500'
                                    )}
                                    style={{ width: `${Math.min(100, r.risk_score || 0)}%` }}
                                  />
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* v9.0: 预算消耗预测 Tab（接 v8.0 budget_burn_predictor 引擎） */}
            {activeTab === '预算消耗预测' && (
              <motion.div
                key="burn"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-finance-800">预算消耗预测（v8.0 引擎）</h3>
                      <p className="text-xs text-surface-500 mt-0.5">
                        基于线性回归 + 季节性调整预测燃尽月份
                      </p>
                    </div>
                    <button
                      className="btn-secondary text-xs"
                      onClick={loadBurnPrediction}
                      disabled={burnPredictionLoading}
                    >
                      <RefreshCw size={12} className={burnPredictionLoading ? 'animate-spin' : ''} /> 重新计算
                    </button>
                  </div>

                  {burnPredictionLoading ? (
                    <div className="text-center py-12 text-surface-400 text-sm">预测计算中...</div>
                  ) : !burnPrediction ? (
                    <div className="text-center py-12 text-surface-400 text-sm">暂无预算预测数据</div>
                  ) : (
                    <>
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div className="p-4 rounded-xl border border-finance-200 bg-finance-50/30">
                          <p className="text-xs text-surface-500">当前已消耗</p>
                          <p className="text-lg font-bold text-finance-700 mt-1">
                            {formatAmount(burnPrediction.consumed)}
                          </p>
                        </div>
                        <div className="p-4 rounded-xl border border-surface-200 bg-white">
                          <p className="text-xs text-surface-500">年度预算</p>
                          <p className="text-lg font-bold text-finance-800 mt-1">
                            {formatAmount(burnPrediction.total_budget)}
                          </p>
                        </div>
                        <div className="p-4 rounded-xl border border-surface-200 bg-white">
                          <p className="text-xs text-surface-500">执行率</p>
                          <p className="text-lg font-bold text-finance-800 mt-1">
                            {burnPrediction.execution_rate?.toFixed(1) ?? 0}%
                          </p>
                        </div>
                        <div className={clsx(
                          'p-4 rounded-xl border bg-white',
                          burnPrediction.runway_months < 3 ? 'border-rose-200 bg-rose-50/30' :
                          burnPrediction.runway_months < 6 ? 'border-amber-200 bg-amber-50/30' :
                          'border-emerald-200 bg-emerald-50/30'
                        )}>
                          <p className="text-xs text-surface-500">预计燃尽月份</p>
                          <p className={clsx(
                            'text-lg font-bold mt-1',
                            burnPrediction.runway_months < 3 ? 'text-rose-600' :
                            burnPrediction.runway_months < 6 ? 'text-amber-600' :
                            'text-emerald-600'
                          )}>
                            {burnPrediction.runway_months?.toFixed(1) ?? '∞'} 月
                          </p>
                        </div>
                      </div>

                      {/* 趋势列表 */}
                      {Array.isArray(burnPrediction.trend) && burnPrediction.trend.length > 0 && (
                        <div className="p-4 rounded-xl border border-surface-200 bg-white">
                          <h4 className="text-xs font-semibold text-surface-600 mb-2">消耗趋势</h4>
                          <div className="space-y-1.5">
                            {burnPrediction.trend.map((t: any, i: number) => (
                              <div key={i} className="flex items-center gap-3 text-xs">
                                <span className="font-mono text-surface-500 w-20 shrink-0">{t.month}</span>
                                <div className="flex-1 h-2 bg-surface-100 rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-gradient-to-r from-finance-400 to-finance-600 rounded-full"
                                    style={{ width: `${Math.min(100, t.execution_rate || 0)}%` }}
                                  />
                                </div>
                                <span className="text-surface-700 w-20 text-right shrink-0">
                                  {formatAmount(t.amount)}
                                </span>
                                <span className="text-surface-500 w-14 text-right shrink-0">
                                  {t.execution_rate?.toFixed(0) ?? 0}%
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {burnPrediction.warning && (
                        <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/30">
                          <div className="flex items-center gap-2 mb-1">
                            <AlertCircle size={14} className="text-amber-600" />
                            <span className="text-sm font-semibold text-amber-800">预警</span>
                          </div>
                          <p className="text-xs text-amber-700 leading-relaxed">{burnPrediction.warning}</p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </motion.div>
            )}

            {/* ── v12.1: 阶段 3 — AI 智能预审 ─────────── */}
            {activeTab === 'AI智能预审' && (
              <motion.div
                key="ai-review"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                  {/* 左：单笔 AI 预审 */}
                  <div className="space-y-4">
                    <div className="glass-card p-5">
                      <div className="flex items-center gap-2 mb-4">
                        <Brain size={16} className="text-finance-600" />
                        <h3 className="text-sm font-semibold text-finance-800">单笔预审（提交前 AI 体检）</h3>
                      </div>

                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-surface-600 mb-1">
                            报销说明 <span className="text-alert-500">*</span>
                          </label>
                          <textarea
                            value={aiReviewForm.description}
                            onChange={e => setAiReviewForm(f => ({ ...f, description: e.target.value }))}
                            placeholder="如：出差北京参加行业峰会，含 3 天酒店 + 高铁"
                            rows={2}
                            className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-surface-600 mb-1">
                              金额 (¥) <span className="text-alert-500">*</span>
                            </label>
                            <input
                              type="number"
                              value={aiReviewForm.amount || ''}
                              onChange={e => setAiReviewForm(f => ({ ...f, amount: Number(e.target.value) }))}
                              placeholder="5000"
                              className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-surface-600 mb-1">申请人 ID</label>
                            <input
                              type="text"
                              value={aiReviewForm.applicant_id}
                              onChange={e => setAiReviewForm(f => ({ ...f, applicant_id: e.target.value }))}
                              placeholder="EMP-001"
                              className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-surface-600 mb-1">发票号（可选）</label>
                            <input
                              type="text"
                              value={aiReviewForm.invoice_number}
                              onChange={e => setAiReviewForm(f => ({ ...f, invoice_number: e.target.value }))}
                              placeholder="INV-XXX"
                              className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-surface-600 mb-1">发生日期</label>
                            <input
                              type="date"
                              value={aiReviewForm.expense_date}
                              onChange={e => setAiReviewForm(f => ({ ...f, expense_date: e.target.value }))}
                              className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                            />
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={handleAiReview}
                        disabled={aiReviewLoading || !aiReviewForm.description.trim() || aiReviewForm.amount <= 0}
                        className={clsx(
                          'btn-primary w-full mt-4 flex items-center justify-center gap-2',
                          (aiReviewLoading || !aiReviewForm.description.trim() || aiReviewForm.amount <= 0) && 'opacity-50 cursor-not-allowed'
                        )}
                      >
                        {aiReviewLoading ? (
                          <>
                            <Loader2 size={14} className="animate-spin" /> AI 预审中…
                          </>
                        ) : (
                          <>
                            <Sparkles size={14} /> 启动 AI 预审
                          </>
                        )}
                      </button>
                    </div>

                    {/* 预审结果 */}
                    {aiReviewResult && (
                      <div className="glass-card p-5 space-y-4">
                        {/* 顶部摘要 */}
                        <div className={clsx(
                          'p-3 rounded-xl border',
                          aiReviewResult.should_submit
                            ? 'bg-compliance-50 border-compliance-200'
                            : 'bg-alert-50 border-alert-200'
                        )}>
                          <div className="flex items-center gap-2">
                            {aiReviewResult.should_submit ? (
                              <CheckCircle2 size={16} className="text-compliance-700" />
                            ) : (
                              <AlertTriangle size={16} className="text-alert-700" />
                            )}
                            <span className={clsx(
                              'text-sm font-semibold',
                              aiReviewResult.should_submit ? 'text-compliance-800' : 'text-alert-800'
                            )}>
                              {aiReviewResult.should_submit ? '建议提交' : '建议暂缓提交'}
                            </span>
                            <span className="ml-auto text-xs text-surface-500">
                              拒付概率 <span className="font-mono font-semibold">{aiReviewResult.rejection_prediction.reject_probability}%</span>
                            </span>
                          </div>
                        </div>

                        {/* L3 识别 */}
                        <div>
                          <p className="text-xs font-semibold text-surface-700 mb-2 flex items-center gap-1">
                            <Target size={12} /> L3 智能识别
                          </p>
                          <div className="p-2.5 rounded-lg bg-brand-50/50 border border-brand-200">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-finance-800">
                                {aiReviewResult.l3_recognition.l3_name}
                              </span>
                              <span className="text-xs font-mono text-surface-500">
                                {aiReviewResult.l3_recognition.l3_code}
                              </span>
                              <span className={clsx(
                                'ml-auto text-[10px] px-1.5 py-0.5 rounded',
                                aiReviewResult.l3_recognition.control_tag === '强管控' ? 'bg-alert-100 text-alert-700' :
                                aiReviewResult.l3_recognition.control_tag === '不管控' ? 'bg-compliance-100 text-compliance-700' :
                                'bg-warning-100 text-warning-700'
                              )}>
                                {aiReviewResult.l3_recognition.control_tag}
                              </span>
                              <span className="text-[10px] font-mono text-surface-500">
                                置信度 {aiReviewResult.l3_recognition.confidence}%
                              </span>
                            </div>
                            {aiReviewResult.l3_recognition.matched_keywords?.length > 0 && (
                              <p className="text-[10px] text-surface-500 mt-1">
                                命中关键词：{aiReviewResult.l3_recognition.matched_keywords.join('、')}
                              </p>
                            )}
                            {aiReviewResult.l3_recognition.alternatives?.length > 0 && (
                              <div className="mt-2 text-[10px] text-surface-500">
                                候选项：{aiReviewResult.l3_recognition.alternatives.map((a: any) => `${a.l3_name}(${a.score})`).join('、')}
                              </div>
                            )}
                          </div>
                        </div>

                        {/* 异常检测 */}
                        <div>
                          <p className="text-xs font-semibold text-surface-700 mb-2 flex items-center gap-1">
                            <ShieldAlert size={12} /> 5 维异常检测
                            <span className={clsx(
                              'ml-1 text-[10px] px-1.5 py-0.5 rounded',
                              aiReviewResult.anomaly_detection.risk_level === '高' ? 'bg-alert-100 text-alert-700' :
                              aiReviewResult.anomaly_detection.risk_level === '中' ? 'bg-warning-100 text-warning-700' :
                              'bg-compliance-100 text-compliance-700'
                            )}>
                              {aiReviewResult.anomaly_detection.risk_level}风险（{aiReviewResult.anomaly_detection.risk_score}）
                            </span>
                          </p>
                          {aiReviewResult.anomaly_detection.anomalies.length === 0 ? (
                            <p className="text-xs text-surface-400 px-2 py-1.5">未发现异常 ✓</p>
                          ) : (
                            <div className="space-y-1">
                              {aiReviewResult.anomaly_detection.anomalies.map((a: any, i: number) => (
                                <div key={i} className={clsx(
                                  'flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs',
                                  a.severity === '高' ? 'bg-alert-50 text-alert-700' : 'bg-warning-50 text-warning-700'
                                )}>
                                  <AlertCircle size={11} />
                                  <span className="font-semibold">{a.type}</span>
                                  <span className="text-surface-400">|</span>
                                  <span className="flex-1">{a.detail}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* 智能路由 */}
                        <div>
                          <p className="text-xs font-semibold text-surface-700 mb-2 flex items-center gap-1">
                            <RouteIcon size={12} /> 智能审批路由
                            {aiReviewResult.smart_routing.auto_approve && (
                              <span className="ml-1 text-[10px] px-1.5 py-0.5 rounded bg-compliance-100 text-compliance-700">
                                自动通过
                              </span>
                            )}
                            <span className="ml-auto text-[10px] text-surface-500">
                              预计 {aiReviewResult.smart_routing.estimated_sla_hours} 小时
                            </span>
                          </p>
                          {aiReviewResult.smart_routing.approval_chain.length === 0 ? (
                            <p className="text-xs text-surface-400 px-2 py-1.5">不管控 — 自动通过</p>
                          ) : (
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {aiReviewResult.smart_routing.approval_chain.map((step: string, i: number) => (
                                <div key={i} className="flex items-center gap-1.5">
                                  <span className="text-xs px-2 py-1 rounded-lg bg-finance-50 border border-finance-200 text-finance-700">
                                    {step}
                                  </span>
                                  {i < aiReviewResult.smart_routing.approval_chain.length - 1 && (
                                    <ChevronRight size={12} className="text-surface-400" />
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                          <p className="text-[10px] text-surface-500 mt-2">
                            {aiReviewResult.smart_routing.routing_reason}
                          </p>
                        </div>

                        {/* 修复建议 */}
                        {aiReviewResult.rejection_prediction.recommendations.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold text-surface-700 mb-2 flex items-center gap-1">
                              <Zap size={12} className="text-brand-600" /> 修复建议
                            </p>
                            <ul className="space-y-1">
                              {aiReviewResult.rejection_prediction.recommendations.map((r: string, i: number) => (
                                <li key={i} className="text-xs text-surface-700 px-2 py-1 rounded bg-brand-50/50">
                                  • {r}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* 右：批量异常扫描 */}
                  <div className="space-y-4">
                    <div className="glass-card p-5">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <Shield size={16} className="text-finance-600" />
                          <h3 className="text-sm font-semibold text-finance-800">近 7 天批量异常扫描</h3>
                        </div>
                        <button
                          onClick={loadBatchScan}
                          className="text-xs text-brand-600 hover:underline flex items-center gap-1"
                        >
                          <RefreshCw size={11} /> 重新扫描
                        </button>
                      </div>

                      {batchScanLoading ? (
                        <div className="text-xs text-surface-400 py-8 text-center">
                          <Loader2 size={16} className="inline-block animate-spin mr-2" /> 扫描中…
                        </div>
                      ) : batchScan ? (
                        <>
                          {/* 摘要 */}
                          <div className="grid grid-cols-3 gap-2 mb-3">
                            <div className="p-2 rounded-lg bg-surface-50 text-center">
                              <p className="text-[10px] text-surface-500">扫描</p>
                              <p className="text-base font-bold text-finance-700 font-mono">{batchScan.scanned_count}</p>
                            </div>
                            <div className="p-2 rounded-lg bg-alert-50 text-center">
                              <p className="text-[10px] text-alert-600">高风险</p>
                              <p className="text-base font-bold text-alert-700 font-mono">{batchScan.high_risk_count}</p>
                            </div>
                            <div className="p-2 rounded-lg bg-warning-50 text-center">
                              <p className="text-[10px] text-warning-600">高频申请人</p>
                              <p className="text-base font-bold text-warning-700 font-mono">{batchScan.high_freq_applicants?.length || 0}</p>
                            </div>
                          </div>

                          {/* 拆单聚类 */}
                          {batchScan.split_clusters?.length > 0 ? (
                            <div className="space-y-2">
                              <p className="text-xs font-semibold text-alert-700">⚠ 拆单嫌疑聚类（Top {batchScan.split_clusters.length}）</p>
                              {batchScan.split_clusters.slice(0, 5).map((c: any, i: number) => (
                                <div key={i} className="p-2.5 rounded-lg bg-alert-50/50 border border-alert-200">
                                  <div className="flex items-center gap-2">
                                    <span className="text-[10px] font-mono text-surface-500">{c.applicant_id}</span>
                                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-100 text-surface-600">{c.l3_code}</span>
                                    <span className="ml-auto text-xs font-mono font-semibold text-alert-700">
                                      ¥{c.total_amount.toLocaleString()}
                                    </span>
                                  </div>
                                  <p className="text-[10px] text-surface-600 mt-1">
                                    {c.expense_count} 笔，相似金额 {c.expense_ids.length} 笔，平均 ¥{c.avg_amount.toFixed(0)}
                                  </p>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="p-4 text-center text-xs text-compliance-700 bg-compliance-50/50 rounded-lg">
                              ✓ 未发现拆单嫌疑
                            </div>
                          )}

                          {/* 高频申请人 */}
                          {batchScan.high_freq_applicants?.length > 0 && (
                            <div className="mt-3">
                              <p className="text-xs font-semibold text-warning-700 mb-2">高频报销人（Top {batchScan.high_freq_applicants.length}）</p>
                              <div className="space-y-1">
                                {batchScan.high_freq_applicants.map((a: any, i: number) => (
                                  <div key={i} className="flex items-center justify-between px-2.5 py-1.5 rounded bg-warning-50/50">
                                    <span className="text-xs text-surface-700 font-mono">{a.applicant_id}</span>
                                    <span className="text-xs font-mono font-semibold text-warning-700">{a.count} 笔</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="text-xs text-surface-400 py-6 text-center">暂无数据</div>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Effect evaluation modal */}
      {showEffectModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowEffectModal(false)}>
          <div className="bg-white rounded-2xl p-6 shadow-xl max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-finance-800 mb-4">报销效果评估</h3>
            <p className="text-sm text-surface-500 mb-4">报销单号: {effectExpenseId}</p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">预期效果</label>
                <textarea
                  value={effectForm.expected_outcome}
                  onChange={e => setEffectForm(f => ({ ...f, expected_outcome: e.target.value }))}
                  placeholder="请描述预期效果"
                  className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">实际效果</label>
                <textarea
                  value={effectForm.actual_outcome}
                  onChange={e => setEffectForm(f => ({ ...f, actual_outcome: e.target.value }))}
                  placeholder="请描述实际效果"
                  className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  rows={2}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">效果评分 (1-5)</label>
                <div className="flex gap-2">
                  {[1, 2, 3, 4, 5].map(score => (
                    <button
                      key={score}
                      onClick={() => setEffectForm(f => ({ ...f, effect_score: score }))}
                      className={clsx(
                        'w-10 h-10 rounded-xl text-sm font-bold transition-colors',
                        effectForm.effect_score === score
                          ? 'bg-finance-600 text-white'
                          : 'bg-surface-50 text-surface-600 border border-surface-200 hover:bg-finance-50'
                      )}
                    >
                      {score}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="follow_up"
                  checked={effectForm.follow_up_required}
                  onChange={e => setEffectForm(f => ({ ...f, follow_up_required: e.target.checked }))}
                  className="rounded border-surface-300 text-finance-600 focus:ring-finance-500"
                />
                <label htmlFor="follow_up" className="text-sm text-surface-600">需要后续跟进</label>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button className="btn-secondary" onClick={() => setShowEffectModal(false)}>取消</button>
              <button className="btn-primary" onClick={handleEvaluateEffect}>提交评估</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
