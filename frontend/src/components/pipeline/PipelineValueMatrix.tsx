import { motion } from 'framer-motion';
import { ScatterChart, Wallet, TrendingUp, Lightbulb, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import ReactECharts from 'echarts-for-react';

export interface PipelineValue {
  pipeline_id: string;
  name: string;
  indication: string;
  current_stage: string;
  stage_probability: number;
  cumulative_probability: number;
  peak_sales: number;
  net_margin: number;
  expected_value: number;
  total_invested: number;
  risk_adjusted_npv: number;
  value_tier: 'S' | 'A' | 'B' | 'C';
  recommendation: string;
}

export interface ValueMatrix {
  pipelines: PipelineValue[];
  summary: {
    total_pipelines: number;
    tier_counts: Record<string, number>;
    total_expected_value: number;
    total_risk_adjusted_npv: number;
    avg_expected_value: number;
    avg_cumulative_probability: number;
  };
  quadrants: Record<string, string[]>;
}

const TIER_STYLE: Record<string, { color: string; bg: string; border: string }> = {
  S: { color: 'text-alert-700', bg: 'bg-alert-100/60', border: 'border-alert-300' },
  A: { color: 'text-finance-700', bg: 'bg-finance-50/60', border: 'border-finance-300' },
  B: { color: 'text-brand-700', bg: 'bg-brand-50/60', border: 'border-brand-300' },
  C: { color: 'text-surface-600', bg: 'bg-surface-100/60', border: 'border-surface-300' },
};

const QUADRANT_STYLE: Record<string, { color: string; bg: string; border: string; icon: string }> = {
  明星: { color: 'text-alert-700', bg: 'bg-alert-50/60', border: 'border-alert-300', icon: '⭐' },
  问号: { color: 'text-warning-700', bg: 'bg-warning-50/60', border: 'border-warning-300', icon: '❓' },
  金牛: { color: 'text-compliance-700', bg: 'bg-compliance-50/60', border: 'border-compliance-300', icon: '🐄' },
  瘦狗: { color: 'text-surface-600', bg: 'bg-surface-50/60', border: 'border-surface-300', icon: '🐕' },
};

function formatAmount(n: number): string {
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}亿`;
  return `${n.toFixed(0)}万`;
}

export default function PipelineValueMatrix({ data }: { data: ValueMatrix | null }) {
  if (!data) {
    return (
      <div className="glass-card-static p-5 text-center text-surface-400 text-sm">
        <ScatterChart size={20} className="mx-auto mb-2 opacity-40" />
        暂无价值矩阵数据
      </div>
    );
  }

  // 散点图：横轴=上市概率(0-1)，纵轴=预期价值(万元)
  const scatterData = data.pipelines.map((p) => ({
    name: p.name,
    value: [
      Math.round(p.cumulative_probability * 100),
      Math.round(p.expected_value),
      p.pipeline_id,
      p.value_tier,
    ],
  }));

  const avgValue = data.summary.avg_expected_value;
  const avgProb = data.summary.avg_cumulative_probability * 100;

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const [prob, val, id, tier] = params.value;
        return `<b>${params.name}</b><br/>ID: ${id}<br/>上市概率: ${prob}%<br/>预期价值: ${val}万<br/>分层: ${tier}`;
      },
    },
    grid: { left: 60, right: 20, bottom: 50, top: 30 },
    xAxis: {
      type: 'value',
      name: '上市概率 (%)',
      nameLocation: 'middle',
      nameGap: 30,
      min: 0,
      max: 100,
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    yAxis: {
      type: 'value',
      name: '预期价值 (万)',
      nameLocation: 'middle',
      nameGap: 45,
      axisLabel: { color: '#94a3b8', fontSize: 10, formatter: (v: number) => v.toLocaleString() },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    series: [
      {
        type: 'scatter',
        symbolSize: (val: number[]) => 12 + Math.min(20, val[1] / 1000),
        itemStyle: {
          color: (params: any) => {
            const tier = params.value[3];
            return tier === 'S' ? '#f87171' : tier === 'A' ? '#3b82f6' : tier === 'B' ? '#6366f1' : '#94a3b8';
          },
          opacity: 0.7,
          borderColor: '#fff',
          borderWidth: 1,
        },
        data: scatterData,
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', color: '#cbd5e1', width: 1 },
          data: [
            { xAxis: avgProb, label: { formatter: `平均概率 ${avgProb.toFixed(0)}%`, color: '#94a3b8', fontSize: 9 } },
            { yAxis: avgValue, label: { formatter: `平均价值 ${avgValue.toFixed(0)}万`, color: '#94a3b8', fontSize: 9 } },
          ],
        },
      },
    ],
  };

  return (
    <div className="space-y-4">
      {/* 顶部统计 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="glass-card-static p-3 text-center">
          <p className="metric-label">管线总数</p>
          <p className="text-2xl font-bold text-finance-800 font-display">{data.summary.total_pipelines}</p>
        </div>
        {(['S', 'A', 'B', 'C'] as const).map(t => {
          const s = TIER_STYLE[t];
          return (
            <div key={t} className={clsx('rounded-xl p-3 text-center border-2', s.bg, s.border)}>
              <p className="metric-label">{t} 级</p>
              <p className={clsx('text-2xl font-bold font-display', s.color)}>{data.summary.tier_counts[t] || 0}</p>
            </div>
          );
        })}
      </div>

      {/* 价值散点图 */}
      <div className="bg-white rounded-xl border border-surface-200/60 p-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-finance-800 flex items-center gap-2">
            <ScatterChart size={14} />
            价值矩阵：上市概率 × 预期价值
          </h4>
          <span className="text-[10px] text-surface-500">气泡大小 ∝ 预期价值</span>
        </div>
        <ReactECharts option={option} style={{ height: '320px' }} />
        <p className="text-[11px] text-surface-500 mt-2 leading-relaxed">
          象限划分：<span className="text-alert-600">右上 明星</span>（高概率+高价值） ·{' '}
          <span className="text-warning-600">左上 问号</span>（低概率+高价值） ·{' '}
          <span className="text-compliance-600">右下 金牛</span>（高概率+低价值） ·{' '}
          <span className="text-surface-500">左下 瘦狗</span>（低概率+低价值）
        </p>
      </div>

      {/* BCG 象限分桶 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(['明星', '问号', '金牛', '瘦狗'] as const).map(q => {
          const s = QUADRANT_STYLE[q];
          const ids = data.quadrants[q] || [];
          return (
            <div key={q} className={clsx('rounded-xl border-2 p-3', s.bg, s.border)}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-base">{s.icon}</span>
                  <h4 className={clsx('text-xs font-bold', s.color)}>{q}</h4>
                </div>
                <span className={clsx('text-xs font-mono font-bold', s.color)}>{ids.length}</span>
              </div>
              <div className="space-y-0.5 max-h-24 overflow-y-auto">
                {ids.length === 0 ? (
                  <p className="text-[10px] text-surface-400 italic">无</p>
                ) : (
                  ids.map(id => (
                    <p key={id} className="text-[10px] text-surface-600 font-mono truncate">
                      {id}
                    </p>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 管线价值列表 */}
      <div className="bg-white rounded-xl border border-surface-200/60 overflow-hidden">
        <div className="px-4 py-2 bg-surface-50/50 border-b border-surface-200/60 flex items-center gap-2">
          <TrendingUp size={14} className="text-finance-600" />
          <h4 className="text-xs font-semibold text-surface-700">管线价值详情（按 rNPV 排序）</h4>
        </div>
        <div className="max-h-72 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white/95 backdrop-blur">
              <tr className="border-b border-surface-200/60 text-surface-500">
                <th className="text-left py-2 px-3 font-semibold">管线</th>
                <th className="text-left py-2 px-3 font-semibold">适应症</th>
                <th className="text-left py-2 px-3 font-semibold">当前阶段</th>
                <th className="text-right py-2 px-3 font-semibold">上市概率</th>
                <th className="text-right py-2 px-3 font-semibold">预期价值</th>
                <th className="text-right py-2 px-3 font-semibold">rNPV</th>
                <th className="text-center py-2 px-3 font-semibold">分层</th>
              </tr>
            </thead>
            <tbody>
              {[...data.pipelines].sort((a, b) => b.risk_adjusted_npv - a.risk_adjusted_npv).map((p) => {
                const tStyle = TIER_STYLE[p.value_tier];
                return (
                  <motion.tr
                    key={p.pipeline_id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors"
                  >
                    <td className="py-2 px-3">
                      <p className="font-medium text-surface-800 truncate max-w-[160px]">{p.name}</p>
                      <p className="text-[10px] text-surface-400 font-mono">{p.pipeline_id}</p>
                    </td>
                    <td className="py-2 px-3 text-surface-600">{p.indication}</td>
                    <td className="py-2 px-3 text-surface-600">{p.current_stage}</td>
                    <td className="py-2 px-3 text-right font-mono">
                      <span className="text-finance-700 font-bold">{(p.cumulative_probability * 100).toFixed(1)}%</span>
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-surface-800">{formatAmount(p.expected_value)}</td>
                    <td className="py-2 px-3 text-right font-mono">
                      <span className={clsx(
                        p.risk_adjusted_npv >= 0 ? 'text-compliance-700 font-bold' : 'text-alert-700 font-bold'
                      )}>
                        {p.risk_adjusted_npv >= 0 ? '+' : ''}{formatAmount(p.risk_adjusted_npv)}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-center">
                      <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold border', tStyle.bg, tStyle.color, tStyle.border)}>
                        {p.value_tier}
                      </span>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 总价值 & 总 rNPV */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-finance-50/60 border-2 border-finance-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Wallet size={14} className="text-finance-600" />
            <p className="text-[10px] text-surface-500 font-semibold">总预期价值</p>
          </div>
          <p className="text-2xl font-bold text-finance-800 font-display">
            {formatAmount(data.summary.total_expected_value)}
          </p>
        </div>
        <div className={clsx(
          'border-2 rounded-xl p-4',
          data.summary.total_risk_adjusted_npv >= 0
            ? 'bg-compliance-50/60 border-compliance-200'
            : 'bg-alert-50/60 border-alert-200'
        )}>
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp size={14} className={data.summary.total_risk_adjusted_npv >= 0 ? 'text-compliance-600' : 'text-alert-600'} />
            <p className="text-[10px] text-surface-500 font-semibold">总 rNPV</p>
          </div>
          <p className={clsx(
            'text-2xl font-bold font-display',
            data.summary.total_risk_adjusted_npv >= 0 ? 'text-compliance-700' : 'text-alert-700'
          )}>
            {data.summary.total_risk_adjusted_npv >= 0 ? '+' : ''}{formatAmount(data.summary.total_risk_adjusted_npv)}
          </p>
        </div>
        <div className="bg-brand-50/60 border-2 border-brand-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1">
            <Lightbulb size={14} className="text-brand-600" />
            <p className="text-[10px] text-surface-500 font-semibold">平均上市概率</p>
          </div>
          <p className="text-2xl font-bold text-brand-700 font-display">
            {(data.summary.avg_cumulative_probability * 100).toFixed(1)}%
          </p>
        </div>
      </div>
    </div>
  );
}
