import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FlaskConical,
  ArrowRight,
  ChevronRight,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Search,
  TrendingUp,
  Wallet,
  Layers,
  Play,
  Inbox,
  RefreshCw,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAppStore } from '../store';
import { pipelineApi } from '../services/api';
import PipelineValueMatrix, { type ValueMatrix } from '../components/pipeline/PipelineValueMatrix';
import GoNoGoPanel, { type GoNoGoDecision } from '../components/pipeline/GoNoGoPanel';

const TABS = ['管线总览', '管线推进', '管线状态', '管线认知'] as const;

const PIPELINE_STAGES = ['发现', '临床前', 'I期临床', 'II期临床', 'III期临床', '注册申报', '上市'] as const;

const STAGE_ICONS: Record<string, React.ReactNode> = {
  '发现': <Search size={14} />,
  '临床前': <FlaskConical size={14} />,
  'I期临床': <Play size={14} />,
  'II期临床': <TrendingUp size={14} />,
  'III期临床': <Layers size={14} />,
  '注册申报': <CheckCircle2 size={14} />,
  '上市': <Wallet size={14} />,
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

// v9.0 C: 不再使用 MOCK 数据，全部接后端 API 真实数据
// 当 API 不可用时显示空状态而非 mock

function formatAmount(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '¥ 0';
  if (n >= 10000) return `¥ ${(n / 10000).toFixed(1)}万`;
  return `¥ ${n.toLocaleString()}`;
}

export default function PipelinePage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('管线总览');
  const addToast = useAppStore((s) => s.addToast);

  // Tab 1 - Overview
  const [overview, setOverview] = useState<any>(null);
  const [overviewLoading, setOverviewLoading] = useState(true);

  // Tab 2 - Advance
  const [advancePipelineId, setAdvancePipelineId] = useState('');
  const [targetStage, setTargetStage] = useState<string>('');
  const [goNoGo, setGoNoGo] = useState<'go' | 'no-go'>('go');
  const [advanceResult, setAdvanceResult] = useState<any>(null);
  const [advanceLoading, setAdvanceLoading] = useState(false);

  // Tab 3 - Status
  const [statusPipelineId, setStatusPipelineId] = useState('');
  const [pipelineStatus, setPipelineStatus] = useState<any>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  // ── Module E.3：管线认知状态 ──
  const [cognitiveSubTab, setCognitiveSubTab] = useState<'matrix' | 'gonogo'>('matrix');
  const [valueMatrix, setValueMatrix] = useState<ValueMatrix | null>(null);
  const [matrixLoading, setMatrixLoading] = useState(false);
  const [pipelines, setPipelines] = useState<any[]>([]);
  const [goNoGoId, setGoNoGoId] = useState<string>('');
  const [goNoGoDecision, setGoNoGoDecision] = useState<GoNoGoDecision | null>(null);
  const [goNoGoLoading, setGoNoGoLoading] = useState(false);

  const fetchOverview = async () => {
    try {
      const res = await apiRequest<any>('/api/pipeline/overview');
      setOverview(res.data || res);
    } catch (e: any) {
      // v9.0 C: 不再回退到 MOCK
      addToast({ type: 'warning', title: '管线总览加载失败', message: e?.message || '请检查后端连接' });
      setOverview(null);
    } finally {
      setOverviewLoading(false);
    }
  };

  useState(() => { fetchOverview(); });

  const handleAdvance = async () => {
    if (!advancePipelineId.trim() || !targetStage) {
      addToast({ type: 'error', title: '参数缺失', message: '请输入管线ID并选择目标阶段' });
      return;
    }
    setAdvanceLoading(true);
    try {
      const res = await apiRequest<any>('/api/pipeline/advance', {
        method: 'POST',
        body: JSON.stringify({ pipeline_id: advancePipelineId, target_stage: targetStage, go_no_go: goNoGo }),
      });
      setAdvanceResult(res.data || res);
      addToast({ type: 'success', title: '操作成功', message: '管线推进已执行' });
    } catch (e: any) {
      // v9.0 C: 不再回退到 MOCK
      setAdvanceResult(null);
      addToast({ type: 'warning', title: '推进服务暂不可用', message: e?.message || '请检查后端连接' });
    } finally {
      setAdvanceLoading(false);
    }
  };

  const handleQueryStatus = async () => {
    if (!statusPipelineId.trim()) {
      addToast({ type: 'error', title: '参数缺失', message: '请输入管线ID' });
      return;
    }
    setStatusLoading(true);
    try {
      const res = await apiRequest<any>(`/api/pipeline/status?pipeline_id=${encodeURIComponent(statusPipelineId)}`);
      setPipelineStatus(res.data || res);
    } catch (e: any) {
      // v9.0 C: 不再回退到 MOCK
      setPipelineStatus(null);
      addToast({ type: 'warning', title: '状态查询暂不可用', message: e?.message || '请检查后端连接' });
    } finally {
      setStatusLoading(false);
    }
  };

  // ── Module E.3：认知数据加载 ──
  const fetchPipelinesList = async () => {
    try {
      const res: any = await pipelineApi.list();
      if (res?.success && res.data) {
        setPipelines(res.data);
        return res.data as any[];
      }
      setPipelines([]);
      return [];
    } catch (e: any) {
      addToast({ type: 'error', title: '管线列表加载失败', message: e?.message || '未知错误' });
      setPipelines([]);
      return [];
    }
  };

  const fetchValueMatrix = async () => {
    setMatrixLoading(true);
    try {
      const res: any = await pipelineApi.getValueMatrix();
      if (res?.success && res.data) {
        setValueMatrix(res.data);
      } else if (res?.data) {
        setValueMatrix(res.data);
      } else {
        setValueMatrix(null);
      }
    } catch (error: any) {
      addToast({ type: 'error', title: '价值矩阵加载失败', message: error?.message || '未知错误' });
      setValueMatrix(null);
    } finally {
      setMatrixLoading(false);
    }
  };

  const fetchGoNoGo = async (pipelineId: string) => {
    if (!pipelineId) return;
    setGoNoGoLoading(true);
    setGoNoGoId(pipelineId);
    try {
      const res: any = await pipelineApi.getGoNoGo(pipelineId);
      if (res?.success && res.data) {
        setGoNoGoDecision(res.data);
      } else if (res?.data) {
        setGoNoGoDecision(res.data);
      } else {
        setGoNoGoDecision(null);
      }
    } catch (error: any) {
      addToast({ type: 'error', title: 'Go/No-Go 评估失败', message: error?.message || '未知错误' });
      setGoNoGoDecision(null);
    } finally {
      setGoNoGoLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === '管线认知') {
      if (cognitiveSubTab === 'matrix' && !valueMatrix && !matrixLoading) {
        fetchValueMatrix();
        fetchPipelinesList();
      }
    }
  }, [activeTab, cognitiveSubTab]);

  useEffect(() => {
    if (cognitiveSubTab === 'gonogo' && pipelines.length > 0 && !goNoGoId) {
      setGoNoGoId(pipelines[0].pipeline_id);
    }
  }, [cognitiveSubTab, pipelines, goNoGoId]);

  useEffect(() => {
    if (goNoGoId && activeTab === '管线认知' && cognitiveSubTab === 'gonogo') {
      fetchGoNoGo(goNoGoId);
    }
  }, [goNoGoId, activeTab, cognitiveSubTab]);

  if (overviewLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-surface-400">加载中...</div>
      </div>
    );
  }

  const data = overview;

  if (!data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-finance-800 font-display">管线管理</h1>
          <p className="text-sm text-surface-400 mt-1">研发管线生命周期与Go/No-Go决策</p>
        </div>
        <div className="glass-card p-10 flex flex-col items-center justify-center text-surface-400 text-sm">
          <Inbox className="w-8 h-8 opacity-50 mb-2" />
          <p className="text-surface-600 font-medium">管线总览暂不可用</p>
          <p className="text-[11px] text-surface-400 mt-1">请检查后端连接或稍后重试</p>
          <button
            onClick={() => { setOverviewLoading(true); fetchOverview(); }}
            className="mt-3 text-xs px-3 py-1.5 rounded-lg bg-finance-50 hover:bg-finance-100 text-finance-700 border border-finance-200 flex items-center gap-1.5"
          >
            <RefreshCw size={12} /> 重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">管线管理</h1>
        <p className="text-sm text-surface-400 mt-1">研发管线生命周期与Go/No-Go决策</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: '活跃管线', value: data.active_pipelines, gradient: 'from-brand-500 to-finance-600' },
          { label: '管线总预算', value: formatAmount(data.total_budget), gradient: 'from-finance-500 to-finance-700' },
          { label: '平均消耗率', value: `${data.avg_consumption_rate}%`, gradient: 'from-compliance-500 to-health-600' },
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
                  layoutId="pipelineTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === '管线总览' && (
              <motion.div
                key="overview"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="space-y-5">
                  {/* Pipeline stages visualization */}
                  <div className="glass-card-static p-5">
                    <h3 className="text-sm font-semibold text-finance-800 mb-4">管线阶段分布</h3>
                    <div className="flex items-center justify-center gap-1 overflow-x-auto py-3">
                      {PIPELINE_STAGES.map((stage, idx) => {
                        const count = data.pipelines_by_stage?.[stage] || 0;
                        const isActive = count > 0;
                        return (
                          <div key={stage} className="flex items-center">
                            <div className={clsx(
                              'rounded-xl border-2 p-3 min-w-[110px] text-center transition-all',
                              isActive
                                ? 'border-finance-300 bg-finance-50/60 shadow-sm'
                                : 'border-surface-200 bg-surface-50/30'
                            )}>
                              <div className={clsx(
                                'w-7 h-7 rounded-full mx-auto mb-1.5 flex items-center justify-center text-white text-xs',
                                isActive ? 'bg-finance-500' : 'bg-surface-300'
                              )}>
                                {idx + 1}
                              </div>
                              <h4 className={clsx('text-xs font-bold', isActive ? 'text-finance-700' : 'text-surface-400')}>
                                {stage}
                              </h4>
                              <p className={clsx('text-lg font-bold font-display mt-1', isActive ? 'text-finance-800' : 'text-surface-300')}>
                                {count}
                              </p>
                            </div>
                            {idx < PIPELINE_STAGES.length - 1 && (
                              <div className="flex items-center mx-0.5">
                                <ChevronRight size={14} className="text-surface-300" />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === '管线推进' && (
              <motion.div
                key="advance"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="max-w-2xl space-y-5">
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-surface-700 mb-1">管线 ID</label>
                      <input
                        type="text"
                        value={advancePipelineId}
                        onChange={e => setAdvancePipelineId(e.target.value)}
                        placeholder="请输入管线编号，如 PL-001"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-surface-700 mb-1">目标阶段</label>
                      <select
                        value={targetStage}
                        onChange={e => setTargetStage(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      >
                        <option value="">请选择目标阶段</option>
                        {PIPELINE_STAGES.map(s => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-surface-700 mb-1">Go/No-Go 决策</label>
                      <div className="flex items-center gap-4">
                        <label className={clsx(
                          'flex items-center gap-2 px-4 py-2 rounded-xl border-2 cursor-pointer transition-all',
                          goNoGo === 'go' ? 'border-compliance-300 bg-compliance-50' : 'border-surface-200 bg-white'
                        )}>
                          <input
                            type="radio"
                            name="goNoGo"
                            value="go"
                            checked={goNoGo === 'go'}
                            onChange={() => setGoNoGo('go')}
                            className="sr-only"
                          />
                          <CheckCircle2 size={16} className={goNoGo === 'go' ? 'text-compliance-600' : 'text-surface-400'} />
                          <span className={clsx('text-sm font-medium', goNoGo === 'go' ? 'text-compliance-700' : 'text-surface-500')}>Go</span>
                        </label>
                        <label className={clsx(
                          'flex items-center gap-2 px-4 py-2 rounded-xl border-2 cursor-pointer transition-all',
                          goNoGo === 'no-go' ? 'border-alert-300 bg-alert-50' : 'border-surface-200 bg-white'
                        )}>
                          <input
                            type="radio"
                            name="goNoGo"
                            value="no-go"
                            checked={goNoGo === 'no-go'}
                            onChange={() => setGoNoGo('no-go')}
                            className="sr-only"
                          />
                          <XCircle size={16} className={goNoGo === 'no-go' ? 'text-alert-600' : 'text-surface-400'} />
                          <span className={clsx('text-sm font-medium', goNoGo === 'no-go' ? 'text-alert-700' : 'text-surface-500')}>No-Go</span>
                        </label>
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={handleAdvance}
                    disabled={advanceLoading}
                    className={clsx('btn-primary', advanceLoading && 'opacity-50 cursor-not-allowed')}
                  >
                    <ArrowRight size={14} /> {advanceLoading ? '执行中...' : '推进管线'}
                  </button>

                  {advanceResult && (
                    <div className="glass-card-static p-5 space-y-3">
                      <div className="flex items-center gap-2">
                        <FlaskConical size={18} className="text-finance-600" />
                        <span className="font-semibold text-finance-800">推进结果</span>
                        <span className="font-mono text-xs text-surface-400">{advanceResult.pipeline_id}</span>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">管线名称</p>
                          <p className="text-sm font-medium text-surface-800">{advanceResult.pipeline_name}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">前一阶段</p>
                          <p className="text-sm font-medium text-surface-800">{advanceResult.previous_stage}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">当前阶段</p>
                          <p className="text-sm font-bold text-finance-700">{advanceResult.current_stage}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">Go/No-Go</p>
                          <span className={advanceResult.go_no_go === 'go' ? 'badge-green' : 'badge-red'}>
                            {advanceResult.go_no_go === 'go' ? 'Go' : 'No-Go'}
                          </span>
                        </div>
                      </div>

                      {advanceResult.go_no_go === 'no-go' && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-alert-50 border border-alert-200">
                          <AlertTriangle size={16} className="text-alert-500 flex-shrink-0" />
                          <span className="text-sm text-alert-700 font-medium">No-Go决策：请录入终止评估说明</span>
                        </div>
                      )}

                      {advanceResult.message && (
                        <p className="text-sm text-surface-600">{advanceResult.message}</p>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === '管线状态' && (
              <motion.div
                key="status"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="space-y-5">
                  <div className="flex items-end gap-3 max-w-xl">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-surface-700 mb-1">管线 ID</label>
                      <input
                        type="text"
                        value={statusPipelineId}
                        onChange={e => setStatusPipelineId(e.target.value)}
                        placeholder="请输入管线编号，如 PL-001"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <button
                      onClick={handleQueryStatus}
                      disabled={statusLoading}
                      className={clsx('btn-primary', statusLoading && 'opacity-50 cursor-not-allowed')}
                    >
                      <Search size={14} /> {statusLoading ? '查询中...' : '查询'}
                    </button>
                  </div>

                  {pipelineStatus && (
                    <div className="space-y-4">
                      {/* Pipeline Info */}
                      <div className="glass-card-static p-5">
                        <h3 className="text-sm font-semibold text-finance-800 mb-3">管线信息</h3>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          <div className="p-3 rounded-lg bg-surface-50">
                            <p className="metric-label">管线名称</p>
                            <p className="text-sm font-medium text-surface-800">{pipelineStatus.pipeline_name}</p>
                          </div>
                          <div className="p-3 rounded-lg bg-surface-50">
                            <p className="metric-label">适应症</p>
                            <p className="text-sm font-medium text-surface-800">{pipelineStatus.indication}</p>
                          </div>
                          <div className="p-3 rounded-lg bg-surface-50">
                            <p className="metric-label">当前阶段</p>
                            <p className="text-sm font-bold text-finance-700">{pipelineStatus.current_stage}</p>
                          </div>
                          <div className="p-3 rounded-lg bg-surface-50">
                            <p className="metric-label">状态</p>
                            <span className={pipelineStatus.status === 'active' ? 'badge-green' : pipelineStatus.status === 'terminated' ? 'badge-red' : 'badge-amber'}>
                              {pipelineStatus.status === 'active' ? '活跃' : pipelineStatus.status === 'terminated' ? '已终止' : '暂停'}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Budget Info */}
                      <div className="glass-card-static p-5">
                        <h3 className="text-sm font-semibold text-finance-800 mb-3">预算信息</h3>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                          <div className="p-3 rounded-lg bg-surface-50">
                            <p className="metric-label">总预算</p>
                            <p className="text-sm font-bold text-surface-800 font-display">{formatAmount(pipelineStatus.budget?.total)}</p>
                          </div>
                          <div className="p-3 rounded-lg bg-surface-50">
                            <p className="metric-label">已消耗</p>
                            <p className="text-sm font-bold text-finance-700 font-display">{formatAmount(pipelineStatus.budget?.consumed)}</p>
                          </div>
                          <div className="p-3 rounded-lg bg-surface-50">
                            <p className="metric-label">剩余</p>
                            <p className="text-sm font-bold text-compliance-600 font-display">{formatAmount(pipelineStatus.budget?.remaining)}</p>
                          </div>
                          <div className="p-3 rounded-lg bg-surface-50">
                            <p className="metric-label">消耗率</p>
                            <p className="text-sm font-bold text-finance-700 font-display">{pipelineStatus.budget?.consumption_rate}%</p>
                          </div>
                        </div>
                        <div className="w-full h-3 bg-surface-100 rounded-full overflow-hidden">
                          <div
                            className={clsx(
                              'h-full rounded-full transition-all',
                              pipelineStatus.budget?.consumption_rate > 90 ? 'bg-alert-500' :
                              pipelineStatus.budget?.consumption_rate > 70 ? 'bg-warning-500' : 'bg-compliance-500'
                            )}
                            style={{ width: `${Math.min(100, pipelineStatus.budget?.consumption_rate || 0)}%` }}
                          />
                        </div>
                      </div>

                      {/* Stage Progress */}
                      <div className="glass-card-static p-5">
                        <h3 className="text-sm font-semibold text-finance-800 mb-3">阶段进展</h3>
                        <div className="flex items-center gap-1 overflow-x-auto py-2">
                          {(pipelineStatus.stage_progress || []).map((sp: any, idx: number) => (
                            <div key={sp.stage} className="flex items-center">
                              <div className={clsx(
                                'rounded-xl border-2 p-2.5 min-w-[90px] text-center transition-all',
                                sp.status === 'completed' ? 'border-compliance-300 bg-compliance-50/60' :
                                sp.status === 'active' ? 'border-finance-300 bg-finance-50/60 shadow-sm' :
                                'border-surface-200 bg-surface-50/30'
                              )}>
                                <div className={clsx(
                                  'w-5 h-5 rounded-full mx-auto mb-1 flex items-center justify-center text-white text-[10px]',
                                  sp.status === 'completed' ? 'bg-compliance-500' :
                                  sp.status === 'active' ? 'bg-finance-500' : 'bg-surface-300'
                                )}>
                                  {sp.status === 'completed' ? <CheckCircle2 size={10} /> : idx + 1}
                                </div>
                                <p className={clsx(
                                  'text-[10px] font-bold',
                                  sp.status === 'completed' ? 'text-compliance-700' :
                                  sp.status === 'active' ? 'text-finance-700' : 'text-surface-400'
                                )}>
                                  {sp.stage}
                                </p>
                              </div>
                              {idx < (pipelineStatus.stage_progress || []).length - 1 && (
                                <ChevronRight size={12} className="text-surface-300 mx-0.5" />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Projects & Clinical Trials */}
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="glass-card-static p-5">
                          <h3 className="text-sm font-semibold text-finance-800 mb-3">关联项目</h3>
                          {(pipelineStatus.projects || []).length > 0 ? (
                            <div className="space-y-2">
                              {pipelineStatus.projects.map((p: any) => (
                                <div key={p.project_id} className="flex items-center justify-between p-2.5 rounded-lg bg-surface-50">
                                  <div>
                                    <p className="text-sm font-medium text-surface-800">{p.name}</p>
                                    <p className="text-[10px] text-surface-400 font-mono">{p.project_id}</p>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <div className="w-16 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                                      <div
                                        className={clsx(
                                          'h-full rounded-full',
                                          p.execution_rate >= 80 ? 'bg-compliance-500' :
                                          p.execution_rate >= 50 ? 'bg-finance-500' : 'bg-warning-500'
                                        )}
                                        style={{ width: `${p.execution_rate}%` }}
                                      />
                                    </div>
                                    <span className="text-xs font-bold text-surface-700">{p.execution_rate}%</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-surface-400 text-center py-4">暂无关联项目</p>
                          )}
                        </div>

                        <div className="glass-card-static p-5">
                          <h3 className="text-sm font-semibold text-finance-800 mb-3">临床试验</h3>
                          {(pipelineStatus.clinical_trials || []).length > 0 ? (
                            <div className="space-y-2">
                              {pipelineStatus.clinical_trials.map((t: any) => (
                                <div key={t.trial_id} className="p-2.5 rounded-lg bg-surface-50">
                                  <div className="flex items-center justify-between">
                                    <p className="text-sm font-medium text-surface-800">{t.name}</p>
                                    <span className={t.status === '进行中' ? 'badge-green' : 'badge-amber'}>{t.status}</span>
                                  </div>
                                  <div className="flex items-center gap-3 mt-1 text-[10px] text-surface-400">
                                    <span>{t.trial_id}</span>
                                    <span>{t.phase}</span>
                                    <span>{t.sites} 个中心</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-surface-400 text-center py-4">暂无临床试验</p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* 管线认知（Module E.3：价值矩阵 + Go/No-Go 决策） */}
            {activeTab === '管线认知' && (
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
                    <h2 className="text-base font-semibold text-finance-800">管线认知分析</h2>
                    <p className="text-xs text-surface-500 mt-0.5">rNPV 价值评估 · 5 因素 Go/No-Go 决策 · BCG 象限</p>
                  </div>
                  <span className="text-[10px] text-surface-400 px-2 py-0.5 rounded bg-finance-50/60 border border-finance-200">
                    AI · 数据驱动
                  </span>
                </div>

                {/* 子 Tabs */}
                <div className="flex border-b border-surface-200/60">
                  {([
                    { key: 'matrix', label: '价值矩阵' },
                    { key: 'gonogo', label: 'Go/No-Go 决策' },
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
                          layoutId="pipelineCognitiveTab"
                          className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                        />
                      )}
                    </button>
                  ))}
                </div>

                <AnimatePresence mode="wait">
                  {cognitiveSubTab === 'matrix' && (
                    <motion.div
                      key="matrix"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.15 }}
                    >
                      {matrixLoading ? (
                        <div className="text-center py-10 text-surface-400 text-sm">
                          <div className="inline-block w-5 h-5 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2" />
                          正在计算价值矩阵…
                        </div>
                      ) : (
                        <PipelineValueMatrix data={valueMatrix} />
                      )}
                    </motion.div>
                  )}

                  {cognitiveSubTab === 'gonogo' && (
                    <motion.div
                      key="gonogo"
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.15 }}
                      className="space-y-4"
                    >
                      {/* 管线选择器 */}
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-surface-600">选择管线：</span>
                        <select
                          value={goNoGoId}
                          onChange={e => setGoNoGoId(e.target.value)}
                          className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 min-w-[280px]"
                          disabled={pipelines.length === 0}
                        >
                          {pipelines.length === 0 ? (
                            <option value="">暂无管线数据</option>
                          ) : (
                            pipelines.map((p: any) => (
                              <option key={p.pipeline_id} value={p.pipeline_id}>
                                {p.pipeline_id} · {p.name}（{p.current_stage}）
                              </option>
                            ))
                          )}
                        </select>
                      </div>
                      <GoNoGoPanel data={goNoGoDecision} loading={goNoGoLoading} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
