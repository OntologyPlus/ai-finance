/**
 * ReasoningAuditorPage — AI 推理审计员（v12.0 评测驱动进化）
 *
 * 功能：
 * - 列出所有 AI 推理轨迹（含场景、置信度、反馈汇总）
 * - 单条 trace 详情：输入数据 → 推理步骤 → 结论 → 置信度
 * - 反馈机制：准确性评分 / 有帮助 / 改进建议 / 期望置信度
 * - 评测汇总：整体健康度 + 按场景分布 + 校准差
 */
import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain,
  Search,
  Sparkles,
  ThumbsUp,
  ThumbsDown,
  X,
  Loader2,
  Target,
  CheckCircle2,
  AlertTriangle,
  Eye,
  BarChart3,
  Activity,
} from 'lucide-react';
import { clsx } from 'clsx';

interface TraceStep {
  step: string;
  detail: string;
}

interface TraceRecord {
  trace_id: string;
  scene_name: string;
  input_data: any;
  steps: TraceStep[];
  conclusion: string;
  confidence: number;
  rule_ids: string[];
  created_at: string;
  feedback_summary?: {
    feedback_count: number;
    avg_accuracy: number;
    helpful_count: number;
    avg_calibration: number | null;
  };
  calibration_gap?: number | null;
}

interface EvalSummary {
  trace_total: number;
  feedback_total: number;
  feedback_coverage: number;
  avg_accuracy: number;
  helpful_rate: number;
  low_confidence_count: number;
  calibration_gap: number | null;
  scene_breakdown: Array<{ scene_name: string; trace_count: number; avg_confidence: number }>;
  evaluation_health: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function apiGet<T>(path: string): Promise<T> {
  const token = localStorage.getItem('auth_token');
  const res = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).message || res.statusText);
  return res.json();
}

async function apiPost<T>(path: string, body: any): Promise<T> {
  const token = localStorage.getItem('auth_token');
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).message || res.statusText);
  return res.json();
}

function safeParseSteps(steps: any): TraceStep[] {
  if (!steps) return [];
  if (Array.isArray(steps)) return steps;
  try {
    return JSON.parse(steps);
  } catch {
    return [{ step: 'raw', detail: typeof steps === 'string' ? steps : JSON.stringify(steps) }];
  }
}

function safeParseJSON(value: any): any {
  if (!value) return null;
  if (typeof value === 'object') return value;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function confidenceColor(c: number): string {
  if (c >= 85) return 'text-compliance-700';
  if (c >= 70) return 'text-finance-700';
  if (c >= 50) return 'text-warning-700';
  return 'text-alert-700';
}

function confidenceBg(c: number): string {
  if (c >= 85) return 'bg-compliance-50 border-compliance-200';
  if (c >= 70) return 'bg-finance-50 border-finance-200';
  if (c >= 50) return 'bg-warning-50 border-warning-200';
  return 'bg-alert-50 border-alert-200';
}

// ─────────────────────────────────────────────
// 评测汇总看板
// ─────────────────────────────────────────────
function EvalSummaryPanel({ summary }: { summary: EvalSummary | null }) {
  if (!summary) {
    return (
      <div className="glass-card-static p-4 text-center text-surface-400 text-sm">
        加载评测汇总…
      </div>
    );
  }

  return (
    <div className="glass-card-static p-4">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={14} className="text-finance-600" />
        <h3 className="text-sm font-semibold text-finance-800">AI 推理评测总览</h3>
        <span className={clsx(
          'text-[10px] px-2 py-0.5 rounded-md font-semibold ml-auto',
          summary.evaluation_health === '良好' ? 'bg-compliance-50 text-compliance-700 border border-compliance-200' :
          summary.evaluation_health === '样本不足' ? 'bg-surface-50 text-surface-500 border border-surface-200' :
          'bg-warning-50 text-warning-700 border border-warning-200'
        )}>
          健康度：{summary.evaluation_health}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
        <div className="rounded-lg p-2.5 bg-finance-50/40 border border-finance-100">
          <p className="text-[10px] text-surface-500">推理总量</p>
          <p className="text-xl font-bold text-finance-700">{summary.trace_total}</p>
        </div>
        <div className="rounded-lg p-2.5 bg-brand-50/40 border border-brand-100">
          <p className="text-[10px] text-surface-500">反馈覆盖</p>
          <p className="text-xl font-bold text-brand-700">{summary.feedback_coverage}%</p>
        </div>
        <div className={clsx(
          'rounded-lg p-2.5 border',
          summary.avg_accuracy >= 4 ? 'bg-compliance-50/40 border-compliance-100' :
          summary.avg_accuracy >= 3 ? 'bg-warning-50/40 border-warning-100' :
          'bg-alert-50/40 border-alert-100'
        )}>
          <p className="text-[10px] text-surface-500">平均准确性</p>
          <p className={clsx(
            'text-xl font-bold',
            summary.avg_accuracy >= 4 ? 'text-compliance-700' :
            summary.avg_accuracy >= 3 ? 'text-warning-700' :
            'text-alert-700'
          )}>{summary.avg_accuracy || '-'}<span className="text-xs">/5</span></p>
        </div>
        <div className="rounded-lg p-2.5 bg-purple-50/40 border border-purple-100">
          <p className="text-[10px] text-surface-500">校准差（AI vs 审计）</p>
          <p className={clsx(
            'text-xl font-bold',
            summary.calibration_gap == null ? 'text-surface-400' :
            Math.abs(summary.calibration_gap) < 10 ? 'text-compliance-700' :
            Math.abs(summary.calibration_gap) < 25 ? 'text-warning-700' : 'text-alert-700'
          )}>
            {summary.calibration_gap == null ? '-' :
              (summary.calibration_gap > 0 ? '+' : '') + summary.calibration_gap}
          </p>
          <p className="text-[9px] text-surface-500 mt-0.5">
            {summary.calibration_gap == null ? '尚无反馈数据' :
             Math.abs(summary.calibration_gap) < 10 ? '✓ 校准良好' :
             summary.calibration_gap > 0 ? '⚠ AI过于自信' : '⚠ AI过于保守'}
          </p>
        </div>
      </div>

      {/* 场景分布 */}
      {summary.scene_breakdown.length > 0 && (
        <div>
          <p className="text-[10px] text-surface-500 font-semibold mb-1.5">按场景分布</p>
          <div className="space-y-1">
            {summary.scene_breakdown.slice(0, 5).map(s => (
              <div key={s.scene_name} className="flex items-center gap-2 text-[11px]">
                <span className="text-surface-700 flex-1 truncate">{s.scene_name}</span>
                <span className="text-surface-500">{s.trace_count}条</span>
                <div className="w-24 h-1.5 rounded-full bg-surface-100 overflow-hidden">
                  <div
                    className={clsx(
                      'h-full',
                      s.avg_confidence >= 85 ? 'bg-compliance-500' :
                      s.avg_confidence >= 70 ? 'bg-finance-500' :
                      s.avg_confidence >= 50 ? 'bg-warning-500' : 'bg-alert-500'
                    )}
                    style={{ width: `${s.avg_confidence}%` }}
                  />
                </div>
                <span className={clsx('font-semibold w-10 text-right', confidenceColor(Number(s.avg_confidence ?? 0)))}>
                  {Number(s.avg_confidence ?? 0).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// 单条 trace 详情 + 反馈
// ─────────────────────────────────────────────
function TraceDetailDrawer({
  trace,
  onClose,
  onFeedbackSubmit,
}: {
  trace: TraceRecord | null;
  onClose: () => void;
  onFeedbackSubmit: () => void;
}) {
  const [accuracy, setAccuracy] = useState(4);
  const [helpful, setHelpful] = useState(true);
  const [comment, setComment] = useState('');
  const [calibration, setCalibration] = useState<number | ''>('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    setAccuracy(4);
    setHelpful(true);
    setComment('');
    setCalibration('');
    setSuccess(false);
  }, [trace?.trace_id]);

  if (!trace) return null;

  const steps = safeParseSteps(trace.steps);
  const inputData = safeParseJSON(trace.input_data);
  const ruleIds = safeParseJSON(trace.rule_ids) || [];
  const fb = trace.feedback_summary;

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await apiPost(`/api/ontology/traces/${trace.trace_id}/feedback`, {
        accuracy_score: accuracy,
        helpful,
        comment,
        confidence_calibration: calibration === '' ? null : Number(calibration),
        reviewer_id: 'auditor',
        reviewer_role: '财经BP',
      });
      setSuccess(true);
      onFeedbackSubmit();
    } catch (e) {
      // swallow, but show success/fail toast
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {trace && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/30 z-40"
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'tween', duration: 0.25 }}
            className="fixed top-0 right-0 h-full w-full sm:w-[560px] bg-white shadow-2xl z-50 flex flex-col"
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-surface-200">
              <div>
                <h2 className="text-base font-semibold text-finance-800 flex items-center gap-2">
                  <Brain size={16} />
                  推理轨迹审计
                </h2>
                <p className="text-[11px] text-surface-500 mt-0.5">Trace ID: {trace.trace_id}</p>
              </div>
              <button onClick={onClose} className="p-1.5 rounded-lg text-surface-400 hover:text-surface-600 hover:bg-surface-100">
                <X size={18} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {/* 头部信息 */}
              <div className={clsx('rounded-lg p-3 border', confidenceBg(trace.confidence || 0))}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] text-surface-500">场景</span>
                  <span className="text-sm font-semibold text-finance-700">{trace.scene_name || '未分类'}</span>
                </div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] text-surface-500">置信度</span>
                  <span className={clsx('text-lg font-bold', confidenceColor(Number(trace.confidence ?? 0)))}>
                    {Number(trace.confidence ?? 0).toFixed(0)}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-surface-500">触发规则</span>
                  <div className="flex flex-wrap gap-1">
                    {ruleIds.length > 0 ? ruleIds.map((r: string) => (
                      <code key={r} className="text-[10px] px-1.5 py-0.5 rounded bg-finance-100 text-finance-700 font-mono">{r}</code>
                    )) : <span className="text-[10px] text-surface-400">未匹配规则</span>}
                  </div>
                </div>
              </div>

              {/* 反馈历史 */}
              {fb && fb.feedback_count > 0 && (
                <div className="rounded-lg p-3 bg-surface-50 border border-surface-200">
                  <p className="text-[11px] text-surface-500 font-semibold mb-2">历史反馈汇总（{fb.feedback_count}条）</p>
                  <div className="grid grid-cols-3 gap-2 text-[11px]">
                    <div>
                      <p className="text-surface-500">平均分</p>
                      <p className="font-bold text-finance-700">{fb.avg_accuracy.toFixed(1)}/5</p>
                    </div>
                    <div>
                      <p className="text-surface-500">有帮助率</p>
                      <p className="font-bold text-compliance-700">
                        {Math.round(fb.helpful_count / fb.feedback_count * 100)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-surface-500">校准差</p>
                      <p className={clsx(
                        'font-bold',
                        trace.calibration_gap == null ? 'text-surface-400' :
                        Math.abs(trace.calibration_gap) < 10 ? 'text-compliance-700' :
                        'text-warning-700'
                      )}>
                        {trace.calibration_gap == null ? '-' :
                          (trace.calibration_gap > 0 ? '+' : '') + trace.calibration_gap}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* 输入数据 */}
              <div className="rounded-lg p-3 border border-surface-200">
                <p className="text-[11px] text-surface-500 font-semibold mb-2 flex items-center gap-1.5">
                  <Target size={12} /> 输入数据
                </p>
                <pre className="text-[11px] text-surface-700 bg-surface-50 rounded p-2 overflow-x-auto max-h-40 overflow-y-auto">
                  {inputData ? JSON.stringify(inputData, null, 2) : '(无)'}
                </pre>
              </div>

              {/* 推理步骤 */}
              <div className="rounded-lg p-3 border border-surface-200">
                <p className="text-[11px] text-surface-500 font-semibold mb-2 flex items-center gap-1.5">
                  <Activity size={12} /> 推理步骤
                </p>
                <div className="space-y-1.5">
                  {steps.length === 0 ? (
                    <p className="text-[11px] text-surface-400">无步骤记录</p>
                  ) : steps.map((s, i) => (
                    <div key={i} className="flex gap-2 text-[11px]">
                      <span className="w-5 h-5 rounded-full bg-finance-100 text-finance-700 flex items-center justify-center font-bold flex-shrink-0">
                        {i + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="font-semibold text-finance-700">{s.step}</p>
                        <p className="text-surface-600 mt-0.5">{s.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 结论 */}
              <div className="rounded-lg p-3 border-2 border-finance-200 bg-finance-50/30">
                <p className="text-[11px] text-surface-500 font-semibold mb-1.5 flex items-center gap-1.5">
                  <Sparkles size={12} className="text-finance-600" /> 最终结论
                </p>
                <p className="text-xs text-surface-700">{trace.conclusion || '(无)'}</p>
              </div>

              {/* 反馈表单 */}
              <div className="rounded-lg p-3 border-2 border-dashed border-brand-200 bg-brand-50/20">
                <p className="text-[11px] text-surface-700 font-semibold mb-2 flex items-center gap-1.5">
                  <CheckCircle2 size={12} className="text-brand-600" /> 审计员反馈（评测驱动进化）
                </p>

                <div className="space-y-2">
                  <div>
                    <p className="text-[10px] text-surface-500 mb-1">准确性评分（1=完全错误，5=完全正确）</p>
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5].map(n => (
                        <button
                          key={n}
                          onClick={() => setAccuracy(n)}
                          className={clsx(
                            'w-8 h-8 rounded-lg text-sm font-semibold transition-colors',
                            accuracy === n
                              ? 'bg-finance-500 text-white'
                              : 'bg-white border border-surface-200 text-surface-500 hover:border-finance-300'
                          )}
                        >{n}</button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-[10px] text-surface-500 mb-1">是否有帮助</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setHelpful(true)}
                        className={clsx(
                          'flex-1 py-1.5 rounded-lg text-xs flex items-center justify-center gap-1',
                          helpful ? 'bg-compliance-500 text-white' : 'bg-white border border-surface-200 text-surface-500'
                        )}
                      ><ThumbsUp size={12} /> 有帮助</button>
                      <button
                        onClick={() => setHelpful(false)}
                        className={clsx(
                          'flex-1 py-1.5 rounded-lg text-xs flex items-center justify-center gap-1',
                          !helpful ? 'bg-alert-500 text-white' : 'bg-white border border-surface-200 text-surface-500'
                        )}
                      ><ThumbsDown size={12} /> 无帮助</button>
                    </div>
                  </div>

                  <div>
                    <p className="text-[10px] text-surface-500 mb-1">期望置信度（用于校准，可选）</p>
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={calibration}
                      onChange={e => setCalibration(e.target.value === '' ? '' : Number(e.target.value))}
                      placeholder={`AI 实际：${Number(trace.confidence ?? 0).toFixed(0)}%`}
                      className="w-full px-2 py-1 rounded border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20"
                    />
                  </div>

                  <div>
                    <p className="text-[10px] text-surface-500 mb-1">改进建议（可选）</p>
                    <textarea
                      rows={2}
                      value={comment}
                      onChange={e => setComment(e.target.value)}
                      placeholder="例如：建议将警报阈值从105%调高到110%..."
                      className="w-full px-2 py-1 rounded border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 resize-none"
                    />
                  </div>

                  <button
                    onClick={handleSubmit}
                    disabled={submitting || success}
                    className={clsx(
                      'w-full py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5',
                      success ? 'bg-compliance-500 text-white' :
                      submitting ? 'bg-surface-300 text-surface-500 cursor-not-allowed' :
                      'btn-primary'
                    )}
                  >
                    {submitting ? <><Loader2 size={12} className="animate-spin" /> 提交中...</> :
                     success ? <><CheckCircle2 size={12} /> 反馈已记录</> :
                     <><Sparkles size={12} /> 提交反馈</>
                    }
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ─────────────────────────────────────────────
// 主页面
// ─────────────────────────────────────────────
export default function ReasoningAuditorPage() {
  const [traces, setTraces] = useState<TraceRecord[]>([]);
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [sceneFilter, setSceneFilter] = useState<string>('');
  const [minConfidence, setMinConfidence] = useState<number | ''>('');
  const [selectedTrace, setSelectedTrace] = useState<TraceRecord | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (sceneFilter) params.append('scene_name', sceneFilter);
      if (minConfidence !== '') params.append('min_confidence', String(minConfidence));
      params.append('limit', '80');

      const [tracesRes, summaryRes] = await Promise.all([
        apiGet<{ data: { traces: TraceRecord[]; scene_stats: any } }>(`/api/ontology/traces-with-feedback?${params}`),
        apiGet<{ data: EvalSummary }>('/api/ontology/eval-summary'),
      ]);
      setTraces(tracesRes.data.traces || []);
      setSummary(summaryRes.data);
    } catch (e: any) {
      setTraces([]);
    } finally {
      setLoading(false);
    }
  }, [sceneFilter, minConfidence]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // 场景下拉选项
  const sceneOptions = summary?.scene_breakdown?.map(s => s.scene_name) || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display flex items-center gap-2">
          <Brain size={22} className="text-finance-600" />
          AI 推理审计员
        </h1>
        <p className="text-sm text-surface-400 mt-1">
          文档 §5.3 评测驱动进化：审计每一次 AI 推理 · 校准置信度 · 驱动规则库迭代
        </p>
      </div>

      <EvalSummaryPanel summary={summary} />

      {/* 过滤栏 */}
      <div className="glass-card-static p-3 flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 text-xs text-surface-500">
          <Search size={12} /> 过滤：
        </div>
        <select
          value={sceneFilter}
          onChange={e => setSceneFilter(e.target.value)}
          className="px-2 py-1 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20"
        >
          <option value="">全部场景</option>
          {sceneOptions.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          value={minConfidence}
          onChange={e => setMinConfidence(e.target.value === '' ? '' : Number(e.target.value))}
          className="px-2 py-1 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20"
        >
          <option value="">全部置信度</option>
          <option value="90">≥90%</option>
          <option value="70">≥70%</option>
          <option value="50">≥50%</option>
        </select>
        <span className="text-xs text-surface-500 ml-auto">
          共 <strong className="text-finance-700">{traces.length}</strong> 条轨迹
        </span>
      </div>

      {/* 轨迹列表 */}
      {loading ? (
        <div className="text-center py-12 text-surface-400 text-sm">
          <Loader2 size={20} className="mx-auto mb-2 animate-spin" />
          加载推理轨迹…
        </div>
      ) : traces.length === 0 ? (
        <div className="text-center py-12 text-surface-400 text-sm">
          <Brain size={32} className="mx-auto mb-2 text-surface-300" />
          暂无推理轨迹。可在 BudgetPage 触发 B→A 转换、或在 AnalysisPage 跑 3GAP+3List 产生轨迹。
        </div>
      ) : (
        <div className="space-y-2">
          {traces.map(t => {
            const fb = t.feedback_summary;
            const calGap = t.calibration_gap;
            return (
              <button
                key={t.trace_id}
                onClick={() => setSelectedTrace(t)}
                className="w-full text-left p-3 rounded-xl bg-white border border-surface-200 hover:border-finance-300 hover:shadow-sm transition-all"
              >
                <div className="flex items-center gap-3 mb-1">
                  <span className="font-mono text-[10px] text-surface-500">{t.trace_id}</span>
                  <span className="badge-blue" style={{ fontSize: 9, padding: '1px 5px' }}>{t.scene_name || '未分类'}</span>
                  <span className="text-[10px] text-surface-400 ml-auto">{new Date(t.created_at).toLocaleString('zh-CN')}</span>
                </div>
                <p className="text-xs text-surface-700 line-clamp-2 mb-2">{t.conclusion || '(无结论)'}</p>
                <div className="flex items-center gap-3 text-[10px]">
                  <span className={clsx('font-bold', confidenceColor(Number(t.confidence ?? 0)))}>
                    置信度 {Number(t.confidence ?? 0).toFixed(0)}%
                  </span>
                  {fb && fb.feedback_count > 0 && (
                    <>
                      <span className="text-finance-600">
                        反馈 {fb.feedback_count}条 · 评分 {Number(fb.avg_accuracy ?? 0).toFixed(1)}/5
                      </span>
                      {calGap != null && (
                        <span className={clsx(
                          'font-semibold',
                          Math.abs(calGap) < 10 ? 'text-compliance-600' : 'text-warning-600'
                        )}>
                          校准 {calGap > 0 ? '+' : ''}{calGap}
                        </span>
                      )}
                    </>
                  )}
                  <Eye size={10} className="ml-auto text-surface-400" />
                </div>
              </button>
            );
          })}
        </div>
      )}

      <TraceDetailDrawer
        trace={selectedTrace}
        onClose={() => setSelectedTrace(null)}
        onFeedbackSubmit={fetchData}
      />
    </div>
  );
}
