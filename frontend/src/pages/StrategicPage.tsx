import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  Target,
  Plus,
  Pencil,
  Trash2,
  X,
  Gauge,
  GitBranch,
  TrendingDown,
  Sparkles,
  ChevronRight,
  ChevronDown,
  CheckCircle2,
  Loader2,
  Wand2,
} from 'lucide-react';
import { clsx } from 'clsx';
import { strategicApi, budgetApi } from '../services/api';
import StrategicRiskGauge from '../components/strategic/StrategicRiskGauge';
import InitiativeImpactChain from '../components/strategic/InitiativeImpactChain';
import GapAnalysisPanel from '../components/strategic/GapAnalysisPanel';

const TABS = ['战略举措', '策略-预算矩阵', '战略对齐矩阵', '战略认知', '战略分解'] as const;

const L1_OPTIONS = ['全渠道商业化', '创新研发', '国际化'];

const L2_PRODUCT_LINES = ['产品线A', '产品线B', '产品线C'];
const L2_REGIONS = ['华北', '华东', '华南', '海外'];

const PRIORITY_MAP: Record<string, { label: string; cls: string }> = {
  high: { label: '高', cls: 'badge-red' },
  medium: { label: '中', cls: 'badge-amber' },
  low: { label: '低', cls: 'badge-blue' },
};

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  active: { label: '进行中', cls: 'badge-green' },
  completed: { label: '已完成', cls: 'badge-blue' },
  paused: { label: '已暂停', cls: 'badge-amber' },
  cancelled: { label: '已取消', cls: 'badge-red' },
};

function formatAmount(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '¥ 0';
  if (n >= 10000) return `¥ ${(n / 10000).toFixed(1)}万`;
  return `¥ ${n.toLocaleString()}`;
}

interface InitiativeForm {
  name: string;
  description: string;
  strategic_intent_l1: string;
  l2_dimension_product: string;
  l2_dimension_region: string;
  priority: string;
  target_amount: number;
  status: string;
}

const emptyForm: InitiativeForm = {
  name: '',
  description: '',
  strategic_intent_l1: '',
  l2_dimension_product: '',
  l2_dimension_region: '',
  priority: 'medium',
  target_amount: 0,
  status: 'active',
};

export default function StrategicPage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('战略举措');
  const [initiatives, setInitiatives] = useState<any[]>([]);
  const [allocations, setAllocations] = useState<any[]>([]);
  const [subjects, setSubjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<InitiativeForm>(emptyForm);
  const [matrixData, setMatrixData] = useState<any>(null);
  const [coverage, setCoverage] = useState<{ item_coverage: number; amount_coverage: number; aligned_items: number; total_items: number } | null>(null);

  // v9.0 E.1: 战略认知数据
  const [riskGauge, setRiskGauge] = useState<any>(null);
  const [gapAnalysis, setGapAnalysis] = useState<any>(null);
  const [cognitiveLoading, setCognitiveLoading] = useState(false);
  const [selectedInitiativeId, setSelectedInitiativeId] = useState<string>('');
  const [impactChain, setImpactChain] = useState<any>(null);
  const [impactChainLoading, setImpactChainLoading] = useState(false);

  const fetchData = async () => {
    try {
      const [initRes, allocRes, subjRes, matrixRes] = await Promise.all([
        strategicApi.getInitiatives(),
        strategicApi.getAllocations(),
        budgetApi.getSubjects({ level: 'L1' }),
        strategicApi.getMatrix(),
      ]);
      setInitiatives(initRes.data || []);
      setAllocations(allocRes.data || []);
      setSubjects(subjRes.data || []);
      if (matrixRes.data) {
        setMatrixData(matrixRes.data);
        setCoverage(matrixRes.data.coverage || null);
      }
    } catch (error) {
      console.error('Failed to fetch strategic data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // v9.0 E.1: 加载战略认知数据
  const fetchCognitive = async () => {
    setCognitiveLoading(true);
    try {
      const [gaugeRes, gapRes] = await Promise.all([
        strategicApi.getRiskGauge(),
        strategicApi.getGapAnalysis(),
      ]);
      setRiskGauge(gaugeRes.data || null);
      setGapAnalysis(gapRes.data || null);
    } catch (error) {
      console.error('Failed to fetch cognitive data:', error);
    } finally {
      setCognitiveLoading(false);
    }
  };

  // v9.0 E.1: 加载影响链
  const fetchImpactChain = async (initiativeId: string) => {
    if (!initiativeId) {
      setImpactChain(null);
      return;
    }
    setImpactChainLoading(true);
    setSelectedInitiativeId(initiativeId);
    try {
      const res = await strategicApi.getImpactChain(initiativeId);
      setImpactChain(res.data || null);
    } catch (error) {
      console.error('Failed to fetch impact chain:', error);
      setImpactChain(null);
    } finally {
      setImpactChainLoading(false);
    }
  };

  // v12.1: 阶段 1 — 战略主题自动分解
  const [decomposeForm, setDecomposeForm] = useState<{
    theme: string;
    year: number;
    total_budget: number;
    strategic_intent_l1: string;
  }>({
    theme: '',
    year: new Date().getFullYear() + 1,
    total_budget: 0,
    strategic_intent_l1: '',
  });
  const [decomposition, setDecomposition] = useState<any>(null);
  const [decomposing, setDecomposing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [expandedIni, setExpandedIni] = useState<Record<string, boolean>>({});
  const [applyResult, setApplyResult] = useState<any>(null);

  const handleAutoDecompose = async () => {
    if (!decomposeForm.theme.trim() || decomposeForm.total_budget <= 0) return;
    setDecomposing(true);
    setDecomposition(null);
    setApplyResult(null);
    try {
      const res = await budgetApi.autoDecompose({
        theme: decomposeForm.theme,
        year: decomposeForm.year,
        total_budget: decomposeForm.total_budget,
        strategic_intent_l1: decomposeForm.strategic_intent_l1 || undefined,
      });
      if (res.success && res.data) {
        setDecomposition(res.data);
        // 默认展开所有举措
        const map: Record<string, boolean> = {};
        (res.data.initiatives || []).forEach((ini: any) => { map[ini.initiative_id] = true; });
        setExpandedIni(map);
      }
    } catch (error) {
      console.error('Auto-decompose failed:', error);
      alert(`自动分解失败：${(error as Error).message}`);
    } finally {
      setDecomposing(false);
    }
  };

  const handleApplyDecomposition = async () => {
    if (!decomposition) return;
    if (!confirm('确认将分解结果写入数据库？将创建举措 + 预算项。')) return;
    setApplying(true);
    try {
      const res = await budgetApi.applyDecomposition({
        decomposition,
        year: decomposeForm.year,
      });
      if (res.success) {
        setApplyResult(res.data);
        fetchData();
      } else {
        alert(`落库失败：${res.message || '未知错误'}`);
      }
    } catch (error) {
      console.error('Apply decomposition failed:', error);
      alert(`落库失败：${(error as Error).message}`);
    } finally {
      setApplying(false);
    }
  };

  useEffect(() => {
    if (activeTab === '战略认知') {
      fetchCognitive();
    }
  }, [activeTab]);

  const handleCreate = async () => {
    try {
      await strategicApi.createInitiative({
        ...form,
        l2_dimension: `${form.l2_dimension_product}×${form.l2_dimension_region}`,
      });
      setShowModal(false);
      setForm(emptyForm);
      fetchData();
    } catch (error) {
      console.error('Failed to create initiative:', error);
    }
  };

  const handleUpdate = async () => {
    if (!editingId) return;
    try {
      await strategicApi.updateInitiative(editingId, {
        ...form,
        l2_dimension: `${form.l2_dimension_product}×${form.l2_dimension_region}`,
      });
      setShowModal(false);
      setEditingId(null);
      setForm(emptyForm);
      fetchData();
    } catch (error) {
      console.error('Failed to update initiative:', error);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await strategicApi.deleteInitiative(id);
      fetchData();
    } catch (error) {
      console.error('Failed to delete initiative:', error);
    }
  };

  const openEditModal = (item: any) => {
    setEditingId(item.id);
    const l2Dim = item.l2_dimension || '';
    const parts = l2Dim.split('×');
    setForm({
      name: item.name || '',
      description: item.description || '',
      strategic_intent_l1: item.strategic_intent_l1 || '',
      l2_dimension_product: parts[0] || '',
      l2_dimension_region: parts[1] || '',
      priority: item.priority || 'medium',
      target_amount: item.target_amount || 0,
      status: item.status || 'active',
    });
    setShowModal(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-surface-400">加载中...</div>
      </div>
    );
  }

  const totalTarget = initiatives.reduce((s: number, i: any) => s + (i.target_amount || 0), 0);
  const activeCount = initiatives.filter((i: any) => i.status === 'active').length;
  const highPriorityCount = initiatives.filter((i: any) => i.priority === 'high').length;

  // Build matrix data from backend API
  const l1Codes = matrixData?.l1_codes || subjects.map((s: any) => s.code || s.l1_code);
  const intentL1List = matrixData?.intent_l1_list || initiatives.map((i: any) => i.strategic_intent_l1).filter(Boolean);
  const uniqueIntentL1List = [...new Set(intentL1List)];

  const getMatrixCellValue = (l1Code: string, intentL1: string): { total_amount: number; used_amount: number; execution_rate: number } => {
    // Use backend matrix data with precise l1_code matching
    if (matrixData?.matrix) {
      const row = matrixData.matrix.find((r: any) => r.intent === intentL1);
      if (row?.cells?.[l1Code]) {
        return row.cells[l1Code];
      }
    }
    // Fallback: precise l1_code match from allocations
    const alloc = allocations.find(
      (a: any) =>
        a.l1_code === l1Code &&
        a.initiative_name === intentL1
    );
    const amount = alloc?.amount || 0;
    return { total_amount: amount, used_amount: 0, execution_rate: 0 };
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">战略意图管理</h1>
        <p className="text-sm text-surface-400 mt-1">战略举措管理、策略-预算矩阵映射</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: '战略举措总数', value: initiatives.length, gradient: 'from-brand-500 to-finance-600' },
          { label: '进行中', value: activeCount, gradient: 'from-compliance-500 to-health-600' },
          { label: '高优先级', value: highPriorityCount, gradient: 'from-alert-500 to-warning-500' },
          { label: '目标总额', value: formatAmount(totalTarget), gradient: 'from-finance-500 to-finance-700' },
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
                  layoutId="strategicTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === '战略举措' && (
              <motion.div
                key="initiatives"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="flex justify-end mb-4">
                  <button
                    onClick={() => { setForm(emptyForm); setEditingId(null); setShowModal(true); }}
                    className="btn-primary"
                  >
                    <Plus size={14} /> 新建举措
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-surface-200/60">
                        <th className="text-left py-3 px-3 metric-label">ID</th>
                        <th className="text-left py-3 px-3 metric-label">名称</th>
                        <th className="text-left py-3 px-3 metric-label">L1方向</th>
                        <th className="text-left py-3 px-3 metric-label">L2维度</th>
                        <th className="text-center py-3 px-3 metric-label">优先级</th>
                        <th className="text-center py-3 px-3 metric-label">状态</th>
                        <th className="text-right py-3 px-3 metric-label">目标金额</th>
                        <th className="text-center py-3 px-3 metric-label">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {initiatives.map((item: any) => (
                        <tr
                          key={item.id}
                          className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors"
                        >
                          <td className="py-3 px-3 font-mono text-xs text-finance-700">{item.id}</td>
                          <td className="py-3 px-3 font-medium text-surface-800">{item.name}</td>
                          <td className="py-3 px-3 text-surface-600">{item.strategic_intent_l1}</td>
                          <td className="py-3 px-3 text-surface-500 text-xs">{item.l2_dimension || '-'}</td>
                          <td className="py-3 px-3 text-center">
                            <span className={PRIORITY_MAP[item.priority]?.cls || 'badge-blue'}>
                              {PRIORITY_MAP[item.priority]?.label || item.priority}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-center">
                            <span className={STATUS_MAP[item.status]?.cls || 'badge-blue'}>
                              {STATUS_MAP[item.status]?.label || item.status}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right font-mono">
                            {item.target_amount ? formatAmount(item.target_amount) : '-'}
                          </td>
                          <td className="py-3 px-3 text-center">
                            <div className="flex gap-1 justify-center">
                              <button
                                onClick={() => openEditModal(item)}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-brand-50 text-brand-700 border border-brand-200 hover:bg-brand-100 transition-colors"
                              >
                                <Pencil size={10} /> 编辑
                              </button>
                              <button
                                onClick={() => handleDelete(item.id)}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-alert-50 text-alert-700 border border-alert-200 hover:bg-alert-100 transition-colors"
                              >
                                <Trash2 size={10} /> 删除
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                      {initiatives.length === 0 && (
                        <tr>
                          <td colSpan={8} className="py-10 text-center text-surface-400">
                            暂无战略举措数据
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {activeTab === '策略-预算矩阵' && (
              <motion.div
                key="matrix"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                {/* Strategic Coverage Cards */}
                {coverage && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
                    <div className="glass-card p-4 text-center">
                      <p className="metric-label mb-1">项数覆盖率</p>
                      <p className="text-2xl font-bold">
                        <span className="bg-gradient-to-r from-brand-500 to-finance-600 bg-clip-text text-transparent">
                          {(coverage.item_coverage * 100).toFixed(1)}%
                        </span>
                      </p>
                      <p className="text-xs text-surface-400 mt-1">{coverage.aligned_items}/{coverage.total_items} 项</p>
                    </div>
                    <div className="glass-card p-4 text-center">
                      <p className="metric-label mb-1">金额覆盖率</p>
                      <p className="text-2xl font-bold">
                        <span className="bg-gradient-to-r from-compliance-500 to-health-600 bg-clip-text text-transparent">
                          {(coverage.amount_coverage * 100).toFixed(1)}%
                        </span>
                      </p>
                    </div>
                    <div className="glass-card p-4 text-center">
                      <p className="metric-label mb-1">已对齐项数</p>
                      <p className="text-2xl font-bold text-finance-700">{coverage.aligned_items}</p>
                    </div>
                    <div className="glass-card p-4 text-center">
                      <p className="metric-label mb-1">总预算项数</p>
                      <p className="text-2xl font-bold text-surface-600">{coverage.total_items}</p>
                    </div>
                  </div>
                )}

                {uniqueIntentL1List.length === 0 || l1Codes.length === 0 ? (
                  <div className="text-center py-10 text-surface-400">
                    <Target size={40} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">暂无矩阵数据，请先创建战略举措</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-surface-200/60">
                          <th className="text-left py-3 px-3 metric-label sticky left-0 bg-white">战略意图L1</th>
                          {l1Codes.map(code => (
                            <th key={code} className="text-right py-3 px-3 metric-label min-w-[120px]">{code}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {uniqueIntentL1List.map(intent => (
                          <tr key={intent} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                            <td className="py-3 px-3 font-medium text-surface-800 sticky left-0 bg-white">{intent}</td>
                            {l1Codes.map(code => {
                              const cell = getMatrixCellValue(code, intent);
                              return (
                                <td key={`${intent}-${code}`} className="py-3 px-3 text-right font-mono">
                                  {cell.total_amount > 0 ? (
                                    <div>
                                      <div>{formatAmount(cell.total_amount)}</div>
                                      {cell.execution_rate > 0 && (
                                        <div className="text-xs text-surface-400">执行率 {cell.execution_rate}%</div>
                                      )}
                                    </div>
                                  ) : (
                                    <span className="text-surface-300">-</span>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </motion.div>
            )}

            {activeTab === '战略对齐矩阵' && (
              <motion.div
                key="alignment"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                {/* Strategic Alignment Heatmap */}
                <div className="glass-card-static p-5 mb-5">
                  <h3 className="text-sm font-semibold text-surface-700 mb-3">战略-预算对齐热力图</h3>
                  {uniqueIntentL1List.length > 0 && l1Codes.length > 0 ? (
                    <ReactECharts
                      option={{
                        tooltip: {
                          position: 'top' as const,
                          formatter: (params: any) => {
                            const data = params.data;
                            return `<strong>${data[0]}</strong> × <strong>${data[1]}</strong><br/>金额: ${formatAmount(data[2])}`;
                          },
                        },
                        grid: { left: 120, right: 40, bottom: 60, top: 20 },
                        xAxis: {
                          type: 'category' as const,
                          data: l1Codes,
                          axisLabel: { color: '#94a3b8', fontSize: 10, rotate: 30 },
                          axisLine: { lineStyle: { color: '#e2e8f0' } },
                          splitArea: { show: true, areaStyle: { color: ['#fafafa', '#f5f5f5'] } },
                        },
                        yAxis: {
                          type: 'category' as const,
                          data: uniqueIntentL1List,
                          axisLabel: { color: '#94a3b8', fontSize: 10 },
                          axisLine: { lineStyle: { color: '#e2e8f0' } },
                          splitArea: { show: true, areaStyle: { color: ['#fafafa', '#f5f5f5'] } },
                        },
                        visualMap: {
                          min: 0,
                          max: Math.max(1, ...uniqueIntentL1List.flatMap(intent =>
                            l1Codes.map(code => getMatrixCellValue(code, intent).total_amount)
                          )),
                          calculable: true,
                          orient: 'horizontal' as const,
                          left: 'center',
                          bottom: 0,
                          inRange: {
                            color: ['#e0e7ff', '#818cf8', '#4f46e5'],
                          },
                          textStyle: { color: '#94a3b8', fontSize: 10 },
                        },
                        series: [{
                          type: 'heatmap' as const,
                          data: uniqueIntentL1List.flatMap((intent, yIdx) =>
                            l1Codes.map((code, xIdx) => {
                              const cell = getMatrixCellValue(code, intent);
                              return [xIdx, yIdx, cell.total_amount];
                            })
                          ),
                          label: {
                            show: true,
                            formatter: (params: any) => {
                              const val = params.data[2];
                              return val > 0 ? formatAmount(val) : '';
                            },
                            fontSize: 9,
                            color: '#475569',
                          },
                          emphasis: {
                          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' },
                        },
                      }],
                    }}
                    style={{ height: `${Math.max(280, uniqueIntentL1List.length * 50 + 120)}px` }}
                    notMerge={true}
                    lazyUpdate={true}
                    showLoading={uniqueIntentL1List.length === 0 || l1Codes.length === 0}
                  />
                  ) : (
                    <div className="text-center py-10 text-surface-400">
                      <Target size={40} className="mx-auto mb-3 opacity-30" />
                      <p className="text-sm">暂无矩阵数据，请先创建战略举措</p>
                    </div>
                  )}
                </div>

                {/* Strategic Alignment Radar Chart */}
                {uniqueIntentL1List.length > 0 && (
                  <div className="glass-card-static p-5 mb-5">
                    <h3 className="text-sm font-semibold text-surface-700 mb-3">战略方向预算覆盖雷达</h3>
                    <ReactECharts
                      option={{
                        tooltip: {},
                        radar: {
                          indicator: uniqueIntentL1List.map(intent => ({
                            name: intent,
                            max: Math.max(1, ...l1Codes.map(code => getMatrixCellValue(code, intent).total_amount)),
                          })),
                          shape: 'polygon' as const,
                          splitNumber: 4,
                          axisName: { color: '#475569', fontSize: 11 },
                          splitArea: { areaStyle: { color: ['#fafafa', '#f0f0ff', '#e8e8ff', '#e0e0ff'] } },
                        },
                        series: [{
                          type: 'radar' as const,
                          data: l1Codes.map((code, idx) => ({
                            value: uniqueIntentL1List.map(intent => getMatrixCellValue(code, intent).total_amount),
                            name: code,
                            lineStyle: { width: 2 },
                            areaStyle: { opacity: 0.15 },
                          })),
                        }],
                        color: ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4'],
                        legend: {
                          data: l1Codes,
                          bottom: 0,
                          textStyle: { color: '#94a3b8', fontSize: 10 },
                        },
                      }}
                      style={{ height: '320px' }}
                      notMerge={true}
                      lazyUpdate={true}
                      showLoading={uniqueIntentL1List.length === 0 || l1Codes.length === 0}
                    />
                  </div>
                )}

                {/* Alignment Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {uniqueIntentL1List.map(intent => {
                    const intentItems = initiatives.filter((i: any) => i.strategic_intent_l1 === intent);
                    const totalAmount = l1Codes.reduce((s: number, code: string) => s + getMatrixCellValue(code, intent).total_amount, 0);
                    const coveredL1s = l1Codes.filter(code => getMatrixCellValue(code, intent).total_amount > 0);
                    const coverageRate = l1Codes.length > 0 ? Math.round((coveredL1s.length / l1Codes.length) * 100) : 0;
                    return (
                      <div key={intent} className="glass-card p-4">
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="font-semibold text-finance-800">{intent}</h4>
                          <span className={clsx(
                            'px-2 py-0.5 rounded-full text-xs font-medium',
                            coverageRate >= 80 ? 'bg-compliance-100 text-compliance-700' :
                            coverageRate >= 50 ? 'bg-warning-100 text-warning-700' :
                            'bg-alert-100 text-alert-700'
                          )}>
                            覆盖率 {coverageRate}%
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-3 mb-3">
                          <div>
                            <p className="text-[10px] text-surface-400">预算总额</p>
                            <p className="text-sm font-bold text-finance-700 font-mono">{formatAmount(totalAmount)}</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-surface-400">关联举措</p>
                            <p className="text-sm font-bold text-surface-700">{intentItems.length} 项</p>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {l1Codes.map(code => {
                            const amount = getMatrixCellValue(code, intent).total_amount;
                            return (
                              <span
                                key={code}
                                className={clsx(
                                  'px-2 py-0.5 rounded text-[10px] font-medium',
                                  amount > 0 ? 'bg-brand-100 text-brand-700' : 'bg-surface-100 text-surface-400'
                                )}
                              >
                                {code}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            )}

            {/* ── v9.0 E.1: 战略认知（风险仪表 + 举措影响链 + GAP 分析） ── */}
            {activeTab === '战略认知' && (
              <motion.div
                key="cognitive"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {cognitiveLoading ? (
                  <div className="text-center py-12 text-surface-400 text-sm">
                    <div className="inline-block w-6 h-6 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2"></div>
                    正在计算战略风险评分…
                  </div>
                ) : (
                  <>
                    {/* 子模块标题 */}
                    <div className="flex items-center gap-2 mb-1">
                      <Gauge size={16} className="text-finance-600" />
                      <h3 className="text-sm font-semibold text-finance-800">战略风险仪表（5 维加权）</h3>
                    </div>
                    <StrategicRiskGauge data={riskGauge} />

                    <div className="border-t border-surface-200/60 pt-5 mt-5">
                      <div className="flex items-center gap-2 mb-3">
                        <GitBranch size={16} className="text-finance-600" />
                        <h3 className="text-sm font-semibold text-finance-800">举措影响链（战略意图 → 预算 → 执行 4 层传导）</h3>
                      </div>
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-xs text-surface-500">选择战略举措：</span>
                        <select
                          value={selectedInitiativeId}
                          onChange={e => fetchImpactChain(e.target.value)}
                          className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 min-w-[280px]"
                        >
                          <option value="">— 请选择 —</option>
                          {initiatives.map((ini: any) => (
                            <option key={ini.initiative_id} value={ini.initiative_id}>
                              {ini.initiative_id} - {ini.name || ini.initiative_name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <InitiativeImpactChain data={impactChain} loading={impactChainLoading} />
                    </div>

                    <div className="border-t border-surface-200/60 pt-5 mt-5">
                      <div className="flex items-center gap-2 mb-3">
                        <TrendingDown size={16} className="text-finance-600" />
                        <h3 className="text-sm font-semibold text-finance-800">战略 GAP 分析（按意图分组）</h3>
                      </div>
                      <GapAnalysisPanel data={gapAnalysis} />
                    </div>
                  </>
                )}
              </motion.div>
            )}
            {/* ── v12.1: 阶段 1 — 战略主题自动分解 ─────────── */}
            {activeTab === '战略分解' && (
              <motion.div
                key="decompose"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* 输入区 */}
                <div className="glass-card p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Wand2 size={16} className="text-finance-600" />
                    <h3 className="text-sm font-semibold text-finance-800">AI 战略主题自动分解</h3>
                    <span className="text-xs text-surface-400">— 输入主题，一键拆分举措+预算项</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
                    <div className="md:col-span-6">
                      <label className="block text-xs font-medium text-surface-600 mb-1">
                        战略主题 <span className="text-alert-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={decomposeForm.theme}
                        onChange={e => setDecomposeForm(f => ({ ...f, theme: e.target.value }))}
                        placeholder="如：全渠道商业化提速、国际化 BD 突破、创新研发投入加码"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-xs font-medium text-surface-600 mb-1">年度</label>
                      <input
                        type="number"
                        value={decomposeForm.year}
                        onChange={e => setDecomposeForm(f => ({ ...f, year: Number(e.target.value) }))}
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-xs font-medium text-surface-600 mb-1">
                        总预算 (¥) <span className="text-alert-500">*</span>
                      </label>
                      <input
                        type="number"
                        value={decomposeForm.total_budget || ''}
                        onChange={e => setDecomposeForm(f => ({ ...f, total_budget: Number(e.target.value) }))}
                        placeholder="10000000"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-xs font-medium text-surface-600 mb-1">L1 方向</label>
                      <select
                        value={decomposeForm.strategic_intent_l1}
                        onChange={e => setDecomposeForm(f => ({ ...f, strategic_intent_l1: e.target.value }))}
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      >
                        <option value="">自动推断</option>
                        {L1_OPTIONS.map(opt => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="flex gap-3 mt-4 justify-end">
                    {decomposition && (
                      <button
                        onClick={() => { setDecomposition(null); setApplyResult(null); }}
                        className="btn-secondary"
                      >
                        重新拆分
                      </button>
                    )}
                    <button
                      onClick={handleAutoDecompose}
                      disabled={decomposing || !decomposeForm.theme.trim() || decomposeForm.total_budget <= 0}
                      className={clsx(
                        'btn-primary flex items-center gap-2',
                        (decomposing || !decomposeForm.theme.trim() || decomposeForm.total_budget <= 0) && 'opacity-50 cursor-not-allowed'
                      )}
                    >
                      {decomposing ? (
                        <>
                          <Loader2 size={14} className="animate-spin" /> AI 拆解中…
                        </>
                      ) : (
                        <>
                          <Sparkles size={14} /> 一键 AI 拆分
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* 结果区 */}
                {decomposition && (
                  <div className="space-y-4">
                    {/* 摘要卡片 */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">战略意图 (L1)</p>
                        <p className="text-sm font-bold text-finance-700 truncate">{decomposition.intent_l1}</p>
                      </div>
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">象限</p>
                        <p className="text-sm font-bold text-finance-700">{decomposition.quadrant}</p>
                      </div>
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">举措 / 预算项</p>
                        <p className="text-sm font-bold text-finance-700 font-mono">
                          {decomposition.summary.total_initiatives} / {decomposition.summary.total_budget_items}
                        </p>
                      </div>
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">A / B 分类</p>
                        <p className="text-sm font-bold text-finance-700 font-mono">
                          {decomposition.summary.category_a_count} / {decomposition.summary.category_b_count}
                        </p>
                      </div>
                      <div className="glass-card p-3">
                        <p className="text-[10px] text-surface-400 mb-0.5">置信度</p>
                        <p className="text-sm font-bold text-finance-700 font-mono">
                          {Number(decomposition.summary.confidence ?? 0).toFixed(1)}%
                        </p>
                      </div>
                    </div>

                    {/* 树形预览 */}
                    <div className="glass-card p-5">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-semibold text-finance-800 flex items-center gap-2">
                          <GitBranch size={14} /> 主题 → 举措 → 预算项 预览
                        </h4>
                        <span className="text-xs text-surface-400">
                          总预算 <span className="font-mono font-semibold text-finance-700">{formatAmount(decomposition.total_budget)}</span>
                        </span>
                      </div>

                      <div className="border-l-2 border-finance-300 pl-4 space-y-2">
                        <div className="flex items-center gap-2 py-1.5 px-3 rounded-lg bg-finance-50 border border-finance-200">
                          <Target size={14} className="text-finance-700" />
                          <span className="font-semibold text-finance-800 text-sm">{decomposition.theme}</span>
                          <span className="ml-auto text-[10px] text-surface-500">
                            {decomposition.intent_l1} · {decomposition.quadrant}
                          </span>
                        </div>

                        {decomposition.initiatives.map((ini: any) => (
                          <div key={ini.initiative_id} className="ml-4">
                            <button
                              onClick={() => setExpandedIni(m => ({ ...m, [ini.initiative_id]: !m[ini.initiative_id] }))}
                              className="w-full flex items-center gap-2 py-1.5 px-3 rounded-lg bg-brand-50 border border-brand-200 hover:bg-brand-100 transition-colors"
                            >
                              {expandedIni[ini.initiative_id] ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                              <span className="font-medium text-brand-800 text-sm">{ini.name}</span>
                              <span className={clsx(
                                'text-[10px] px-1.5 py-0.5 rounded font-medium',
                                ini.category === 'A' ? 'bg-compliance-100 text-compliance-700' : 'bg-warning-100 text-warning-700'
                              )}>
                                {ini.category}
                              </span>
                              <span className={clsx(
                                'text-[10px] px-1.5 py-0.5 rounded font-medium',
                                ini.priority === 'high' ? 'bg-alert-100 text-alert-700' :
                                ini.priority === 'medium' ? 'bg-warning-100 text-warning-700' :
                                'bg-brand-100 text-brand-700'
                              )}>
                                {ini.priority}
                              </span>
                              <span className="ml-auto text-xs font-mono text-finance-700">
                                {formatAmount(ini.allocated_amount)} ({ini.budget_weight_pct}%)
                              </span>
                            </button>
                            {ini.description && (
                              <p className="text-xs text-surface-500 ml-7 mt-1 mb-1">{ini.description}</p>
                            )}
                            {expandedIni[ini.initiative_id] && (
                              <div className="ml-6 mt-1 space-y-1.5 border-l border-brand-200 pl-4">
                                {ini.budget_items.map((bi: any) => (
                                  <div key={bi.budget_id} className="flex items-center gap-2 py-1.5 px-3 rounded-lg bg-white border border-surface-200 text-xs">
                                    <span className="font-mono text-[10px] text-surface-500">{bi.budget_id}</span>
                                    <span className="font-medium text-surface-800">{bi.budget_name}</span>
                                    <span className="px-1.5 py-0.5 rounded bg-surface-100 text-surface-600 text-[10px]">
                                      L1: {bi.l1_code}
                                    </span>
                                    <span className={clsx(
                                      'px-1.5 py-0.5 rounded text-[10px] font-medium',
                                      bi.category === 'A' ? 'bg-compliance-100 text-compliance-700' : 'bg-warning-100 text-warning-700'
                                    )}>
                                      {bi.category}
                                    </span>
                                    <span className="ml-auto font-mono font-semibold text-finance-700">
                                      {formatAmount(bi.amount)}
                                    </span>
                                  </div>
                                ))}
                                {ini.budget_items.length === 0 && (
                                  <div className="text-xs text-surface-400 pl-3 py-1">无预算项</div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* 落库操作 */}
                      <div className="mt-5 flex items-center justify-between pt-4 border-t border-surface-200/60">
                        <div className="text-xs text-surface-500">
                          {applyResult ? (
                            <span className="text-compliance-700 flex items-center gap-1">
                              <CheckCircle2 size={12} />
                              已创建 {applyResult.created_initiatives} 个举措 + {applyResult.created_budget_items} 个预算项
                            </span>
                          ) : (
                            <span>预览后，点击「落库」将结果写入数据库（SP+BP 闭环）</span>
                          )}
                        </div>
                        <button
                          onClick={handleApplyDecomposition}
                          disabled={applying || !!applyResult}
                          className={clsx(
                            'btn-primary flex items-center gap-2',
                            (applying || applyResult) && 'opacity-50 cursor-not-allowed'
                          )}
                        >
                          {applying ? (
                            <>
                              <Loader2 size={14} className="animate-spin" /> 落库中…
                            </>
                          ) : applyResult ? (
                            <>
                              <CheckCircle2 size={14} /> 已落库
                            </>
                          ) : (
                            <>
                              <CheckCircle2 size={14} /> 一键创建预算
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {!decomposition && !decomposing && (
                  <div className="glass-card-static p-10 text-center text-surface-400">
                    <Sparkles size={40} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">输入战略主题，让 AI 自动拆解为举措 + 预算项</p>
                    <p className="text-xs mt-2">支持关键词自动推断 L1 方向、象限、A/B 分类及金额分配</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Create/Edit Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => setShowModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-lg mx-4"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-finance-800">
                  {editingId ? '编辑战略举措' : '新建战略举措'}
                </h3>
                <button onClick={() => setShowModal(false)} className="text-surface-400 hover:text-surface-600">
                  <X size={18} />
                </button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">名称 <span className="text-alert-500">*</span></label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="请输入举措名称"
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">描述</label>
                  <textarea
                    value={form.description}
                    onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                    rows={2}
                    placeholder="请输入描述..."
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 mb-1">L1方向 <span className="text-alert-500">*</span></label>
                    <select
                      value={form.strategic_intent_l1}
                      onChange={e => setForm(f => ({ ...f, strategic_intent_l1: e.target.value }))}
                      className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    >
                      <option value="">请选择</option>
                      {L1_OPTIONS.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-surface-700 mb-1">优先级</label>
                    <select
                      value={form.priority}
                      onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}
                      className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    >
                      <option value="high">高</option>
                      <option value="medium">中</option>
                      <option value="low">低</option>
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 mb-1">L2维度-产品线</label>
                    <select
                      value={form.l2_dimension_product}
                      onChange={e => setForm(f => ({ ...f, l2_dimension_product: e.target.value }))}
                      className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    >
                      <option value="">请选择</option>
                      {L2_PRODUCT_LINES.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-surface-700 mb-1">L2维度-区域</label>
                    <select
                      value={form.l2_dimension_region}
                      onChange={e => setForm(f => ({ ...f, l2_dimension_region: e.target.value }))}
                      className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    >
                      <option value="">请选择</option>
                      {L2_REGIONS.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">目标金额</label>
                  <input
                    type="number"
                    value={form.target_amount || ''}
                    onChange={e => setForm(f => ({ ...f, target_amount: Number(e.target.value) }))}
                    placeholder="请输入目标金额"
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  />
                </div>
              </div>
              <div className="flex gap-3 justify-end mt-5">
                <button onClick={() => setShowModal(false)} className="btn-secondary">取消</button>
                <button
                  onClick={editingId ? handleUpdate : handleCreate}
                  disabled={!form.name.trim() || !form.strategic_intent_l1}
                  className={clsx('btn-primary', (!form.name.trim() || !form.strategic_intent_l1) && 'opacity-50 cursor-not-allowed')}
                >
                  {editingId ? '保存修改' : '创建举措'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
