/**
 * EvalPage — 评测看板（v9.0 从占位变实装）
 * 9 个核心能力维度的 AI 系统质量评测
 */
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  Award,
  CheckCircle2,
  XCircle,
  TrendingUp,
  AlertCircle,
  Play,
  RefreshCw,
  Target,
  Lightbulb,
  BarChart3,
} from 'lucide-react';
import { clsx } from 'clsx';

interface EvalCategory {
  id: string;
  name: string;
  description: string;
}

interface EvalResult {
  category: string;
  category_name: string;
  baseline: number;
  latest_pass_rate: number | null;
  status: string;
}

interface RunResult {
  run_id: string;
  category: string;
  category_name: string;
  total_checks: number;
  passed: number;
  failed: number;
  pass_rate: number;
  baseline: number;
  status: 'PASS' | 'FAIL';
  run_at: string;
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function getToken(): string | null {
  return localStorage.getItem('auth_token');
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
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

const evalApi = {
  getCategories: () => request<{ success: boolean; data: EvalCategory[] }>('/api/eval/categories'),
  getResults: () => request<{ success: boolean; data: EvalResult[] }>('/api/eval/results'),
  getBaseline: () => request<{ success: boolean; data: Record<string, number> }>('/api/eval/baseline'),
  run: (category: string) =>
    request<{ success: boolean; data: RunResult; message?: string }>('/api/eval/run', {
      method: 'POST',
      body: JSON.stringify({ category }),
    }),
};

const STATUS_STYLE: Record<string, { cls: string; icon: typeof CheckCircle2; label: string }> = {
  PASS: { cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: CheckCircle2, label: '通过' },
  FAIL: { cls: 'bg-rose-50 text-rose-700 border-rose-200', icon: XCircle, label: '未通过' },
  not_run: { cls: 'bg-slate-50 text-slate-500 border-slate-200', icon: AlertCircle, label: '未评测' },
};

const IMPROVEMENT_TIPS: Record<string, string[]> = {
  budget_planning: ['检查象限归属规则是否覆盖新业务', '增加战略意图对齐权重', '扩充科目分类标准'],
  budget_grant: ['验证 B 类额度释放条件', '校准 A/B 转换阈值', '完善历史预算调整回溯'],
  expense_reimbursement: ['校验发票查重逻辑边界', '增加重复发票类型', '优化管控级别自动识别'],
  approval: ['检查双线审批并行性', '验证审批链强制步骤', '完善审批人推荐'],
  alert_monitoring: ['调整预警阈值', '增加里程碑预测', '集成多源数据信号'],
  business_analysis: ['扩展 3GAP/3List 维度', '增加归因分析', '优化执行率口径'],
  pdca_review: ['建立改进建议闭环', '增加同业对标', '完善月度回顾模板'],
  report_generation: ['增加 LLM 起草质量', '扩充报告模板', '增加图表自动生成'],
  ontology_rules: ['增强软规则自适应', '优化推理链路', '补充缺失规则'],
};

export default function EvalPage() {
  const [categories, setCategories] = useState<EvalCategory[]>([]);
  const [results, setResults] = useState<EvalResult[]>([]);
  const [baseline, setBaseline] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [lastRunResult, setLastRunResult] = useState<RunResult | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [catRes, resRes, baseRes] = await Promise.all([
        evalApi.getCategories(),
        evalApi.getResults(),
        evalApi.getBaseline(),
      ]);
      setCategories(catRes.data || []);
      setResults(resRes.data || []);
      setBaseline(baseRes.data || {});
    } catch (e) {
      // 静默失败
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRun = async (category: string) => {
    setRunningId(category);
    try {
      const res = await evalApi.run(category);
      setLastRunResult(res.data);
      const resRes = await evalApi.getResults();
      setResults(resRes.data || []);
    } catch (e) {
      // 静默
    } finally {
      setRunningId(null);
    }
  };

  const totalCategories = results.length;
  const passedCount = results.filter((r) => r.status === 'PASS').length;
  const failedCount = results.filter((r) => r.status === 'FAIL').length;
  const overallPassRate = totalCategories > 0
    ? results.reduce((sum, r) => sum + (r.latest_pass_rate || 0), 0) / totalCategories
    : 0;

  const radarOption = {
    tooltip: { trigger: 'item' },
    legend: { data: ['当前', '基线'], textStyle: { color: '#64748b', fontSize: 11 } },
    radar: {
      indicator: results.map((r) => ({ name: r.category_name, max: 1.0 })),
      shape: 'polygon',
      splitArea: { areaStyle: { color: ['#f8fafc', '#f1f5f9'] } },
      axisName: { color: '#64748b', fontSize: 10 },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            name: '当前',
            value: results.map((r) => r.latest_pass_rate ?? 0),
            areaStyle: { color: 'rgba(59,130,246,0.2)' },
            lineStyle: { color: '#3b82f6', width: 2 },
            itemStyle: { color: '#3b82f6' },
          },
          {
            name: '基线',
            value: results.map((r) => r.baseline),
            areaStyle: { color: 'rgba(244,114,182,0.1)' },
            lineStyle: { color: '#f472b6', width: 2, type: 'dashed' },
            itemStyle: { color: '#f472b6' },
          },
        ],
      },
    ],
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-finance-800 font-display">评测看板</h1>
          <p className="text-sm text-surface-400 mt-1">9 大能力维度的 AI 系统质量评测 · 识别弱项并提供改进建议</p>
        </div>
        <button className="btn-secondary" onClick={loadData} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> 刷新
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-5">
          <p className="metric-label mb-2">评测维度</p>
          <p className="metric-value">
            <span className="bg-gradient-to-r from-brand-500 to-finance-600 bg-clip-text text-transparent">
              {totalCategories}
            </span>
            <span className="text-xs font-normal text-surface-400 ml-1">个</span>
          </p>
        </div>
        <div className="glass-card p-5">
          <p className="metric-label mb-2">通过维度</p>
          <p className="metric-value">
            <span className="bg-gradient-to-r from-emerald-500 to-compliance-600 bg-clip-text text-transparent">
              {passedCount}
            </span>
            <span className="text-xs font-normal text-surface-400 ml-1">/ {totalCategories}</span>
          </p>
        </div>
        <div className="glass-card p-5">
          <p className="metric-label mb-2">未通过维度</p>
          <p className="metric-value">
            <span className={clsx(
              'bg-gradient-to-r bg-clip-text text-transparent',
              failedCount > 0 ? 'from-rose-500 to-alert-600' : 'from-slate-300 to-slate-400'
            )}>
              {failedCount}
            </span>
            <span className="text-xs font-normal text-surface-400 ml-1">/ {totalCategories}</span>
          </p>
        </div>
        <div className="glass-card p-5">
          <p className="metric-label mb-2">平均通过率</p>
          <p className="metric-value">
            <span className={clsx(
              'bg-gradient-to-r bg-clip-text text-transparent',
              overallPassRate >= 0.85 ? 'from-emerald-500 to-compliance-600' :
              overallPassRate >= 0.7 ? 'from-amber-500 to-warning-600' :
              'from-rose-500 to-alert-600'
            )}>
              {(overallPassRate * 100).toFixed(1)}%
            </span>
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 glass-card p-5">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 size={16} className="text-brand-500" />
            <h3 className="text-sm font-semibold text-finance-800">9 维度雷达图（当前 vs 基线）</h3>
          </div>
          {results.length > 0 ? (
            <ReactECharts option={radarOption} style={{ height: 360 }} />
          ) : (
            <div className="h-80 flex items-center justify-center text-surface-400 text-sm">
              暂无评测数据
            </div>
          )}
        </div>

        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-3">
            <Award size={16} className="text-amber-500" />
            <h3 className="text-sm font-semibold text-finance-800">最近一次评测</h3>
          </div>
          {lastRunResult ? (
            <div className="space-y-3">
              <div className={clsx(
                'p-3 rounded-lg border-2',
                lastRunResult.status === 'PASS'
                  ? 'border-emerald-200 bg-emerald-50/40'
                  : 'border-rose-200 bg-rose-50/40'
              )}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-finance-800">{lastRunResult.category_name}</span>
                  {lastRunResult.status === 'PASS'
                    ? <CheckCircle2 size={18} className="text-emerald-600" />
                    : <XCircle size={18} className="text-rose-600" />}
                </div>
                <p className="text-xs text-surface-500 mt-1">run_id: {lastRunResult.run_id}</p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 rounded-lg bg-surface-50">
                  <p className="text-[10px] text-surface-500">通过率</p>
                  <p className="text-lg font-bold text-finance-700">{(lastRunResult.pass_rate * 100).toFixed(1)}%</p>
                </div>
                <div className="p-3 rounded-lg bg-surface-50">
                  <p className="text-[10px] text-surface-500">基线</p>
                  <p className="text-lg font-bold text-surface-700">{(lastRunResult.baseline * 100).toFixed(0)}%</p>
                </div>
                <div className="p-3 rounded-lg bg-surface-50">
                  <p className="text-[10px] text-surface-500">检查项</p>
                  <p className="text-lg font-bold text-surface-700">{lastRunResult.total_checks}</p>
                </div>
                <div className="p-3 rounded-lg bg-surface-50">
                  <p className="text-[10px] text-surface-500">通过数</p>
                  <p className="text-lg font-bold text-emerald-600">{lastRunResult.passed}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-surface-400 text-sm">
              <Target size={32} className="mx-auto mb-2 opacity-30" />
              点击下方「运行评测」启动单维度评测
            </div>
          )}
        </div>
      </div>

      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-3">
          <Target size={16} className="text-finance-600" />
          <h3 className="text-sm font-semibold text-finance-800">9 维度评测矩阵</h3>
        </div>
        {loading ? (
          <div className="text-center py-8 text-surface-400 text-sm">加载中...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {results.map((r) => {
              const style = STATUS_STYLE[r.status] || STATUS_STYLE.not_run;
              const Icon = style.icon;
              const rate = r.latest_pass_rate;
              return (
                <div key={r.category} className="p-4 rounded-xl border border-surface-200 bg-white">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="text-sm font-semibold text-finance-800">{r.category_name}</p>
                      <p className="text-[11px] text-surface-500 mt-0.5">
                        基线 {(r.baseline * 100).toFixed(0)}%
                      </p>
                    </div>
                    <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold border flex items-center gap-1', style.cls)}>
                      <Icon size={10} />
                      {style.label}
                    </span>
                  </div>
                  {rate != null ? (
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-surface-500">通过率</span>
                        <span className={clsx(
                          'text-sm font-bold',
                          rate >= r.baseline ? 'text-emerald-600' : 'text-rose-600'
                        )}>
                          {(rate * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-2 bg-surface-100 rounded-full overflow-hidden relative">
                        <div
                          className={clsx(
                            'h-full rounded-full transition-all',
                            rate >= r.baseline ? 'bg-gradient-to-r from-emerald-400 to-compliance-500' : 'bg-gradient-to-r from-rose-400 to-alert-500'
                          )}
                          style={{ width: `${Math.min(100, rate * 100)}%` }}
                        />
                        <div
                          className="absolute top-0 bottom-0 w-px bg-slate-400"
                          style={{ left: `${r.baseline * 100}%` }}
                          title={`基线 ${(r.baseline * 100).toFixed(0)}%`}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-surface-400 py-1">未评测</p>
                  )}
                  <button
                    className="mt-3 w-full text-xs py-1.5 rounded-lg border border-finance-200 text-finance-700 hover:bg-finance-50 transition-colors flex items-center justify-center gap-1"
                    onClick={() => handleRun(r.category)}
                    disabled={runningId === r.category}
                  >
                    {runningId === r.category ? (
                      <><RefreshCw size={12} className="animate-spin" /> 评测中...</>
                    ) : (
                      <><Play size={12} /> 运行评测</>
                    )}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {failedCount > 0 && (
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-3">
            <Lightbulb size={16} className="text-amber-500" />
            <h3 className="text-sm font-semibold text-finance-800">未通过维度改进建议</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {results.filter((r) => r.status === 'FAIL').map((r) => (
              <div key={r.category} className="p-3 rounded-lg border border-amber-200 bg-amber-50/30">
                <div className="flex items-center gap-2 mb-1.5">
                  <TrendingUp size={14} className="text-amber-600" />
                  <span className="text-sm font-semibold text-amber-800">{r.category_name}</span>
                </div>
                <ul className="text-xs text-amber-700 space-y-1">
                  {(IMPROVEMENT_TIPS[r.category] || ['分析失败原因', '优化引擎逻辑', '扩充测试用例']).map((tip, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-amber-500 mt-0.5">•</span>
                      <span>{tip}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      <AnimatePresence>
        {categories.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-5"
          >
            <h3 className="text-sm font-semibold text-finance-800 mb-3">9 评测类别说明</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {categories.map((c) => (
                <div key={c.id} className="p-2.5 rounded-lg border border-surface-100">
                  <p className="text-xs font-semibold text-finance-800">{c.name}</p>
                  <p className="text-[11px] text-surface-500 mt-0.5 leading-relaxed">{c.description}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
