import { motion } from 'framer-motion';
import { Lightbulb, AlertTriangle, TrendingDown, RefreshCw, Calendar, Eye } from 'lucide-react';
import { clsx } from 'clsx';

export interface ProactiveSuggestion {
  priority: 'critical' | 'attention' | 'info';
  category: string;
  title: string;
  detail: string;
  action_label: string;
  target_budget_id?: string | null;
  estimated_impact?: string | null;
}

export interface SuggestionsResponse {
  period: string;
  total: number;
  critical_count: number;
  attention_count: number;
  info_count: number;
  suggestions: ProactiveSuggestion[];
}

const PRIORITY_STYLE: Record<string, { color: string; bg: string; border: string; label: string }> = {
  critical: { color: 'text-alert-700', bg: 'bg-alert-50/70', border: 'border-alert-300', label: '紧急' },
  attention: { color: 'text-warning-700', bg: 'bg-warning-50/70', border: 'border-warning-300', label: '关注' },
  info: { color: 'text-brand-700', bg: 'bg-brand-50/70', border: 'border-brand-300', label: '提示' },
};

const CATEGORY_ICON: Record<string, any> = {
  风险: AlertTriangle,
  调拨: RefreshCw,
  节约: TrendingDown,
  复盘: Calendar,
  监控: Eye,
};

export default function ProactiveSuggestionPanel({
  data,
  loading,
}: {
  data: SuggestionsResponse | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="text-center py-10 text-surface-400 text-sm">
        <div className="inline-block w-5 h-5 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2" />
        AI 正在扫描预算风险…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-10 text-surface-400 text-sm">
        <Lightbulb size={20} className="mx-auto mb-2 opacity-40" />
        暂无主动建议
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 顶部统计 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="glass-card-static p-3 text-center">
          <p className="metric-label">建议总数</p>
          <p className="text-2xl font-bold text-finance-800 font-display">{data.total}</p>
        </div>
        <div className="bg-alert-50/60 border border-alert-200 rounded-xl p-3 text-center">
          <p className="metric-label">紧急</p>
          <p className="text-2xl font-bold text-alert-700 font-display">{data.critical_count}</p>
        </div>
        <div className="bg-warning-50/60 border border-warning-200 rounded-xl p-3 text-center">
          <p className="metric-label">关注</p>
          <p className="text-2xl font-bold text-warning-700 font-display">{data.attention_count}</p>
        </div>
        <div className="bg-brand-50/60 border border-brand-200 rounded-xl p-3 text-center">
          <p className="metric-label">提示</p>
          <p className="text-2xl font-bold text-brand-700 font-display">{data.info_count}</p>
        </div>
      </div>

      {data.suggestions.length === 0 ? (
        <div className="text-center py-8 text-surface-400 text-sm">
          <Lightbulb size={20} className="mx-auto mb-2 opacity-40" />
          当前预算执行状态良好，暂无主动建议
        </div>
      ) : (
        <div className="space-y-2.5">
          {data.suggestions.map((s, i) => {
            const style = PRIORITY_STYLE[s.priority] || PRIORITY_STYLE.info;
            const Icon = CATEGORY_ICON[s.category] || Lightbulb;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: i * 0.04 }}
                className={clsx(
                  'rounded-xl border-2 p-4 flex items-start gap-3',
                  style.bg,
                  style.border
                )}
              >
                <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center bg-white/60 shrink-0', style.color)}>
                  <Icon size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <h4 className="text-sm font-semibold text-finance-800">{s.title}</h4>
                    <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold', style.color, 'bg-white/60 border', style.border)}>
                      {style.label}
                    </span>
                    <span className="text-[10px] text-surface-500 px-1.5 py-0.5 rounded bg-white/40">
                      {s.category}
                    </span>
                  </div>
                  <p className="text-xs text-surface-700 leading-relaxed">{s.detail}</p>
                  <div className="flex items-center gap-3 mt-2 flex-wrap">
                    {s.action_label && (
                      <button
                        className={clsx(
                          'text-[11px] px-2.5 py-1 rounded-lg font-medium transition-colors',
                          style.color,
                          'bg-white/70 hover:bg-white border',
                          style.border
                        )}
                      >
                        {s.action_label}
                      </button>
                    )}
                    {s.estimated_impact && (
                      <span className="text-[10px] text-surface-500">
                        预期影响：<span className="font-semibold text-finance-700">{s.estimated_impact}</span>
                      </span>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
