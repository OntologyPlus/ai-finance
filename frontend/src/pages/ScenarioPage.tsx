import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  Layers,
  SlidersHorizontal,
  Zap,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Plus,
  GitCompare,
  Info,
  ShieldAlert,
  Clock,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAppStore } from '../store';
import { scenarioApi } from '../services/api';
import Pagination from '../components/Pagination';
import CrossPeriodImpactChart from '../components/scenario/CrossPeriodImpactChart';

const TABS = ['情景管理', '弹性调整', '压力测试', '紧急调拨'] as const;

// ── v9.0 C: MOCK 数据已废弃，全部接后端 API 真实数据 ──

const TYPE_MAP: Record<string, { label: string; cls: string }> = {
  '乐观': { label: '乐观', cls: 'badge-green' },
  '基准': { label: '基准', cls: 'badge-blue' },
  '悲观': { label: '悲观', cls: 'badge-red' },
};

function formatWan(n: number): string {
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}万`;
  return n.toLocaleString();
}

export default function ScenarioPage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('情景管理');
  const [loading, setLoading] = useState(true);
  const addToast = useAppStore((s) => s.addToast);

  // Tab 1 state
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({ name: '', scenario_type: '基准', assumptions: '{}' });
  const [selectedForCompare, setSelectedForCompare] = useState<Set<string>>(new Set());
  const [comparisonData, setComparisonData] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(5);

  // Tab 2 state
  const [elasticForm, setElasticForm] = useState({ budget_id: '', actual_volume: 0 });
  const [elasticResult, setElasticResult] = useState<any>(null);

  // Tab 3 state
  const [stressScenarioId, setStressScenarioId] = useState('');
  const [stressResult, setStressResult] = useState<any>(null);

  // Tab 4 state
  const [transferForm, setTransferForm] = useState({ reserve_id: '', budget_id: '', amount: 0, reason: '' });
  const [transferResult, setTransferResult] = useState<any>(null);

  const fetchScenarios = async () => {
    try {
      const res = await scenarioApi.list();
      setScenarios(Array.isArray(res.data) ? res.data : []);
    } catch {
      // v9.0 C: 不再回退到 MOCK
      setScenarios([]);
      addToast({ type: 'warning', title: '情景服务暂不可用', message: '请检查后端连接或稍后重试' });
    }
  };

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await fetchScenarios();
      setLoading(false);
    };
    init();
  }, []);

  const handleCreateScenario = async () => {
    if (!createForm.name.trim()) {
      addToast({ type: 'error', title: '创建失败', message: '请输入情景名称' });
      return;
    }
    let assumptionsObj: Record<string, unknown> = {};
    try {
      assumptionsObj = JSON.parse(createForm.assumptions || '{}');
    } catch {
      addToast({ type: 'error', title: '创建失败', message: '假设条件JSON格式错误' });
      return;
    }
    try {
      await scenarioApi.create({ name: createForm.name, scenario_type: createForm.scenario_type, assumptions: assumptionsObj });
      addToast({ type: 'success', title: '创建成功', message: `情景"${createForm.name}"已创建` });
      setShowCreateForm(false);
      setCreateForm({ name: '', scenario_type: '基准', assumptions: '{}' });
      fetchScenarios();
    } catch (error: any) {
      addToast({ type: 'error', title: '创建失败', message: error.message });
    }
  };

  const handleCompare = async () => {
    if (selectedForCompare.size < 2) {
      addToast({ type: 'error', title: '对比失败', message: '请至少选择2个情景进行对比' });
      return;
    }
    try {
      const res = await scenarioApi.compare(Array.from(selectedForCompare));
      setComparisonData(res.data);
    } catch {
      setComparisonData(null);
      addToast({ type: 'warning', title: '对比服务暂不可用', message: '请检查后端连接' });
    }
  };

  const handleElasticAdjust = async () => {
    if (!elasticForm.budget_id.trim()) {
      addToast({ type: 'error', title: '调整失败', message: '请输入预算ID' });
      return;
    }
    try {
      const res = await scenarioApi.elasticAdjustment({ budget_id: elasticForm.budget_id, actual_volume: elasticForm.actual_volume });
      setElasticResult(res.data);
    } catch {
      setElasticResult(null);
      addToast({ type: 'warning', title: '弹性调整服务暂不可用', message: '请检查后端连接' });
    }
  };

  const handleStressTest = async () => {
    if (!stressScenarioId) {
      addToast({ type: 'error', title: '测试失败', message: '请选择情景' });
      return;
    }
    try {
      const res = await scenarioApi.stressTest({ scenario_id: stressScenarioId });
      setStressResult(res.data);
    } catch {
      setStressResult(null);
      addToast({ type: 'warning', title: '压力测试服务暂不可用', message: '请检查后端连接' });
    }
  };

  const handleEmergencyTransfer = async () => {
    if (!transferForm.reserve_id.trim() || !transferForm.budget_id.trim() || transferForm.amount <= 0) {
      addToast({ type: 'error', title: '调拨失败', message: '请填写完整的调拨信息' });
      return;
    }
    try {
      const res = await scenarioApi.emergencyAllocation(transferForm);
      setTransferResult(res.data);
      addToast({ type: 'success', title: '提交成功', message: '紧急调拨申请已提交' });
    } catch {
      setTransferResult(null);
      addToast({ type: 'warning', title: '调拨服务暂不可用', message: '请检查后端连接' });
    }
  };

  const toggleCompareSelect = (id: string) => {
    setSelectedForCompare(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setComparisonData(null);
  };

  if (loading && scenarios.length === 0) {
    return <div className="flex items-center justify-center h-64 text-surface-400">加载中...</div>;
  }

  const pagedScenarios = scenarios.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const scenarioTotalPages = Math.max(1, Math.ceil(scenarios.length / pageSize));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-finance-800 font-display">情景规划</h1>
          <p className="text-sm text-surface-400 mt-1">多情景预算与弹性调整</p>
        </div>
        <button onClick={fetchScenarios} className="btn-primary">
          <RefreshCw size={14} /> 刷新数据
        </button>
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
                  layoutId="scenarioTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {/* ── Tab 1: 情景管理 ── */}
            {activeTab === '情景管理' && (
              <motion.div
                key="scenario-mgmt"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* Create scenario */}
                <div className="flex items-center gap-3">
                  <button onClick={() => setShowCreateForm(!showCreateForm)} className="btn-primary">
                    <Plus size={14} /> 新建情景
                  </button>
                  <button onClick={handleCompare} className="btn-secondary" disabled={selectedForCompare.size < 2}>
                    <GitCompare size={14} /> 对比选中 ({selectedForCompare.size})
                  </button>
                </div>

                <AnimatePresence>
                  {showCreateForm && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="glass-card-static p-5 space-y-4">
                        <h3 className="text-sm font-semibold text-surface-700">创建新情景</h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-sm text-surface-600 mb-1">情景名称</label>
                            <input
                              type="text"
                              value={createForm.name}
                              onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
                              placeholder="输入情景名称"
                              className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                            />
                          </div>
                          <div>
                            <label className="block text-sm text-surface-600 mb-1">情景类型</label>
                            <select
                              value={createForm.scenario_type}
                              onChange={e => setCreateForm(f => ({ ...f, scenario_type: e.target.value }))}
                              className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                            >
                              <option value="乐观">乐观</option>
                              <option value="基准">基准</option>
                              <option value="悲观">悲观</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm text-surface-600 mb-1">假设条件 (JSON)</label>
                            <input
                              type="text"
                              value={createForm.assumptions}
                              onChange={e => setCreateForm(f => ({ ...f, assumptions: e.target.value }))}
                              placeholder='{"revenue_growth": 0.08}'
                              className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm font-mono focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                            />
                          </div>
                        </div>
                        <div className="flex gap-3">
                          <button onClick={handleCreateScenario} className="btn-primary">
                            <CheckCircle2 size={14} /> 创建
                          </button>
                          <button onClick={() => setShowCreateForm(false)} className="btn-secondary">取消</button>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Scenario list table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-surface-200/60">
                        <th className="text-center py-3 px-3 metric-label">对比</th>
                        <th className="text-left py-3 px-3 metric-label">情景ID</th>
                        <th className="text-left py-3 px-3 metric-label">名称</th>
                        <th className="text-center py-3 px-3 metric-label">类型</th>
                        <th className="text-left py-3 px-3 metric-label">假设条件</th>
                        <th className="text-left py-3 px-3 metric-label">创建时间</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagedScenarios.map(s => (
                        <tr key={s.scenario_id} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                          <td className="py-3 px-3 text-center">
                            <input
                              type="checkbox"
                              checked={selectedForCompare.has(s.scenario_id)}
                              onChange={() => toggleCompareSelect(s.scenario_id)}
                              className="w-4 h-4 rounded border-surface-300 text-finance-600 focus:ring-finance-500"
                            />
                          </td>
                          <td className="py-3 px-3 font-mono text-xs text-finance-700">{s.scenario_id}</td>
                          <td className="py-3 px-3 text-surface-700 font-medium">{s.name}</td>
                          <td className="py-3 px-3 text-center">
                            <span className={TYPE_MAP[s.scenario_type]?.cls || 'badge-blue'}>
                              {TYPE_MAP[s.scenario_type]?.label || s.scenario_type}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-xs text-surface-500 font-mono max-w-[200px] truncate">
                            {JSON.stringify(s.assumptions)}
                          </td>
                          <td className="py-3 px-3 text-xs text-surface-500">{s.created_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <Pagination currentPage={currentPage} totalPages={scenarioTotalPages} onPageChange={setCurrentPage} pageSize={pageSize} />
                </div>

                {/* Comparison results */}
                <AnimatePresence>
                  {comparisonData && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.2 }}
                      className="glass-card-static p-5 space-y-4"
                    >
                      <div className="flex items-center gap-2">
                        <GitCompare size={16} className="text-finance-600" />
                        <h3 className="text-sm font-semibold text-surface-700">情景对比结果</h3>
                      </div>
                      <ReactECharts
                        option={{
                          tooltip: { trigger: 'axis' as const },
                          legend: {
                            data: (comparisonData.scenarios || []).map((id: string) => {
                              const s = scenarios.find(sc => sc.scenario_id === id);
                              return s?.name || id;
                            }),
                            textStyle: { color: '#94a3b8', fontSize: 11 },
                          },
                          grid: { left: 60, right: 20, bottom: 30, top: 40 },
                          xAxis: {
                            type: 'category' as const,
                            data: comparisonData.metrics || [],
                            axisLabel: { color: '#94a3b8', fontSize: 11 },
                            axisLine: { lineStyle: { color: '#e2e8f0' } },
                          },
                          yAxis: {
                            type: 'value' as const,
                            axisLabel: { color: '#94a3b8', fontSize: 10, formatter: (v: number) => formatWan(v) },
                            splitLine: { lineStyle: { color: '#f1f5f9' } },
                          },
                          series: (comparisonData.scenarios || []).map((id: string, idx: number) => {
                            const colors = ['#10b981', '#3b82f6', '#ef4444', '#f97316'];
                            const s = scenarios.find(sc => sc.scenario_id === id);
                            return {
                              name: s?.name || id,
                              type: 'bar' as const,
                              data: (comparisonData.metrics || []).map((m: string) => comparisonData.data?.[id]?.[m] ?? 0),
                              barWidth: 20,
                              itemStyle: { borderRadius: [4, 4, 0, 0], color: colors[idx % colors.length] },
                            };
                          }),
                        }}
                        style={{ height: '280px' }}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}

            {/* ── Tab 2: 弹性调整 ── */}
            {activeTab === '弹性调整' && (
              <motion.div
                key="elastic"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* Form */}
                <div className="glass-card-static p-5 space-y-4">
                  <div className="flex items-center gap-2 mb-2">
                    <SlidersHorizontal size={16} className="text-finance-600" />
                    <h3 className="text-sm font-semibold text-surface-700">弹性调整</h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-surface-600 mb-1">预算ID</label>
                      <input
                        type="text"
                        value={elasticForm.budget_id}
                        onChange={e => setElasticForm(f => ({ ...f, budget_id: e.target.value }))}
                        placeholder="输入预算ID"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-surface-600 mb-1">实际业务量</label>
                      <input
                        type="number"
                        value={elasticForm.actual_volume}
                        onChange={e => setElasticForm(f => ({ ...f, actual_volume: Number(e.target.value) }))}
                        placeholder="输入实际业务量"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                  </div>
                  <button onClick={handleElasticAdjust} className="btn-primary">
                    <SlidersHorizontal size={14} /> 执行调整
                  </button>
                </div>

                {/* Result */}
                <AnimatePresence>
                  {elasticResult && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.2 }}
                      className="space-y-4"
                    >
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="glass-card p-5">
                          <p className="metric-label mb-2">基准金额</p>
                          <p className="metric-value">
                            <span className="bg-gradient-to-r from-finance-500 to-finance-700 bg-clip-text text-transparent">
                              ¥ {formatWan(elasticResult.base_amount)}
                            </span>
                          </p>
                        </div>
                        <div className="glass-card p-5">
                          <p className="metric-label mb-2">调整后金额</p>
                          <p className="metric-value">
                            <span className={clsx(
                              'bg-gradient-to-r bg-clip-text text-transparent',
                              elasticResult.capped ? 'from-alert-500 to-alert-600' : 'from-compliance-500 to-health-600'
                            )}>
                              ¥ {formatWan(elasticResult.adjusted_amount)}
                            </span>
                          </p>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="glass-card p-5">
                          <p className="metric-label mb-2">调整比例</p>
                          <p className={clsx('text-2xl font-bold font-display', Math.abs(elasticResult.adjustment_ratio) > 0.3 ? 'text-alert-600' : 'text-finance-600')}>
                            {(elasticResult.adjustment_ratio * 100).toFixed(1)}%
                          </p>
                        </div>
                        <div className={clsx(
                          'rounded-xl border-2 p-5 transition-all',
                          elasticResult.capped ? 'bg-alert-50/60 border-alert-300' : 'bg-compliance-50/60 border-compliance-300'
                        )}>
                          <p className="metric-label mb-2">封顶状态</p>
                          <div className="flex items-center gap-2">
                            {elasticResult.capped ? (
                              <>
                                <AlertTriangle size={20} className="text-alert-600" />
                                <span className="text-lg font-bold text-alert-600">已触发30%封顶</span>
                              </>
                            ) : (
                              <>
                                <CheckCircle2 size={20} className="text-compliance-600" />
                                <span className="text-lg font-bold text-compliance-600">未触发封顶</span>
                              </>
                            )}
                          </div>
                          <p className="text-xs text-surface-400 mt-1">
                            {elasticResult.capped ? '调整比例超过30%，已自动封顶' : '调整比例在30%以内，未触发封顶机制'}
                          </p>
                        </div>
                      </div>

                      {elasticResult.capped && (
                        <div className="p-4 rounded-xl border border-alert-200 bg-alert-50/50">
                          <div className="flex items-center gap-2 mb-2">
                            <ShieldAlert size={16} className="text-alert-600" />
                            <h3 className="text-sm font-semibold text-alert-800">封顶警告</h3>
                          </div>
                          <p className="text-sm text-surface-600">
                            弹性调整比例 {(elasticResult.adjustment_ratio * 100).toFixed(1)}% 已超过30%封顶线，系统已自动限制调整幅度。如需突破封顶，请提交特殊审批流程。
                          </p>
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}

            {/* ── Tab 3: 压力测试 ── */}
            {activeTab === '压力测试' && (
              <motion.div
                key="stress"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* Scenario selector */}
                <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-50/50 border border-surface-200/60">
                  <Zap size={14} className="text-finance-600" />
                  <span className="text-sm text-surface-500">选择情景</span>
                  <select
                    value={stressScenarioId}
                    onChange={e => setStressScenarioId(e.target.value)}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value="">请选择</option>
                    {scenarios.map(s => (
                      <option key={s.scenario_id} value={s.scenario_id}>{s.name} ({TYPE_MAP[s.scenario_type]?.label || s.scenario_type})</option>
                    ))}
                  </select>
                  <button onClick={handleStressTest} className="btn-primary text-xs">
                    <Zap size={14} /> 执行压力测试
                  </button>
                </div>

                {/* Result */}
                <AnimatePresence>
                  {stressResult && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.2 }}
                      className="space-y-5"
                    >
                      {/* Base vs Stressed comparison */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {[
                          { label: '收入', base: stressResult.base.revenue, stressed: stressResult.stressed.revenue, change: stressResult.impact.revenue_change },
                          { label: '成本', base: stressResult.base.cost, stressed: stressResult.stressed.cost, change: stressResult.impact.cost_change },
                          { label: '利润', base: stressResult.base.profit, stressed: stressResult.stressed.profit, change: stressResult.impact.profit_change },
                        ].map(item => (
                          <div key={item.label} className="glass-card p-5">
                            <p className="metric-label mb-2">{item.label}</p>
                            <div className="space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="text-xs text-surface-400">基准</span>
                                <span className="text-sm font-mono text-finance-600">¥ {formatWan(item.base)}</span>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-xs text-surface-400">压力</span>
                                <span className="text-sm font-mono text-alert-600">¥ {formatWan(item.stressed)}</span>
                              </div>
                              <div className="flex items-center justify-between pt-1 border-t border-surface-100">
                                <span className="text-xs text-surface-400">变动</span>
                                <span className={clsx('text-sm font-mono font-bold', item.change < 0 ? 'text-alert-600' : 'text-compliance-600')}>
                                  {item.change > 0 ? '+' : ''}{item.change.toFixed(1)}%
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Chart */}
                      <div className="glass-card-static p-5">
                        <h3 className="text-sm font-semibold text-surface-700 mb-4">压力测试影响</h3>
                        <ReactECharts
                          option={{
                            tooltip: { trigger: 'axis' as const },
                            legend: { data: ['基准', '压力'], textStyle: { color: '#94a3b8', fontSize: 11 } },
                            grid: { left: 60, right: 20, bottom: 30, top: 40 },
                            xAxis: {
                              type: 'category' as const,
                              data: ['收入', '成本', '利润'],
                              axisLabel: { color: '#94a3b8', fontSize: 11 },
                              axisLine: { lineStyle: { color: '#e2e8f0' } },
                            },
                            yAxis: {
                              type: 'value' as const,
                              axisLabel: { color: '#94a3b8', fontSize: 10, formatter: (v: number) => formatWan(v) },
                              splitLine: { lineStyle: { color: '#f1f5f9' } },
                            },
                            series: [
                              {
                                name: '基准',
                                type: 'bar' as const,
                                data: [stressResult.base.revenue, stressResult.base.cost, stressResult.base.profit],
                                barWidth: 24,
                                itemStyle: { borderRadius: [4, 4, 0, 0], color: '#3b82f6' },
                              },
                              {
                                name: '压力',
                                type: 'bar' as const,
                                data: [stressResult.stressed.revenue, stressResult.stressed.cost, stressResult.stressed.profit],
                                barWidth: 24,
                                itemStyle: { borderRadius: [4, 4, 0, 0], color: '#ef4444' },
                              },
                            ],
                          }}
                          style={{ height: '260px' }}
                        />
                      </div>

                      {/* Recommendation */}
                      <div className="p-4 rounded-xl border border-finance-100 bg-finance-50/30">
                        <div className="flex items-center gap-2 mb-2">
                          <Info size={16} className="text-finance-600" />
                          <h3 className="text-sm font-semibold text-finance-800">建议</h3>
                        </div>
                        <p className="text-sm text-surface-600">{stressResult.recommendation || '暂无建议'}</p>
                      </div>

                      {/* v9.0 E.4：跨期影响链 */}
                      <div className="rounded-xl border-2 border-finance-200/60 bg-white p-5">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2">
                              <Clock size={16} className="text-finance-600" />
                              跨期影响链
                            </h3>
                            <p className="text-[11px] text-surface-500 mt-0.5">
                              T+0 / T+3 / T+6 / T+12 月的传导路径与累计损失
                            </p>
                          </div>
                          <span className="text-[10px] text-surface-400 px-2 py-0.5 rounded bg-finance-50/60 border border-finance-200">
                            AI · 预测
                          </span>
                        </div>
                        <CrossPeriodImpactChart
                          data={null}
                          scenarioName={stressResult.scenario_name}
                          baseProfit={stressResult.base?.profit}
                          profitChangePct={stressResult.impact?.profit_change}
                        />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )}

            {/* ── Tab 4: 紧急调拨 ── */}
            {activeTab === '紧急调拨' && (
              <motion.div
                key="transfer"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* Form */}
                <div className="glass-card-static p-5 space-y-4">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle size={16} className="text-alert-600" />
                    <h3 className="text-sm font-semibold text-surface-700">紧急调拨申请</h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-surface-600 mb-1">储备金ID</label>
                      <input
                        type="text"
                        value={transferForm.reserve_id}
                        onChange={e => setTransferForm(f => ({ ...f, reserve_id: e.target.value }))}
                        placeholder="输入储备金ID"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-surface-600 mb-1">预算ID</label>
                      <input
                        type="text"
                        value={transferForm.budget_id}
                        onChange={e => setTransferForm(f => ({ ...f, budget_id: e.target.value }))}
                        placeholder="输入目标预算ID"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-surface-600 mb-1">调拨金额</label>
                      <input
                        type="number"
                        value={transferForm.amount || ''}
                        onChange={e => setTransferForm(f => ({ ...f, amount: Number(e.target.value) }))}
                        placeholder="输入调拨金额"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-surface-600 mb-1">调拨原因</label>
                      <input
                        type="text"
                        value={transferForm.reason}
                        onChange={e => setTransferForm(f => ({ ...f, reason: e.target.value }))}
                        placeholder="输入调拨原因"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                  </div>
                  <button onClick={handleEmergencyTransfer} className="btn-primary">
                    <AlertTriangle size={14} /> 提交调拨
                  </button>
                </div>

                {/* Result */}
                <AnimatePresence>
                  {transferResult && (
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.2 }}
                      className="space-y-4"
                    >
                      <div className={clsx(
                        'rounded-xl border-2 p-5 transition-all',
                        transferResult.status === 'completed'
                          ? 'bg-compliance-50/60 border-compliance-300'
                          : 'bg-amber-50/60 border-amber-300'
                      )}>
                        <div className="flex items-center gap-3 mb-3">
                          {transferResult.status === 'completed' ? (
                            <CheckCircle2 size={24} className="text-compliance-600" />
                          ) : (
                            <AlertTriangle size={24} className="text-amber-600" />
                          )}
                          <div>
                            <h3 className="font-semibold text-surface-800">
                              {transferResult.status === 'completed' ? '调拨完成' : '等待审批'}
                            </h3>
                            <p className="text-sm text-surface-500">{transferResult.message}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <div>
                            <p className="metric-label">调拨单号</p>
                            <p className="font-mono text-sm text-finance-700">{transferResult.transfer_id}</p>
                          </div>
                          <div>
                            <p className="metric-label">状态</p>
                            <span className={transferResult.status === 'completed' ? 'badge-green' : 'badge-amber'}>
                              {transferResult.status === 'completed' ? '已完成' : '待审批'}
                            </span>
                          </div>
                        </div>
                      </div>

                      {transferResult.status === 'pending_approval' && (
                        <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/50">
                          <div className="flex items-center gap-2 mb-2">
                            <ShieldAlert size={16} className="text-amber-600" />
                            <h3 className="text-sm font-semibold text-amber-800">审批提醒</h3>
                          </div>
                          <p className="text-sm text-surface-600">
                            紧急调拨需要经过审批流程。调拨申请已提交至审批队列，请等待相关负责人审批通过后执行。如为紧急情况，请联系财务总监加速审批。
                          </p>
                        </div>
                      )}
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
