import { motion } from 'framer-motion';
import { CheckCircle2, XCircle, AlertCircle, Sparkles, TrendingUp, TrendingDown, Gauge } from 'lucide-react';
import { clsx } from 'clsx';
import ReactECharts from 'echarts-for-react';

export interface DecisionFactor {
  name: string;
  score: number;
  weight: number;
  weighted: number;
  assessment: string;
  detail: string;
}

export interface GoNoGoDecision {
  pipeline_id: string;
  name: string;
  current_stage: string;
  total_score: number;
  decision: 'Go' | 'No-Go' | 'Conditional';
  confidence: 'high' | 'medium' | 'low';
  factors: DecisionFactor[];
  risk_factors: string[];
  enablers: string[];
  next_action: string;
}

const DECISION_STYLE: Record<string, { color: string; bg: string; border: string; icon: any; label: string }> = {
  Go: { color: 'text-compliance-700', bg: 'bg-compliance-50/70', border: 'border-compliance-300', icon: CheckCircle2, label: 'Go（推进）' },
  'No-Go': { color: 'text-alert-700', bg: 'bg-alert-50/70', border: 'border-alert-300', icon: XCircle, label: 'No-Go（终止）' },
  Conditional: { color: 'text-warning-700', bg: 'bg-warning-50/70', border: 'border-warning-300', icon: AlertCircle, label: 'Conditional（有条件）' },
};

const ASSESS_COLOR: Record<string, string> = {
  高: 'text-compliance-700',
  中: 'text-finance-700',
  低: 'text-alert-700',
};

export default function GoNoGoPanel({
  data,
  loading,
}: {
  data: GoNoGoDecision | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="text-center py-10 text-surface-400 text-sm">
        <div className="inline-block w-5 h-5 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2" />
        AI 正在评估 Go/No-Go…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-10 text-surface-400 text-sm">
        <Gauge size={20} className="mx-auto mb-2 opacity-40" />
        请选择管线查看 Go/No-Go 决策
      </div>
    );
  }

  const dStyle = DECISION_STYLE[data.decision] || DECISION_STYLE.Conditional;
  const Icon = dStyle.icon;

  // 雷达图
  const radarOption = {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: data.factors.map((f) => ({ name: f.name, max: 100 })),
      shape: 'polygon' as const,
      splitNumber: 4,
      axisName: { color: '#475569', fontSize: 11 },
      splitArea: { areaStyle: { color: ['#fafafa', '#f0f4ff', '#e0e7ff', '#dbeafe'] } },
    },
    series: [
      {
        type: 'radar' as const,
        data: [
          {
            name: '5 因素评分',
            value: data.factors.map((f) => f.score),
            lineStyle: { color: '#3b82f6', width: 2 },
            areaStyle: { color: 'rgba(59,130,246,0.2)' },
            itemStyle: { color: '#3b82f6' },
          },
        ],
      },
    ],
  };

  return (
    <div className="space-y-4">
      {/* 顶部决策卡 */}
      <motion.div
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className={clsx('rounded-xl border-2 p-5', dStyle.bg, dStyle.border)}
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2">
              <Icon size={18} className={dStyle.color} />
              {data.name}（{data.pipeline_id}）
            </h3>
            <p className="text-xs text-surface-500 mt-1">当前阶段：{data.current_stage}</p>
          </div>
          <div className="text-right">
            <div className={clsx('text-4xl font-bold font-display', dStyle.color)}>
              {data.total_score.toFixed(0)}
            </div>
            <div className="flex items-center gap-1.5 mt-1">
              <span className={clsx('px-2 py-0.5 rounded-full text-xs font-bold', dStyle.bg, dStyle.color, 'border', dStyle.border)}>
                {dStyle.label}
              </span>
              <span className="text-[10px] text-surface-500">置信度 {data.confidence}</span>
            </div>
          </div>
        </div>
        <div className="bg-white/60 rounded-lg p-2.5 flex items-start gap-2">
          <Sparkles size={14} className="text-brand-500 mt-0.5 shrink-0" />
          <div>
            <p className="text-[10px] text-surface-400 font-semibold">下一步行动</p>
            <p className="text-xs text-surface-800 mt-0.5">{data.next_action}</p>
          </div>
        </div>
      </motion.div>

      {/* 雷达图 + 因素列表 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass-card-static p-4">
          <h4 className="text-sm font-semibold text-surface-700 mb-2">5 因素评分雷达</h4>
          <ReactECharts option={radarOption} style={{ height: '280px' }} />
        </div>
        <div className="glass-card-static p-4">
          <h4 className="text-sm font-semibold text-surface-700 mb-3">因素评分明细</h4>
          <div className="space-y-2.5">
            {data.factors.map((f, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-surface-700 flex items-center gap-1.5">
                    {f.name}
                    <span className={clsx('text-[10px] font-bold', ASSESS_COLOR[f.assessment] || 'text-surface-500')}>
                      {f.assessment}
                    </span>
                  </span>
                  <span className="text-xs font-mono text-surface-600">
                    {f.score.toFixed(0)} <span className="text-surface-400">×{(f.weight * 100).toFixed(0)}%</span>
                  </span>
                </div>
                <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden">
                  <motion.div
                    className={clsx(
                      'h-full rounded-full',
                      f.score >= 70 ? 'bg-compliance-500' : f.score >= 40 ? 'bg-finance-500' : 'bg-alert-500'
                    )}
                    initial={{ width: 0 }}
                    animate={{ width: `${f.score}%` }}
                    transition={{ duration: 0.6, ease: 'easeOut', delay: i * 0.1 }}
                  />
                </div>
                <p className="text-[10px] text-surface-400 mt-0.5">{f.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 风险点 & 推动因素 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data.risk_factors.length > 0 && (
          <div className="bg-alert-50/40 border border-alert-200 rounded-xl p-4">
            <h4 className="text-sm font-semibold text-alert-700 mb-2 flex items-center gap-2">
              <TrendingDown size={14} />
              关键风险点（{data.risk_factors.length}）
            </h4>
            <ul className="space-y-1.5">
              {data.risk_factors.map((r, i) => (
                <li key={i} className="text-xs text-surface-700 flex gap-2">
                  <span className="text-alert-500 shrink-0">▸</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {data.enablers.length > 0 && (
          <div className="bg-compliance-50/40 border border-compliance-200 rounded-xl p-4">
            <h4 className="text-sm font-semibold text-compliance-700 mb-2 flex items-center gap-2">
              <TrendingUp size={14} />
              关键推动因素（{data.enablers.length}）
            </h4>
            <ul className="space-y-1.5">
              {data.enablers.map((e, i) => (
                <li key={i} className="text-xs text-surface-700 flex gap-2">
                  <span className="text-compliance-500 shrink-0">▸</span>
                  <span>{e}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
