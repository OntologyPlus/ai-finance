/**
 * HealthScoreRadar — 预算健康度 5 维雷达图
 * 5 维：执行率、战略对齐、风险敞口、调拨合理性、数据完整度
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
  scores: DimensionScores;
  height?: number;
}

const DIM_META: { key: keyof DimensionScores; label: string }[] = [
  { key: 'execution', label: '执行率' },
  { key: 'alignment', label: '战略对齐' },
  { key: 'risk', label: '风险敞口' },
  { key: 'transfer', label: '调拨合理' },
  { key: 'data', label: '数据完整' },
];

export default function HealthScoreRadar({ scores, height = 320 }: Props) {
  const values = DIM_META.map(d => scores[d.key] ?? 50);

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const items = params.value.map((v: number, i: number) =>
          `${DIM_META[i].label}：<b>${v.toFixed(1)}</b>`
        ).join('<br/>');
        return `<div style="font-size:12px">${items}</div>`;
      },
    },
    radar: {
      indicator: DIM_META.map(d => ({ name: d.label, max: 100 })),
      shape: 'polygon',
      splitNumber: 5,
      axisName: { color: '#475569', fontSize: 12 },
      splitLine: { lineStyle: { color: '#e2e8f0' } },
      splitArea: { areaStyle: { color: ['#f8fafc', '#ffffff'] } },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '本期评分',
            symbol: 'circle',
            symbolSize: 6,
            lineStyle: { color: '#0ea5e9', width: 2 },
            areaStyle: { color: 'rgba(14, 165, 233, 0.18)' },
            itemStyle: { color: '#0ea5e9' },
          },
        ],
      },
    ],
  };

  return (
    <div className="bg-white rounded-xl border border-surface-200/60 p-4">
      <h3 className="text-sm font-semibold text-surface-700 mb-2">5 维健康度雷达</h3>
      <ReactECharts option={option} style={{ height }} notMerge={true} lazyUpdate={true} />
    </div>
  );
}
