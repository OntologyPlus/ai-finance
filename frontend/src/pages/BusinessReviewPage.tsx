import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  Presentation,
  FileCheck,
  Target,
  BarChart3,
  Plus,
  Search,
  Clock,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAppStore } from '../store';
import ResolutionTracker, { Resolution } from '../components/review/ResolutionTracker';

const TABS = ['议程生成', '决议管理', '决议闭环', '跨中心对比'] as const;

const PRIORITY_MAP: Record<string, { label: string; cls: string }> = {
  urgent: { label: '紧急', cls: 'badge-red' },
  important: { label: '重要', cls: 'badge-amber' },
  normal: { label: '常规', cls: 'badge-blue' },
};

const RISK_FLAG_MAP: Record<string, { label: string; cls: string }> = {
  none: { label: '无', cls: 'badge-green' },
  low: { label: '低', cls: 'badge-blue' },
  medium: { label: '中', cls: 'badge-amber' },
  high: { label: '高', cls: 'badge-red' },
};

// Inline API helpers
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function getToken(): string | null {
  return localStorage.getItem('auth_token');
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
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
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }
  return response.json();
}

// v9.0 C: MOCK 数据已废弃，全部接后端 API 真实数据

function formatAmount(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '¥ 0';
  if (n >= 10000) return `¥ ${(n / 10000).toFixed(1)}万`;
  return `¥ ${n.toLocaleString()}`;
}

export default function BusinessReviewPage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('议程生成');
  const addToast = useAppStore((s) => s.addToast);

  // Tab 1 - Agenda
  const [meetingType, setMeetingType] = useState<'monthly' | 'quarterly'>('monthly');
  const [agendaPeriod, setAgendaPeriod] = useState('');
  const [agendaResult, setAgendaResult] = useState<any>(null);
  const [agendaLoading, setAgendaLoading] = useState(false);

  // Tab 2 - Resolutions
  const [meetingId, setMeetingId] = useState('');
  const [resolutions, setResolutions] = useState<any[]>([]);
  const [resolutionForm, setResolutionForm] = useState({ content: '', owner: '', deadline: '' });
  const [resolutionLoading, setResolutionLoading] = useState(false);

  // Tab 3 - Tracking
  const [trackResolutionId, setTrackResolutionId] = useState('');
  const [trackProgress, setTrackProgress] = useState(0);
  const [trackRiskFlag, setTrackRiskFlag] = useState<string>('none');
  const [trackingResult, setTrackingResult] = useState<any>(null);
  const [trackLoading, setTrackLoading] = useState(false);

  // Tab 4 - Comparison
  const [comparePeriod, setComparePeriod] = useState('');
  const [compareCenterIds, setCompareCenterIds] = useState('');
  const [comparisonResult, setComparisonResult] = useState<any>(null);
  const [compareLoading, setCompareLoading] = useState(false);

  const handleGenerateAgenda = async () => {
    setAgendaLoading(true);
    try {
      const res = await apiRequest<any>('/api/business-review/generate-agenda', {
        method: 'POST',
        body: JSON.stringify({ meeting_type: meetingType, period: agendaPeriod || undefined }),
      });
      setAgendaResult(res.data || res);
    } catch {
      // v9.0 C: 不再回退到 MOCK
      setAgendaResult(null);
      addToast({ type: 'warning', title: '议程生成服务暂不可用', message: '请检查后端连接' });
    } finally {
      setAgendaLoading(false);
    }
  };

  const handleFetchResolutions = async () => {
    if (!meetingId.trim()) {
      addToast({ type: 'error', title: '参数缺失', message: '请输入会议ID' });
      return;
    }
    setResolutionLoading(true);
    try {
      const res = await apiRequest<any>(`/api/business-review/resolutions?meeting_id=${encodeURIComponent(meetingId)}`);
      setResolutions(res.data || []);
    } catch {
      // v9.0 C: 不再回退到 MOCK
      setResolutions([]);
      addToast({ type: 'warning', title: '决议服务暂不可用', message: '请检查后端连接' });
    } finally {
      setResolutionLoading(false);
    }
  };

  const handleRecordResolution = async () => {
    if (!meetingId.trim() || !resolutionForm.content.trim()) {
      addToast({ type: 'error', title: '参数缺失', message: '请输入会议ID和决议内容' });
      return;
    }
    try {
      await apiRequest<any>('/api/business-review/resolutions', {
        method: 'POST',
        body: JSON.stringify({ meeting_id: meetingId, ...resolutionForm }),
      });
      addToast({ type: 'success', title: '操作成功', message: '决议已录入' });
      setResolutionForm({ content: '', owner: '', deadline: '' });
      handleFetchResolutions();
    } catch {
      addToast({ type: 'warning', title: '决议录入失败', message: '请检查后端连接或稍后重试' });
    }
  };

  const handleUpdateTracking = async () => {
    if (!trackResolutionId.trim()) {
      addToast({ type: 'error', title: '参数缺失', message: '请输入决议ID' });
      return;
    }
    setTrackLoading(true);
    try {
      const res = await apiRequest<any>('/api/business-review/tracking', {
        method: 'POST',
        body: JSON.stringify({ resolution_id: trackResolutionId, progress: trackProgress, risk_flag: trackRiskFlag }),
      });
      setTrackingResult(res.data || res);
      addToast({ type: 'success', title: '操作成功', message: '追踪信息已更新' });
    } catch {
      // v9.0 C: 不再回退到 MOCK
      setTrackingResult(null);
      addToast({ type: 'warning', title: '追踪服务暂不可用', message: '请检查后端连接' });
    } finally {
      setTrackLoading(false);
    }
  };

  const handleCompare = async () => {
    setCompareLoading(true);
    try {
      const centerIds = compareCenterIds.split(',').map(s => s.trim()).filter(Boolean);
      const res = await apiRequest<any>('/api/business-review/compare', {
        method: 'POST',
        body: JSON.stringify({ period: comparePeriod || undefined, center_ids: centerIds.length > 0 ? centerIds : undefined }),
      });
      setComparisonResult(res.data || res);
    } catch {
      // v9.0 C: 不再回退到 MOCK
      setComparisonResult(null);
      addToast({ type: 'warning', title: '对比服务暂不可用', message: '请检查后端连接' });
    } finally {
      setCompareLoading(false);
    }
  };

  const getComparisonBarOption = (centers: any[]) => ({
    tooltip: { trigger: 'axis' as const },
    grid: { left: 80, right: 20, bottom: 30, top: 20 },
    xAxis: {
      type: 'value' as const,
      max: 100,
      axisLabel: { color: '#94a3b8', fontSize: 10, formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    yAxis: {
      type: 'category' as const,
      data: centers.map(c => c.center_name || c.center_id),
      axisLabel: { color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
    },
    series: [{
      type: 'bar' as const,
      data: centers.map(c => ({
        value: c.execution_rate,
        itemStyle: {
          color: c.execution_rate >= 80 ? '#22c55e' : c.execution_rate >= 60 ? '#3b82f6' : c.execution_rate >= 40 ? '#f59e0b' : '#ef4444',
          borderRadius: [0, 4, 4, 0],
        },
      })),
      barWidth: 20,
      label: {
        show: true,
        position: 'right' as const,
        formatter: '{c}%',
        fontSize: 11,
        color: '#64748b',
      },
    }],
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">经营分析会</h1>
        <p className="text-sm text-surface-400 mt-1">一报一会·三聚焦·决议闭环</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: '议程生成', value: '智能编排', gradient: 'from-brand-500 to-finance-600', icon: <Presentation size={16} /> },
          { label: '决议管理', value: '闭环追踪', gradient: 'from-finance-500 to-finance-700', icon: <FileCheck size={16} /> },
          { label: '决议追踪', value: '实时监控', gradient: 'from-compliance-500 to-health-600', icon: <Target size={16} /> },
          { label: '跨中心对比', value: '多维分析', gradient: 'from-warning-500 to-alert-500', icon: <BarChart3 size={16} /> },
        ].map(card => (
          <div key={card.label} className="glass-card p-5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-surface-400">{card.icon}</span>
              <p className="metric-label">{card.label}</p>
            </div>
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
                  layoutId="bizReviewTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === '议程生成' && (
              <motion.div
                key="agenda"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="max-w-2xl space-y-5">
                  <div className="flex items-end gap-3">
                    <div>
                      <label className="block text-sm font-medium text-surface-700 mb-1">会议类型</label>
                      <select
                        value={meetingType}
                        onChange={e => setMeetingType(e.target.value as 'monthly' | 'quarterly')}
                        className="px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      >
                        <option value="monthly">月度</option>
                        <option value="quarterly">季度</option>
                      </select>
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-surface-700 mb-1">周期</label>
                      <input
                        type="text"
                        value={agendaPeriod}
                        onChange={e => setAgendaPeriod(e.target.value)}
                        placeholder="如 2026-06"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <button
                      onClick={handleGenerateAgenda}
                      disabled={agendaLoading}
                      className={clsx('btn-primary', agendaLoading && 'opacity-50 cursor-not-allowed')}
                    >
                      <Presentation size={14} /> {agendaLoading ? '生成中...' : '生成议程'}
                    </button>
                  </div>

                  {agendaResult && (
                    <div className="glass-card-static p-5 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Presentation size={18} className="text-finance-600" />
                          <span className="font-semibold text-finance-800">会议议程</span>
                          <span className="text-xs text-surface-400">
                            {agendaResult.meeting_type === 'monthly' ? '月度' : '季度'} · {agendaResult.period}
                          </span>
                        </div>
                      </div>

                      <div className="space-y-2">
                        {(agendaResult.agenda_items || []).map((item: any, idx: number) => (
                          <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-surface-50">
                            <div className="w-6 h-6 rounded-full bg-finance-100 text-finance-700 flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5">
                              {item.order || idx + 1}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-medium text-surface-800">{item.title}</span>
                                <span className={PRIORITY_MAP[item.priority]?.cls || 'badge-blue'}>
                                  {PRIORITY_MAP[item.priority]?.label || item.priority}
                                </span>
                              </div>
                              <p className="text-xs text-surface-500">{item.detail}</p>
                            </div>
                            <div className="flex items-center gap-1 text-xs text-surface-400 flex-shrink-0">
                              <Clock size={10} />
                              <span>{item.duration}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === '决议管理' && (
              <motion.div
                key="resolutions"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="max-w-3xl space-y-5">
                  <div className="flex items-end gap-3">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-surface-700 mb-1">会议 ID</label>
                      <input
                        type="text"
                        value={meetingId}
                        onChange={e => setMeetingId(e.target.value)}
                        placeholder="请输入会议编号，如 MTG-001"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <button
                      onClick={handleFetchResolutions}
                      disabled={resolutionLoading}
                      className={clsx('btn-secondary', resolutionLoading && 'opacity-50 cursor-not-allowed')}
                    >
                      <Search size={14} /> {resolutionLoading ? '查询中...' : '查询'}
                    </button>
                  </div>

                  {/* Resolution form */}
                  <div className="glass-card-static p-5 space-y-3">
                    <h3 className="text-sm font-semibold text-finance-800">录入新决议</h3>
                    <div>
                      <label className="block text-sm font-medium text-surface-700 mb-1">决议内容 <span className="text-alert-500">*</span></label>
                      <textarea
                        value={resolutionForm.content}
                        onChange={e => setResolutionForm(f => ({ ...f, content: e.target.value }))}
                        rows={2}
                        placeholder="请输入决议内容..."
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-none"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">负责人</label>
                        <input
                          type="text"
                          value={resolutionForm.owner}
                          onChange={e => setResolutionForm(f => ({ ...f, owner: e.target.value }))}
                          placeholder="请输入负责人"
                          className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-surface-700 mb-1">截止日期</label>
                        <input
                          type="date"
                          value={resolutionForm.deadline}
                          onChange={e => setResolutionForm(f => ({ ...f, deadline: e.target.value }))}
                          className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                        />
                      </div>
                    </div>
                    <button
                      onClick={handleRecordResolution}
                      disabled={!resolutionForm.content.trim()}
                      className={clsx('btn-primary', !resolutionForm.content.trim() && 'opacity-50 cursor-not-allowed')}
                    >
                      <Plus size={14} /> 录入决议
                    </button>
                  </div>

                  {/* Resolution list */}
                  {resolutions.length > 0 && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-surface-200/60">
                            <th className="text-left py-3 px-3 metric-label">决议ID</th>
                            <th className="text-left py-3 px-3 metric-label">内容</th>
                            <th className="text-left py-3 px-3 metric-label">负责人</th>
                            <th className="text-left py-3 px-3 metric-label">截止日期</th>
                            <th className="text-center py-3 px-3 metric-label">状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {resolutions.map((r: any) => (
                            <tr key={r.resolution_id} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                              <td className="py-3 px-3 font-mono text-xs text-finance-700">{r.resolution_id}</td>
                              <td className="py-3 px-3 text-surface-800 max-w-xs truncate">{r.content}</td>
                              <td className="py-3 px-3 text-surface-600">{r.owner || '-'}</td>
                              <td className="py-3 px-3 text-surface-500 text-xs">{r.deadline || '-'}</td>
                              <td className="py-3 px-3 text-center">
                                <span className={
                                  r.status === 'completed' ? 'badge-green' :
                                  r.status === 'in_progress' ? 'badge-amber' : 'badge-blue'
                                }>
                                  {r.status === 'completed' ? '已完成' : r.status === 'in_progress' ? '进行中' : '待执行'}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === '决议闭环' && (
              <motion.div
                key="tracking"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* v9.0 E.5：闭环看板 + 多决议追踪 */}
                <ResolutionTracker
                  resolutions={resolutions as Resolution[] | null}
                  onTrack={async (id, progress, risk) => {
                    try {
                      await apiRequest<any>(`/api/business-review/resolutions/${id}/track`, {
                        method: 'POST',
                        body: JSON.stringify({ progress, risk_flag: risk }),
                      });
                      addToast({ type: 'success', title: '更新成功', message: `决议 ${id} 进度已更新至 ${progress}%` });
                      setResolutions(prev => prev.map((r: any) => r.resolution_id === id ? { ...r, progress, risk_flag: risk } : r));
                    } catch {
                      setResolutions(prev => prev.map((r: any) => r.resolution_id === id ? { ...r, progress, risk_flag: risk } : r));
                      addToast({ type: 'info', title: '已本地更新', message: 'API 不可用，进度已本地暂存' });
                    }
                  }}
                  loading={resolutionLoading}
                />
              </motion.div>
            )}

            {activeTab === '跨中心对比' && (
              <motion.div
                key="comparison"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="space-y-5">
                  <div className="flex items-end gap-3 max-w-2xl">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-surface-700 mb-1">周期</label>
                      <input
                        type="text"
                        value={comparePeriod}
                        onChange={e => setComparePeriod(e.target.value)}
                        placeholder="如 2026-06"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-surface-700 mb-1">中心ID（逗号分隔）</label>
                      <input
                        type="text"
                        value={compareCenterIds}
                        onChange={e => setCompareCenterIds(e.target.value)}
                        placeholder="如 C-001,C-002"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <button
                      onClick={handleCompare}
                      disabled={compareLoading}
                      className={clsx('btn-primary', compareLoading && 'opacity-50 cursor-not-allowed')}
                    >
                      <BarChart3 size={14} /> {compareLoading ? '对比中...' : '对比'}
                    </button>
                  </div>

                  {comparisonResult && (
                    <div className="space-y-4">
                      {/* Comparison table */}
                      <div className="glass-card-static p-5">
                        <h3 className="text-sm font-semibold text-finance-800 mb-3">跨中心对比</h3>
                        <div className="overflow-x-auto">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="border-b border-surface-200/60">
                                <th className="text-left py-3 px-3 metric-label">中心</th>
                                <th className="text-right py-3 px-3 metric-label">总预算</th>
                                <th className="text-right py-3 px-3 metric-label">已使用</th>
                                <th className="text-center py-3 px-3 metric-label">执行率</th>
                                <th className="text-center py-3 px-3 metric-label">开放预警</th>
                                <th className="text-center py-3 px-3 metric-label">红色预警</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(comparisonResult.centers || []).map((c: any) => (
                                <tr key={c.center_id} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                                  <td className="py-3 px-3">
                                    <div>
                                      <span className="font-medium text-surface-800">{c.center_name || c.center_id}</span>
                                      <span className="text-[10px] text-surface-400 ml-1.5 font-mono">{c.center_id}</span>
                                    </div>
                                  </td>
                                  <td className="py-3 px-3 text-right font-mono">{formatAmount(c.total_budget)}</td>
                                  <td className="py-3 px-3 text-right font-mono">{formatAmount(c.total_used)}</td>
                                  <td className="py-3 px-3 text-center">
                                    <span className={clsx(
                                      'font-bold',
                                      c.execution_rate >= 80 ? 'text-compliance-600' :
                                      c.execution_rate >= 60 ? 'text-finance-700' :
                                      c.execution_rate >= 40 ? 'text-warning-600' : 'text-alert-600'
                                    )}>
                                      {c.execution_rate}%
                                    </span>
                                  </td>
                                  <td className="py-3 px-3 text-center">
                                    <span className={c.open_alerts > 3 ? 'badge-amber' : 'badge-blue'}>{c.open_alerts}</span>
                                  </td>
                                  <td className="py-3 px-3 text-center">
                                    <span className={c.red_alerts > 0 ? 'badge-red' : 'badge-green'}>{c.red_alerts}</span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {/* Bar chart */}
                      <div className="glass-card-static p-5">
                        <h3 className="text-sm font-semibold text-finance-800 mb-4">执行率对比</h3>
                        <ReactECharts
                          option={getComparisonBarOption(comparisonResult.centers || [])}
                          style={{ height: '240px' }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
