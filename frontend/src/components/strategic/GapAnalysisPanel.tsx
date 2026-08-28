import { motion } from 'framer-motion';
import { Target, CheckCircle2, AlertCircle, TrendingUp, TrendingDown } from 'lucide-react';
import { clsx } from 'clsx';

interface GapItem {
  intent: string;
  initiative_count: number;
  kpi_target: number;
  kpi_actual: number;
  achievement_rate: number;
  gap_amount: number;
  gap_rate: number;
  budget_planned: number;
  budget_used: number;
  budget_execution_rate: number;
  status: string;
  status_label: string;
  suggestions: string[];
}

interface GapAnalysis {
  gaps: GapItem[];
  summary: {
    total_intents: number;
    on_track_count: number;
    critical_count: number;
    watch_count: number;
    behind_count: number;
    overall_health_rate: number;
  };
}

const STATUS_STYLE: Record<string, { color: string; bg: string; border: string; icon: any }> = {
  on_track: { color: 'text-compliance-700', bg: 'bg-compliance-50/60', border: 'border-compliance-300', icon: CheckCircle2 },
  watch: { color: 'text-finance-700', bg: 'bg-finance-50/60', border: 'border-finance-300', icon: Target },
  behind: { color: 'text-warning-700', bg: 'bg-warning-50/60', border: 'border-warning-300', icon: AlertCircle },
  critical: { color: 'text-alert-700', bg: 'bg-alert-50/60', border: 'border-alert-300', icon: AlertCircle },
};

function formatAmount(n: number): string {
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}万`;
  return n.toLocaleString();
}

export default function GapAnalysisPanel({ data }: { data: GapAnalysis | null }) {
  if (!data) {
    return (
      <div className="glass-card-static p-5 text-center text-surface-400 text-sm">
        <Target size={20} className="mx-auto mb-2 opacity-40" />
        暂无 GAP 分析数据
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 顶部摘要 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="glass-card-static p-3 text-center">
          <p className="metric-label mb-1">战略意图总数</p>
          <p className="text-2xl font-bold text-finance-800 font-display">{data.summary.total_intents}</p>
        </div>
        <div className="bg-compliance-50/60 border border-compliance-200 rounded-xl p-3 text-center">
          <p className="metric-label mb-1">达标</p>
          <p className="text-2xl font-bold text-compliance-700 font-display">{data.summary.on_track_count}</p>
        </div>
        <div className="bg-finance-50/60 border border-finance-200 rounded-xl p-3 text-center">
          <p className="metric-label mb-1">观察</p>
          <p className="text-2xl font-bold text-finance-700 font-display">{data.summary.watch_count}</p>
        </div>
        <div className="bg-warning-50/60 border border-warning-200 rounded-xl p-3 text-center">
          <p className="metric-label mb-1">落后</p>
          <p className="text-2xl font-bold text-warning-700 font-display">{data.summary.behind_count}</p>
        </div>
        <div className="bg-alert-50/60 border border-alert-200 rounded-xl p-3 text-center">
          <p className="metric-label mb-1">严重落后</p>
          <p className="text-2xl font-bold text-alert-700 font-display">{data.summary.critical_count}</p>
        </div>
      </div>

      {/* 整体健康度 */}
      <div className="rounded-xl border-2 border-finance-200 bg-finance-50/40 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-finance-800">整体战略健康度</h4>
            <p className="text-xs text-surface-500 mt-0.5">基于战略意图达标率（达标/总数）</p>
          </div>
          <div className="text-3xl font-bold font-display text-finance-700">
            {data.summary.overall_health_rate.toFixed(0)}%
          </div>
        </div>
      </div>

      {/* 每个战略意图详细 GAP */}
      <div className="space-y-3">
        {data.gaps.map((g) => {
          const style = STATUS_STYLE[g.status] || STATUS_STYLE.watch;
          const Icon = style.icon;
          return (
            <motion.div
              key={g.intent}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={clsx('rounded-xl border-2 p-4', style.bg, style.border)}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Icon size={16} className={style.color} />
                  <h4 className="font-semibold text-finance-800">{g.intent}</h4>
                  <span className={clsx('px-2 py-0.5 rounded-full text-[10px] font-bold', style.bg, style.color, 'border', style.border)}>
                    {g.status_label}
                  </span>
                </div>
                <span className="text-xs text-surface-500">{g.initiative_count} 项举措</span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                <div className="bg-white/60 rounded-lg p-2.5">
                  <p className="text-[10px] text-surface-400">KPI 目标</p>
                  <p className="text-sm font-bold text-surface-800 font-mono">{formatAmount(g.kpi_target)}</p>
                </div>
                <div className="bg-white/60 rounded-lg p-2.5">
                  <p className="text-[10px] text-surface-400">KPI 实际</p>
                  <p className="text-sm font-bold text-finance-700 font-mono">{formatAmount(g.kpi_actual)}</p>
                </div>
                <div className="bg-white/60 rounded-lg p-2.5">
                  <p className="text-[10px] text-surface-400">达成率</p>
                  <div className="flex items-center gap-1">
                    <p className={clsx('text-sm font-bold font-mono', g.achievement_rate >= 90 ? 'text-compliance-700' : g.achievement_rate >= 70 ? 'text-finance-700' : 'text-warning-700')}>
                      {g.achievement_rate.toFixed(0)}%
                    </p>
                    {g.achievement_rate >= 100 ? <TrendingUp size={12} className="text-compliance-500" /> : <TrendingDown size={12} className="text-warning-500" />}
                  </div>
                </div>
                <div className="bg-white/60 rounded-lg p-2.5">
                  <p className="text-[10px] text-surface-400">预算执行</p>
                  <p className={clsx('text-sm font-bold font-mono', g.budget_execution_rate >= 80 ? 'text-compliance-700' : g.budget_execution_rate >= 50 ? 'text-finance-700' : 'text-warning-700')}>
                    {g.budget_execution_rate.toFixed(0)}%
                  </p>
                </div>
              </div>

              <div className="h-1.5 bg-white/40 rounded-full overflow-hidden mb-3">
                <motion.div
                  className={clsx('h-full', g.achievement_rate >= 90 ? 'bg-compliance-500' : g.achievement_rate >= 70 ? 'bg-finance-500' : g.achievement_rate >= 50 ? 'bg-warning-500' : 'bg-alert-500')}
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, g.achievement_rate)}%` }}
                  transition={{ duration: 0.6 }}
                />
              </div>

              {g.suggestions.length > 0 && (
                <div className="border-t border-white/40 pt-2.5">
                  <p className="text-[10px] text-surface-500 mb-1 font-semibold">AI 建议</p>
                  <ul className="space-y-0.5">
                    {g.suggestions.map((s, i) => (
                      <li key={i} className="text-xs text-surface-700 flex gap-1.5">
                        <span className="text-brand-500 shrink-0">▸</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
