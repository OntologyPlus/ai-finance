import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Layers, ChevronDown, ChevronRight, Sparkles } from 'lucide-react';
import { clsx } from 'clsx';

export interface RootCauseLayer {
  level: number;
  title: string;
  finding: string;
  severity: 'info' | 'warning' | 'risk';
  metric?: number | null;
  metric_unit?: string;
  evidence: string[];
}

export interface RootCauseDrill {
  budget_id: string;
  budget_name: string;
  issue_type: string;
  severity: 'info' | 'warning' | 'risk' | 'critical';
  summary: string;
  layers: RootCauseLayer[];
  final_recommendation: string;
}

const SEVERITY_STYLE: Record<string, { color: string; bg: string; border: string }> = {
  info: { color: 'text-brand-700', bg: 'bg-brand-50/60', border: 'border-brand-200' },
  warning: { color: 'text-warning-700', bg: 'bg-warning-50/60', border: 'border-warning-200' },
  risk: { color: 'text-alert-700', bg: 'bg-alert-50/60', border: 'border-alert-200' },
  critical: { color: 'text-alert-800', bg: 'bg-alert-100/60', border: 'border-alert-300' },
};

const LAYER_ICON: Record<number, string> = {
  1: '🔍',
  2: '📊',
  3: '🏗️',
  4: '⏱️',
  5: '🔗',
};

export default function RootCauseDrillDown({
  data,
  budgetOptions,
  loading,
}: {
  data: RootCauseDrill | null;
  budgetOptions: { budget_id: string; description: string; rate: number }[];
  loading: boolean;
}) {
  const [selectedId, setSelectedId] = useState<string>(budgetOptions[0]?.budget_id || '');
  const [expanded, setExpanded] = useState<Set<number>>(new Set([1, 2, 3, 4, 5]));

  const toggleLayer = (lvl: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(lvl)) next.delete(lvl);
      else next.add(lvl);
      return next;
    });
  };

  const selected = budgetOptions.find((b) => b.budget_id === selectedId);

  return (
    <div className="space-y-4">
      {/* 顶部选择器 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-surface-600">
          <Search size={12} />
          <span>选择预算项：</span>
        </div>
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 min-w-[260px]"
        >
          {budgetOptions.map((b) => (
            <option key={b.budget_id} value={b.budget_id}>
              {b.budget_id} · {b.description} ({b.rate}%)
            </option>
          ))}
        </select>
        {selected && (
          <div className="flex items-center gap-2 text-[11px] text-surface-500">
            <span>执行率</span>
            <span
              className={clsx(
                'font-mono font-bold px-1.5 py-0.5 rounded',
                selected.rate >= 100
                  ? 'text-alert-700 bg-alert-50'
                  : selected.rate >= 80
                    ? 'text-warning-700 bg-warning-50'
                    : 'text-compliance-700 bg-compliance-50'
              )}
            >
              {selected.rate}%
            </span>
          </div>
        )}
      </div>

      {loading && (
        <div className="text-center py-10 text-surface-400 text-sm">
          <div className="inline-block w-5 h-5 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2" />
          正在分析根因…
        </div>
      )}

      {!loading && !data && (
        <div className="text-center py-10 text-surface-400 text-sm">
          <Layers size={20} className="mx-auto mb-2 opacity-40" />
          请选择预算项以查看 5 层根因下钻
        </div>
      )}

      {!loading && data && (
        <>
          {/* 顶部摘要卡 */}
          <div
            className={clsx(
              'rounded-xl border-2 p-4',
              SEVERITY_STYLE[data.severity]?.bg,
              SEVERITY_STYLE[data.severity]?.border
            )}
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2">
                  <Layers size={14} className="text-finance-600" />
                  {data.budget_name}（{data.budget_id}）
                </h3>
                <p className="text-xs text-surface-600 mt-1">{data.summary}</p>
              </div>
              <span
                className={clsx(
                  'px-2 py-0.5 rounded-full text-[10px] font-bold border',
                  SEVERITY_STYLE[data.severity]?.color,
                  SEVERITY_STYLE[data.severity]?.border
                )}
              >
                {data.issue_type}
              </span>
            </div>
            <div className="bg-white/60 rounded-lg p-2.5 mt-2 flex items-start gap-2">
              <Sparkles size={14} className="text-brand-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-[10px] text-surface-400 font-semibold">最终建议</p>
                <p className="text-xs text-surface-800 mt-0.5">{data.final_recommendation}</p>
              </div>
            </div>
          </div>

          {/* 5 层根因下钻 */}
          <div className="space-y-2">
            {data.layers.map((layer) => {
              const isOpen = expanded.has(layer.level);
              const style = SEVERITY_STYLE[layer.severity] || SEVERITY_STYLE.info;
              return (
                <motion.div
                  key={layer.level}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.15 }}
                  className={clsx('rounded-xl border p-3', style.bg, style.border)}
                >
                  <button
                    onClick={() => toggleLayer(layer.level)}
                    className="w-full flex items-center justify-between text-left"
                  >
                    <div className="flex items-center gap-2 flex-1">
                      <span className="text-base">{LAYER_ICON[layer.level] || '·'}</span>
                      <h4 className={clsx('text-xs font-semibold', style.color)}>{layer.title}</h4>
                      <span
                        className={clsx(
                          'px-1.5 py-0.5 rounded text-[10px] font-bold',
                          style.color === 'text-alert-700' || style.color === 'text-alert-800'
                            ? 'bg-alert-100'
                            : style.color === 'text-warning-700'
                              ? 'bg-warning-100'
                              : 'bg-brand-100'
                        )}
                      >
                        {layer.severity}
                      </span>
                    </div>
                    {isOpen ? (
                      <ChevronDown size={14} className="text-surface-400" />
                    ) : (
                      <ChevronRight size={14} className="text-surface-400" />
                    )}
                  </button>

                  <p className="text-xs text-surface-700 mt-1.5 leading-relaxed">{layer.finding}</p>

                  <AnimatePresence>
                    {isOpen && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="mt-2 space-y-1"
                      >
                        {layer.metric != null && (
                          <div className="flex items-center gap-2 text-[11px] text-surface-500">
                            <span className="font-semibold">度量值：</span>
                            <span className="font-mono text-surface-800">
                              {layer.metric.toFixed(1)}
                              {layer.metric_unit || ''}
                            </span>
                          </div>
                        )}
                        {layer.evidence && layer.evidence.length > 0 && (
                          <div className="bg-white/50 rounded-lg p-2">
                            <p className="text-[10px] text-surface-400 font-semibold mb-1">证据</p>
                            <ul className="space-y-0.5">
                              {layer.evidence.map((e, i) => (
                                <li
                                  key={i}
                                  className="text-[11px] text-surface-600 flex gap-1.5"
                                >
                                  <span className="text-brand-500 shrink-0">·</span>
                                  <span>{e}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
