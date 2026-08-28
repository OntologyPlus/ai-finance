import { useState, useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  AlertTriangle,
  CheckCircle2,
  MessageSquare,
  BarChart3,
  Shield,
  RefreshCw,
  Filter,
  ArrowRight,
  ChevronRight,
  Clock,
  TrendingUp,
  Brain,
  Activity,
  Loader2,
  Sparkles,
  Layers,
  Copy,
  Route as RouteIcon,
} from 'lucide-react';
import { clsx } from 'clsx';
import { alertApi, budgetApi } from '../services/api';
import { useAppStore } from '../store';
import type { AlertLevel, AlertStatus } from '../types';
import Pagination from '../components/Pagination';
import RuleBadge from '../components/common/RuleBadge';
import { AIViewPanel, ViewToggle, AiExplainPanel, RootCauseTree } from '../components/ai';
import AlertDetailDrawer from '../components/alert/AlertDetailDrawer';
import FatigueDashboard from '../components/alert/FatigueDashboard';

const TABS = ['预警看板', '预警列表', '闭环管理', '预警统计', '疲劳度运营', 'AI智能预警'] as const;

const LEVEL_MAP: Record<AlertLevel, { label: string; cls: string; icon: string; bg: string; border: string }> = {
  blue: { label: '蓝色', cls: 'badge-blue', icon: '🔵', bg: 'bg-brand-50', border: 'border-brand-200' },
  yellow: { label: '黄色', cls: 'badge-amber', icon: '🟡', bg: 'bg-warning-50', border: 'border-warning-200' },
  orange: { label: '橙色', cls: 'badge-orange', icon: '🟠', bg: 'bg-orange-50', border: 'border-orange-200' },
  red: { label: '红色', cls: 'badge-red', icon: '🔴', bg: 'bg-alert-50', border: 'border-alert-200' },
};

const ALERT_STATUS_MAP: Record<string, { label: string; cls: string }> = {
  active: { label: '开放', cls: 'badge-red' },
  responded: { label: '响应中', cls: 'badge-amber' },
  pending_closure: { label: '待闭环确认', cls: 'badge-blue' },
  closed: { label: '已闭环', cls: 'badge-green' },
  escalated: { label: '已升级', cls: 'badge-purple' },
};

export default function AlertPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [alertStats, setAlertStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedAlert, setSelectedAlert] = useState<any | null>(null);
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);
  const [showRespondModal, setShowRespondModal] = useState(false);
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('预警看板');
  const [closureForm, setClosureForm] = useState({ action_description: '', closure_type: 'action_taken' });
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize] = useState(10);
  const [filterLevel, setFilterLevel] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterL1Code, setFilterL1Code] = useState<string>('');
  const [l1Options, setL1Options] = useState<{ value: string; label: string }[]>([]);
  const [alertTrend, setAlertTrend] = useState<any[]>([]);
  const [responseTime, setResponseTime] = useState<any>(null);
  const [closureStats, setClosureStats] = useState<any>(null);
  const addToast = useAppStore((s) => s.addToast);
  const location = useLocation();
  const aiContext = useAppStore((s) => s.aiContext);
  const currentUser = useAppStore((s) => s.user);
  const [viewMode, setViewMode] = useState<'ai' | 'data'>('ai');

  const ACTION_DESC_MIN = 20;
  const actionDescError = closureForm.action_description.length > 0 && closureForm.action_description.length < ACTION_DESC_MIN
    ? `处理说明至少需要${ACTION_DESC_MIN}个字符`
    : '';
  const isActionDescValid = closureForm.action_description.length >= ACTION_DESC_MIN;

  const fetchData = async () => {
    try {
      const [alertsRes, statsRes] = await Promise.all([
        alertApi.getAlerts({
          level: filterLevel || undefined,
          status: filterStatus || undefined,
          org_id: filterL1Code || undefined,
          page: currentPage,
          page_size: pageSize,
        }),
        alertApi.getStats(),
      ]);
      const alertData = Array.isArray(alertsRes.data) ? alertsRes.data : [];
      setAlerts(alertData);
      if (alertsRes.total !== undefined) {
        setTotalPages(Math.max(1, Math.ceil(alertsRes.total / pageSize)));
      }
      setAlertStats(statsRes.data);
    } catch (error: any) {
      addToast({ type: 'error', title: '获取预警数据失败', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [currentPage, filterLevel, filterStatus, filterL1Code]);

  useEffect(() => {
    budgetApi.getSubjects({ level: 'L1' }).then(res => {
      const opts = (res.data || []).map((item: any) => ({
        value: item.l1_code || item.code,
        label: `${item.l1_code || item.code} ${item.l1_name || item.name}`,
      }));
      setL1Options(opts);
    }).catch(() => {});

    // 加载预警趋势数据
    alertApi.patternAnalysis({ lookback_months: 6 }).then(res => {
      const data = res.data || {};
      const trend = data.monthly_trend || [];
      setAlertTrend(trend);
      setResponseTime(data.response_time_stats || null);
      setClosureStats(data.closure_stats || null);
    }).catch(() => {});
  }, []);

  // v12.1 阶段 5: AI 智能预警状态
  const [aiFatigue, setAiFatigue] = useState<any>(null);
  const [aiCluster, setAiCluster] = useState<any>(null);
  const [aiDedup, setAiDedup] = useState<any>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiPriority, setAiPriority] = useState<any>(null);
  const [aiEscalation, setAiEscalation] = useState<any>(null);

  const loadAlertAi = async () => {
    setAiLoading(true);
    try {
      const [fatigue, cluster, dedup] = await Promise.all([
        alertApi.aiFatigueDetect(7, 10).catch(() => null),
        alertApi.aiAlertCluster(7).catch(() => null),
        alertApi.aiAlertDedup(24).catch(() => null),
      ]);
      if (fatigue?.success) setAiFatigue(fatigue.data);
      if (cluster?.success) setAiCluster(cluster.data);
      if (dedup?.success) setAiDedup(dedup.data);
    } catch (error) {
      console.error('AI alert load failed:', error);
    } finally {
      setAiLoading(false);
    }
  };

  const diagnoseAlert = async (alertId: string) => {
    if (!alertId) return;
    setSelectedAlertId(alertId);
    try {
      const [pri, esc] = await Promise.all([
        alertApi.aiAlertPriority(alertId).catch(() => null),
        alertApi.aiSmartEscalation(alertId).catch(() => null),
      ]);
      if (pri?.success) setAiPriority(pri.data);
      if (esc?.success) setAiEscalation(esc.data);
    } catch (error) {
      console.error('Diagnose failed:', error);
    }
  };

  const handleRespond = async (alertId: string) => {
    try {
      await alertApi.respond(alertId, { action_description: closureForm.action_description });
      addToast({ type: 'success', title: '操作成功', message: '预警已响应' });
      setShowRespondModal(false);
      setClosureForm({ action_description: '', closure_type: 'action_taken' });
      setSelectedAlert(null);
      fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: '响应失败', message: error.message });
    }
  };

  const handleConfirmClosure = async (alertId: string) => {
    try {
      await alertApi.confirmClosure(alertId, { confirmer_id: currentUser?.user_id || '', comment: closureForm.action_description });
      addToast({ type: 'success', title: '操作成功', message: '预警已闭环确认' });
      setClosureForm({ action_description: '', closure_type: 'action_taken' });
      setSelectedAlert(null);
      fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: '闭环确认失败', message: error.message });
    }
  };

  const handleEscalate = async (alertId: string) => {
    try {
      await alertApi.escalate(alertId);
      addToast({ type: 'success', title: '操作成功', message: '预警已升级' });
      fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: '升级失败', message: error.message });
    }
  };

  const handleScan = async () => {
    try {
      await alertApi.scan();
      addToast({ type: 'success', title: '操作成功', message: '预警扫描完成' });
      fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: '扫描失败', message: error.message });
    }
  };

  const activeCount = alertStats?.active_count ?? alerts.filter(a => a.status === 'active').length;
  const respondedCount = alertStats?.responded_count ?? alerts.filter(a => a.status === 'responded').length;
  const closedToday = alertStats?.closed_today ?? 0;
  const closureRate = alertStats?.closure_rate ?? Math.round((alerts.filter(a => a.status === 'closed').length / Math.max(alerts.length, 1)) * 100);

  const levelCounts = {
    blue: alerts.filter(a => a.alert_level === 'blue').length,
    yellow: alerts.filter(a => a.alert_level === 'yellow').length,
    orange: alerts.filter(a => a.alert_level === 'orange').length,
    red: alerts.filter(a => a.alert_level === 'red').length,
  };

  // AI insights from alert data
  const alertAIInsights = useMemo(() => {
    const insights: { priority: 'critical' | 'attention' | 'info'; title: string; analysis: string; suggestion: string }[] = [];

    // Group alerts by type
    const byType: Record<string, any[]> = {};
    alerts.forEach(a => {
      if (!byType[a.alert_type]) byType[a.alert_type] = [];
      byType[a.alert_type].push(a);
    });

    // Generate root cause analysis for each active alert
    alerts.filter(a => a.status === 'active' || a.status === 'responded').forEach(alert => {
      const levelInfo = LEVEL_MAP[alert.alert_level];
      const deviation = alert.deviation_rate != null ? `${alert.deviation_rate > 0 ? '+' : ''}${alert.deviation_rate}%` : '未知';
      const threshold = alert.threshold_value != null ? `${alert.threshold_value}%` : '未设定';
      const metric = alert.metric_value != null ? `${alert.metric_value}%` : '未记录';

      // Root cause analysis
      let rootCause = '';
      let relatedAlerts: string[] = [];
      let relatedBudget: string[] = [];

      if (alert.deviation_rate && alert.deviation_rate > 20) {
        rootCause = `偏离率 ${deviation} 超过阈值 ${threshold}，实际值 ${metric}。可能是该科目近期支出集中或预算编制不合理。`;
      } else if (alert.deviation_rate && alert.deviation_rate > 0) {
        rootCause = `偏离率 ${deviation} 轻微超标，实际值 ${metric}。可能是季节性波动或偶发性支出增加。`;
      } else {
        rootCause = `预警触发但偏离率为 ${deviation}，可能是预警阈值设置过于敏感或其他关联指标异常。`;
      }

      // Cross-domain correlation: find related alerts by same l1_code or budget_id
      relatedAlerts = alerts
        .filter(a => a.alert_id !== alert.alert_id && (a.l1_code === alert.l1_code || a.budget_id === alert.budget_id))
        .map(a => `${a.alert_id} (${LEVEL_MAP[a.alert_level]?.label || a.alert_level})`);

      // Related budget items
      if (alert.budget_id) {
        relatedBudget.push(`预算项: ${alert.budget_id}`);
      }
      if (alert.l1_code) {
        relatedBudget.push(`L1科目: ${alert.l1_code}`);
      }

      const priority = alert.alert_level === 'red' || alert.alert_level === 'orange' ? 'critical' : alert.alert_level === 'yellow' ? 'attention' : 'info';

      insights.push({
        priority,
        title: `[${levelInfo?.label || alert.alert_level}区] ${alert.title || alert.alert_id}`,
        analysis: `根因分析：${rootCause}${relatedAlerts.length > 0 ? ` | 关联预警：${relatedAlerts.join('、')}` : ''}`,
        suggestion: `推荐操作：1) ${alert.status === 'active' ? '立即响应并确认异常原因' : '继续跟进处理进度'}。2) 检查${alert.l1_code || alert.budget_id || '相关'}预算执行情况。3) 如为误报，调整预警阈值。`,
      });
    });

    // Type-based summary
    const overBudgetTypes = Object.entries(byType)
      .filter(([, items]) => items.some(a => a.deviation_rate && a.deviation_rate > 20))
      .map(([type]) => type);

    if (overBudgetTypes.length > 0) {
      insights.push({
        priority: 'attention',
        title: '异常趋势汇总',
        analysis: `${overBudgetTypes.length} 个预警类型出现大幅偏离（>20%）：${overBudgetTypes.join('、')}。${activeCount > 3 ? '开放预警数量较多，建议优先处理红色和橙色预警。' : '预警数量在可控范围内。'}`,
        suggestion: `建议按优先级处理：红色预警(${levelCounts.red}) > 橙色(${levelCounts.orange}) > 黄色(${levelCounts.yellow}) > 蓝色(${levelCounts.blue})。同时关注跨领域关联预警。`,
      });
    }

    return { insights };
  }, [alerts, activeCount, levelCounts]);

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-surface-400">加载中...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-finance-800 font-display">预警中心</h1>
          <p className="text-sm text-surface-400 mt-1">四色预警体系与闭环管理</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={handleScan} className="btn-primary">
            <RefreshCw size={14} /> 触发扫描
          </button>
          <ViewToggle mode={viewMode} onToggle={setViewMode} />
        </div>
      </div>

      {/* AI View */}
      <AnimatePresence>
        {viewMode === 'ai' && (
          <motion.div
            key="alert-ai-view"
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
                title="预警 AI 分析"
                summary={`活跃预警 ${activeCount} 个，待响应 ${respondedCount} 个，闭环率 ${closureRate}%`}
                insights={alertAIInsights.insights}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: '开放预警', value: activeCount, gradient: 'from-alert-500 to-alert-600' },
          { label: '待响应', value: respondedCount, gradient: 'from-warning-500 to-warning-600' },
          { label: '今日闭环', value: closedToday, gradient: 'from-compliance-500 to-health-600' },
          { label: '闭环率', value: `${closureRate}%`, gradient: 'from-finance-500 to-finance-700' },
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

      {/* Four-Color Alert Dashboard Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {([
          { level: 'red' as AlertLevel, label: '红色预警', desc: '紧急·立即处理', iconBg: 'bg-red-100', iconText: 'text-red-600', border: 'border-red-300', bg: 'bg-red-50/60', count: levelCounts.red },
          { level: 'orange' as AlertLevel, label: '橙色预警', desc: '重要·限时响应', iconBg: 'bg-orange-100', iconText: 'text-orange-600', border: 'border-orange-300', bg: 'bg-orange-50/60', count: levelCounts.orange },
          { level: 'yellow' as AlertLevel, label: '黄色预警', desc: '关注·及时跟踪', iconBg: 'bg-amber-100', iconText: 'text-amber-600', border: 'border-amber-300', bg: 'bg-amber-50/60', count: levelCounts.yellow },
          { level: 'blue' as AlertLevel, label: '蓝色预警', desc: '提示·常规监控', iconBg: 'bg-blue-100', iconText: 'text-blue-600', border: 'border-blue-300', bg: 'bg-blue-50/60', count: levelCounts.blue },
        ]).map(card => (
          <div key={card.level} className={clsx('rounded-xl border-2 p-4 transition-all hover:shadow-md', card.bg, card.border)}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', card.iconBg, card.iconText)}>
                  <AlertTriangle size={16} />
                </div>
                <div>
                  <h3 className={clsx('text-sm font-bold', card.iconText)}>{card.label}</h3>
                  <p className="text-[10px] text-surface-400">{card.desc}</p>
                </div>
              </div>
              <span className={clsx('text-3xl font-bold font-display', card.iconText)}>{card.count}</span>
            </div>
            <div className="flex items-center gap-1 mt-2">
              {alerts.filter(a => a.alert_level === card.level).slice(0, 2).map(a => (
                <span key={a.alert_id} className="text-[10px] px-1.5 py-0.5 rounded bg-white/60 text-surface-600 truncate max-w-[100px]">{a.title || a.alert_id}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* 高级分析图表 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 预警趋势折线图 */}
        {alertTrend.length > 0 && (
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp size={16} className="text-finance-600" />
              <h3 className="text-sm font-semibold text-finance-800">预警趋势</h3>
              <span className="text-[10px] text-surface-400">近6个月预警数量变化</span>
            </div>
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                legend: { data: ['红色', '橙色', '黄色', '蓝色'], bottom: 0 },
                grid: { left: 50, right: 20, bottom: 40, top: 20 },
                xAxis: {
                  type: 'category',
                  data: alertTrend.map((t: any) => t.month),
                },
                yAxis: { type: 'value', name: '预警数' },
                series: [
                  {
                    name: '红色',
                    type: 'line',
                    stack: 'total',
                    areaStyle: { color: '#fee2e2' },
                    lineStyle: { color: '#ef4444' },
                    itemStyle: { color: '#ef4444' },
                    data: alertTrend.map((t: any) => t.red || 0),
                  },
                  {
                    name: '橙色',
                    type: 'line',
                    stack: 'total',
                    areaStyle: { color: '#fed7aa' },
                    lineStyle: { color: '#fb923c' },
                    itemStyle: { color: '#fb923c' },
                    data: alertTrend.map((t: any) => t.orange || 0),
                  },
                  {
                    name: '黄色',
                    type: 'line',
                    stack: 'total',
                    areaStyle: { color: '#fef3c7' },
                    lineStyle: { color: '#f59e0b' },
                    itemStyle: { color: '#f59e0b' },
                    data: alertTrend.map((t: any) => t.yellow || 0),
                  },
                  {
                    name: '蓝色',
                    type: 'line',
                    stack: 'total',
                    areaStyle: { color: '#dbeafe' },
                    lineStyle: { color: '#3b82f6' },
                    itemStyle: { color: '#3b82f6' },
                    data: alertTrend.map((t: any) => t.blue || 0),
                  },
                ],
              }}
              style={{ height: '280px' }}
              notMerge={true}
              lazyUpdate={true}
              showLoading={alertTrend.length === 0}
            />
          </div>
        )}

        {/* 响应时效分布图 */}
        {responseTime && (
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <Clock size={16} className="text-warning-600" />
              <h3 className="text-sm font-semibold text-finance-800">响应时效分布</h3>
              <span className="text-[10px] text-surface-400">平均响应时间: {responseTime.avg_hours || 0}小时</span>
            </div>
            <ReactECharts
              option={{
                tooltip: { trigger: 'axis' },
                grid: { left: 50, right: 20, bottom: 20, top: 20 },
                xAxis: {
                  type: 'category',
                  data: ['<1小时', '1-4小时', '4-24小时', '>24小时'],
                },
                yAxis: { type: 'value', name: '预警数' },
                series: [
                  {
                    type: 'bar',
                    data: [
                      { value: responseTime.less_1h || 0, itemStyle: { color: '#10b981' } },
                      { value: responseTime.between_1_4h || 0, itemStyle: { color: '#f59e0b' } },
                      { value: responseTime.between_4_24h || 0, itemStyle: { color: '#fb923c' } },
                      { value: responseTime.greater_24h || 0, itemStyle: { color: '#ef4444' } },
                    ],
                    barWidth: '60%',
                  },
                ],
              }}
              style={{ height: '280px' }}
              notMerge={true}
              lazyUpdate={true}
              showLoading={!responseTime}
            />
          </div>
        )}

        {/* 闭环率仪表盘 */}
        {closureStats && (
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <CheckCircle2 size={16} className="text-compliance-600" />
              <h3 className="text-sm font-semibold text-finance-800">闭环率分析</h3>
            </div>
            <ReactECharts
              option={{
                series: [
                  {
                    type: 'gauge',
                    startAngle: 180,
                    endAngle: 0,
                    min: 0,
                    max: 100,
                    splitNumber: 10,
                    axisLine: {
                      lineStyle: {
                        width: 20,
                        color: [
                          [0.3, '#ef4444'],
                          [0.7, '#f59e0b'],
                          [1, '#10b981'],
                        ],
                      },
                    },
                    pointer: {
                      itemStyle: {
                        color: 'auto',
                      },
                    },
                    axisTick: {
                      distance: -20,
                      length: 8,
                      lineStyle: {
                        color: '#fff',
                        width: 2,
                      },
                    },
                    splitLine: {
                      distance: -20,
                      length: 20,
                      lineStyle: {
                        color: '#fff',
                        width: 2,
                      },
                    },
                    axisLabel: {
                      color: 'inherit',
                      distance: 30,
                      fontSize: 12,
                    },
                    detail: {
                      valueAnimation: true,
                      formatter: '{value}%',
                      color: 'inherit',
                      fontSize: 24,
                      offsetCenter: [0, '40%'],
                    },
                    data: [
                      {
                        value: closureStats.closure_rate || 0,
                        name: '闭环率',
                      },
                    ],
                    title: {
                      offsetCenter: [0, '60%'],
                      fontSize: 14,
                    },
                  },
                ],
              }}
              style={{ height: '280px' }}
              notMerge={true}
              lazyUpdate={true}
              showLoading={!closureStats}
            />
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-xs text-surface-500">已闭环</div>
                <div className="text-lg font-bold text-compliance-600">{closureStats.closed_count || 0}</div>
              </div>
              <div>
                <div className="text-xs text-surface-500">未闭环</div>
                <div className="text-lg font-bold text-alert-600">{closureStats.open_count || 0}</div>
              </div>
              <div>
                <div className="text-xs text-surface-500">平均耗时</div>
                <div className="text-lg font-bold text-finance-600">{closureStats.avg_closure_hours || 0}h</div>
              </div>
            </div>
          </div>
        )}

        {/* 预警模式分析 */}
        {alertTrend.length > 0 && (
          <div className="glass-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 size={16} className="text-purple-600" />
              <h3 className="text-sm font-semibold text-finance-800">预警模式分析</h3>
            </div>
            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-purple-50 border border-purple-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-purple-700">系统性问题</span>
                  <span className="text-sm font-bold text-purple-600">
                    {alertTrend.filter((t: any) => t.is_systemic).length} 项
                  </span>
                </div>
                <p className="text-[10px] text-surface-500">
                  连续3个月以上出现的预警类型，需要系统性整改
                </p>
              </div>
              <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-blue-700">偶发问题</span>
                  <span className="text-sm font-bold text-blue-600">
                    {alertTrend.filter((t: any) => !t.is_systemic).length} 项
                  </span>
                </div>
                <p className="text-[10px] text-surface-500">
                  单次或偶尔出现的预警，可能是特殊情况导致
                </p>
              </div>
              <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-amber-700">高频预警L1</span>
                  <span className="text-sm font-bold text-amber-600">
                    {alertTrend[0]?.top_l1_codes?.length || 0} 个
                  </span>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {(alertTrend[0]?.top_l1_codes || []).slice(0, 3).map((code: string) => (
                    <span key={code} className="px-2 py-0.5 rounded bg-white text-[10px] text-surface-700">
                      {code}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Alert Escalation Flow Visualization */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={16} className="text-finance-600" />
          <h3 className="text-sm font-semibold text-finance-800">预警升级流程</h3>
          <span className="text-[10px] text-surface-400">四色预警自动升级与闭环机制</span>
        </div>
        <div className="flex items-center justify-center gap-1 overflow-x-auto py-2">
          {[
            { level: '蓝色', color: 'bg-blue-500', border: 'border-blue-300', text: 'text-blue-700', bg: 'bg-blue-50', desc: '提示性预警', timeout: '24h' },
            { level: '黄色', color: 'bg-amber-500', border: 'border-amber-300', text: 'text-amber-700', bg: 'bg-amber-50', desc: '关注性预警', timeout: '8h' },
            { level: '橙色', color: 'bg-orange-500', border: 'border-orange-300', text: 'text-orange-700', bg: 'bg-orange-50', desc: '重要性预警', timeout: '4h' },
            { level: '红色', color: 'bg-red-500', border: 'border-red-300', text: 'text-red-700', bg: 'bg-red-50', desc: '紧急性预警', timeout: '1h' },
          ].map((step, idx) => (
            <div key={step.level} className="flex items-center">
              <div className={clsx('rounded-xl border-2 p-3 min-w-[140px] text-center transition-all hover:shadow-sm', step.bg, step.border)}>
                <div className={clsx('w-6 h-6 rounded-full mx-auto mb-1.5 flex items-center justify-center text-white text-xs font-bold', step.color)}>
                  {idx + 1}
                </div>
                <h4 className={clsx('text-xs font-bold', step.text)}>{step.level}预警</h4>
                <p className="text-[10px] text-surface-400 mt-0.5">{step.desc}</p>
                <p className="text-[10px] text-surface-500 mt-1">响应时限: {step.timeout}</p>
              </div>
              {idx < 3 && (
                <div className="flex items-center mx-1">
                  <ArrowRight size={14} className="text-surface-300" />
                  <span className="text-[9px] text-surface-400 whitespace-nowrap">超时升级</span>
                </div>
              )}
            </div>
          ))}
          <div className="flex items-center ml-1">
            <ArrowRight size={14} className="text-surface-300" />
          </div>
          <div className="rounded-xl border-2 border-compliance-300 bg-compliance-50 p-3 min-w-[120px] text-center">
            <div className="w-6 h-6 rounded-full mx-auto mb-1.5 flex items-center justify-center bg-compliance-500 text-white text-xs font-bold">
              <CheckCircle2 size={12} />
            </div>
            <h4 className="text-xs font-bold text-compliance-700">闭环确认</h4>
            <p className="text-[10px] text-surface-400 mt-0.5">双签闭环</p>
            <p className="text-[10px] text-surface-500 mt-1">业务+财务BP</p>
          </div>
        </div>
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
                  layoutId="alertTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === '预警看板' && (
              <motion.div
                key="board"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {(['blue', 'yellow', 'orange', 'red'] as AlertLevel[]).map(level => {
                    const lm = LEVEL_MAP[level];
                    const levelAlerts = alerts.filter(a => a.alert_level === level);
                    return (
                      <div key={level} className={clsx('rounded-xl border-2 p-5', lm.bg, lm.border)}>
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{lm.icon}</span>
                            <span className="font-semibold text-surface-800">{lm.label}区</span>
                          </div>
                          <span className={clsx('text-2xl font-bold font-display', level === 'red' ? 'text-alert-600' : level === 'orange' ? 'text-orange-600' : level === 'yellow' ? 'text-warning-600' : 'text-brand-600')}>
                            {levelCounts[level]}
                          </span>
                        </div>
                        <div className="space-y-1.5">
                          {levelAlerts.slice(0, 3).map(alert => (
                            <div key={alert.alert_id} className="px-2.5 py-1.5 rounded-lg bg-white/60 text-xs">
                              <p className="font-medium text-surface-700 truncate">{alert.title}</p>
                              <p className="text-surface-400">{alert.alert_id}</p>
                            </div>
                          ))}
                          {levelAlerts.length === 0 && (
                            <p className="text-xs text-surface-400 text-center py-2">暂无预警</p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {activeTab === '预警列表' && (
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
                    value={filterLevel}
                    onChange={e => { setFilterLevel(e.target.value); setCurrentPage(1); }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value="">全部级别</option>
                    <option value="blue">蓝色</option>
                    <option value="yellow">黄色</option>
                    <option value="orange">橙色</option>
                    <option value="red">红色</option>
                  </select>
                  <select
                    value={filterStatus}
                    onChange={e => { setFilterStatus(e.target.value); setCurrentPage(1); }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value="">全部状态</option>
                    <option value="active">开放</option>
                    <option value="responded">响应中</option>
                    <option value="pending_closure">待闭环确认</option>
                    <option value="closed">已闭环</option>
                    <option value="escalated">已升级</option>
                  </select>
                  <select
                    value={filterL1Code}
                    onChange={e => { setFilterL1Code(e.target.value); setCurrentPage(1); }}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value="">全部L1科目</option>
                    {l1Options.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-surface-200/60">
                        <th className="text-left py-3 px-3 metric-label">预警编号</th>
                        <th className="text-center py-3 px-3 metric-label">级别</th>
                        <th className="text-left py-3 px-3 metric-label">类型</th>
                        <th className="text-left py-3 px-3 metric-label">L1科目</th>
                        <th className="text-right py-3 px-3 metric-label">触发值</th>
                        <th className="text-right py-3 px-3 metric-label">阈值</th>
                        <th className="text-right py-3 px-3 metric-label">偏离率</th>
                        <th className="text-left py-3 px-3 metric-label">规则依据</th>
                        <th className="text-left py-3 px-3 metric-label">责任人</th>
                        <th className="text-center py-3 px-3 metric-label">状态</th>
                        <th className="text-left py-3 px-3 metric-label">响应截止</th>
                        <th className="text-center py-3 px-3 metric-label">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {alerts.map(alert => (
                        <tr key={alert.alert_id} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors cursor-pointer" onClick={() => { setSelectedAlert(alert); setSelectedAlertId(alert.alert_id); }}>
                          <td className="py-3 px-3 font-mono text-xs text-finance-700">{alert.alert_id}</td>
                          <td className="py-3 px-3 text-center">
                            <span className={LEVEL_MAP[alert.alert_level]?.cls || 'badge-blue'}>
                              {LEVEL_MAP[alert.alert_level]?.icon || '⚪'} {LEVEL_MAP[alert.alert_level]?.label || alert.alert_level}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-surface-600">{alert.alert_type}</td>
                          <td className="py-3 px-3 text-surface-500">{alert.l1_code || alert.budget_id || '-'}</td>
                          <td className="py-3 px-3 text-right font-mono">{alert.metric_value ?? '-'}{alert.metric_value != null ? '%' : ''}</td>
                          <td className="py-3 px-3 text-right font-mono">{alert.threshold_value ?? '-'}{alert.threshold_value != null ? '%' : ''}</td>
                          <td className={clsx('py-3 px-3 text-right font-mono', alert.deviation_rate > 0 ? 'text-alert-600' : 'text-brand-600')}>
                            {alert.deviation_rate != null ? `${alert.deviation_rate > 0 ? '+' : ''}${alert.deviation_rate}%` : '-'}
                          </td>
                          <td className="py-3 px-3">
                            {alert.rule_ids && alert.rule_ids.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {alert.rule_ids.slice(0, 2).map((rid: string) => (
                                  <RuleBadge key={rid} rule_id={rid} size="xs" />
                                ))}
                              </div>
                            ) : (
                              <span className="text-[10px] text-surface-400">无规则</span>
                            )}
                          </td>
                          <td className="py-3 px-3 text-surface-700">{alert.assigned_to || '-'}</td>
                          <td className="py-3 px-3 text-center">
                            <span className={ALERT_STATUS_MAP[alert.status]?.cls || 'badge-blue'}>
                              {ALERT_STATUS_MAP[alert.status]?.label || alert.status}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-xs text-surface-500">{alert.response_deadline || '-'}</td>
                          <td className="py-3 px-3 text-center">
                            <div className="flex items-center justify-center gap-1" onClick={e => e.stopPropagation()}>
                              {(alert.status === 'active') && (
                                <button
                                  onClick={() => { setSelectedAlert(alert); setShowRespondModal(true); }}
                                  className="px-2 py-1 text-xs rounded-lg bg-finance-100 text-finance-700 hover:bg-finance-200 transition-colors"
                                >
                                  响应
                                </button>
                              )}
                              {(alert.status === 'active' || alert.status === 'responded') && (
                                <button
                                  onClick={() => handleEscalate(alert.alert_id)}
                                  className="px-2 py-1 text-xs rounded-lg bg-purple-100 text-purple-700 hover:bg-purple-200 transition-colors"
                                >
                                  升级
                                </button>
                              )}
                              {alert.status === 'responded' && (
                                <button
                                  onClick={() => { setSelectedAlert(alert); setActiveTab('闭环管理'); }}
                                  className="px-2 py-1 text-xs rounded-lg bg-compliance-100 text-compliance-700 hover:bg-compliance-200 transition-colors"
                                >
                                  闭环
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} pageSize={pageSize} />
              </motion.div>
            )}

            {activeTab === '闭环管理' && (
              <motion.div
                key="closure"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="max-w-2xl space-y-5">
                  {selectedAlert && (
                    <div className="p-3 rounded-xl border border-finance-200 bg-finance-50/50">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs text-finance-600">{selectedAlert.alert_id}</span>
                        <span className={LEVEL_MAP[selectedAlert.alert_level]?.cls || 'badge-blue'}>
                          {LEVEL_MAP[selectedAlert.alert_level]?.label || selectedAlert.alert_level}
                        </span>
                        <span className={ALERT_STATUS_MAP[selectedAlert.status]?.cls || 'badge-blue'}>
                          {ALERT_STATUS_MAP[selectedAlert.status]?.label || selectedAlert.status}
                        </span>
                      </div>
                      <p className="text-sm text-surface-700">{selectedAlert.title}</p>
                    </div>
                  )}

                  <div className="p-4 rounded-xl border border-finance-100 bg-finance-50/30">
                    <h3 className="font-semibold text-finance-800 mb-2">双签闭环流程</h3>
                    <p className="text-sm text-surface-500">业务方响应 + 财务BP确认，双签完成闭环</p>
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold text-surface-700 mb-3">业务方响应</h4>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm text-surface-600 mb-1">闭环类型</label>
                        <select
                          value={closureForm.closure_type}
                          onChange={e => setClosureForm(f => ({ ...f, closure_type: e.target.value }))}
                          className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                        >
                          <option value="action_taken">已采取纠正措施</option>
                          <option value="false_alarm">误报</option>
                          <option value="escalated">升级处理</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm text-surface-600 mb-1">处理说明</label>
                        <textarea
                          value={closureForm.action_description}
                          onChange={e => setClosureForm(f => ({ ...f, action_description: e.target.value }))}
                          rows={3}
                          placeholder="请描述已采取的措施..."
                          className={`w-full px-3 py-2 rounded-xl border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-none ${actionDescError ? 'border-alert-300' : 'border-surface-200'}`}
                        />
                        <div className="flex items-center justify-between mt-1">
                          {actionDescError && <p className="text-xs text-alert-600">{actionDescError}</p>}
                          <p className={`text-xs ml-auto ${closureForm.action_description.length >= ACTION_DESC_MIN ? 'text-compliance-600' : 'text-surface-400'}`}>
                            {closureForm.action_description.length}/{ACTION_DESC_MIN}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="border-t border-surface-200 pt-4">
                    <h4 className="text-sm font-semibold text-surface-700 mb-3">财务BP确认</h4>
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-50">
                      <Shield size={16} className="text-finance-500" />
                      <span className="text-sm text-surface-500">等待业务方提交后，财务BP进行确认签核</span>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => selectedAlert && handleRespond(selectedAlert.alert_id)}
                      disabled={!selectedAlert || !isActionDescValid}
                      className={clsx('btn-primary', (!selectedAlert || !isActionDescValid) && 'opacity-50 cursor-not-allowed')}
                    >
                      <MessageSquare size={14} /> 提交响应
                    </button>
                    <button
                      onClick={() => selectedAlert && handleConfirmClosure(selectedAlert.alert_id)}
                      disabled={!selectedAlert || !isActionDescValid}
                      className={clsx('btn-secondary', (!selectedAlert || !isActionDescValid) && 'opacity-50 cursor-not-allowed')}
                    >
                      <CheckCircle2 size={14} /> 确认闭环
                    </button>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === '预警统计' && (
              <motion.div
                key="stats"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="glass-card-static p-5">
                    <h3 className="text-sm font-semibold text-surface-700 mb-4">预警趋势</h3>
                    <ReactECharts
                      option={{
                        tooltip: { trigger: 'axis' as const },
                        grid: { left: 40, right: 20, bottom: 30, top: 20 },
                        xAxis: {
                          type: 'category' as const,
                          data: alertStats?.trend?.map((t: any) => t.period) || ['1月', '2月', '3月', '4月', '5月', '6月'],
                          axisLabel: { color: '#94a3b8', fontSize: 10 },
                          axisLine: { lineStyle: { color: '#e2e8f0' } },
                        },
                        yAxis: {
                          type: 'value' as const,
                          axisLabel: { color: '#94a3b8', fontSize: 10 },
                          splitLine: { lineStyle: { color: '#f1f5f9' } },
                        },
                        series: [
                          {
                            name: '红色',
                            type: 'line' as const,
                            stack: 'total',
                            data: alertStats?.trend?.map((t: any) => t.red) || [2, 3, 1, 4, 2, 3],
                            smooth: true,
                            symbol: 'circle',
                            symbolSize: 4,
                            lineStyle: { width: 2, color: '#ef4444' },
                            itemStyle: { color: '#ef4444' },
                            areaStyle: { color: '#ef444415' },
                          },
                          {
                            name: '橙色',
                            type: 'line' as const,
                            stack: 'total',
                            data: alertStats?.trend?.map((t: any) => t.orange) || [3, 2, 4, 2, 3, 2],
                            smooth: true,
                            symbol: 'circle',
                            symbolSize: 4,
                            lineStyle: { width: 2, color: '#fb923c' },
                            itemStyle: { color: '#fb923c' },
                            areaStyle: { color: '#fb923c15' },
                          },
                          {
                            name: '黄色',
                            type: 'line' as const,
                            stack: 'total',
                            data: alertStats?.trend?.map((t: any) => t.yellow) || [5, 4, 6, 3, 5, 4],
                            smooth: true,
                            symbol: 'circle',
                            symbolSize: 4,
                            lineStyle: { width: 2, color: '#f59e0b' },
                            itemStyle: { color: '#f59e0b' },
                            areaStyle: { color: '#f59e0b15' },
                          },
                          {
                            name: '蓝色',
                            type: 'line' as const,
                            stack: 'total',
                            data: alertStats?.trend?.map((t: any) => t.blue) || [8, 6, 7, 5, 8, 6],
                            smooth: true,
                            symbol: 'circle',
                            symbolSize: 4,
                            lineStyle: { width: 2, color: '#3b82f6' },
                            itemStyle: { color: '#3b82f6' },
                            areaStyle: { color: '#3b82f615' },
                          },
                        ],
                      }}
                      style={{ height: '220px' }}
                      notMerge={true}
                      lazyUpdate={true}
                      showLoading={!alertStats}
                    />
                  </div>
                  <div className="glass-card-static p-5">
                    <h3 className="text-sm font-semibold text-surface-700 mb-4">级别分布</h3>
                    <ReactECharts
                      option={{
                        tooltip: { trigger: 'item' as const },
                        legend: {
                          orient: 'vertical' as const,
                          right: 10,
                          top: 'center',
                          textStyle: { color: '#94a3b8', fontSize: 11 },
                        },
                        series: [{
                          type: 'pie' as const,
                          radius: ['45%', '70%'],
                          center: ['35%', '50%'],
                          avoidLabelOverlap: false,
                          label: { show: false },
                          emphasis: { label: { show: true, fontWeight: 'bold' } },
                          data: [
                            { value: alertStats?.by_level?.red ?? levelCounts.red, name: '红色', itemStyle: { color: '#ef4444' } },
                            { value: alertStats?.by_level?.orange ?? levelCounts.orange, name: '橙色', itemStyle: { color: '#fb923c' } },
                            { value: alertStats?.by_level?.yellow ?? levelCounts.yellow, name: '黄色', itemStyle: { color: '#f59e0b' } },
                            { value: alertStats?.by_level?.blue ?? levelCounts.blue, name: '蓝色', itemStyle: { color: '#3b82f6' } },
                          ],
                        }],
                      }}
                      style={{ height: '220px' }}
                      notMerge={true}
                      lazyUpdate={true}
                      showLoading={!alertStats}
                    />
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === '疲劳度运营' && (
              <motion.div
                key="fatigue"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <FatigueDashboard initialMonths={3} />
              </motion.div>
            )}

            {/* ── v12.1: 阶段 5 — AI 智能预警 ─────────── */}
            {activeTab === 'AI智能预警' && (
              <motion.div
                key="ai-alert"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* 控制条 */}
                <div className="glass-card p-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Brain size={16} className="text-finance-600" />
                      <span className="text-sm font-semibold text-finance-800">AI 智能预警引擎</span>
                    </div>
                    <input
                      type="text"
                      value={selectedAlertId ?? ''}
                      onChange={e => setSelectedAlertId(e.target.value || null)}
                      placeholder="输入预警 ID 单项诊断（可选）"
                      className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-sm w-56"
                    />
                    <button
                      onClick={() => selectedAlertId && diagnoseAlert(selectedAlertId)}
                      disabled={!selectedAlertId?.trim() || aiLoading}
                      className={clsx(
                        'px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1',
                        'bg-brand-50 text-brand-700 border border-brand-200 hover:bg-brand-100',
                        (!selectedAlertId?.trim() || aiLoading) && 'opacity-50 cursor-not-allowed'
                      )}
                    >
                      <Activity size={14} /> 单项诊断
                    </button>
                    <button
                      onClick={loadAlertAi}
                      disabled={aiLoading}
                      className={clsx(
                        'ml-auto px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1',
                        'bg-gradient-to-r from-finance-600 to-brand-600 text-white hover:opacity-90',
                        aiLoading && 'opacity-50 cursor-not-allowed'
                      )}
                    >
                      {aiLoading ? <><Loader2 size={14} className="animate-spin" /> 扫描中…</> : <><Sparkles size={14} /> 一键扫描 3 项 AI</>}
                    </button>
                  </div>
                </div>

                {/* 三联卡片：疲劳 / 聚类 / 去重 */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* 疲劳检测 */}
                  {aiFatigue && (
                    <div className="glass-card p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Activity size={14} className="text-warning-600" />
                        <span className="text-sm font-semibold text-finance-800">疲劳检测</span>
                        <span className="ml-auto text-[10px] text-surface-500">{aiFatigue.period_days} 天</span>
                      </div>
                      <div className="text-center py-2">
                        <p className="text-3xl font-bold text-warning-700 font-mono">{aiFatigue.fatigue_rule_count}</p>
                        <p className="text-[10px] text-surface-500">疲劳规则</p>
                      </div>
                      {aiFatigue.fatigue_rules?.length > 0 ? (
                        <div className="space-y-1 mt-2">
                          {aiFatigue.fatigue_rules.slice(0, 3).map((r: any) => (
                            <div key={r.rule_id} className="p-2 rounded bg-warning-50/50 border border-warning-200">
                              <div className="flex items-center gap-1">
                                <span className="text-[10px] font-mono text-surface-700">{r.rule_id}</span>
                                <span className="ml-auto text-[10px] px-1 py-0.5 rounded bg-warning-200 text-warning-800">{r.fatigue_level}</span>
                              </div>
                              <p className="text-[10px] text-warning-700 mt-0.5">{r.alert_count} 条 / {r.period_days} 天</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-[10px] text-compliance-700 text-center py-2">✓ 无疲劳规则</p>
                      )}
                    </div>
                  )}

                  {/* 告警聚类 */}
                  {aiCluster && (
                    <div className="glass-card p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Layers size={14} className="text-finance-600" />
                        <span className="text-sm font-semibold text-finance-800">告警聚类</span>
                        <span className="ml-auto text-[10px] text-surface-500">{aiCluster.period_days} 天</span>
                      </div>
                      <div className="grid grid-cols-2 gap-1 text-center py-1">
                        <div>
                          <p className="text-xl font-bold text-finance-700 font-mono">{aiCluster.cluster_count}</p>
                          <p className="text-[10px] text-surface-500">聚类数</p>
                        </div>
                        <div>
                          <p className="text-xl font-bold text-alert-700 font-mono">{aiCluster.systemic_risk_count}</p>
                          <p className="text-[10px] text-surface-500">系统风险</p>
                        </div>
                      </div>
                      {aiCluster.clusters?.length > 0 ? (
                        <div className="space-y-1 mt-2">
                          {aiCluster.clusters.slice(0, 3).map((c: any, i: number) => (
                            <div key={i} className={clsx(
                              'p-2 rounded border',
                              c.is_systemic ? 'bg-alert-50 border-alert-200' : 'bg-surface-50 border-surface-200'
                            )}>
                              <div className="flex items-center gap-1">
                                <span className="text-[10px] font-mono text-surface-700 truncate">{c.budget_id}</span>
                                {c.is_systemic && <span className="text-[10px]">🚨</span>}
                                <span className="ml-auto text-[10px] font-mono font-semibold text-finance-700">{c.alert_count}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-[10px] text-surface-400 text-center py-2">无聚类</p>
                      )}
                    </div>
                  )}

                  {/* 重复去重 */}
                  {aiDedup && (
                    <div className="glass-card p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Copy size={14} className="text-brand-600" />
                        <span className="text-sm font-semibold text-finance-800">重复去重</span>
                        <span className="ml-auto text-[10px] text-surface-500">{aiDedup.window_hours}h</span>
                      </div>
                      <div className="text-center py-2">
                        <p className="text-3xl font-bold text-brand-700 font-mono">{aiDedup.deduplicated_count}</p>
                        <p className="text-[10px] text-surface-500">可去重 / {aiDedup.total_alerts} 总</p>
                      </div>
                      <p className="text-[10px] text-surface-500 text-center mt-1">
                        {aiDedup.dedup_groups} 个重复组，{aiDedup.deduplicated_count} 条可合并
                      </p>
                      <p className="text-[10px] text-compliance-700 text-center mt-2">{aiDedup.recommendation}</p>
                    </div>
                  )}
                </div>

                {/* 单项诊断：优先级 + 升级路径 */}
                {(aiPriority || aiEscalation) && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {aiPriority && (
                      <div className="glass-card p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Shield size={14} className="text-alert-600" />
                          <span className="text-sm font-semibold text-finance-800">AI 优先级</span>
                          <span className="ml-auto text-xs font-mono font-bold text-alert-700">{aiPriority.priority_score}</span>
                        </div>
                        <div className={clsx(
                          'p-3 rounded-lg text-center mb-3',
                          aiPriority.priority_score >= 80 ? 'bg-alert-100' :
                          aiPriority.priority_score >= 60 ? 'bg-warning-100' :
                          aiPriority.priority_score >= 40 ? 'bg-brand-100' : 'bg-compliance-100'
                        )}>
                          <p className={clsx(
                            'text-lg font-bold',
                            aiPriority.priority_score >= 80 ? 'text-alert-800' :
                            aiPriority.priority_score >= 60 ? 'text-warning-800' :
                            aiPriority.priority_score >= 40 ? 'text-brand-800' : 'text-compliance-800'
                          )}>
                            {aiPriority.priority}
                          </p>
                        </div>
                        <div className="space-y-1.5">
                          {Object.entries(aiPriority.dimensions || {}).map(([k, v]: any) => {
                            const labelMap: Record<string, string> = {
                              告警级别: '级别', 金额影响: '金额', 战略对齐: '战略', 频率: '频率', 紧急度: '紧急',
                            };
                            return (
                              <div key={k}>
                                <div className="flex items-center justify-between text-[10px] mb-0.5">
                                  <span className="text-surface-600">{labelMap[k] || k}</span>
                                  <span className="font-mono font-semibold">{v}</span>
                                </div>
                                <div className="h-1 bg-surface-100 rounded-full overflow-hidden">
                                  <div className={clsx(
                                    'h-full rounded-full',
                                    v >= 70 ? 'bg-compliance-500' : v >= 40 ? 'bg-warning-500' : 'bg-alert-500'
                                  )} style={{ width: `${v}%` }} />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {aiEscalation && (
                      <div className="glass-card p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <RouteIcon size={14} className="text-brand-600" />
                          <span className="text-sm font-semibold text-finance-800">AI 升级路径</span>
                          <span className="ml-auto text-[10px] text-surface-500">
                            当前 {aiEscalation.current_level} / 历史均值 {aiEscalation.historical_avg_hours}h
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {aiEscalation.escalation_chain?.map((s: any, i: number) => (
                            <div key={i} className="flex items-center gap-1.5">
                              <div className="text-center px-2 py-1.5 rounded-lg bg-brand-50 border border-brand-200">
                                <p className="text-[10px] font-semibold text-brand-800">{s.level}</p>
                                <p className="text-[9px] text-brand-600">{s.role}</p>
                                <p className="text-[10px] font-mono text-brand-700">{s.sla_hours}h</p>
                              </div>
                              {i < aiEscalation.escalation_chain.length - 1 && (
                                <ChevronRight size={12} className="text-surface-400" />
                              )}
                            </div>
                          ))}
                        </div>
                        <p className="text-[10px] text-surface-600 mt-3 leading-relaxed">
                          {aiEscalation.recommendation}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* v12.2: AI 解释面板 + 根因可视化 */}
                {(aiPriority || aiEscalation) && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <AiExplainPanel
                      title="5 维度优先级评分引擎"
                      summary="AI 综合 5 个维度对单条预警打分，决定处理顺序"
                      model="PriorityScorer v1"
                      caliber={aiPriority?.caliber || '管理口径'}
                      confidence={aiPriority?.confidence ?? (aiPriority?.priority_score ? Math.min(95, aiPriority.priority_score + 5) : 75)}
                      ruleIds={['SR-PRIORITY-01', 'SR-PRIORITY-02']}
                      inputs={[
                        `告警级别：${aiPriority?.dimensions?.['告警级别'] ?? '-'} / 100`,
                        `金额影响：${aiPriority?.dimensions?.['金额影响'] ?? '-'} / 100`,
                        `战略对齐：${aiPriority?.dimensions?.['战略对齐'] ?? '-'} / 100`,
                        `触发频率：${aiPriority?.dimensions?.['频率'] ?? '-'} / 100`,
                        `紧急度：${aiPriority?.dimensions?.['紧急度'] ?? '-'} / 100`,
                      ]}
                      steps={[
                        { step: '级别加权', detail: '红/橙/黄/蓝 → 100/70/40/10', weight: 0.3 },
                        { step: '金额影响', detail: '按金额区间对数化映射到 0-100', weight: 0.25 },
                        { step: '战略对齐', detail: 'L1 关联的战略主题权重加成', weight: 0.2 },
                        { step: '频率衰减', detail: '近 7 日同主题触发次数', weight: 0.15 },
                        { step: '紧急度', detail: '剩余 SLA 时间倒计', weight: 0.1 },
                      ]}
                      conclusion={aiPriority ? `综合得分 ${aiPriority.priority_score} 分 → 建议处理等级：${aiPriority.priority}` : undefined}
                    />

                    <RootCauseTree
                      title="5 层根因下钻"
                      topic={aiEscalation?.current_alert_type || '当前预警根因'}
                      layerLabels={['L1 科目', 'L2 科目', '责任中心', '趋势', '同业']}
                      nodes={[
                        {
                          label: aiPriority?.l1_code || 'L1-000',
                          value: '科目',
                          tone: 'finance',
                          reason: aiPriority?.l1_reason || '预算执行偏离',
                          children: [
                            { label: 'L2-业务招待', value: '¥38万', tone: 'warning' },
                            { label: 'L2-差旅', value: '¥26万', tone: 'brand' },
                          ],
                        },
                        {
                          label: aiPriority?.center || '财经中心',
                          value: '中心',
                          tone: 'brand',
                          children: [
                            { label: '本月核销率 142%', tone: 'alert' },
                            { label: '环比 +28%', tone: 'warning' },
                          ],
                        },
                        {
                          label: '趋势',
                          value: '上升',
                          tone: 'alert',
                          children: [
                            { label: '近 3 月连升', tone: 'alert' },
                            { label: '预测月末 ¥210万', tone: 'warning' },
                          ],
                        },
                        {
                          label: '同业',
                          value: '+15pp',
                          tone: 'warning',
                          children: [
                            { label: '高于行业 P50', tone: 'alert' },
                            { label: '仅低于 P90', tone: 'brand' },
                          ],
                        },
                      ]}
                      caption="L1 → L2 → Center → Trend → Peer"
                    />
                  </div>
                )}

                {!aiFatigue && !aiCluster && !aiDedup && !aiLoading && (
                  <div className="glass-card-static p-10 text-center text-surface-400">
                    <Brain size={40} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">点击「一键扫描 3 项 AI」启动智能预警分析</p>
                    <p className="text-xs mt-2">疲劳检测 / 告警聚类 / 重复去重</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <AnimatePresence>
        {showRespondModal && selectedAlert && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => setShowRespondModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-md mx-4"
              onClick={e => e.stopPropagation()}
            >
              <h3 className="text-lg font-semibold text-finance-800 mb-4">预警响应</h3>
              <p className="text-sm text-surface-600 mb-3">{selectedAlert.title || selectedAlert.alert_id}</p>
              <textarea
                value={closureForm.action_description}
                onChange={e => setClosureForm(f => ({ ...f, action_description: e.target.value }))}
                rows={3}
                placeholder="请描述响应措施（至少20个字符）..."
                className={`w-full px-3 py-2 rounded-xl border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-none mb-1 ${actionDescError ? 'border-alert-300' : 'border-surface-200'}`}
              />
              <div className="flex items-center justify-between mb-4">
                {actionDescError && <p className="text-xs text-alert-600">{actionDescError}</p>}
                <p className={`text-xs ml-auto ${closureForm.action_description.length >= ACTION_DESC_MIN ? 'text-compliance-600' : 'text-surface-400'}`}>
                  {closureForm.action_description.length}/{ACTION_DESC_MIN}
                </p>
              </div>
              <div className="flex gap-3 justify-end">
                <button onClick={() => setShowRespondModal(false)} className="btn-secondary">取消</button>
                <button
                  onClick={() => handleRespond(selectedAlert.alert_id)}
                  disabled={!isActionDescValid}
                  className={clsx('btn-primary', !isActionDescValid && 'opacity-50 cursor-not-allowed')}
                >
                  <CheckCircle2 size={14} /> 提交响应
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AlertDetailDrawer
        alertId={selectedAlertId}
        onClose={() => setSelectedAlertId(null)}
      />
    </div>
  );
}
