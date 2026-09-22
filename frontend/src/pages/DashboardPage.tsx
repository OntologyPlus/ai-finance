import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { motion } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  TrendingUp,
  RefreshCw,
  Bot,
  Send,
  Target,
  Sparkles,
  Building2,
  Droplets,
  BarChart3,
  GitBranch,
  Wallet,
  Zap,
  Eye,
  Clock,
  CheckCircle,
  Shield,
} from 'lucide-react';
import { dashboardApi, expenseApi, budgetApi, analysisApi, alertApi, strategicApi, insightsApi } from '../services/api';
import { useAppStore } from '../store';
import AnimatedNumber from '../components/ai/AnimatedNumber';
import InsightRail, { type InsightItem, type InsightPriority } from '../components/ai/InsightRail';
import CollapsibleSection from '../components/ui/CollapsibleSection';
import { CFODashboard, CenterLeadDashboard, ProductManagerDashboard, RoleSwitcher } from '../components/dashboard/RoleDashboards';

// ─── Helpers ─────────────────────────────────────────────────────────────

function getPersonalizedGreeting(user: any, criticalCount: number): { text: string; icon: string } {
  const hour = new Date().getHours();
  const name = user?.display_name || user?.username || '';

  let timeText: string;
  let icon: string;
  if (hour < 6) { timeText = '夜深了'; icon = '🌙'; }
  else if (hour < 9) { timeText = '早上好'; icon = '☀️'; }
  else if (hour < 12) { timeText = '上午好'; icon = '☀️'; }
  else if (hour < 14) { timeText = '中午好'; icon = '🌤️'; }
  else if (hour < 18) { timeText = '下午好'; icon = '🌤️'; }
  else if (hour < 22) { timeText = '晚上好'; icon = '🌙'; }
  else { timeText = '夜深了'; icon = '🌙'; }

  if (criticalCount > 0) {
    return { text: `${timeText}，${name}。今天有 ${criticalCount} 件急事需要你处理。`, icon: '⚡' };
  }
  if (hour > 20 || hour < 6) {
    return { text: `这么晚了还在工作，${name}。一切正常。`, icon: '🌙' };
  }
  return { text: `${timeText}，${name}。一切运行正常。`, icon };
}

function formatAmount(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '¥ 0';
  if (n >= 10000) return `¥ ${(n / 10000).toFixed(1)}万`;
  return `¥ ${n.toLocaleString()}`;
}

type DecisionBriefItem = {
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
};

const BRIEF_TONE: Record<DecisionBriefItem['severity'], string> = {
  red: 'bg-alert-100 text-alert-700',
  orange: 'bg-warning-100 text-warning-700',
  yellow: 'bg-brand-100 text-brand-700',
};

// ─── Main Component ──────────────────────────────────────────────────────

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAppStore();
  const addToast = useAppStore((s) => s.addToast);
  const [summary, setSummary] = useState<any>(null);
  const [pendingApprovals, setPendingApprovals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [insights, setInsights] = useState<InsightItem[]>([]);
  const [showQuickInput, setShowQuickInput] = useState(false);
  const [quickInput, setQuickInput] = useState('');
  const [l1Names, setL1Names] = useState<Record<string, string>>({ 'L1-01': '研发费用', 'L1-02': '市场费用', 'L1-03': '管理费用' });
  const [analysisInsights, setAnalysisInsights] = useState<any[]>([]);
  const [trendData, setTrendData] = useState<any>(null);
  const [alertHeatmap, setAlertHeatmap] = useState<any[]>([]);
  const [quadrantData, setQuadrantData] = useState<any[]>([]);
  const [waterfallData, setWaterfallData] = useState<any[]>([]);
  const [proactiveInsights, setProactiveInsights] = useState<any[]>([]);
  const [decisionBrief, setDecisionBrief] = useState<DecisionBriefItem[]>([]);
  const [dashboardMetrics, setDashboardMetrics] = useState<{
    recentAlertsCount: number;
    budgetExecutionRate: number;
    activeStrategicCount: number;
    gapSummary: { gap1: number; gap2: number; gap3: number } | null;
  }>({ recentAlertsCount: 0, budgetExecutionRate: 0, activeStrategicCount: 0, gapSummary: null });
  // v8.0 角色化视图
  const [currentRole, setCurrentRole] = useState<'cfo' | 'center_lead' | 'product_manager'>(() => {
    const saved = typeof window !== 'undefined' ? localStorage.getItem('dashboard_role') : null;
    return (saved as any) || 'cfo';
  });

  const handleRoleChange = useCallback((role: 'cfo' | 'center_lead' | 'product_manager') => {
    setCurrentRole(role);
    if (typeof window !== 'undefined') {
      localStorage.setItem('dashboard_role', role);
    }
  }, []);

  const fetchData = useCallback(() => {
    setLoading(true);
    Promise.allSettled([
      dashboardApi.getOverview().then(res => setSummary(res.data)),
      expenseApi.getReports({ status: 'pending_approval', page: 1, page_size: 10 }).then(res => setPendingApprovals(res.data || [])),
      dashboardApi.getDecisionBrief().then(res => setDecisionBrief(res.data?.items || [])),
    ]).then(() => {
      generateInsights();
    }).catch((error: any) => {
      addToast({ type: 'error', title: '获取驾驶舱数据失败', message: error.message });
    }).finally(() => setLoading(false));

    budgetApi.getSubjects({ level: 'L1' }).then(res => {
      const mapping: Record<string, string> = {};
      (res.data || []).forEach((item: any) => {
        mapping[item.l1_code || item.code] = item.l1_name || item.name;
      });
      if (Object.keys(mapping).length > 0) {
        setL1Names(mapping);
      }
    }).catch(() => {});

    // Fetch analysis insights for AI insight cards
    analysisApi.getDashboard().then(res => {
      const data = res.data || {};
      const gapAnalyses = data.gap_analyses || [];
      const listAnalyses = data.list_analyses || [];
      const insights: any[] = [];

      if (gapAnalyses.length > 0) {
        const latest = gapAnalyses[0];
        if (latest.gap1 > 0) {
          insights.push({ type: 'gap', label: 'GAP1 目标差距', value: latest.gap1, detail: `当前预测低于年度目标 ${latest.gap1} 万元` });
        }
        if (latest.gap2 > 0) {
          insights.push({ type: 'gap', label: 'GAP2 执行差距', value: latest.gap2, detail: `预测与实际偏差 ${latest.gap2} 万元` });
        }
        if (latest.gap3 !== 0) {
          insights.push({ type: 'gap', label: 'GAP3 预测变动', value: latest.gap3, detail: `预测较上期${latest.gap3 > 0 ? '上调' : '下调'} ${Math.abs(latest.gap3)} 万元` });
        }
        setDashboardMetrics(prev => ({ ...prev, gapSummary: { gap1: latest.gap1 || 0, gap2: latest.gap2 || 0, gap3: latest.gap3 || 0 } }));
      }

      const mustWin = listAnalyses.filter((l: any) => l.list_type === '必赢清单');
      const improve = listAnalyses.filter((l: any) => l.list_type === '改善清单');
      if (mustWin.length > 0) {
        insights.push({ type: 'list', label: '必赢清单', value: mustWin.length, detail: `${mustWin.length} 项战略核心科目需重点保障` });
      }
      if (improve.length > 0) {
        insights.push({ type: 'list', label: '改善清单', value: improve.length, detail: `${improve.length} 项非核心科目存在超支风险` });
      }

      setAnalysisInsights(insights);
    }).catch(() => {});

    // Fetch dashboard metrics: alerts count, execution rate, strategic initiatives
    alertApi.getStats().then(res => {
      const stats = res.data || {};
      setDashboardMetrics(prev => ({ ...prev, recentAlertsCount: stats.active_count ?? 0 }));
    }).catch(() => {});

    analysisApi.getExecutionRates({}).then(res => {
      const rates = res.data || [];
      if (rates.length > 0) {
        const avgRate = Math.round(rates.reduce((s: number, r: any) => s + (r.execution_rate || 0), 0) / rates.length);
        setDashboardMetrics(prev => ({ ...prev, budgetExecutionRate: avgRate }));
      }
    }).catch(() => {});

    strategicApi.getInitiatives({ status: 'active' }).then(res => {
      const items = res.data || [];
      setDashboardMetrics(prev => ({ ...prev, activeStrategicCount: items.length }));
    }).catch(() => {});

    // Fetch trend prediction data
    analysisApi.getExecutionRates({}).then(res => {
      const rates = res.data || [];
      console.log('Dashboard: execution rates', rates);
      if (rates.length > 0) {
        const l1Code = rates[0].l1_code || 'L1-01';
        console.log('Dashboard: predicting trend for', l1Code);
        analysisApi.predictTrend({ l1_code: l1Code, months_ahead: 6 }).then(res => {
          console.log('Dashboard: trend data', res.data);
          setTrendData(res.data);
        }).catch(err => console.error('Dashboard: predictTrend error', err));
      } else {
        console.log('Dashboard: no execution rates data');
      }
    }).catch(err => console.error('Dashboard: getExecutionRates error', err));

    // Fetch alert heatmap data
    alertApi.getStats().then(res => {
      const stats = res.data || {};
      const heatmapData: any[] = [];
      const byL1 = stats.by_l1 || {};
      const months = ['2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06'];
      Object.entries(byL1).forEach(([l1Code, l1Data]: [string, any]) => {
        months.forEach((month, monthIdx) => {
          // 数据驱动：优先取真实月度计数，缺失时回退 0（无 mock）
          const count = l1Data?.[month] || 0;
          heatmapData.push([monthIdx, Object.keys(byL1).indexOf(l1Code), count]);
        });
      });
      setAlertHeatmap(heatmapData);
    }).catch(() => {});

    // Fetch quadrant distribution data
    analysisApi.getExecutionRates({}).then(res => {
      const rates = res.data || [];
      const quadrantPoints = rates.map((r: any) => ({
        name: l1Names[r.l1_code] || r.l1_code,
        // 数据驱动：三维 [执行率, 战略对齐(0 占位无 mock), 预算金额]
        value: [r.execution_rate || 0, 0, r.budget_amount || 100],
        l1_code: r.l1_code,
      }));
      setQuadrantData(quadrantPoints);
    }).catch(() => {});

    // Fetch waterfall data (3GAP contribution)
    analysisApi.getExecutionRates({}).then(res => {
      const rates = res.data || [];
      const waterfall = rates.slice(0, 5).map((r: any) => ({
        name: l1Names[r.l1_code] || r.l1_code,
        value: (r.execution_rate || 0) - 50,
        l1_code: r.l1_code,
      }));
      setWaterfallData(waterfall);
    }).catch(() => {});
  }, [addToast]);

  // AI 洞察生成（基于实际数据）
  const generateInsights = useCallback(() => {
    const items: InsightItem[] = [];
    const data = summary;
    if (!data) return;

    // 分析预算超支 — 自然语言化
    const budgetByQuadrant = data.budget_by_quadrant || data.budget_summary?.budget_by_quadrant || [];
    budgetByQuadrant.forEach((q: any) => {
      const rate = q.total_budget > 0 ? ((q.actual_spend / q.total_budget) * 100).toFixed(0) : 0;
      if (Number(rate) > 100) {
        items.push({
          id: `over-budget-${q.quadrant}`,
          priority: 'critical',
          icon: <TrendingUp size={16} />,
          title: `${q.quadrant}象限预算超支 ${rate}%`,
          aiAnalysis: `${q.quadrant}象限这个月花得比预算快了。预算 ${formatAmount(q.total_budget)}，实际已经支出了 ${formatAmount(q.actual_spend)}，超了 ${formatAmount(q.actual_spend - q.total_budget)}。我建议你尽快确认一下支出原因。`,
          aiSuggestion: `建议：1) 先冻结${q.quadrant}象限的非紧急支出，看看能不能缓一缓；2) 查一下有没有 B 类预算可以转过来；3) 和业务负责人聊聊，确认后续的支出计划。`,
          actions: [
            { label: '查看明细', type: 'primary', action: () => navigate('/budget') },
            { label: '冻结支出', type: 'secondary', action: () => addToast({ type: 'info', title: '功能开发中', message: '请联系AI助手执行此操作' }) },
            { label: '忽略', type: 'link', action: () => {} },
          ],
        });
      }
    });

    // 分析预警 — 自然语言化
    const recentAlerts = data.recent_alerts || [];
    const criticalAlerts = recentAlerts.filter((a: any) => a.alert_level === 'red' || a.alert_level === 'orange');
    if (criticalAlerts.length > 0) {
      criticalAlerts.slice(0, 3).forEach((alert: any) => {
        const levelText = alert.alert_level === 'red' ? '红色' : '橙色';
        const statusText = alert.status === 'active' ? '还没处理' : alert.status === 'responded' ? '处理中' : '已经升级';
        items.push({
          id: `alert-${alert.alert_id}`,
          priority: 'critical',
          icon: <AlertTriangle size={16} />,
          title: alert.title,
          aiAnalysis: `这是一条${levelText}预警，当前状态是${statusText}。我建议你先看看详情，确认是否需要紧急处理。`,
          aiSuggestion: '建议：立即查看预警详情，确认是否需要升级处理。如果需要协助，可以直接跟我说。',
          actions: [
            { label: '处理预警', type: 'primary', action: () => navigate('/alert') },
            { label: '查看详情', type: 'secondary', action: () => navigate('/alert') },
          ],
        });
      });
    }

    // 分析待审批 — 自然语言化
    if (pendingApprovals.length > 0) {
      const totalAmount = pendingApprovals.reduce((sum: number, e: any) => sum + (e.amount || 0), 0);
      const smallCount = pendingApprovals.filter((e: any) => (e.amount || 0) < 5000).length;
      items.push({
        id: 'pending-approvals',
        priority: 'attention',
        icon: <Clock size={16} />,
        title: `${pendingApprovals.length} 笔报销等你审批，合计 ${formatAmount(totalAmount)}`,
        aiAnalysis: `我看了一下，其中 ${smallCount} 笔金额都不到 5000 块，按照管控规则是可以自动通过的。剩下的你抽空审一下就好。`,
        aiSuggestion: '建议：先处理大额的，小额的我可以帮你自动审批，帮你省点时间。',
        actions: [
          { label: '批量审批', type: 'primary', action: () => navigate('/approval') },
          { label: 'AI自动审批', type: 'secondary', action: () => addToast({ type: 'info', title: 'AI正在审批...', message: '小额报销将自动通过' }) },
        ],
      });
    }

    // 分析执行率 — 自然语言化
    const executionRate = data.execution_rate ?? 0;
    if (executionRate < 50) {
      items.push({
        id: 'low-execution',
        priority: 'attention',
        icon: <Target size={16} />,
        title: `预算执行率有点低（${executionRate}%）`,
        aiAnalysis: `整体预算执行率只有 ${executionRate}%，说明很多预算都在闲置。这样下去可能下年度预算会被砍掉，有点可惜。`,
        aiSuggestion: '建议：我帮你看看哪些预算在闲置，制定一个 Q4 支出计划。或者考虑把闲置预算调拨到需要的地方。',
        actions: [
          { label: '查看闲置科目', type: 'primary', action: () => navigate('/budget') },
          { label: 'AI调拨方案', type: 'secondary', action: () => navigate('/ai-agent') },
        ],
      });
    }

    // 分析自动审批成果 — 自然语言化
    const autoApproved = pendingApprovals.filter((e: any) => (e.amount || 0) < 5000);
    if (autoApproved.length > 0) {
      items.push({
        id: 'auto-approved',
        priority: 'info',
        icon: <CheckCircle size={16} />,
        title: `${autoApproved.length} 笔报销我帮你自动审过了`,
        aiAnalysis: `金额都不到 5000 元，符合管控规则，不需要人工审批。帮你省了大约 ${autoApproved.length * 0.5} 小时的审批时间，你可以把精力放在更重要的事情上。`,
        aiSuggestion: '如果你想开启自动审批，随时跟我说一声就行。',
        actions: [
          { label: '查看详情', type: 'secondary', action: () => navigate('/approval') },
        ],
      });
    }

    // 如果没有数据，显示默认洞察 — 自然语言化
    if (items.length === 0) {
      items.push({
        id: 'all-clear',
        priority: 'info',
        icon: <Shield size={16} />,
        title: '一切正常，放心',
        aiAnalysis: '预算管控正常，审批流程正常，没有异常预警。今天你可以放心处理其他工作了。',
        aiSuggestion: '如果你想做点什么，我可以帮你生成月度报告或者做个经营分析。',
        actions: [
          { label: '生成月度报告', type: 'primary', action: () => navigate('/report') },
          { label: '经营分析', type: 'secondary', action: () => navigate('/analysis') },
        ],
      });
    }

    setInsights(items);
  }, [summary, pendingApprovals, navigate, addToast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchData();
    }, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Fetch proactive insights (v6.0 新增)
  useEffect(() => {
    const fetchProactive = async () => {
      try {
        const res = await insightsApi.getActive();
        if (res.success) setProactiveInsights((res.data as any[]) || []);
      } catch {
        // 静默：不影响 Dashboard 主流程
      }
    };
    fetchProactive();
    const interval = setInterval(fetchProactive, 60000);
    return () => clearInterval(interval);
  }, []);

  // v10.0: 合并 3 处主动建议 → InsightRail 数据源
  // 用 useMemo 稳定引用，避免 effect 无限触发
  const unifiedInsights: InsightItem[] = useMemo(() => {
    return [
      ...insights.map((it) => ({
        id: it.id,
        priority: it.priority as InsightPriority,
        title: it.title,
        summary: it.aiAnalysis?.split(/[。！？]/)[0] || '',
        action_url: undefined,
      })),
      ...proactiveInsights.map((it: any) => ({
        id: `proactive-${it.id}`,
        priority: (it.priority || 'info') as InsightPriority,
        title: it.title,
        summary: it.detail?.slice(0, 60) || '',
        action_url: it.action_url,
        action_label: it.action_label,
      })),
      ...analysisInsights.map((it: any, idx: number) => ({
        id: `analysis-${idx}`,
        priority: 'attention' as InsightPriority,
        title: it.label,
        summary: it.detail,
        action_url: '/analysis',
        action_label: '分析',
      })),
    ];
  }, [insights, proactiveInsights, analysisInsights]);

  const criticalCount = unifiedInsights.filter((i) => i.priority === 'critical').length;
  const briefCount = decisionBrief.length;
  const greeting = getPersonalizedGreeting(user, Math.max(criticalCount, briefCount));
  const { setAIContext } = useAppStore();

  // 序列化关键 ID 用于 effect 依赖（避免 array 引用变化导致无限循环）
  const insightFingerprint = unifiedInsights
    .filter((i) => i.priority === 'critical')
    .map((i) => i.id)
    .join(',');

  useEffect(() => {
    if (unifiedInsights.length === 0) return;
    const lastCritical = unifiedInsights.find((i) => i.priority === 'critical');
    setAIContext({
      lastTopic: lastCritical ? lastCritical.title : unifiedInsights[0].title,
      lastInsight: '',
      trackedItems: unifiedInsights.filter((i) => i.priority === 'critical').map((i) => i.id),
      lastUpdate: new Date().toISOString(),
    });
    // 仅在关键 ID 变化时触发，避免重复 setState
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [insightFingerprint]);

  const handleQuickSend = () => {
    if (!quickInput.trim()) return;
    navigate('/ai-agent', { state: { initialMessage: quickInput } });
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-surface-400">
        <RefreshCw size={24} className="animate-spin" />
        <p className="mt-3 text-sm">AI 正在分析财经数据...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 w-full min-w-0">
      {/* ── 1. 问候 Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-finance-800 font-display">
            {greeting.icon} {greeting.text}
          </h1>
          <p className="text-xs text-surface-500 mt-1">
            {briefCount > 0
              ? `本周 ${briefCount} 笔需要拍板，金额与动作已列在下方。`
              : criticalCount > 0
                ? `以下 ${criticalCount} 件需立即处理，其它一切正常。`
                : '所有财经数据已检查，未发现异常。'}
          </p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-surface-500 hover:text-finance-600 hover:bg-finance-50 transition-colors"
        >
          <RefreshCw size={12} />
          刷新
        </button>
      </div>

      {/* ── 1.5 本周拍板：金额 · 动作 · 一句理由 ── */}
      <div className="rounded-xl border border-finance-200 bg-white overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 border-b border-finance-100 bg-finance-50/60">
          <h2 className="section-title">
            <Zap size={14} className="text-finance-600" />
            本周拍板
          </h2>
          <span className="text-[10px] text-surface-400">
            {briefCount > 0 ? `${briefCount} 笔 · 点进去批` : '暂无待拍板事项'}
          </span>
        </div>
        {decisionBrief.length === 0 ? (
          <p className="px-4 py-6 text-xs text-surface-400 text-center">诊断灯、待审报销与红橙预警均无需要当场拍板的事项。</p>
        ) : (
          <div className="divide-y divide-finance-50">
            {decisionBrief.map((item) => (
              <div key={item.id} className="flex items-start gap-3 px-4 py-3">
                <span className={`mt-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded ${BRIEF_TONE[item.severity] || BRIEF_TONE.yellow}`}>
                  {item.rank}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-semibold text-finance-800">{item.title}</p>
                    <span className="text-sm font-display font-bold text-finance-700">{item.money_label}</span>
                  </div>
                  <p className="text-[11px] text-surface-500 mt-0.5 line-clamp-1">{item.why}</p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    onClick={() => navigate(item.href)}
                    className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-finance-600 text-white hover:bg-finance-700"
                  >
                    {item.action}
                  </button>
                  {item.secondary_href ? (
                    <button
                      type="button"
                      onClick={() => navigate(item.secondary_href!)}
                      className="px-2 py-1 rounded-md text-[11px] text-finance-600 hover:bg-finance-50"
                    >
                      影响面
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── 2. L1 决策层：4 KPI 卡（无渐变） ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button onClick={() => navigate('/alert')} className="kpi-card text-left hover:border-alert-300 transition-colors group">
          <div className="flex items-center gap-1.5">
            <AlertTriangle size={13} className="text-alert-500" />
            <span className="text-xs text-surface-500 group-hover:text-alert-600">活跃预警</span>
          </div>
          <p className="text-2xl font-bold text-alert-600 font-display">
            <AnimatedNumber value={dashboardMetrics.recentAlertsCount} />
          </p>
        </button>
        <button onClick={() => navigate('/budget')} className="kpi-card text-left hover:border-brand-300 transition-colors group">
          <div className="flex items-center gap-1.5">
            <Target size={13} className="text-brand-500" />
            <span className="text-xs text-surface-500 group-hover:text-brand-600">预算执行率</span>
          </div>
          <p className="text-2xl font-bold text-brand-600 font-display">
            <AnimatedNumber value={dashboardMetrics.budgetExecutionRate} suffix="%" />
          </p>
        </button>
        <button onClick={() => navigate('/cashflow')} className="kpi-card text-left hover:border-finance-300 transition-colors group">
          <div className="flex items-center gap-1.5">
            <Droplets size={13} className="text-finance-500" />
            <span className="text-xs text-surface-500 group-hover:text-finance-600">现金流</span>
          </div>
          <p className="text-2xl font-bold text-finance-600 font-display">
            {summary?.cashflow_status === 'tight' ? '紧' : summary?.cashflow_status === 'risk' ? '⚠风险' : '正常'}
          </p>
        </button>
        <button onClick={() => navigate('/strategic')} className="kpi-card text-left hover:border-compliance-300 transition-colors group">
          <div className="flex items-center gap-1.5">
            <Sparkles size={13} className="text-compliance-500" />
            <span className="text-xs text-surface-500 group-hover:text-compliance-600">战略举措</span>
          </div>
          <p className="text-2xl font-bold text-compliance-600 font-display">
            <AnimatedNumber value={dashboardMetrics.activeStrategicCount} />
          </p>
        </button>
      </div>

      {/* ── 3. 关键洞察（合并 3 处主动建议 → 1 个 InsightRail） ── */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="section-title">
            <Bot size={14} className="text-brand-500" />
            关键洞察
          </h2>
          <span className="text-[10px] text-surface-400">已合并去重</span>
        </div>
        <InsightRail
          insights={unifiedInsights}
          maxVisible={3}
          onAction={(it) => {
            if (it.action_url) navigate(it.action_url);
          }}
        />
      </div>

      {/* ── 4. 角色化视图（保留） ── */}
      <div className="surface-card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="section-title">
            <Sparkles size={14} className="text-finance-600" />
            角色化决策视图
          </h2>
          <RoleSwitcher currentRole={currentRole} onChange={handleRoleChange} />
        </div>
        {currentRole === 'cfo' && <CFODashboard period={new Date().toISOString().slice(0, 7)} />}
        {currentRole === 'center_lead' && <CenterLeadDashboard />}
        {currentRole === 'product_manager' && <ProductManagerDashboard />}
      </div>

      {/* ── 5. L2 解释层：4 个图表区折叠 ── */}
      <div className="space-y-3">
        <CollapsibleSection title="预算执行趋势预测" icon={TrendingUp} badge="AI">
          {trendData ? (
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                legend: { data: ['历史数据', '预测数据'], bottom: 0, textStyle: { fontSize: 11 } },
                grid: { left: 50, right: 20, top: 10, bottom: 40 },
                xAxis: {
                  type: 'category',
                  data: [
                    ...(trendData.historical_data || []).map((d: any) => d.period),
                    ...(trendData.predictions || []).map((d: any) => `+${d.month_offset}月`),
                  ],
                  axisLabel: { rotate: 30, fontSize: 10 },
                },
                yAxis: { type: 'value', name: '执行率(%)', nameTextStyle: { fontSize: 10 } },
                series: [
                  { name: '历史数据', type: 'line', data: (trendData.historical_data || []).map((d: any) => d.monthly_rate), lineStyle: { color: '#3b82f6' }, itemStyle: { color: '#3b82f6' } },
                  { name: '预测数据', type: 'line', data: (trendData.predictions || []).map((d: any) => d.predicted), lineStyle: { color: '#f59e0b', type: 'dashed' }, itemStyle: { color: '#f59e0b' } },
                ],
              }}
              style={{ height: '240px' }}
              notMerge={true}
              lazyUpdate={true}
              showLoading={!trendData}
            />
          ) : (
            <p className="text-xs text-surface-400 py-6 text-center">暂无趋势数据</p>
          )}
        </CollapsibleSection>

        <CollapsibleSection title="3GAP 象限分布" icon={Target}>
          {quadrantData.length > 0 ? (
            <ReactECharts
              option={{
                tooltip: { formatter: (p: any) => `${p.data.name}<br/>执行率: ${p.data.value[0]}%` },
                grid: { left: 60, right: 30, top: 20, bottom: 40 },
                xAxis: { type: 'value', name: '执行率(%)', min: 0, max: 100, nameTextStyle: { fontSize: 10 } },
                yAxis: { type: 'value', name: '重要性', min: 0, max: 100, nameTextStyle: { fontSize: 10 } },
                series: [{
                  type: 'scatter',
                  data: quadrantData,
                  symbolSize: (d: any) => Math.max(Math.sqrt(d[2]) * 2, 10),
                  itemStyle: { color: '#10b981' },
                  label: { show: true, formatter: (p: any) => p.data.name, position: 'right', fontSize: 10 },
                }],
              }}
              style={{ height: '260px' }}
              notMerge={true}
              lazyUpdate={true}
              showLoading={quadrantData.length === 0}
            />
          ) : (
            <p className="text-xs text-surface-400 py-6 text-center">暂无 GAP 数据</p>
          )}
        </CollapsibleSection>

        <CollapsibleSection title="3GAP 贡献瀑布" icon={BarChart3}>
          {waterfallData.length > 0 ? (
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                grid: { left: 50, right: 20, top: 10, bottom: 40 },
                xAxis: { type: 'category', data: waterfallData.map((d) => d.name), axisLabel: { fontSize: 10 } },
                yAxis: { type: 'value', nameTextStyle: { fontSize: 10 } },
                series: [{
                  type: 'bar',
                  data: waterfallData.map((d) => ({ value: d.value, itemStyle: { color: d.value > 0 ? '#10b981' : '#f87171' } })),
                  barWidth: '50%',
                }],
              }}
              style={{ height: '240px' }}
              notMerge={true}
              lazyUpdate={true}
              showLoading={waterfallData.length === 0}
            />
          ) : (
            <p className="text-xs text-surface-400 py-6 text-center">暂无瀑布数据</p>
          )}
        </CollapsibleSection>

        <CollapsibleSection title="预警分布热力图" icon={AlertTriangle}>
          {alertHeatmap.length > 0 ? (
            <ReactECharts
              option={{
                tooltip: { position: 'top' },
                grid: { left: 60, right: 20, top: 10, bottom: 40 },
                xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] },
                yAxis: { type: 'category', data: ['L1-01', 'L1-02', 'L1-03'] },
                visualMap: { min: 0, max: 5, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#f0f9ff', '#3b82f6', '#1e40af'] } },
                series: [{ type: 'heatmap', data: alertHeatmap, label: { show: true } }],
              }}
              style={{ height: '200px' }}
              notMerge={true}
              lazyUpdate={true}
              showLoading={alertHeatmap.length === 0}
            />
          ) : (
            <p className="text-xs text-surface-400 py-6 text-center">暂无预警数据</p>
          )}
        </CollapsibleSection>
      </div>

      {/* ── 6. Quick Actions（2 个） ── */}
      <div className="flex items-center gap-2">
        <button onClick={() => navigate('/budget')} className="btn-secondary text-xs">
          <Wallet size={13} /> 预算
        </button>
        <button onClick={() => navigate('/analysis')} className="btn-secondary text-xs">
          <BarChart3 size={13} /> 分析
        </button>
        <button onClick={() => navigate('/report')} className="btn-secondary text-xs">
          <GitBranch size={13} /> 报告
        </button>
        <div className="ml-auto flex items-center gap-2 flex-1 max-w-md">
          <input
            type="text"
            value={quickInput}
            onChange={(e) => setQuickInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleQuickSend()}
            placeholder="问 AI：例如本月预算执行率如何？"
            className="flex-1 px-3 py-1.5 rounded-lg text-sm border border-surface-200 bg-white text-surface-700 placeholder:text-surface-400 outline-none focus:border-brand-400"
          />
          <button
            onClick={handleQuickSend}
            disabled={!quickInput.trim()}
            className="p-1.5 rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="发送"
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
