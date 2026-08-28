import { useState, useEffect, useMemo, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  Wallet,
  ChevronDown,
  ChevronRight,
  ArrowRightLeft,
  Unlock,
  Lock,
  TreePine,
  Grid3X3,
  Layers,
  X,
  Filter,
  TrendingUp,
  TrendingDown,
  Activity,
  Heart,
  Loader2,
  AlertTriangle,
  Brain,
  Sparkles,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { clsx } from 'clsx';
import type { BudgetItem, BudgetCategory, QuadrantType } from '../types';
import { budgetApi } from '../services/api';
import { useAppStore } from '../store';
import Pagination from '../components/Pagination';
import { AIViewPanel, ViewToggle } from '../components/ai';
import HealthScoreRadar from '../components/budget/HealthScoreRadar';
import HealthScoreGauge from '../components/budget/HealthScoreGauge';
import TransferSimulator from '../components/budget/TransferSimulator';
import RootCauseDrillDown, { type RootCauseDrill } from '../components/budget/RootCauseDrillDown';
import ProactiveSuggestionPanel, { type SuggestionsResponse } from '../components/budget/ProactiveSuggestionPanel';
import BusinessLinkagePanel, { type BusinessLinkage } from '../components/budget/BusinessLinkagePanel';

const TABS = ['预算项目', '科目体系', 'A/B分类', '象限视图', '调拨管理', '健康度', '调拨模拟', '预算认知', 'B→A预判'] as const;

const CONTROL_TAG_MAP: Record<string, { label: string; cls: string }> = {
  strong: { label: '强管控', cls: 'badge-red' },
  weak: { label: '中心弱管控', cls: 'badge-amber' },
  combo: { label: '组合管控', cls: 'badge-blue' },
  none: { label: '不管控', cls: 'badge-green' },
};

const QUADRANT_COLORS: Record<QuadrantType, { bg: string; border: string; text: string; icon: string }> = {
  '发展': { bg: 'bg-compliance-50', border: 'border-compliance-200', text: 'text-compliance-700', icon: '📈' },
  '收缩': { bg: 'bg-alert-50', border: 'border-alert-200', text: 'text-alert-700', icon: '📉' },
  '稳定': { bg: 'bg-brand-50', border: 'border-brand-200', text: 'text-brand-700', icon: '⚖️' },
  '探索': { bg: 'bg-purple-50', border: 'border-purple-200', text: 'text-purple-700', icon: '🔬' },
};

function formatAmount(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '¥ 0';
  if (n >= 10000) return `¥ ${(n / 10000).toFixed(1)}万`;
  return `¥ ${n.toLocaleString()}`;
}

function getExecutionRate(item: BudgetItem): number {
  if (item.annual_amount === 0) return 0;
  return Math.round((item.used_amount / item.annual_amount) * 100);
}

function getStatusBadge(rate: number) {
  if (rate >= 90) return <span className="badge-red">超额</span>;
  if (rate >= 70) return <span className="badge-amber">偏高</span>;
  if (rate >= 30) return <span className="badge-green">正常</span>;
  return <span className="badge-blue">偏低</span>;
}

export default function BudgetPage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('预算项目');
  const [healthPeriod, setHealthPeriod] = useState<string>(new Date().toISOString().slice(0, 7));
  const [healthLoading, setHealthLoading] = useState<boolean>(false);
  const [healthScore, setHealthScore] = useState<any>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [expandedSubjects, setExpandedSubjects] = useState<Set<string>>(new Set());
  const [subjects, setSubjects] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showGrantModal, setShowGrantModal] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any | null>(null);
  const [filterLevel, setFilterLevel] = useState('L1');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize] = useState(10);
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [filterQuadrant, setFilterQuadrant] = useState<string>('');
  const [filterBudgetStatus, setFilterBudgetStatus] = useState<string>('');
  const [viewMode, setViewMode] = useState<'ai' | 'data'>('ai');
  const addToast = useAppStore((s) => s.addToast);
  const aiContext = useAppStore((s) => s.aiContext);
  const location = useLocation();
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const tableRef = useRef<HTMLDivElement>(null);

  // Handle deep link from Dashboard
  useEffect(() => {
    const state = location.state as { highlight?: string; fromDashboard?: boolean } | null;
    if (state?.highlight) {
      setHighlightId(state.highlight);
    }
  }, [location.state]);

  // B→A 转换弹窗
  const [showB2AModal, setShowB2AModal] = useState(false);
  const [b2aForm, setB2aForm] = useState({ budget_id: '', milestone_evidence: '', amount: 0 });
  // v12.0: B→A 转换预览（三维度验证结果）
  const [b2aPreview, setB2aPreview] = useState<any>(null);
  const [b2aPreviewLoading, setB2aPreviewLoading] = useState(false);

  // 释放额度弹窗
  const [showReleaseModal, setShowReleaseModal] = useState(false);
  const [releaseForm, setReleaseForm] = useState({ budget_id: '', amount: 0, reason: '' });

  // 调拨管理
  const [transfers, setTransfers] = useState<any[]>([]);
  const [filterTransferStatus, setFilterTransferStatus] = useState<string>('');
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [transferForm, setTransferForm] = useState({ from_budget_id: '', to_budget_id: '', amount: 0 });
  // v12.0: 调拨沙盘推演结果
  const [transferSandbox, setTransferSandbox] = useState<any>(null);
  const [transferSandboxLoading, setTransferSandboxLoading] = useState(false);

  // ── Module E.2：预算认知状态 ──
  const [cognitiveSubTab, setCognitiveSubTab] = useState<'root-cause' | 'suggestions' | 'linkage'>('root-cause');
  const [rootCause, setRootCause] = useState<RootCauseDrill | null>(null);
  const [rootCauseLoading, setRootCauseLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<SuggestionsResponse | null>(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [linkage, setLinkage] = useState<BusinessLinkage | null>(null);
  const [linkageLoading, setLinkageLoading] = useState(false);
  const [selectedBudgetId, setSelectedBudgetId] = useState<string>('');

  const fetchData = async () => {
    try {
      const [subjectsRes, itemsRes] = await Promise.all([
        budgetApi.getSubjects({}),
        budgetApi.getItems({ page: currentPage, page_size: pageSize }),
      ]);
      setSubjects(subjectsRes.data || []);
      const itemsData = Array.isArray(itemsRes.data) ? itemsRes.data : [];
      setItems(itemsData);
      if (itemsRes.total !== undefined) {
        setTotalPages(Math.max(1, Math.ceil(itemsRes.total / pageSize)));
      }
    } catch (error: any) {
      addToast({ type: 'error', title: '获取预算数据失败', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [currentPage]);

  useEffect(() => {
    if (activeTab === '调拨管理') {
      fetchTransfers(filterTransferStatus || undefined);
    }
    if (activeTab === '健康度') {
      fetchHealthScore(healthPeriod);
    }
    if (activeTab === '预算认知') {
      if (cognitiveSubTab === 'suggestions' && !suggestions && !suggestionsLoading) {
        fetchSuggestions();
      }
      if (cognitiveSubTab === 'linkage' && !linkage && !linkageLoading) {
        fetchLinkage();
      }
    }
    if (activeTab === 'B→A预判' && !b2aDashboard && !b2aDashboardLoading) {
      fetchB2aDashboard();
    }
  }, [activeTab, cognitiveSubTab]);

  // v12.1: 阶段 2 — B→A 智能预判数据加载
  const [b2aDashboard, setB2aDashboard] = useState<any>(null);
  const [b2aDashboardLoading, setB2aDashboardLoading] = useState(false);
  const [b2aPredictResult, setB2aPredictResult] = useState<any>(null);
  const [b2aPredictLoading, setB2aPredictLoading] = useState(false);
  const [b2aSelectedBudgetId, setB2aSelectedBudgetId] = useState<string>('');

  const fetchB2aDashboard = async () => {
    setB2aDashboardLoading(true);
    try {
      const res = await budgetApi.b2aRiskDashboard(10);
      if (res.success) setB2aDashboard(res.data);
    } catch (error) {
      console.error('Failed to fetch B→A risk dashboard:', error);
    } finally {
      setB2aDashboardLoading(false);
    }
  };

  const handleB2aPredict = async (budgetId: string) => {
    if (!budgetId) return;
    setB2aPredictLoading(true);
    setB2aPredictResult(null);
    setB2aSelectedBudgetId(budgetId);
    try {
      const res = await budgetApi.b2aPredict(budgetId);
      if (res.success) setB2aPredictResult(res.data);
    } catch (error) {
      console.error('B→A predict failed:', error);
    } finally {
      setB2aPredictLoading(false);
    }
  };

  // ── Module E.2：认知数据加载 ──
  const fetchRootCause = async (budgetId: string) => {
    if (!budgetId) return;
    setRootCauseLoading(true);
    setSelectedBudgetId(budgetId);
    try {
      const res: any = await budgetApi.getRootCause(budgetId);
      if (res?.success && res.data) {
        setRootCause(res.data);
      } else if (res?.data) {
        setRootCause(res.data);
      } else {
        setRootCause(null);
      }
    } catch (error: any) {
      addToast({ type: 'error', title: '根因分析失败', message: error?.message || '未知错误' });
      setRootCause(null);
    } finally {
      setRootCauseLoading(false);
    }
  };

  const fetchSuggestions = async () => {
    setSuggestionsLoading(true);
    try {
      const res: any = await budgetApi.getProactiveSuggestions();
      if (res?.success && res.data) {
        setSuggestions(res.data);
      } else if (res?.data) {
        setSuggestions(res.data);
      } else {
        setSuggestions(null);
      }
    } catch (error: any) {
      addToast({ type: 'error', title: '主动建议加载失败', message: error?.message || '未知错误' });
      setSuggestions(null);
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const fetchLinkage = async () => {
    setLinkageLoading(true);
    try {
      const res: any = await budgetApi.getBusinessLinkage();
      if (res?.success && res.data) {
        setLinkage(res.data);
      } else if (res?.data) {
        setLinkage(res.data);
      } else {
        setLinkage(null);
      }
    } catch (error: any) {
      addToast({ type: 'error', title: '业务联动加载失败', message: error?.message || '未知错误' });
      setLinkage(null);
    } finally {
      setLinkageLoading(false);
    }
  };

  // 数据加载完成后默认选中第一个有问题的预算
  useEffect(() => {
    if (items.length > 0 && !selectedBudgetId) {
      const problemItem = items.find((b: any) => {
        const a = Number(b.annual_amount) || 0;
        const u = Number(b.used_amount) || 0;
        if (a <= 0) return false;
        const r = u / a;
        return r >= 0.9 || r < 0.3;
      });
      setSelectedBudgetId((problemItem || items[0]).budget_id);
    }
  }, [items, selectedBudgetId]);

  useEffect(() => {
    if (selectedBudgetId && activeTab === '预算认知' && cognitiveSubTab === 'root-cause') {
      fetchRootCause(selectedBudgetId);
    }
  }, [selectedBudgetId, activeTab, cognitiveSubTab]);

  const fetchHealthScore = async (period: string) => {
    setHealthLoading(true);
    try {
      const res: any = await budgetApi.getHealthScore(period);
      if (res?.success && res.data) {
        setHealthScore(res.data);
      } else if (res?.data) {
        setHealthScore(res.data);
      }
    } catch (error: any) {
      addToast({ type: 'error', title: '获取健康度失败', message: error?.message || '未知错误' });
      setHealthScore(null);
    } finally {
      setHealthLoading(false);
    }
  };

  const handleCreateItem = async (data: Partial<BudgetItem>) => {
    try {
      await budgetApi.createItem(data);
      addToast({ type: 'success', title: '操作成功', message: '预算项目已创建' });
      await fetchData();
      setShowCreateModal(false);
    } catch (error: any) {
      addToast({ type: 'error', title: '创建预算失败', message: error.message });
    }
  };

  const handleGrantA = async (budgetId: string, amount?: number) => {
    try {
      await budgetApi.grantA(budgetId, amount ? { amount } : undefined);
      addToast({ type: 'success', title: '操作成功', message: 'A类授予成功' });
      await fetchData();
      setShowGrantModal(false);
      setSelectedItem(null);
    } catch (error: any) {
      addToast({ type: 'error', title: '授予A类失败', message: error.message });
    }
  };

  const handleGrantB = async (budgetId: string, amount?: number) => {
    try {
      await budgetApi.grantB(budgetId, amount ? { amount } : undefined);
      addToast({ type: 'success', title: '操作成功', message: 'B类授予成功' });
      await fetchData();
      setShowGrantModal(false);
      setSelectedItem(null);
    } catch (error: any) {
      addToast({ type: 'error', title: '授予B类失败', message: error.message });
    }
  };

  const handleB2AConvert = async (budgetId: string, data: { milestone_evidence: string; amount: number }) => {
    try {
      await budgetApi.b2aConvert(budgetId, data);
      addToast({ type: 'success', title: '操作成功', message: 'B→A转换成功' });
      setShowB2AModal(false);
      setB2aPreview(null);
      await fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: 'B→A转换失败', message: error.message });
    }
  };

  // v12.0: 打开B→A弹窗时自动加载三维度预览
  const handleOpenB2AModal = async (item: BudgetItem) => {
    setB2aForm({ budget_id: item.budget_id, milestone_evidence: '', amount: item.annual_amount || 0 });
    setB2aPreview(null);
    setShowB2AModal(true);
    setB2aPreviewLoading(true);
    try {
      const res = await budgetApi.b2aPreview(item.budget_id);
      setB2aPreview(res.data || res);
    } catch (e: any) {
      // 预览失败不影响主流程
      setB2aPreview({ error: e?.message || '预览加载失败' });
    } finally {
      setB2aPreviewLoading(false);
    }
  };

  // v12.0: 调拨沙盘推演（执行率/预警/方向评分预测）
  const handleSimulateTransfer = async () => {
    if (!transferForm.from_budget_id || !transferForm.to_budget_id || transferForm.amount <= 0) {
      setTransferSandbox(null);
      return;
    }
    setTransferSandboxLoading(true);
    try {
      const res = await budgetApi.simulateTransfer(
        transferForm.from_budget_id,
        transferForm.to_budget_id,
        transferForm.amount
      );
      setTransferSandbox(res.data || res);
    } catch (e: any) {
      setTransferSandbox({ error: e?.message || '沙盘推演失败' });
    } finally {
      setTransferSandboxLoading(false);
    }
  };

  // 打开调拨弹窗时清空沙盘
  const handleOpenTransferModal = () => {
    setTransferForm({ from_budget_id: '', to_budget_id: '', amount: 0 });
    setTransferSandbox(null);
    setShowTransferModal(true);
  };

  const handleRelease = async (budgetId: string, data: { amount: number; reason: string }) => {
    try {
      await budgetApi.release(budgetId, data);
      addToast({ type: 'success', title: '操作成功', message: '额度已释放' });
      await fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: '释放额度失败', message: error.message });
    }
  };

  const handleApprove = async (budgetId: string, data: { approver: string; comment?: string; role: string }) => {
    try {
      await budgetApi.approve(budgetId, data);
      addToast({ type: 'success', title: '操作成功', message: '预算已审批' });
      await fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: '审批失败', message: error.message });
    }
  };

  const fetchTransfers = async (status?: string) => {
    try {
      const params: { status?: string } = {};
      if (status) params.status = status;
      const res = await budgetApi.getTransfers(params);
      setTransfers(res.data || []);
    } catch (error: any) {
      addToast({ type: 'error', title: '获取调拨列表失败', message: error.message });
    }
  };

  const handleCreateTransfer = async () => {
    try {
      await budgetApi.createTransfer(transferForm);
      addToast({ type: 'success', title: '操作成功', message: '调拨请求已创建' });
      setShowTransferModal(false);
      setTransferForm({ from_budget_id: '', to_budget_id: '', amount: 0 });
      await fetchTransfers(filterTransferStatus);
    } catch (error: any) {
      addToast({ type: 'error', title: '创建调拨失败', message: error.message });
    }
  };

  const handleApproveTransfer = async (transferId: string) => {
    try {
      await budgetApi.approveTransfer(transferId, { approved_by: '当前用户' });
      addToast({ type: 'success', title: '操作成功', message: '调拨已审批' });
      await fetchTransfers(filterTransferStatus);
    } catch (error: any) {
      addToast({ type: 'error', title: '审批失败', message: error.message });
    }
  };

  const handleExecuteTransfer = async (transferId: string) => {
    try {
      await budgetApi.executeTransfer(transferId, { approved_by: '当前用户' });
      addToast({ type: 'success', title: '操作成功', message: '调拨已执行' });
      await fetchTransfers(filterTransferStatus);
    } catch (error: any) {
      addToast({ type: 'error', title: '执行失败', message: error.message });
    }
  };

  const toggleSubject = (code: string) => {
    setExpandedSubjects(prev => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  // AI insights computed from budget data — MUST be before any early return
  const budgetAIInsights = useMemo(() => {
    if (items.length === 0) return { insights: [], healthScore: 100, overBudget: [], underUtilized: [], summary: '暂无预算数据' };

    const insights: { priority: 'critical' | 'attention' | 'info'; title: string; analysis: string; suggestion: string }[] = [];
    const overBudget = items.filter((b: BudgetItem) => getExecutionRate(b) >= 90);
    const underUtilized = items.filter((b: BudgetItem) => b.annual_amount > 0 && getExecutionRate(b) < 30);

    // Health score
    const penalty = items.length > 0
      ? items.reduce((sum: number, b: BudgetItem) => {
        const rate = getExecutionRate(b);
        if (rate >= 90) return sum + 20;
        if (rate < 30) return sum + 10;
        return sum;
      }, 0) / items.length * 10
      : 0;
    const healthScore = Math.max(0, Math.min(100, Math.round(100 - penalty)));

    // Over-budget items
    overBudget.forEach((item: BudgetItem) => {
      const rate = getExecutionRate(item);
      insights.push({
        priority: 'critical',
        title: `${item.description} 预算超支`,
        analysis: `执行率 ${rate}%，已使用 ${formatAmount(item.used_amount)} / ${formatAmount(item.annual_amount)}。存在超额支出风险，可能导致后续业务资金不足。`,
        suggestion: `建议立即冻结该预算项的新增支出申请，并审查已发生费用的合理性。如为季度末集中报销，建议加强事前审批流程。`,
      });
    });

    // Under-utilized items
    underUtilized.forEach((item: BudgetItem) => {
      const rate = getExecutionRate(item);
      insights.push({
        priority: 'info',
        title: `${item.description} 预算利用率偏低`,
        analysis: `执行率仅 ${rate}%，已使用 ${formatAmount(item.used_amount)} / ${formatAmount(item.annual_amount)}。大量预算额度闲置，影响资金使用效率。`,
        suggestion: `建议评估是否需要调拨部分额度至其他高需求预算项，或在下次预算编制时适当降低该项目的预算额度。`,
      });
    });

    // Budget structure analysis
    const totalBudget = items.reduce((s: number, b: BudgetItem) => s + b.annual_amount, 0);
    const aTotal = items.filter((b: BudgetItem) => b.budget_category === 'A').reduce((s: number, b: BudgetItem) => s + b.annual_amount, 0);
    const aRatio = totalBudget > 0 ? Math.round((aTotal / totalBudget) * 100) : 0;
    insights.push({
      priority: 'attention',
      title: '预算结构分析',
      analysis: `A类预算占比 ${aRatio}%，当前整体健康度 ${healthScore} 分。${overBudget.length > 0 ? `${overBudget.length} 个预算项超预算需要关注。` : ''}`,
      suggestion: aRatio > 60
        ? '建议适当增加B类弹性预算比例，提高预算管理的灵活性。关注A类预算的执行效率，避免刚性支出浪费。'
        : '预算结构相对合理，保持当前A/B比例。建议重点关注执行率异常的预算项。',
    });

    return { insights, healthScore, overBudget, underUtilized, summary: `共 ${items.length} 个预算项目，${overBudget.length} 个超预算，${underUtilized.length} 个利用率偏低` };
  }, [items]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-surface-400">加载中...</div>
      </div>
    );
  }

  const totalBudget = items.reduce((s: number, b: BudgetItem) => s + b.annual_amount, 0);
  const aTotal = items.filter((b: BudgetItem) => b.budget_category === 'A').reduce((s: number, b: BudgetItem) => s + b.annual_amount, 0);
  const bTotal = items.filter((b: BudgetItem) => b.budget_category === 'B').reduce((s: number, b: BudgetItem) => s + b.annual_amount, 0);
  const avgRate = items.length > 0 ? Math.round(items.reduce((s: number, b: BudgetItem) => s + getExecutionRate(b), 0) / items.length) : 0;

  const filteredItems = items.filter((item: BudgetItem) => {
    if (filterCategory && item.budget_category !== filterCategory) return false;
    if (filterQuadrant && item.quadrant !== filterQuadrant) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-finance-800 font-display">预算管理</h1>
          <p className="text-sm text-surface-400 mt-1">预算科目体系、A/B分类管理与象限视图</p>
        </div>
        <ViewToggle mode={viewMode} onToggle={setViewMode} />
      </div>

      {/* AI View */}
      <AnimatePresence>
        {viewMode === 'ai' && (
          <motion.div
            key="budget-ai-view"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.2 }}
          >
            <div className="glass-card p-6">
              {/* AI Context Source */}
              {aiContext && (
                <div className="flex items-center gap-2 mb-3 pb-3 border-b border-surface-100">
                  <div className="flex items-center gap-1.5 text-[10px] text-surface-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-finance-400" />
                    此分析基于你的 Dashboard 工作清单 · 最后更新于 {new Date(aiContext.lastUpdate).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              )}

              <AIViewPanel
                title="预算 AI 分析"
                summary={budgetAIInsights.summary}
                score={{ value: budgetAIInsights.healthScore, label: '预算健康度' }}
                insights={budgetAIInsights.insights}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: '总预算', value: formatAmount(totalBudget), gradient: 'from-finance-500 to-finance-700' },
          { label: 'A类占比', value: totalBudget > 0 ? `${Math.round((aTotal / totalBudget) * 100)}%` : '0%', gradient: 'from-brand-500 to-finance-600' },
          { label: 'B类占比', value: totalBudget > 0 ? `${Math.round((bTotal / totalBudget) * 100)}%` : '0%', gradient: 'from-warning-500 to-alert-500' },
          { label: '平均执行率', value: `${avgRate}%`, gradient: 'from-compliance-500 to-health-600' },
        ].map(card => (
          <div key={card.label} className="glass-card p-5">
            <p className="metric-label mb-2">{card.label}</p>
            <p className="metric-value">
              <span className={`bg-gradient-to-r ${card.gradient} bg-clip-text text-transparent`}>
                {card.value}
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
                  layoutId="budgetTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === '预算项目' && (
              <motion.div
                key="items"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="flex flex-wrap items-center gap-3 mb-4 p-3 rounded-xl bg-surface-50/50 border border-surface-200/60">
                  <Filter size={14} className="text-surface-400" />
                  <select
                    value={filterCategory}
                    onChange={e => { setFilterCategory(e.target.value); setCurrentPage(1); }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value="">全部类别</option>
                    <option value="A">A类</option>
                    <option value="B">B类</option>
                  </select>
                  <select
                    value={filterQuadrant}
                    onChange={e => { setFilterQuadrant(e.target.value); setCurrentPage(1); }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value="">全部象限</option>
                    <option value="发展">发展</option>
                    <option value="收缩">收缩</option>
                    <option value="稳定">稳定</option>
                    <option value="探索">探索</option>
                  </select>
                  <select
                    value={filterBudgetStatus}
                    onChange={e => { setFilterBudgetStatus(e.target.value); setCurrentPage(1); }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value="">全部状态</option>
                    <option value="draft">编制中</option>
                    <option value="pending_approval">待审批</option>
                    <option value="approved">已批准</option>
                    <option value="active">执行中</option>
                    <option value="closed">已关闭</option>
                  </select>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-surface-200/60">
                        <th className="text-left py-3 px-3 metric-label">预算ID</th>
                        <th className="text-left py-3 px-3 metric-label">名称</th>
                        <th className="text-left py-3 px-3 metric-label">L1科目</th>
                        <th className="text-left py-3 px-3 metric-label">A/B类别</th>
                        <th className="text-left py-3 px-3 metric-label">象限</th>
                        <th className="text-right py-3 px-3 metric-label">年度预算</th>
                        <th className="text-right py-3 px-3 metric-label">已用额度</th>
                        <th className="text-center py-3 px-3 metric-label">执行率</th>
                        <th className="text-center py-3 px-3 metric-label">状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredItems.map((item: BudgetItem, idx: number) => {
                        const rate = getExecutionRate(item);
                        const isExpanded = expandedRow === item.budget_id;
                        return (
                          <motion.tr
                            key={item.budget_id ?? idx}
                            className="border-b border-surface-100 hover:bg-finance-50/30 cursor-pointer transition-colors"
                            onClick={() => setExpandedRow(isExpanded ? null : item.budget_id)}
                            layout
                          >
                            <td className="py-3 px-3 font-mono text-xs text-finance-700">{item.budget_id}</td>
                            <td className="py-3 px-3 font-medium text-surface-800">{item.description}</td>
                            <td className="py-3 px-3 text-surface-500">{item.l1_code}</td>
                            <td className="py-3 px-3">
                              <span className={item.budget_category === 'A' ? 'badge-blue' : 'badge-amber'}>
                                {item.budget_category}类
                              </span>
                            </td>
                            <td className="py-3 px-3">
                              {item.quadrant && QUADRANT_COLORS[item.quadrant] ? (
                                <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium', QUADRANT_COLORS[item.quadrant].bg, QUADRANT_COLORS[item.quadrant].text)}>
                                  {QUADRANT_COLORS[item.quadrant].icon} {item.quadrant}
                                </span>
                              ) : (
                                <span className="text-gray-400 text-xs">未分配</span>
                              )}
                            </td>
                            <td className="py-3 px-3 text-right font-mono">{formatAmount(item.annual_amount)}</td>
                            <td className="py-3 px-3 text-right font-mono">{formatAmount(item.used_amount)}</td>
                            <td className="py-3 px-3">
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-1.5 bg-surface-100 rounded-full overflow-hidden">
                                  <div
                                    className={clsx(
                                      'h-full rounded-full transition-all',
                                      rate >= 90 ? 'bg-alert-500' : rate >= 70 ? 'bg-warning-500' : 'bg-compliance-500'
                                    )}
                                    style={{ width: `${Math.min(rate, 100)}%` }}
                                  />
                                </div>
                                <span className="text-xs font-mono w-8 text-right">{rate}%</span>
                              </div>
                            </td>
                            <td className="py-3 px-3 text-center">{getStatusBadge(rate)}</td>
                          </motion.tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {expandedRow && (() => {
                  const item = items.find((b: BudgetItem) => b.budget_id === expandedRow);
                  if (!item) return null;
                  return (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-4 p-4 bg-finance-50/50 rounded-xl border border-finance-100"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="font-semibold text-finance-800">{item.description} - 详情</h4>
                        <div className="flex gap-2">
                          <button
                            className="btn-primary text-xs px-3 py-1.5"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (item.budget_category === 'A') {
                                handleGrantA(item.budget_id);
                              } else {
                                handleGrantB(item.budget_id);
                              }
                            }}
                          >
                            <Lock size={12} /> 授予{item.budget_category === 'A' ? 'A' : 'B'}类
                          </button>
                          {item.budget_category === 'B' && (
                            <button
                              className="btn-secondary text-xs px-3 py-1.5"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleOpenB2AModal(item);
                              }}
                            >
                              <ArrowRightLeft size={12} /> B→A转换
                            </button>
                          )}
                          <button
                            className="btn-secondary text-xs px-3 py-1.5"
                            onClick={(e) => {
                              e.stopPropagation();
                              setReleaseForm({ budget_id: item.budget_id, amount: item.available_amount, reason: '' });
                              setShowReleaseModal(true);
                            }}
                          >
                            <Unlock size={12} /> 释放额度
                          </button>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                        <div><span className="text-surface-400">已授予:</span> <span className="font-mono">{formatAmount(item.granted_amount)}</span></div>
                        <div><span className="text-surface-400">已冻结:</span> <span className="font-mono">{formatAmount(item.frozen_amount)}</span></div>
                        <div><span className="text-surface-400">可用额度:</span> <span className="font-mono text-compliance-600">{formatAmount(item.available_amount)}</span></div>
                        <div><span className="text-surface-400">组织:</span> <span className="font-mono">{item.org_id}</span></div>
                      </div>
                    </motion.div>
                  );
                })()}
                <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} pageSize={pageSize} />
              </motion.div>
            )}

            {activeTab === '科目体系' && (
              <motion.div
                key="subjects"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="space-y-1">
                  {subjects.map((subject: any) => {
                    const l1Expanded = expandedSubjects.has(subject.code);
                    return (
                      <div key={subject.code}>
                        <button
                          onClick={() => toggleSubject(subject.code)}
                          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg hover:bg-finance-50/50 transition-colors text-left"
                        >
                          {l1Expanded ? <ChevronDown size={14} className="text-surface-400" /> : <ChevronRight size={14} className="text-surface-400" />}
                          <TreePine size={14} className="text-finance-600" />
                          <span className="font-medium text-surface-800">{subject.code}</span>
                          <span className="text-surface-600">{subject.name}</span>
                        </button>
                        <AnimatePresence>
                          {l1Expanded && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              className="ml-6 space-y-0.5"
                            >
                              {(subject.children || []).map((l2Item: any) => {
                                const l2Expanded = expandedSubjects.has(l2Item.code);
                                return (
                                  <div key={l2Item.code}>
                                    <button
                                      onClick={() => toggleSubject(l2Item.code)}
                                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-brand-50/50 transition-colors text-left"
                                    >
                                      {l2Expanded ? <ChevronDown size={12} className="text-surface-400" /> : <ChevronRight size={12} className="text-surface-400" />}
                                      <Layers size={12} className="text-brand-500" />
                                      <span className="text-sm text-surface-600">{l2Item.code}</span>
                                      <span className="text-sm text-surface-700">{l2Item.name}</span>
                                    </button>
                                    <AnimatePresence>
                                      {l2Expanded && (
                                        <motion.div
                                          initial={{ opacity: 0, height: 0 }}
                                          animate={{ opacity: 1, height: 'auto' }}
                                          exit={{ opacity: 0, height: 0 }}
                                          className="ml-6 space-y-0.5"
                                        >
                                          {(l2Item.children || []).map((l3Item: any) => (
                                            <div
                                              key={l3Item.code}
                                              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-50/50"
                                            >
                                              <span className="text-xs text-surface-400">{l3Item.code}</span>
                                              <span className="text-sm text-surface-600">{l3Item.name}</span>
                                              {l3Item.control_tag && CONTROL_TAG_MAP[l3Item.control_tag] && (
                                                <span className={CONTROL_TAG_MAP[l3Item.control_tag].cls}>
                                                  {CONTROL_TAG_MAP[l3Item.control_tag].label}
                                                </span>
                                              )}
                                            </div>
                                          ))}
                                        </motion.div>
                                      )}
                                    </AnimatePresence>
                                  </div>
                                );
                              })}
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {activeTab === 'A/B分类' && (
              <motion.div
                key="ab"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                {/* A/B Classification Pie Chart */}
                <div className="mb-6">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div className="glass-card-static p-5">
                      <h3 className="text-sm font-semibold text-surface-700 mb-3">A/B 预算占比</h3>
                      <ReactECharts
                        option={{
                          tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
                          legend: {
                            orient: 'vertical' as const,
                            right: 10,
                            top: 'center',
                            textStyle: { color: '#64748b', fontSize: 12 },
                          },
                          series: [{
                            type: 'pie' as const,
                            radius: ['40%', '70%'],
                            center: ['40%', '50%'],
                            avoidLabelOverlap: false,
                            label: {
                              show: true,
                              formatter: '{b}\n{d}%',
                              fontSize: 11,
                              color: '#475569',
                            },
                            emphasis: { label: { show: true, fontWeight: 'bold', fontSize: 14 } },
                            data: [
                              {
                                value: aTotal,
                                name: 'A类预算',
                                itemStyle: { color: '#6366f1' },
                              },
                              {
                                value: bTotal,
                                name: 'B类预算',
                                itemStyle: { color: '#f59e0b' },
                              },
                            ],
                          }],
                        }}
                        style={{ height: '240px' }}
                      />
                    </div>
                    <div className="glass-card-static p-5">
                      <h3 className="text-sm font-semibold text-surface-700 mb-3">A/B 执行率对比</h3>
                      <ReactECharts
                        option={{
                          tooltip: { trigger: 'axis' as const },
                          grid: { left: 60, right: 20, bottom: 30, top: 20 },
                          xAxis: {
                            type: 'category' as const,
                            data: ['A类', 'B类'],
                            axisLabel: { color: '#94a3b8', fontSize: 12 },
                            axisLine: { lineStyle: { color: '#e2e8f0' } },
                          },
                          yAxis: {
                            type: 'value' as const,
                            max: 100,
                            axisLabel: { color: '#94a3b8', fontSize: 10, formatter: '{value}%' },
                            splitLine: { lineStyle: { color: '#f1f5f9' } },
                          },
                          series: [
                            {
                              name: '执行率',
                              type: 'bar' as const,
                              barWidth: '40%',
                              data: [
                                {
                                  value: items.filter((b: BudgetItem) => b.budget_category === 'A').length > 0
                                    ? Math.round(items.filter((b: BudgetItem) => b.budget_category === 'A').reduce((s: number, b: BudgetItem) => s + getExecutionRate(b), 0) / items.filter((b: BudgetItem) => b.budget_category === 'A').length)
                                    : 0,
                                  itemStyle: { color: '#6366f1', borderRadius: [4, 4, 0, 0] },
                                },
                                {
                                  value: items.filter((b: BudgetItem) => b.budget_category === 'B').length > 0
                                    ? Math.round(items.filter((b: BudgetItem) => b.budget_category === 'B').reduce((s: number, b: BudgetItem) => s + getExecutionRate(b), 0) / items.filter((b: BudgetItem) => b.budget_category === 'B').length)
                                    : 0,
                                  itemStyle: { color: '#f59e0b', borderRadius: [4, 4, 0, 0] },
                                },
                              ],
                              label: { show: true, position: 'top', formatter: '{c}%', fontSize: 11, color: '#475569' },
                            },
                          ],
                        }}
                        style={{ height: '240px' }}
                      />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {(['A', 'B'] as BudgetCategory[]).map(cat => {
                    const catItems = items.filter((b: BudgetItem) => b.budget_category === cat);
                    const total = catItems.reduce((s: number, b: BudgetItem) => s + b.annual_amount, 0);
                    const used = catItems.reduce((s: number, b: BudgetItem) => s + b.used_amount, 0);
                    return (
                      <div key={cat} className={clsx(
                        'rounded-xl border-2 p-5',
                        cat === 'A' ? 'border-brand-200 bg-brand-50/30' : 'border-warning-200 bg-warning-50/30'
                      )}>
                        <div className="flex items-center gap-3 mb-4">
                          <div className={clsx(
                            'w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold',
                            cat === 'A' ? 'bg-gradient-to-br from-brand-500 to-finance-600' : 'bg-gradient-to-br from-warning-500 to-alert-500'
                          )}>
                            {cat}
                          </div>
                          <div>
                            <h3 className="font-semibold text-surface-800">{cat}类预算</h3>
                            <p className="text-xs text-surface-400">{cat === 'A' ? '战略投入·刚性保障' : '弹性调控·效率优先'}</p>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3 mb-4">
                          <div className="glass-card-static p-3">
                            <p className="metric-label">总额</p>
                            <p className="text-lg font-bold text-surface-800 font-display">{formatAmount(total)}</p>
                          </div>
                          <div className="glass-card-static p-3">
                            <p className="metric-label">已用</p>
                            <p className="text-lg font-bold text-surface-800 font-display">{formatAmount(used)}</p>
                          </div>
                        </div>
                        <div className="space-y-2">
                          {catItems.map((item: BudgetItem) => (
                            <div key={item.budget_id} className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/60">
                              <div>
                                <span className="text-sm font-medium text-surface-700">{item.description}</span>
                                <span className="ml-2 text-xs text-surface-400">{item.budget_id}</span>
                              </div>
                              <span className="text-sm font-mono">{formatAmount(item.annual_amount)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {activeTab === '象限视图' && (
              <motion.div
                key="quadrant"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                {/* Quadrant 2x2 Matrix Visualization */}
                <div className="glass-card-static p-5 mb-6">
                  <h3 className="text-sm font-semibold text-surface-700 mb-4">象限矩阵总览</h3>
                  <div className="relative">
                    {/* Axis labels */}
                    <div className="absolute -left-2 top-1/2 -translate-y-1/2 -rotate-90 text-xs text-surface-400 font-medium whitespace-nowrap">战略重要性 →</div>
                    <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-xs text-surface-400 font-medium whitespace-nowrap">执行紧迫性 →</div>
                    <div className="grid grid-cols-2 gap-3 ml-6 mb-5">
                      {(['发展', '收缩', '稳定', '探索'] as QuadrantType[]).map(q => {
                        const qItems = items.filter((b: BudgetItem) => b.quadrant === q);
                        const total = qItems.reduce((s: number, b: BudgetItem) => s + b.annual_amount, 0);
                        const used = qItems.reduce((s: number, b: BudgetItem) => s + b.used_amount, 0);
                        const rate = total > 0 ? Math.round((used / total) * 100) : 0;
                        const qc = QUADRANT_COLORS[q];
                        return (
                          <div
                            key={q}
                            className={clsx('rounded-xl border-2 p-4 transition-all hover:shadow-md', qc.bg, qc.border)}
                          >
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xl">{qc.icon}</span>
                                <h3 className={clsx('font-bold text-base', qc.text)}>{q}象限</h3>
                              </div>
                              <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium bg-white/60', qc.text)}>
                                {qItems.length} 项
                              </span>
                            </div>
                            <div className="grid grid-cols-2 gap-2 mb-2">
                              <div className="bg-white/50 rounded-lg p-2">
                                <p className="text-[10px] text-surface-400">预算</p>
                                <p className={clsx('text-sm font-bold font-mono', qc.text)}>{formatAmount(total)}</p>
                              </div>
                              <div className="bg-white/50 rounded-lg p-2">
                                <p className="text-[10px] text-surface-400">执行率</p>
                                <p className={clsx('text-sm font-bold font-mono', rate >= 90 ? 'text-alert-600' : rate >= 70 ? 'text-warning-600' : 'text-compliance-600')}>{rate}%</p>
                              </div>
                            </div>
                            <div className="h-1.5 bg-white/40 rounded-full overflow-hidden mb-2">
                              <div
                                className={clsx('h-full rounded-full transition-all', rate >= 90 ? 'bg-alert-400' : rate >= 70 ? 'bg-warning-400' : 'bg-compliance-400')}
                                style={{ width: `${Math.min(rate, 100)}%` }}
                              />
                            </div>
                            <div className="space-y-1 max-h-24 overflow-y-auto">
                              {qItems.slice(0, 4).map((item: BudgetItem) => (
                                <div key={item.budget_id} className="flex items-center justify-between px-2 py-1 rounded bg-white/40 text-xs">
                                  <span className="text-surface-700 truncate max-w-[120px]">{item.description}</span>
                                  <span className={clsx('font-mono ml-1', qc.text)}>{formatAmount(item.annual_amount)}</span>
                                </div>
                              ))}
                              {qItems.length === 0 && (
                                <p className="text-[10px] text-surface-400 text-center py-1">暂无</p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* Detailed quadrant view */}
                <div className="grid grid-cols-2 gap-4">
                  {(['发展', '收缩', '稳定', '探索'] as QuadrantType[]).map(q => {
                    const qItems = items.filter((b: BudgetItem) => b.quadrant === q);
                    const total = qItems.reduce((s: number, b: BudgetItem) => s + b.annual_amount, 0);
                    const qc = QUADRANT_COLORS[q];
                    return (
                      <div key={q} className={clsx('rounded-xl border-2 p-5', qc.bg, qc.border)}>
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-xl">{qc.icon}</span>
                          <h3 className={clsx('font-semibold', qc.text)}>{q}象限</h3>
                        </div>
                        <div className="glass-card-static p-3 mb-3">
                          <p className="metric-label">预算金额</p>
                          <p className={clsx('text-xl font-bold font-display', qc.text)}>{formatAmount(total)}</p>
                        </div>
                        <div className="space-y-1.5">
                          {qItems.map((item: BudgetItem) => (
                            <div key={item.budget_id} className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-white/60 text-sm">
                              <span className="text-surface-700">{item.description}</span>
                              <span className={clsx('font-mono', qc.text)}>{formatAmount(item.annual_amount)}</span>
                            </div>
                          ))}
                          {qItems.length === 0 && (
                            <p className="text-xs text-surface-400 text-center py-3">暂无预算项目</p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {activeTab === '调拨管理' && (
              <motion.div
                key="transfers"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="flex flex-wrap items-center gap-3 mb-4 p-3 rounded-xl bg-surface-50/50 border border-surface-200/60">
                  <Filter size={14} className="text-surface-400" />
                  <select
                    value={filterTransferStatus}
                    onChange={e => {
                      setFilterTransferStatus(e.target.value);
                      fetchTransfers(e.target.value || undefined);
                    }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value="">全部状态</option>
                    <option value="待审批">待审批</option>
                    <option value="已审批">已审批</option>
                    <option value="已执行">已执行</option>
                    <option value="已驳回">已驳回</option>
                    <option value="已取消">已取消</option>
                  </select>
                  <button
                    className="btn-primary text-xs px-3 py-1.5 ml-auto"
                    onClick={handleOpenTransferModal}
                  >
                    <ArrowRightLeft size={12} /> 创建调拨
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-surface-200/60">
                        <th className="text-left py-3 px-3 metric-label">调拨ID</th>
                        <th className="text-left py-3 px-3 metric-label">源预算</th>
                        <th className="text-left py-3 px-3 metric-label">目标预算</th>
                        <th className="text-right py-3 px-3 metric-label">金额</th>
                        <th className="text-center py-3 px-3 metric-label">同象限</th>
                        <th className="text-center py-3 px-3 metric-label">审批要求</th>
                        <th className="text-center py-3 px-3 metric-label">状态</th>
                        <th className="text-center py-3 px-3 metric-label">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {transfers.length === 0 && (
                        <tr>
                          <td colSpan={8} className="text-center py-8 text-surface-400">暂无调拨记录</td>
                        </tr>
                      )}
                      {transfers.map((t: any) => (
                        <tr key={t.transfer_id} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                          <td className="py-3 px-3 font-mono text-xs text-finance-700">{t.transfer_id}</td>
                          <td className="py-3 px-3 text-surface-600">{t.from_budget_id}</td>
                          <td className="py-3 px-3 text-surface-600">{t.to_budget_id}</td>
                          <td className="py-3 px-3 text-right font-mono">{formatAmount(t.amount)}</td>
                          <td className="py-3 px-3 text-center">
                            <span className={t.same_quadrant === '是' ? 'badge-green' : 'badge-amber'}>
                              {t.same_quadrant === '是' ? '同象限' : '跨象限'}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-center text-xs text-surface-500">{t.approval_required}</td>
                          <td className="py-3 px-3 text-center">
                            <span className={
                              t.status === '待审批' ? 'badge-amber' :
                              t.status === '已审批' ? 'badge-blue' :
                              t.status === '已执行' ? 'badge-green' :
                              t.status === '已驳回' ? 'badge-red' : 'badge-blue'
                            }>
                              {t.status}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-center">
                            {t.status === '待审批' && (
                              <button
                                className="btn-primary text-xs px-2 py-1"
                                onClick={() => handleApproveTransfer(t.transfer_id)}
                              >
                                审批
                              </button>
                            )}
                            {t.status === '已审批' && (
                              <button
                                className="btn-secondary text-xs px-2 py-1"
                                onClick={() => handleExecuteTransfer(t.transfer_id)}
                              >
                                执行
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* 健康度（v4.2 新增） */}
            {activeTab === '健康度' && (
              <motion.div
                key="health"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-4"
              >
                <div className="flex items-center gap-3 mb-2">
                  <label className="text-xs text-surface-600">评估期间：</label>
                  <input
                    type="month"
                    value={healthPeriod}
                    onChange={e => {
                      setHealthPeriod(e.target.value);
                      fetchHealthScore(e.target.value);
                    }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20"
                  />
                  <span className="ml-auto text-[11px] text-surface-400">数据驱动 · 5 维度加权</span>
                </div>

                {healthLoading && (
                  <div className="text-center py-12 text-surface-400 text-sm">
                    <div className="inline-block w-6 h-6 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2"></div>
                    正在计算健康度评分…
                  </div>
                )}

                {!healthLoading && !healthScore && (
                  <div className="text-center py-12 text-surface-400 text-sm">
                    <Heart size={24} className="mx-auto mb-2 text-surface-300" />
                    暂无健康度数据，请选择评估期间
                  </div>
                )}

                {!healthLoading && healthScore && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <HealthScoreGauge
                      overallScore={healthScore.overall_score ?? 0}
                      grade={healthScore.grade ?? 'C'}
                      scores={healthScore.dimension_scores ?? {}}
                    />
                    <HealthScoreRadar
                      scores={healthScore.dimension_scores ?? {}}
                    />
                    {healthScore.risk_factors && healthScore.risk_factors.length > 0 && (
                      <div className="lg:col-span-2 bg-white rounded-xl border border-surface-200/60 p-4">
                        <h3 className="text-sm font-semibold text-surface-700 mb-2 flex items-center gap-2">
                          <AlertCircle size={14} className="text-alert-500" />
                          风险因素
                        </h3>
                        <div className="space-y-1.5">
                          {healthScore.risk_factors.map((rf: any, i: number) => (
                            <div key={i} className="flex items-center gap-2 text-xs">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                rf.severity === 'high' ? 'bg-alert-500 text-white' :
                                rf.severity === 'medium' ? 'bg-warning-500 text-white' : 'bg-brand-500 text-white'
                              }`}>
                                {rf.severity === 'high' ? '高' : rf.severity === 'medium' ? '中' : '低'}
                              </span>
                              <span className="text-surface-700">{rf.factor}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {healthScore.recommendations && healthScore.recommendations.length > 0 && (
                      <div className="lg:col-span-2 bg-white rounded-xl border border-surface-200/60 p-4">
                        <h3 className="text-sm font-semibold text-surface-700 mb-2 flex items-center gap-2">
                          <Activity size={14} className="text-brand-500" />
                          AI 改进建议
                        </h3>
                        <ul className="space-y-1.5">
                          {healthScore.recommendations.map((r: string, i: number) => (
                            <li key={i} className="text-xs text-surface-600 flex gap-2">
                              <span className="text-brand-500">▸</span>
                              <span>{r}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            )}

            {/* 调拨模拟（v4.2 新增） */}
            {activeTab === '调拨模拟' && (
              <motion.div
                key="simulate"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <TransferSimulator
                  period={healthPeriod}
                  onMessage={(type, title, message) => addToast({ type, title, message })}
                />
                <div className="mt-4 px-4 py-3 rounded-lg bg-brand-50/40 border border-brand-200/60 text-xs text-brand-700">
                  <strong>使用说明：</strong>选择源/目标预算项并输入金额，提交后将模拟调拨后的执行率变化、触发预警预测和方向合理性评估。草稿会自动保存到浏览器本地，刷新后恢复。
                </div>
              </motion.div>
            )}

            {/* 预算认知（Module E.2：5 层根因下钻 + 主动建议 + 业务联动） */}
            {activeTab === '预算认知' && (
              <motion.div
                key="cognitive"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                <div className="flex items-center justify-between mb-1">
                  <div>
                    <h2 className="text-base font-semibold text-finance-800">预算认知分析</h2>
                    <p className="text-xs text-surface-500 mt-0.5">5 层根因下钻 · 主动建议 · 业务联动</p>
                  </div>
                  <span className="text-[10px] text-surface-400 px-2 py-0.5 rounded bg-finance-50/60 border border-finance-200">
                    AI · 数据驱动
                  </span>
                </div>

                {/* 子 Tabs */}
                <div className="flex border-b border-surface-200/60">
                  {([
                    { key: 'root-cause', label: '5 层根因下钻' },
                    { key: 'suggestions', label: '主动建议面板' },
                    { key: 'linkage', label: '预算-业务联动' },
                  ] as const).map(t => (
                    <button
                      key={t.key}
                      onClick={() => setCognitiveSubTab(t.key)}
                      className={clsx(
                        'px-4 py-2 text-xs font-medium transition-colors relative',
                        cognitiveSubTab === t.key ? 'text-finance-700' : 'text-surface-400 hover:text-surface-600'
                      )}
                    >
                      {t.label}
                      {cognitiveSubTab === t.key && (
                        <motion.div
                          layoutId="budgetCognitiveTab"
                          className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                        />
                      )}
                    </button>
                  ))}
                </div>

                <AnimatePresence mode="wait">
                  {cognitiveSubTab === 'root-cause' && (
                    <motion.div
                      key="root-cause"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.15 }}
                    >
                      <RootCauseDrillDown
                        data={rootCause}
                        budgetOptions={items.map((b: any) => ({
                          budget_id: b.budget_id,
                          description: b.description,
                          rate: b.annual_amount > 0 ? Math.round((b.used_amount / b.annual_amount) * 100) : 0,
                        }))}
                        loading={rootCauseLoading}
                      />
                    </motion.div>
                  )}

                  {cognitiveSubTab === 'suggestions' && (
                    <motion.div
                      key="suggestions"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.15 }}
                    >
                      <ProactiveSuggestionPanel data={suggestions} loading={suggestionsLoading} />
                    </motion.div>
                  )}

                  {cognitiveSubTab === 'linkage' && (
                    <motion.div
                      key="linkage"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.15 }}
                    >
                      <BusinessLinkagePanel data={linkage} loading={linkageLoading} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}

            {/* ── v12.1: 阶段 2 — B→A 智能预判 ─────────── */}
            {activeTab === 'B→A预判' && (
              <motion.div
                key="b2a-predict"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {b2aDashboardLoading ? (
                  <div className="text-center py-12 text-surface-400 text-sm">
                    <Loader2 size={20} className="inline-block animate-spin mr-2" />
                    AI 正在扫描所有 B 类预算…
                  </div>
                ) : b2aDashboard ? (
                  <>
                    {/* 摘要卡片 */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">B 类预算总数</p>
                        <p className="text-lg font-bold text-finance-700 font-mono">
                          {b2aDashboard.summary.total_b_items}
                        </p>
                        <p className="text-[10px] text-surface-500 mt-0.5">
                          总额 {formatAmount(b2aDashboard.summary.total_b_amount)}
                        </p>
                      </div>
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">
                          <CheckCircle2 size={10} className="inline mr-1 text-compliance-600" />
                          可转换
                        </p>
                        <p className="text-lg font-bold text-compliance-700 font-mono">
                          {b2aDashboard.summary.ready_count}
                        </p>
                      </div>
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">
                          <AlertCircle size={10} className="inline mr-1 text-warning-600" />
                          黄色风险
                        </p>
                        <p className="text-lg font-bold text-warning-700 font-mono">
                          {b2aDashboard.summary.yellow_risk_count}
                        </p>
                      </div>
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">
                          <AlertTriangle size={10} className="inline mr-1 text-alert-600" />
                          红色拦截
                        </p>
                        <p className="text-lg font-bold text-alert-700 font-mono">
                          {b2aDashboard.summary.red_blocked_count}
                        </p>
                      </div>
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">扫描时间</p>
                        <p className="text-xs text-surface-600 font-mono">
                          {b2aDashboard.scanned_at ? new Date(b2aDashboard.scanned_at).toLocaleString('zh-CN') : '-'}
                        </p>
                        <button
                          onClick={fetchB2aDashboard}
                          className="text-[10px] text-brand-600 hover:underline mt-1"
                        >
                          重新扫描
                        </button>
                      </div>
                    </div>

                    {/* 双列：可转换 + 高风险 */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      {/* 可转换（高就绪度） */}
                      <div className="glass-card p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <CheckCircle2 size={14} className="text-compliance-600" />
                          <h4 className="text-sm font-semibold text-finance-800">建议立即转换（Top 10）</h4>
                        </div>
                        {b2aDashboard.ready_to_convert.length === 0 ? (
                          <div className="text-xs text-surface-400 py-6 text-center">暂无高就绪度项</div>
                        ) : (
                          <div className="space-y-2">
                            {b2aDashboard.ready_to_convert.map((item: any) => (
                              <button
                                key={item.budget_id}
                                onClick={() => handleB2aPredict(item.budget_id)}
                                className="w-full text-left p-2.5 rounded-lg bg-compliance-50/50 border border-compliance-200 hover:bg-compliance-50 transition-colors"
                              >
                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-[10px] text-surface-500">{item.budget_id}</span>
                                  <span className="font-medium text-xs text-surface-800 truncate flex-1">
                                    {item.budget_name || item.budget_id}
                                  </span>
                                  <span className="px-1.5 py-0.5 rounded bg-compliance-100 text-compliance-700 text-[10px] font-mono font-semibold">
                                    {item.ready_score}
                                  </span>
                                </div>
                                <p className="text-[10px] text-surface-500 mt-1 truncate">
                                  {item.predicted_outcome}
                                </p>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* 高风险（低就绪度） */}
                      <div className="glass-card p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <AlertTriangle size={14} className="text-alert-600" />
                          <h4 className="text-sm font-semibold text-finance-800">高风险项（Top 10）</h4>
                        </div>
                        {b2aDashboard.at_risk.length === 0 ? (
                          <div className="text-xs text-surface-400 py-6 text-center">暂无高风险项</div>
                        ) : (
                          <div className="space-y-2">
                            {b2aDashboard.at_risk.map((item: any) => (
                              <button
                                key={item.budget_id}
                                onClick={() => handleB2aPredict(item.budget_id)}
                                className="w-full text-left p-2.5 rounded-lg bg-alert-50/50 border border-alert-200 hover:bg-alert-50 transition-colors"
                              >
                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-[10px] text-surface-500">{item.budget_id}</span>
                                  <span className="font-medium text-xs text-surface-800 truncate flex-1">
                                    {item.budget_name || item.budget_id}
                                  </span>
                                  <span className={clsx(
                                    'px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold',
                                    item.risk_level === '红色' ? 'bg-alert-100 text-alert-700' : 'bg-warning-100 text-warning-700'
                                  )}>
                                    {item.ready_score}
                                  </span>
                                </div>
                                <p className="text-[10px] text-surface-500 mt-1 truncate">
                                  {item.predicted_outcome}
                                </p>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* 按中心 / L1 聚合 */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="glass-card-static p-4">
                        <h4 className="text-xs font-semibold text-surface-700 mb-3">按中心聚合（平均就绪度）</h4>
                        {Object.keys(b2aDashboard.by_center).length === 0 ? (
                          <div className="text-xs text-surface-400 py-4 text-center">暂无数据</div>
                        ) : (
                          <div className="space-y-2">
                            {Object.entries(b2aDashboard.by_center).map(([cid, v]: any) => (
                              <div key={cid} className="flex items-center gap-2">
                                <span className="text-xs text-surface-700 w-20 truncate">{cid}</span>
                                <div className="flex-1 h-2 bg-surface-100 rounded-full overflow-hidden">
                                  <div
                                    className={clsx(
                                      'h-full rounded-full',
                                      v.avg_score >= 80 ? 'bg-compliance-500' :
                                      v.avg_score >= 60 ? 'bg-warning-500' : 'bg-alert-500'
                                    )}
                                    style={{ width: `${v.avg_score}%` }}
                                  />
                                </div>
                                <span className="text-xs font-mono w-12 text-right">{v.avg_score}</span>
                                <span className="text-[10px] text-surface-500 w-16 text-right">{v.count}项</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="glass-card-static p-4">
                        <h4 className="text-xs font-semibold text-surface-700 mb-3">按 L1 聚合（平均就绪度）</h4>
                        {Object.keys(b2aDashboard.by_l1).length === 0 ? (
                          <div className="text-xs text-surface-400 py-4 text-center">暂无数据</div>
                        ) : (
                          <div className="space-y-2">
                            {Object.entries(b2aDashboard.by_l1).map(([l1, v]: any) => (
                              <div key={l1} className="flex items-center gap-2">
                                <span className="text-xs text-surface-700 w-20 truncate">{l1}</span>
                                <div className="flex-1 h-2 bg-surface-100 rounded-full overflow-hidden">
                                  <div
                                    className={clsx(
                                      'h-full rounded-full',
                                      v.avg_score >= 80 ? 'bg-compliance-500' :
                                      v.avg_score >= 60 ? 'bg-warning-500' : 'bg-alert-500'
                                    )}
                                    style={{ width: `${v.avg_score}%` }}
                                  />
                                </div>
                                <span className="text-xs font-mono w-12 text-right">{v.avg_score}</span>
                                <span className="text-[10px] text-surface-500 w-16 text-right">{v.count}项</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* 单项预判详情 */}
                    {b2aPredictResult && (
                      <div className="glass-card p-5">
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="text-sm font-semibold text-finance-800 flex items-center gap-2">
                            <Brain size={14} /> 预判详情 — {b2aPredictResult.budget_id}
                          </h4>
                          <button
                            onClick={() => { setB2aPredictResult(null); setB2aSelectedBudgetId(''); }}
                            className="text-surface-400 hover:text-surface-600"
                          >
                            <X size={14} />
                          </button>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {/* 评分卡 */}
                          <div className="md:col-span-1 flex flex-col items-center justify-center p-4 rounded-xl bg-gradient-to-br from-finance-50 to-brand-50 border border-finance-200">
                            <p className="text-[10px] text-surface-500 mb-1">转换就绪度</p>
                            <p className={clsx(
                              'text-4xl font-bold font-mono mb-1',
                              b2aPredictResult.risk_level === '蓝色' ? 'text-compliance-700' :
                              b2aPredictResult.risk_level === '黄色' ? 'text-warning-700' : 'text-alert-700'
                            )}>
                              {b2aPredictResult.ready_score}
                            </p>
                            <span className={clsx(
                              'px-2 py-0.5 rounded-full text-[10px] font-semibold',
                              b2aPredictResult.risk_level === '蓝色' ? 'bg-compliance-100 text-compliance-700' :
                              b2aPredictResult.risk_level === '黄色' ? 'bg-warning-100 text-warning-700' : 'bg-alert-100 text-alert-700'
                            )}>
                              {b2aPredictResult.risk_level} 级风险
                            </span>
                            <p className="text-xs text-surface-600 mt-2 text-center">
                              {b2aPredictResult.predicted_outcome}
                            </p>
                          </div>

                          {/* 5 维评分 */}
                          <div className="md:col-span-2 space-y-3">
                            <p className="text-xs font-semibold text-surface-700">5 维评分</p>
                            {Object.entries(b2aPredictResult.dimension_scores || {}).map(([k, v]: any) => {
                              const labelMap: Record<string, string> = {
                                completion: '完成度', time: '时间偏差', cost: '费用偏差', evidence: '证据完整', overdue: '逾期风险',
                              };
                              return (
                                <div key={k}>
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs text-surface-600">{labelMap[k] || k}</span>
                                    <span className="text-xs font-mono font-semibold">{v}</span>
                                  </div>
                                  <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden">
                                    <div
                                      className={clsx(
                                        'h-full rounded-full',
                                        v >= 80 ? 'bg-compliance-500' :
                                        v >= 60 ? 'bg-warning-500' : 'bg-alert-500'
                                      )}
                                      style={{ width: `${v}%` }}
                                    />
                                  </div>
                                </div>
                              );
                            })}
                            <div className="text-[10px] text-surface-500 mt-2 flex items-center gap-3">
                              <span>里程碑：完成 {b2aPredictResult.milestone_summary.completed}/{b2aPredictResult.milestone_summary.total}</span>
                              <span>·</span>
                              <span>逾期 {b2aPredictResult.milestone_summary.overdue}</span>
                              <span>·</span>
                              <span>年度金额 {formatAmount(b2aPredictResult.annual_amount)}</span>
                            </div>
                          </div>
                        </div>

                        {/* 风险因子 */}
                        {b2aPredictResult.risk_factors.length > 0 && (
                          <div className="mt-4">
                            <p className="text-xs font-semibold text-surface-700 mb-2">⚠ 风险因子</p>
                            <div className="space-y-1">
                              {b2aPredictResult.risk_factors.map((rf: any, i: number) => (
                                <div key={i} className={clsx(
                                  'flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs',
                                  rf.severity === '红色' ? 'bg-alert-50 text-alert-700' : 'bg-warning-50 text-warning-700'
                                )}>
                                  <span className="font-semibold">{rf.type}</span>
                                  <span className="text-surface-400">|</span>
                                  <span className="flex-1">{rf.detail}</span>
                                  <span className={clsx(
                                    'px-1.5 py-0.5 rounded text-[10px] font-semibold',
                                    rf.severity === '红色' ? 'bg-alert-200 text-alert-800' : 'bg-warning-200 text-warning-800'
                                  )}>
                                    {rf.severity}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* 修复建议 */}
                        {b2aPredictResult.recommendations.length > 0 && (
                          <div className="mt-4">
                            <p className="text-xs font-semibold text-surface-700 mb-2 flex items-center gap-1">
                              <Sparkles size={12} className="text-brand-600" /> AI 修复建议
                            </p>
                            <ul className="space-y-1">
                              {b2aPredictResult.recommendations.map((r: string, i: number) => (
                                <li key={i} className="flex items-start gap-2 text-xs text-surface-700 px-2 py-1 rounded bg-brand-50/50">
                                  <span className="text-brand-600 font-mono">{i + 1}.</span>
                                  <span>{r}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="glass-card-static p-10 text-center text-surface-400">
                    <Brain size={40} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">暂无 B 类预算数据</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* v12.0: B→A 转换完整流程卡 */}
      <AnimatePresence>
        {showB2AModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => { setShowB2AModal(false); setB2aPreview(null); }}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-finance-800 flex items-center gap-2">
                    <ArrowRightLeft size={18} className="text-finance-600" />
                    B→A 转换流程
                  </h3>
                  <p className="text-xs text-surface-400 mt-0.5">文档 §4.2.3：里程碑验证 → 自动冻结额度 → 状态切换</p>
                </div>
                <button
                  onClick={() => { setShowB2AModal(false); setB2aPreview(null); }}
                  className="text-surface-400 hover:text-surface-600"
                >
                  <X size={18} />
                </button>
              </div>

              {/* 步骤 1: 三维度验证预览 */}
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-5 h-5 rounded-full bg-finance-100 text-finance-700 text-[10px] font-bold flex items-center justify-center">1</span>
                  <span className="text-sm font-semibold text-surface-700">里程碑三维度综合验证</span>
                  {b2aPreviewLoading && <Loader2 size={12} className="animate-spin text-finance-500" />}
                </div>
                {b2aPreview?.error ? (
                  <div className="text-xs text-amber-700 bg-amber-50 rounded-lg p-2">
                    ⚠ 验证服务暂不可用：{b2aPreview.error}（不影响最终转换，但建议人工复核）
                  </div>
                ) : b2aPreview ? (
                  <div className="space-y-2">
                    <div className="grid grid-cols-4 gap-2">
                      {(['时间', '费用', '累计'] as const).map(dim => {
                        const dl = b2aPreview.dimensions?.[dim]?.max_level || '蓝色';
                        return (
                          <div key={dim} className={clsx(
                            'rounded-lg p-2 text-center border',
                            dl === '红色' ? 'bg-alert-50 border-alert-200' :
                            dl === '黄色' ? 'bg-warning-50 border-warning-200' :
                            dl === '橙色' ? 'bg-orange-50 border-orange-200' :
                            'bg-compliance-50 border-compliance-200'
                          )}>
                            <p className="text-[10px] text-surface-500">{dim}维度</p>
                            <p className={clsx(
                              'text-sm font-bold',
                              dl === '红色' ? 'text-alert-700' :
                              dl === '黄色' ? 'text-warning-700' :
                              dl === '橙色' ? 'text-orange-700' :
                              'text-compliance-700'
                            )}>{dl}</p>
                          </div>
                        );
                      })}
                      <div className={clsx(
                        'rounded-lg p-2 text-center border-2',
                        b2aPreview.risk_level === '红色' ? 'bg-alert-100 border-alert-400' :
                        b2aPreview.risk_level === '黄色' ? 'bg-warning-100 border-warning-400' :
                        'bg-compliance-100 border-compliance-400'
                      )}>
                        <p className="text-[10px] text-surface-500">综合</p>
                        <p className={clsx(
                          'text-sm font-bold',
                          b2aPreview.risk_level === '红色' ? 'text-alert-700' :
                          b2aPreview.risk_level === '黄色' ? 'text-warning-700' :
                          'text-compliance-700'
                        )}>{b2aPreview.risk_level}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-surface-600">
                      <span>里程碑：<strong className="text-finance-700">{b2aPreview.completed_milestones}/{b2aPreview.required_milestones}</strong>（至少2个）</span>
                      {b2aPreview.committee_report_required && (
                        <span className="inline-flex items-center gap-1 text-warning-700 bg-warning-50 px-2 py-0.5 rounded-md">
                          <AlertTriangle size={10} /> 需向管委会提交专项报告
                        </span>
                      )}
                    </div>
                    {b2aPreview.block_reasons?.length > 0 && (
                      <div className="text-xs text-alert-700 bg-alert-50 rounded-lg p-2 space-y-1">
                        {b2aPreview.block_reasons.map((r: string, i: number) => (
                          <p key={i}>🚫 {r}</p>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-surface-400">加载验证数据中...</div>
                )}
              </div>

              {/* 步骤 2: 当前 → 转换后 状态对照 */}
              {b2aPreview?.conversion_preview && (
                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-5 h-5 rounded-full bg-finance-100 text-finance-700 text-[10px] font-bold flex items-center justify-center">2</span>
                    <span className="text-sm font-semibold text-surface-700">状态变更预览</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-3">
                      <p className="text-[10px] text-amber-700 font-semibold mb-1">转换前 (B类)</p>
                      <p className="text-xs">类别：<strong>{b2aPreview.conversion_preview.pre_state.category}</strong></p>
                      <p className="text-xs">授予比例：<strong>{b2aPreview.conversion_preview.pre_state.grant_percentage}%</strong></p>
                      <p className="text-xs">已授予：<strong>¥ {b2aPreview.conversion_preview.pre_state.granted_amount.toLocaleString()}</strong></p>
                      <p className="text-xs">状态：<strong>{b2aPreview.conversion_preview.pre_state.status}</strong></p>
                    </div>
                    <div className="rounded-lg border border-compliance-200 bg-compliance-50/40 p-3">
                      <p className="text-[10px] text-compliance-700 font-semibold mb-1">转换后 (A类)</p>
                      <p className="text-xs">类别：<strong>{b2aPreview.conversion_preview.post_state.category}</strong></p>
                      <p className="text-xs">授予比例：<strong>{b2aPreview.conversion_preview.post_state.grant_percentage}%</strong></p>
                      <p className="text-xs">已授予：<strong>¥ {b2aPreview.conversion_preview.post_state.granted_amount.toLocaleString()}</strong></p>
                      <p className="text-xs">状态：<strong>{b2aPreview.conversion_preview.post_state.status}</strong></p>
                    </div>
                  </div>
                </div>
              )}

              {/* 步骤 3: 转换证据输入 */}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-5 h-5 rounded-full bg-finance-100 text-finance-700 text-[10px] font-bold flex items-center justify-center">3</span>
                  <span className="text-sm font-semibold text-surface-700">里程碑证据（提交至管委会）</span>
                </div>
                <textarea
                  value={b2aForm.milestone_evidence}
                  onChange={e => setB2aForm(f => ({ ...f, milestone_evidence: e.target.value }))}
                  rows={3}
                  placeholder="请输入本季度里程碑达成证据（最低10字），例如：Q2 III期临床入组完成率105%，成本在计划内..."
                  className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-none"
                />
              </div>

              <div className="flex gap-3 justify-end mt-5">
                <button
                  onClick={() => { setShowB2AModal(false); setB2aPreview(null); }}
                  className="btn-secondary"
                >
                  取消
                </button>
                <button
                  onClick={async () => {
                    await handleB2AConvert(b2aForm.budget_id, {
                      milestone_evidence: b2aForm.milestone_evidence,
                      amount: b2aForm.amount,
                    });
                  }}
                  disabled={!b2aForm.milestone_evidence.trim() || b2aPreview?.can_convert === false}
                  className={clsx(
                    'btn-primary',
                    (!b2aForm.milestone_evidence.trim() || b2aPreview?.can_convert === false) && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  <ArrowRightLeft size={14} />
                  {b2aPreview?.can_convert === false ? '已被红色风险拦截' : '确认转换（自动冻结额度）'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 释放额度弹窗 */}
      <AnimatePresence>
        {showReleaseModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => setShowReleaseModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-md mx-4"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-finance-800">释放额度</h3>
                <button onClick={() => setShowReleaseModal(false)} className="text-surface-400 hover:text-surface-600"><X size={18} /></button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">释放金额</label>
                  <input
                    type="number"
                    value={releaseForm.amount}
                    onChange={e => setReleaseForm(f => ({ ...f, amount: Number(e.target.value) }))}
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">释放原因 <span className="text-alert-500">*</span></label>
                  <textarea
                    value={releaseForm.reason}
                    onChange={e => setReleaseForm(f => ({ ...f, reason: e.target.value }))}
                    rows={3}
                    placeholder="请输入释放原因..."
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-none"
                  />
                </div>
              </div>
              <div className="flex gap-3 justify-end mt-5">
                <button onClick={() => setShowReleaseModal(false)} className="btn-secondary">取消</button>
                <button
                  onClick={async () => {
                    await handleRelease(releaseForm.budget_id, { amount: releaseForm.amount, reason: releaseForm.reason });
                    setShowReleaseModal(false);
                  }}
                  disabled={!releaseForm.reason.trim()}
                  className={clsx('btn-primary', !releaseForm.reason.trim() && 'opacity-50 cursor-not-allowed')}
                >
                  <Unlock size={14} /> 确认释放
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* v12.0: 创建调拨弹窗（沙盘推演 + 跨象限识别） */}
      <AnimatePresence>
        {showTransferModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => { setShowTransferModal(false); setTransferSandbox(null); }}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-semibold text-finance-800 flex items-center gap-2">
                    <ArrowRightLeft size={18} className="text-finance-600" />
                    预算调拨流程
                  </h3>
                  <p className="text-xs text-surface-400 mt-0.5">文档 §3.5.4：象限内财经中心批 / 跨象限管委会批</p>
                </div>
                <button
                  onClick={() => { setShowTransferModal(false); setTransferSandbox(null); }}
                  className="text-surface-400 hover:text-surface-600"
                >
                  <X size={18} />
                </button>
              </div>

              {/* 步骤 1: 选择源/目标/金额 */}
              <div className="mb-4 space-y-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-5 h-5 rounded-full bg-finance-100 text-finance-700 text-[10px] font-bold flex items-center justify-center">1</span>
                  <span className="text-sm font-semibold text-surface-700">选择调拨双方</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] font-medium text-surface-700 mb-1">源预算项 <span className="text-alert-500">*</span></label>
                    <select
                      value={transferForm.from_budget_id}
                      onChange={e => {
                        setTransferForm(f => ({ ...f, from_budget_id: e.target.value }));
                        setTransferSandbox(null);
                      }}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    >
                      <option value="">请选择</option>
                      {items.map((item: BudgetItem) => (
                        <option key={item.budget_id} value={item.budget_id}>
                          {item.budget_id} - {item.description}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-surface-700 mb-1">目标预算项 <span className="text-alert-500">*</span></label>
                    <select
                      value={transferForm.to_budget_id}
                      onChange={e => {
                        setTransferForm(f => ({ ...f, to_budget_id: e.target.value }));
                        setTransferSandbox(null);
                      }}
                      className="w-full px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    >
                      <option value="">请选择</option>
                      {items.filter((item: BudgetItem) => item.budget_id !== transferForm.from_budget_id).map((item: BudgetItem) => (
                        <option key={item.budget_id} value={item.budget_id}>
                          {item.budget_id} - {item.description}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[11px] font-medium text-surface-700 mb-1">调拨金额 <span className="text-alert-500">*</span></label>
                    <input
                      type="number"
                      value={transferForm.amount || ''}
                      onChange={e => {
                        setTransferForm(f => ({ ...f, amount: Number(e.target.value) }));
                        setTransferSandbox(null);
                      }}
                      placeholder="0.00"
                      className="w-full px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    />
                  </div>
                </div>
                {transferForm.from_budget_id && transferForm.to_budget_id && transferForm.amount > 0 && (
                  <button
                    onClick={handleSimulateTransfer}
                    disabled={transferSandboxLoading}
                    className="w-full text-xs py-2 rounded-lg border border-finance-200 bg-finance-50 text-finance-700 hover:bg-finance-100 transition-colors flex items-center justify-center gap-1.5"
                  >
                    {transferSandboxLoading ? (
                      <><Loader2 size={12} className="animate-spin" /> 沙盘推演中...</>
                    ) : (
                      <><Activity size={12} /> 运行沙盘推演（预测执行率/预警/方向评分）</>
                    )}
                  </button>
                )}
              </div>

              {/* 步骤 2: 沙盘推演结果 */}
              {transferSandbox && !transferSandbox.error && (
                <div className="mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-5 h-5 rounded-full bg-finance-100 text-finance-700 text-[10px] font-bold flex items-center justify-center">2</span>
                    <span className="text-sm font-semibold text-surface-700">沙盘推演结果</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-2.5">
                      <p className="text-[10px] text-amber-700 font-semibold mb-1">源预算（调出）</p>
                      <p className="text-[11px]">调拨前执行率：<strong>{transferSandbox.from_budget?.execution_rate_before?.toFixed(1)}%</strong></p>
                      <p className="text-[11px]">调拨后执行率：<strong className={transferSandbox.from_budget?.execution_rate_after > 110 ? 'text-alert-700' : 'text-finance-700'}>{transferSandbox.from_budget?.execution_rate_after?.toFixed(1)}%</strong></p>
                    </div>
                    <div className="rounded-lg border border-brand-200 bg-brand-50/40 p-2.5">
                      <p className="text-[10px] text-brand-700 font-semibold mb-1">目标预算（调入）</p>
                      <p className="text-[11px]">调拨前执行率：<strong>{transferSandbox.to_budget?.execution_rate_before?.toFixed(1)}%</strong></p>
                      <p className="text-[11px]">调拨后执行率：<strong className={transferSandbox.to_budget?.execution_rate_after < 50 ? 'text-warning-700' : 'text-finance-700'}>{transferSandbox.to_budget?.execution_rate_after?.toFixed(1)}%</strong></p>
                    </div>
                  </div>
                  {transferSandbox.predicted_alerts?.total > 0 && (
                    <div className="text-[11px] bg-warning-50 border border-warning-200 rounded-lg p-2 mb-2">
                      <p className="font-semibold text-warning-700 mb-1">⚠ 预测将触发 {transferSandbox.predicted_alerts.total} 条预警：</p>
                      {transferSandbox.predicted_alerts.from_alerts?.map((a: any, i: number) => (
                        <p key={`f${i}`} className="text-warning-700">源：<span className="badge-amber">{a.level}</span> {a.reason}（{a.rule}）</p>
                      ))}
                      {transferSandbox.predicted_alerts.to_alerts?.map((a: any, i: number) => (
                        <p key={`t${i}`} className="text-warning-700">目标：<span className="badge-amber">{a.level}</span> {a.reason}（{a.rule}）</p>
                      ))}
                    </div>
                  )}
                  <div className={clsx(
                    'rounded-lg p-3 border-2',
                    transferSandbox.direction_score >= 70 ? 'bg-compliance-50 border-compliance-300' :
                    transferSandbox.direction_score >= 40 ? 'bg-warning-50 border-warning-300' :
                    'bg-alert-50 border-alert-300'
                  )}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] text-surface-700 font-semibold">方向合理性评分</span>
                      <span className={clsx(
                        'text-2xl font-bold',
                        transferSandbox.direction_score >= 70 ? 'text-compliance-700' :
                        transferSandbox.direction_score >= 40 ? 'text-warning-700' :
                        'text-alert-700'
                      )}>{transferSandbox.direction_score}</span>
                    </div>
                    <p className="text-[11px] text-surface-600">{transferSandbox.recommendation}</p>
                  </div>
                </div>
              )}

              {transferSandbox?.error && (
                <div className="text-xs text-amber-700 bg-amber-50 rounded-lg p-2 mb-3">
                  ⚠ 沙盘推演暂不可用：{transferSandbox.error}（仍可提交调拨，但建议人工评估）
                </div>
              )}

              <div className="flex gap-3 justify-end mt-5">
                <button
                  onClick={() => { setShowTransferModal(false); setTransferSandbox(null); }}
                  className="btn-secondary"
                >
                  取消
                </button>
                <button
                  onClick={handleCreateTransfer}
                  disabled={!transferForm.from_budget_id || !transferForm.to_budget_id || transferForm.amount <= 0}
                  className={clsx('btn-primary', (!transferForm.from_budget_id || !transferForm.to_budget_id || transferForm.amount <= 0) && 'opacity-50 cursor-not-allowed')}
                >
                  <ArrowRightLeft size={14} />
                  {transferSandbox && transferSandbox.direction_score !== undefined
                    ? (transferSandbox.direction_score >= 70 ? '确认调拨（推荐）' :
                       transferSandbox.direction_score >= 40 ? '⚠ 提交调拨（评分偏低）' :
                       '🚫 不建议调拨（评分过低）')
                    : '确认调拨'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
