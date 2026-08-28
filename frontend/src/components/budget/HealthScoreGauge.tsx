/**
 * HealthScoreGauge — 综合分大圆 + grade 徽章
 * A/B/C/D 四级评定 + 5 维度小条
 */
import ReactECharts from 'echarts-for-react';

interface DimensionScores {
  execution: number;
  alignment: number;
  risk: number;
  transfer: number;
  data: number;
}

interface Props {
  overallScore: number;
  grade: string;
  scores: DimensionScores;
  height?: number;
}

const GRADE_STYLE: Record<string, { bg: string; text: string; ring: string }> = {
  A: { bg: 'bg-compliance-50', text: 'text-compliance-700', ring: '#16a34a' },
  B: { bg: 'bg-brand-50', text: 'text-brand-700', ring: '#0ea5e9' },
  C: { bg: 'bg-warning-50', text: 'text-warning-700', ring: '#f59e0b' },
  D: { bg: 'bg-alert-50', text: 'text-alert-700', ring: '#ef4444' },
};

const DIM_META: { key: keyof DimensionScores; label: string }[] = [
  { key: 'execution', label: '执行率' },
  { key: 'alignment', label: '战略对齐' },
  { key: 'risk', label: '风险敞口' },
  { key: 'transfer', label: '调拨合理' },
  { key: 'data', label: '数据完整' },
];

export default function HealthScoreGauge({ overallScore, grade, scores, height = 280 }: Props) {
  const style = GRADE_STYLE[grade] || GRADE_STYLE.C;

  const option = {
    series: [
      {
        type: 'gauge',
        startAngle: 220,
        endAngle: -40,
        min: 0,
        max: 100,
        progress: { show: true, width: 18, itemStyle: { color: style.ring } },
        axisLine: { lineStyle: { width: 18, color: [[1, '#e2e8f0']] } },
        pointer: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        anchor: { show: false },
        detail: {
          valueAnimation: true,
          formatter: (v: number) => `{val|${v.toFixed(1)}}\n{grade|等级 ${grade}}`,
          rich: {
            val: { fontSize: 36, fontWeight: 700, color: style.ring, lineHeight: 44 },
            grade: { fontSize: 13, color: '#64748b', padding: [4, 0, 0, 0] },
          },
          offsetCenter: [0, 0],
        },
        data: [{ value: overallScore }],
      },
    ],
  };

  return (
    <div className="bg-white rounded-xl border border-surface-200/60 p-4">
      <h3 className="text-sm font-semibold text-surface-700 mb-2">综合健康度评分</h3>
      <ReactECharts option={option} style={{ height }} notMerge={true} lazyUpdate={true} />
      <div className="grid grid-cols-5 gap-2 mt-3 px-2">
        {DIM_META.map(d => {
          const v = scores[d.key] ?? 50;
          return (
            <div key={d.key} className="text-center">
              <div className="text-[10px] text-surface-500 mb-1">{d.label}</div>
              <div className="h-1.5 rounded-full bg-surface-100 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${v}%`,
                    backgroundColor: v >= 80 ? '#16a34a' : v >= 60 ? '#0ea5e9' : v >= 40 ? '#f59e0b' : '#ef4444',
                  }}
                />
              </div>
              <div className="text-[11px] font-medium text-surface-700 mt-1">{v.toFixed(0)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
