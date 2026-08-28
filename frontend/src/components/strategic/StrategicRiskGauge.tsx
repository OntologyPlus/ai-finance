import { motion } from 'framer-motion';
import { Gauge, AlertTriangle, TrendingUp, Lightbulb } from 'lucide-react';
import { clsx } from 'clsx';
import ReactECharts from 'echarts-for-react';

interface DimensionScore {
  dimension: string;
  label: string;
  score: number;
  weight: number;
  weighted: number;
  detail: string;
  evidence: string[];
}

interface RiskGauge {
  overall_score: number;
  grade: string;
  risk_level: string;
  risk_label: string;
  dimensions: DimensionScore[];
  summary: string;
  top_risks: string[];
  recommendations: string[];
}

const LEVEL_STYLE: Record<string, { color: string; bg: string; border: string }> = {
  low: { color: 'text-compliance-700', bg: 'bg-compliance-50/40', border: 'border-compliance-300' },
  medium: { color: 'text-finance-700', bg: 'bg-finance-50/40', border: 'border-finance-300' },
  high: { color: 'text-warning-700', bg: 'bg-warning-50/40', border: 'border-warning-300' },
  critical: { color: 'text-alert-700', bg: 'bg-alert-50/40', border: 'border-alert-300' },
};

export default function StrategicRiskGauge({ data }: { data: RiskGauge | null }) {
  if (!data) {
    return (
      <div className="glass-card-static p-5 text-center text-surface-400 text-sm">
        <Gauge size={20} className="mx-auto mb-2 opacity-40" />
        暂无战略风险数据
      </div>
    );
  }

  const style = LEVEL_STYLE[data.risk_level] || LEVEL_STYLE.medium;
  const score = data.overall_score;

  // 雷达图配置
  const radarOption = {
    tooltip: { trigger: 'item' },
    radar: {
      indicator: data.dimensions.map((d) => ({ name: d.label, max: 100 })),
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
            name: '战略风险评分',
            value: data.dimensions.map((d) => d.score),
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
      {/* 顶部综合评分 */}
      <div className={clsx('rounded-xl border-2 p-5', style.bg, style.border)}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-surface-700 mb-1 flex items-center gap-2">
              <Gauge size={16} className={style.color} />
              战略风险评分
            </h3>
            <p className="text-xs text-surface-500">{data.summary}</p>
          </div>
          <div className="text-right">
            <div className={clsx('text-4xl font-bold font-display', style.color)}>
              {score.toFixed(0)}
            </div>
            <div className="flex items-center gap-1.5 mt-1">
              <span className={clsx('px-2 py-0.5 rounded-full text-xs font-bold', style.bg, style.color, 'border', style.border)}>
                {data.grade} 级
              </span>
              <span className="text-xs text-surface-500">{data.risk_label}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 雷达图 + 维度列表 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass-card-static p-4">
          <h4 className="text-sm font-semibold text-surface-700 mb-2">5 维风险分布</h4>
          <ReactECharts option={radarOption} style={{ height: '280px' }} />
        </div>

        <div className="glass-card-static p-4">
          <h4 className="text-sm font-semibold text-surface-700 mb-3">维度评分明细</h4>
          <div className="space-y-2.5">
            {data.dimensions.map((dim) => {
              const dimStyle = LEVEL_STYLE[
                dim.score >= 75 ? 'low' : dim.score >= 60 ? 'medium' : dim.score >= 40 ? 'high' : 'critical'
              ] || LEVEL_STYLE.medium;
              return (
                <div key={dim.dimension}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-surface-700">{dim.label}</span>
                    <span className="text-xs font-mono text-surface-600">
                      {dim.score.toFixed(0)} <span className="text-surface-400">×{(dim.weight * 100).toFixed(0)}%</span>
                    </span>
                  </div>
                  <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden">
                    <motion.div
                      className={clsx('h-full rounded-full', dimStyle.color.replace('text-', 'bg-'))}
                      initial={{ width: 0 }}
                      animate={{ width: `${dim.score}%` }}
                      transition={{ duration: 0.6, ease: 'easeOut' }}
                    />
                  </div>
                  <p className="text-[10px] text-surface-400 mt-0.5">{dim.detail}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Top 风险 + 改进建议 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {data.top_risks.length > 0 && (
          <div className="bg-alert-50/40 border border-alert-200 rounded-xl p-4">
            <h4 className="text-sm font-semibold text-alert-700 mb-2 flex items-center gap-2">
              <AlertTriangle size={14} />
              Top 风险点
            </h4>
            <ul className="space-y-1.5">
              {data.top_risks.map((r, i) => (
                <li key={i} className="text-xs text-surface-700 flex gap-2">
                  <span className="text-alert-500 shrink-0">▸</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {data.recommendations.length > 0 && (
          <div className="bg-brand-50/40 border border-brand-200 rounded-xl p-4">
            <h4 className="text-sm font-semibold text-brand-700 mb-2 flex items-center gap-2">
              <Lightbulb size={14} />
              AI 改进建议
            </h4>
            <ul className="space-y-1.5">
              {data.recommendations.map((r, i) => (
                <li key={i} className="text-xs text-surface-700 flex gap-2">
                  <span className="text-brand-500 shrink-0">▸</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
