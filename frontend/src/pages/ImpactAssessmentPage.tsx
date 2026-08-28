/**
 * ImpactAssessmentPage 影响力评估页面 — v8.0 Module I
 * 包含 3 个子模块：
 * 1. 决策沙盘（What-If 模拟）
 * 2. 影响归因（反向追溯）
 * 3. Pareto 前沿（多目标优化）
 */
import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Beaker, GitBranch, Target, Sparkles, TrendingUp, AlertCircle,
  CheckCircle2, XCircle, Play, RefreshCw, History, BarChart3,
} from 'lucide-react';
import { impactApi } from '../services/api';
import SankeyChart, { SankeyLink, SankeyNode } from '../components/impact/SankeyChart';
import clsx from 'clsx';

type Tab = 'sandbox' | 'attribution' | 'pareto';

const OPERATION_TYPES = [
  { value: 'budget_change', label: '预算变更', icon: '💰' },
  { value: 'expense_overrun', label: '费用超支', icon: '📈' },
  { value: 'strategic_shift', label: '战略调整', icon: '🎯' },
  { value: 'approval_decision', label: '审批决策', icon: '✅' },
];

const ATTRIBUTABLE_METRICS = [
  { value: 'execution_rate', label: '预算执行率' },
  { value: 'overrun_rate', label: '超支率' },
  { value: 'alert_count', label: '预警数量' },
  { value: 'expense_growth', label: '费用增长率' },
  { value: 'cashflow_gap', label: '现金流缺口' },
  { value: 'strategic_coverage', label: '战略覆盖率' },
  { value: 'roi', label: '投资回报率' },
];

const RISK_COLORS = {
  高: { bg: 'bg-rose-50', border: 'border-rose-200', text: 'text-rose-700', dot: 'bg-rose-500' },
  中: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', dot: 'bg-amber-500' },
  低: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', dot: 'bg-emerald-500' },
};

export default function ImpactAssessmentPage() {
  const [tab, setTab] = useState<Tab>('sandbox');

  return (
    <div className="space-y-6 px-6 py-4">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-surface-900">影响力评估中心</h1>
        <p className="text-sm text-surface-500">
          决策沙盘 · 影响归因 · Pareto 前沿 — 让每一个决策都可推演、可归因、可优化
        </p>
      </header>

      {/* Tab 切换 */}
      <div className="flex items-center gap-1 p-1 bg-surface-100 rounded-xl w-fit">
        {([
          { key: 'sandbox', label: '决策沙盘', icon: Beaker },
          { key: 'attribution', label: '影响归因', icon: GitBranch },
          { key: 'pareto', label: 'Pareto 前沿', icon: Target },
        ] as const).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
              tab === key
                ? 'bg-white text-finance-700 shadow-sm'
                : 'text-surface-500 hover:text-surface-700'
            )}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {tab === 'sandbox' && (
          <motion.div
            key="sandbox"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
          >
            <SandboxPanel />
          </motion.div>
        )}
        {tab === 'attribution' && (
          <motion.div
            key="attribution"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
          >
            <AttributionPanel />
          </motion.div>
        )}
        {tab === 'pareto' && (
          <motion.div
            key="pareto"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
          >
            <ParetoPanel />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 决策沙盘子面板
// ═══════════════════════════════════════════════════════════════

function SandboxPanel() {
  const [scenarioName, setScenarioName] = useState('Q3 预算调减模拟');
  const [operationType, setOperationType] = useState('budget_change');
  const [params, setParams] = useState({
    budget_id: 'B-2026-001',
    change_type: 'decrease',
    amount: 500000,
  });
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    refreshHistory();
  }, []);

  const refreshHistory = async () => {
    try {
      const res = await impactApi.listSandboxes(10);
      if (res.data?.items) setHistory(res.data.items);
    } catch (e) {
      console.error('加载历史失败', e);
    }
  };

  const runSimulation = async () => {
    setLoading(true);
    try {
      const res = await impactApi.simulateSandbox({
        scenario_name: scenarioName,
        operation_type: operationType,
        params,
      });
      if (res.data) {
        setResult(res.data);
        refreshHistory();
      }
    } catch (e: any) {
      alert('模拟失败: ' + (e.message || e));
    } finally {
      setLoading(false);
    }
  };

  // 构造桑基图：场景 → 5 域影响
  const sankeyData = result
    ? buildSankeyFromPrediction(result)
    : { nodes: [], links: [] };

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* 左侧：配置 */}
      <div className="col-span-4 space-y-4">
        <div className="bg-white rounded-2xl border border-surface-200 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Beaker size={18} className="text-finance-600" />
            <h3 className="font-semibold text-surface-900">场景配置</h3>
          </div>

          <div>
            <label className="text-xs text-surface-500 mb-1 block">场景名称</label>
            <input
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-xs text-surface-500 mb-1 block">操作类型</label>
            <div className="grid grid-cols-2 gap-2">
              {OPERATION_TYPES.map((op) => (
                <button
                  key={op.value}
                  onClick={() => setOperationType(op.value)}
                  className={clsx(
                    'px-3 py-2 rounded-lg text-xs font-medium transition border',
                    operationType === op.value
                      ? 'bg-finance-50 border-finance-300 text-finance-700'
                      : 'bg-white border-surface-200 text-surface-600 hover:border-surface-300'
                  )}
                >
                  {op.icon} {op.label}
                </button>
              ))}
            </div>
          </div>

          {operationType === 'budget_change' && (
            <>
              <div>
                <label className="text-xs text-surface-500 mb-1 block">预算 ID</label>
                <input
                  value={params.budget_id}
                  onChange={(e) => setParams({ ...params, budget_id: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-surface-500 mb-1 block">变更类型</label>
                <select
                  value={params.change_type}
                  onChange={(e) => setParams({ ...params, change_type: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
                >
                  <option value="decrease">减少</option>
                  <option value="increase">增加</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-surface-500 mb-1 block">金额（元）</label>
                <input
                  type="number"
                  value={params.amount}
                  onChange={(e) => setParams({ ...params, amount: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
                />
              </div>
            </>
          )}

          {operationType === 'expense_overrun' && (
            <>
              <div>
                <label className="text-xs text-surface-500 mb-1 block">费用单 ID</label>
                <input
                  value={params.expense_id || 'EXP-001'}
                  onChange={(e) => setParams({ ...params, expense_id: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-surface-500 mb-1 block">超支金额（元）</label>
                <input
                  type="number"
                  value={params.overrun_amount || 50000}
                  onChange={(e) => setParams({ ...params, overrun_amount: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
                />
              </div>
            </>
          )}

          {operationType === 'strategic_shift' && (
            <div>
              <label className="text-xs text-surface-500 mb-1 block">新方向</label>
              <input
                value={params.new_direction || ''}
                onChange={(e) => setParams({ ...params, new_direction: e.target.value })}
                placeholder="如：聚焦核心产品"
                className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
              />
            </div>
          )}

          <button
            onClick={runSimulation}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-finance-600 text-white rounded-lg text-sm font-medium hover:bg-finance-700 disabled:opacity-50 transition"
          >
            {loading ? (
              <RefreshCw size={16} className="animate-spin" />
            ) : (
              <Play size={16} />
            )}
            {loading ? '模拟中...' : '开始模拟'}
          </button>
        </div>

        {/* 历史 */}
        <div className="bg-white rounded-2xl border border-surface-200 p-5">
          <div className="flex items-center gap-2 mb-3">
            <History size={16} className="text-surface-500" />
            <h3 className="font-semibold text-sm text-surface-900">历史场景</h3>
          </div>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {history.length === 0 ? (
              <div className="text-xs text-surface-400 py-4 text-center">暂无历史</div>
            ) : (
              history.map((h) => (
                <div
                  key={h.id}
                  className="p-2 rounded-lg border border-surface-100 hover:border-finance-300 hover:bg-finance-50 cursor-pointer transition"
                  onClick={async () => {
                    const detail = await impactApi.getSandbox(h.id);
                    if (detail.data) setResult(detail.data);
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-medium text-surface-800 truncate flex-1">
                      {h.scenario_name}
                    </div>
                    <RiskDot level={h.overall_risk} />
                  </div>
                  <div className="text-[10px] text-surface-500 mt-0.5">
                    {h.operation_type} · 置信度 {(h.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* 右侧：结果 */}
      <div className="col-span-8 space-y-4">
        {result ? (
          <>
            {/* 总览卡片 */}
            <div className="grid grid-cols-4 gap-3">
              <MetricCard
                label="总体风险"
                value={result.overall_risk}
                type="risk"
              />
              <MetricCard
                label="可逆性"
                value={result.reversibility}
                type="reversibility"
              />
              <MetricCard
                label="置信度"
                value={`${(result.confidence * 100).toFixed(0)}%`}
                type="confidence"
              />
              <MetricCard
                label="影响域数"
                value={`${result.prediction.affected_count}（高风险 ${result.prediction.high_risk_count}）`}
                type="info"
              />
            </div>

            {/* 桑基图 */}
            <div className="bg-white rounded-2xl border border-surface-200 p-4">
              <div className="flex items-center gap-2 mb-2">
                <GitBranch size={16} className="text-finance-600" />
                <h3 className="font-semibold text-sm text-surface-900">
                  5 域影响流向（桑基图）
                </h3>
              </div>
              <SankeyChart
                nodes={sankeyData.nodes}
                links={sankeyData.links}
                height={320}
              />
            </div>

            {/* 各域详情 */}
            <div className="bg-white rounded-2xl border border-surface-200 p-5 space-y-3">
              <h3 className="font-semibold text-sm text-surface-900">各域影响详情</h3>
              <div className="grid grid-cols-1 gap-2">
                {Object.entries(result.prediction.domains || {}).map(([domain, info]: [string, any]) => {
                  const color = RISK_COLORS[info.severity as keyof typeof RISK_COLORS];
                  return (
                    <div
                      key={domain}
                      className={clsx(
                        'p-3 rounded-lg border',
                        color.bg,
                        color.border
                      )}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <RiskDot level={info.severity} />
                          <span className="text-sm font-medium text-surface-800">
                            {DOMAIN_LABELS[domain] || domain}
                          </span>
                        </div>
                        <span className={clsx('text-xs', color.text)}>
                          {info.severity}风险
                        </span>
                      </div>
                      <p className="text-xs text-surface-600">{info.description}</p>
                      {info.mitigation && (
                        <p className="text-xs text-surface-500 mt-1">
                          💡 {info.mitigation}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 建议 */}
            <div className="bg-finance-50 rounded-2xl border border-finance-200 p-5 space-y-2">
              <div className="flex items-center gap-2">
                <Sparkles size={16} className="text-finance-600" />
                <h3 className="font-semibold text-sm text-finance-900">智能建议</h3>
              </div>
              <ul className="space-y-1.5">
                {result.recommendations.map((rec: string, idx: number) => (
                  <li
                    key={idx}
                    className="text-sm text-finance-800 flex items-start gap-2"
                  >
                    <span className="text-finance-500 mt-0.5">•</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : (
          <div className="bg-white rounded-2xl border border-surface-200 p-12 text-center">
            <Beaker size={48} className="mx-auto text-surface-300 mb-3" />
            <h3 className="text-base font-semibold text-surface-700 mb-1">
              开始一次决策模拟
            </h3>
            <p className="text-sm text-surface-500">
              在左侧配置场景参数，点击「开始模拟」查看 5 域影响预测
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 影响归因子面板
// ═══════════════════════════════════════════════════════════════

function AttributionPanel() {
  const [targetMetric, setTargetMetric] = useState('execution_rate');
  const [targetPeriod, setTargetPeriod] = useState(
    `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}`
  );
  const [observedValue, setObservedValue] = useState(85.5);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    refreshHistory();
  }, []);

  const refreshHistory = async () => {
    try {
      const res = await impactApi.listAttributions(10);
      if (res.data?.items) setHistory(res.data.items);
    } catch (e) {
      console.error('加载历史失败', e);
    }
  };

  const runAttribution = async () => {
    setLoading(true);
    try {
      const res = await impactApi.attributeMetric({
        target_metric: targetMetric,
        target_period: targetPeriod,
        observed_value: observedValue,
      });
      if (res.data) {
        setResult(res.data);
        refreshHistory();
      }
    } catch (e: any) {
      alert('归因失败: ' + (e.message || e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-4 space-y-4">
        <div className="bg-white rounded-2xl border border-surface-200 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <GitBranch size={18} className="text-finance-600" />
            <h3 className="font-semibold text-surface-900">归因配置</h3>
          </div>

          <div>
            <label className="text-xs text-surface-500 mb-1 block">目标指标</label>
            <select
              value={targetMetric}
              onChange={(e) => setTargetMetric(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
            >
              {ATTRIBUTABLE_METRICS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs text-surface-500 mb-1 block">目标期间 (YYYY-MM)</label>
            <input
              value={targetPeriod}
              onChange={(e) => setTargetPeriod(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-xs text-surface-500 mb-1 block">观测值</label>
            <input
              type="number"
              value={observedValue}
              onChange={(e) => setObservedValue(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
            />
          </div>

          <button
            onClick={runAttribution}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-finance-600 text-white rounded-lg text-sm font-medium hover:bg-finance-700 disabled:opacity-50 transition"
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />}
            {loading ? '分析中...' : '开始归因'}
          </button>
        </div>

        {/* 历史 */}
        <div className="bg-white rounded-2xl border border-surface-200 p-5">
          <div className="flex items-center gap-2 mb-3">
            <History size={16} className="text-surface-500" />
            <h3 className="font-semibold text-sm text-surface-900">历史归因</h3>
          </div>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {history.length === 0 ? (
              <div className="text-xs text-surface-400 py-4 text-center">暂无历史</div>
            ) : (
              history.map((h) => (
                <div
                  key={h.id}
                  className="p-2 rounded-lg border border-surface-100 hover:border-finance-300 hover:bg-finance-50 transition"
                >
                  <div className="text-xs font-medium text-surface-800">
                    {h.target_metric} · {h.target_period}
                  </div>
                  <div className="text-[10px] text-surface-500 mt-0.5">
                    Δ{h.delta >= 0 ? '+' : ''}{h.delta} · 置信度{' '}
                    {(h.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="col-span-8 space-y-4">
        {result ? (
          <>
            <div className="grid grid-cols-4 gap-3">
              <MetricCard label="目标指标" value={result.target_metric_label} type="info" />
              <MetricCard label="基线值" value={String(result.baseline_value)} type="info" />
              <MetricCard
                label="观测值"
                value={String(result.observed_value)}
                type="info"
              />
              <MetricCard
                label="变化量"
                value={`${result.delta >= 0 ? '+' : ''}${result.delta} (${result.delta_pct >= 0 ? '+' : ''}${result.delta_pct}%)`}
                type={result.delta > 0 ? 'success' : result.delta < 0 ? 'risk' : 'info'}
              />
            </div>

            {/* 自然语言解释 */}
            <div className="bg-white rounded-2xl border border-surface-200 p-5">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={16} className="text-finance-600" />
                <h3 className="font-semibold text-sm text-surface-900">归因解释</h3>
                <span className="ml-auto text-xs text-surface-500">
                  置信度 {(result.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <p className="text-sm text-surface-700 leading-relaxed">
                {result.explanation}
              </p>
            </div>

            {/* 根操作列表 */}
            <div className="bg-white rounded-2xl border border-surface-200 p-5 space-y-3">
              <h3 className="font-semibold text-sm text-surface-900">根操作贡献度</h3>
              {result.root_operations.length === 0 ? (
                <div className="text-xs text-surface-400 py-4 text-center">
                  未找到候选根操作
                </div>
              ) : (
                <div className="space-y-2">
                  {result.root_operations.map((op: any, idx: number) => (
                    <div
                      key={idx}
                      className="p-3 rounded-lg border border-surface-200 hover:border-finance-300 transition"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="text-sm font-medium text-surface-800">
                          #{idx + 1} {op.description}
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-2 bg-surface-100 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-finance-500"
                              style={{ width: `${op.contribution}%` }}
                            />
                          </div>
                          <span className="text-xs font-semibold text-finance-700 w-10 text-right">
                            {op.contribution}%
                          </span>
                        </div>
                      </div>
                      <div className="text-xs text-surface-500">
                        {op.operation_type} · {op.occurred_at?.slice(0, 10) || '未知时间'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="bg-white rounded-2xl border border-surface-200 p-12 text-center">
            <GitBranch size={48} className="mx-auto text-surface-300 mb-3" />
            <h3 className="text-base font-semibold text-surface-700 mb-1">
              反向归因分析
            </h3>
            <p className="text-sm text-surface-500">
              选择目标指标并输入观测值，AI 将反向追溯根操作
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// Pareto 前沿子面板
// ═══════════════════════════════════════════════════════════════

function ParetoPanel() {
  const [budgetId, setBudgetId] = useState('B-2026-001');
  const [originalAmount, setOriginalAmount] = useState(5000000);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const runPareto = async () => {
    setLoading(true);
    try {
      const res = await impactApi.autoPareto({
        budget_id: budgetId,
        original_amount: originalAmount,
      });
      if (res.data) setResult(res.data);
    } catch (e: any) {
      alert('Pareto 优化失败: ' + (e.message || e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-3 space-y-4">
        <div className="bg-white rounded-2xl border border-surface-200 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Target size={18} className="text-finance-600" />
            <h3 className="font-semibold text-surface-900">预算调整优化</h3>
          </div>

          <div>
            <label className="text-xs text-surface-500 mb-1 block">预算 ID</label>
            <input
              value={budgetId}
              onChange={(e) => setBudgetId(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-xs text-surface-500 mb-1 block">原预算金额（元）</label>
            <input
              type="number"
              value={originalAmount}
              onChange={(e) => setOriginalAmount(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-lg border border-surface-200 text-sm focus:border-finance-500 focus:outline-none"
            />
          </div>

          <button
            onClick={runPareto}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-finance-600 text-white rounded-lg text-sm font-medium hover:bg-finance-700 disabled:opacity-50 transition"
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <BarChart3 size={16} />}
            {loading ? '优化中...' : '生成 Pareto 前沿'}
          </button>

          <div className="text-xs text-surface-500 leading-relaxed pt-2 border-t border-surface-100">
            <p className="font-medium text-surface-700 mb-1">4 目标权衡：</p>
            <ul className="space-y-0.5">
              <li>• 预算合规度 (30%)</li>
              <li>• 业务影响度 (30%)</li>
              <li>• 战略对齐度 (20%)</li>
              <li>• 现金流稳定性 (20%)</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="col-span-9 space-y-4">
        {result ? (
          <>
            <div className="grid grid-cols-4 gap-3">
              <MetricCard
                label="候选方案"
                value={String(result.summary.total_candidates)}
                type="info"
              />
              <MetricCard
                label="Pareto 最优"
                value={String(result.summary.pareto_optimal_count)}
                type="success"
              />
              <MetricCard
                label="最高加权分"
                value={String(result.summary.best_weighted)}
                type="info"
              />
              <MetricCard
                label="最低加权分"
                value={String(result.summary.worst_weighted)}
                type="info"
              />
            </div>

            {/* 排名表 */}
            <div className="bg-white rounded-2xl border border-surface-200 p-5 space-y-3">
              <h3 className="font-semibold text-sm text-surface-900">方案排名</h3>
              <div className="space-y-2">
                {result.ranked.map((r: any) => (
                  <div
                    key={r.id}
                    className={clsx(
                      'p-3 rounded-lg border transition',
                      r.is_pareto_optimal
                        ? 'border-finance-300 bg-finance-50'
                        : 'border-surface-200'
                    )}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-surface-800">
                          #{r.rank} {r.id}
                        </span>
                        {r.is_pareto_optimal && (
                          <span className="px-2 py-0.5 bg-finance-600 text-white text-[10px] rounded-full font-medium">
                            Pareto 最优
                          </span>
                        )}
                      </div>
                      <div className="text-sm font-semibold text-finance-700">
                        加权 {r.weighted_score}
                      </div>
                    </div>
                    <div className="grid grid-cols-4 gap-2">
                      <ScoreBar label="合规" value={r.scores.budget_compliance} />
                      <ScoreBar label="影响" value={r.scores.business_impact} />
                      <ScoreBar label="战略" value={r.scores.strategic_alignment} />
                      <ScoreBar label="现金流" value={r.scores.cashflow_stability} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="bg-white rounded-2xl border border-surface-200 p-12 text-center">
            <Target size={48} className="mx-auto text-surface-300 mb-3" />
            <h3 className="text-base font-semibold text-surface-700 mb-1">
              多目标 Pareto 优化
            </h3>
            <p className="text-sm text-surface-500">
              输入预算参数，自动生成 7 种调整方案并识别 Pareto 前沿
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 辅助组件
// ═══════════════════════════════════════════════════════════════

const DOMAIN_LABELS: Record<string, string> = {
  budget: '预算',
  expense: '费用',
  alert: '预警',
  cashflow: '现金流',
  strategic: '战略',
  approval: '审批',
};

function RiskDot({ level }: { level: string }) {
  const color = RISK_COLORS[level as keyof typeof RISK_COLORS] || RISK_COLORS.低;
  return (
    <div className="flex items-center gap-1.5">
      <span className={clsx('w-2 h-2 rounded-full', color.dot)} />
      <span className={clsx('text-xs', color.text)}>{level}</span>
    </div>
  );
}

function MetricCard({
  label,
  value,
  type,
}: {
  label: string;
  value: string;
  type: 'info' | 'risk' | 'success' | 'confidence' | 'reversibility';
}) {
  const colorMap = {
    info: 'text-surface-800',
    risk: 'text-rose-600',
    success: 'text-emerald-600',
    confidence: 'text-finance-700',
    reversibility: 'text-amber-600',
  };
  return (
    <div className="bg-white rounded-2xl border border-surface-200 px-4 py-3">
      <div className="text-xs text-surface-500 mb-1">{label}</div>
      <div className={clsx('text-lg font-semibold', colorMap[type])}>{value}</div>
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="flex items-center justify-between text-[10px] text-surface-500 mb-0.5">
        <span>{label}</span>
        <span className="font-medium text-surface-700">{value}</span>
      </div>
      <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden">
        <div
          className={clsx(
            'h-full rounded-full',
            value >= 70 ? 'bg-emerald-500' : value >= 50 ? 'bg-amber-500' : 'bg-rose-500'
          )}
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
    </div>
  );
}

function buildSankeyFromPrediction(result: any): {
  nodes: SankeyNode[];
  links: SankeyLink[];
} {
  const nodes: SankeyNode[] = [
    { name: '决策操作', itemStyle: { color: '#6366f1' } },
  ];
  const links: SankeyLink[] = [];

  // 严重度→颜色
  const severityColor = { 高: '#fb7185', 中: '#f59e0b', 低: '#10b981' };

  Object.entries(result.prediction?.domains || {}).forEach(([domain, info]: [string, any]) => {
    const domainLabel = DOMAIN_LABELS[domain] || domain;
    nodes.push({
      name: domainLabel,
      itemStyle: { color: severityColor[info.severity as keyof typeof severityColor] || '#94a3b8' },
    });
    // 流量 = severity 数值化
    const value = info.severity === '高' ? 80 : info.severity === '中' ? 50 : 20;
    links.push({
      source: '决策操作',
      target: domainLabel,
      value,
      lineStyle: {
        color: severityColor[info.severity as keyof typeof severityColor] || '#94a3b8',
        opacity: 0.5,
      },
    });
  });

  return { nodes, links };
}
