/**
 * BCGMatrixChart — BCG 四象限散点图
 * v4.0 新增：第三部分"产品组合诊断"
 *
 * 横轴：增长率 / 预算达成率
 * 纵轴：收入规模（对数）
 * 颜色：产品生命周期（导入/成长/成熟/衰退）
 */
import ReactECharts from 'echarts-for-react';
import { ScatterChart } from 'lucide-react';

export interface BCGProduct {
  name: string;          // 品种名
  x: number;             // 增长率 %
  y: number;             // 收入（万元）
  lifecycle: 'intro' | 'growth' | 'mature' | 'decline';
  quadrant: 'star' | 'cash_cow' | 'question' | 'dog';
}

export interface BCGData {
  products: BCGProduct[];
  star?: BCGProduct[];       // 明星
  cash_cow?: BCGProduct[];   // 现金牛
  question?: BCGProduct[];   // 问题
  dog?: BCGProduct[];        // 瘦狗
  x_threshold?: number;      // 增长率中位
  y_threshold?: number;      // 收入中位
}

const LIFECYCLE_COLOR: Record<string, string> = {
  intro: '#3b82f6',
  growth: '#10b981',
  mature: '#f59e0b',
  decline: '#ef4444',
};

const LIFECYCLE_LABEL: Record<string, string> = {
  intro: '导入期',
  growth: '成长期',
  mature: '成熟期',
  decline: '衰退期',
};

const QUADRANT_STYLE: Record<string, { border: string; bg: string; label: string }> = {
  star: { border: '#10b981', bg: 'rgba(16, 185, 129, 0.06)', label: '明星' },
  cash_cow: { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.06)', label: '现金牛' },
  question: { border: '#3b82f6', bg: 'rgba(59, 130, 246, 0.06)', label: '问题' },
  dog: { border: '#ef4444', bg: 'rgba(239, 68, 68, 0.06)', label: '瘦狗' },
};

export default function BCGMatrixChart({ data, height = 380 }: { data: BCGData; height?: number }) {
  if (!data?.products || data.products.length === 0) {
    return (
      <div className="p-6 rounded-xl border border-surface-200 bg-white text-center text-surface-400 text-sm flex items-center justify-center gap-2" style={{ height }}>
        <ScatterChart size={14} />
        暂无 BCG 矩阵数据
      </div>
    );
  }

  // 按生命周期分组
  const grouped: Record<string, BCGProduct[]> = {
    intro: [], growth: [], mature: [], decline: [],
  };
  data.products.forEach((p) => grouped[p.lifecycle]?.push(p));

  const series = (['growth', 'mature', 'intro', 'decline'] as const).map((life) => ({
    name: LIFECYCLE_LABEL[life],
    type: 'scatter',
    symbolSize: (val: any[]) => Math.max(10, Math.min(40, Math.log10(val[1] + 10) * 6)),
    data: grouped[life].map((p) => [p.x, p.y, p.name, p.quadrant]),
    itemStyle: { color: LIFECYCLE_COLOR[life], opacity: 0.75, borderColor: '#fff', borderWidth: 1 },
    emphasis: { itemStyle: { opacity: 1, borderColor: '#1e293b' } },
  }));

  const xMax = Math.max(50, ...data.products.map((p) => p.x)) * 1.1;
  const xMin = Math.min(0, ...data.products.map((p) => p.x)) * 0.9;
  const yMax = Math.max(...data.products.map((p) => p.y)) * 1.3;

  const xThreshold = data.x_threshold ?? (xMax + xMin) / 2;
  const yThreshold = data.y_threshold ?? yMax / 2;

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => {
        const [x, y, name, quad] = p.data;
        const quadLabel = QUADRANT_STYLE[quad]?.label || quad;
        return `<b>${name}</b><br/>增长率: ${x.toFixed(1)}%<br/>收入: ${y.toFixed(0)} 万元<br/>象限: ${quadLabel}`;
      },
    },
    legend: {
      data: ['成长期', '成熟期', '导入期', '衰退期'],
      bottom: 0,
      textStyle: { fontSize: 10 },
    },
    grid: { left: 60, right: 30, top: 30, bottom: 50 },
    xAxis: {
      type: 'value',
      name: '增长率 (%)',
      min: xMin,
      max: xMax,
      nameLocation: 'middle',
      nameGap: 25,
      splitLine: { lineStyle: { type: 'dashed' } },
    },
    yAxis: {
      type: 'log',
      name: '收入（万元）',
      min: 1,
      max: yMax,
      nameLocation: 'middle',
      nameGap: 45,
      splitLine: { lineStyle: { type: 'dashed' } },
    },
    series: [
      // 象限背景块
      {
        name: 'cash_cow_bg',
        type: 'rect',
        shape: { x: xThreshold, y: 1, width: xMax - xThreshold, height: yThreshold - 1 },
        style: { fill: QUADRANT_STYLE.cash_cow.bg },
        silent: true,
        z: 0,
      },
      ...series,
      // 象限分割线
      {
        name: 'split',
        type: 'line',
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#cbd5e1', type: 'dashed' },
          data: [
            { xAxis: xThreshold },
            { yAxis: yThreshold },
          ],
        },
      },
    ],
  };

  return (
    <div className="p-4 rounded-xl border border-surface-200 bg-white">
      <h3 className="text-sm font-semibold text-finance-800 mb-2">BCG 矩阵：产品组合诊断</h3>
      <ReactECharts option={option} style={{ height }} />
      <div className="grid grid-cols-4 gap-2 mt-2 text-[10px]">
        {Object.entries(QUADRANT_STYLE).map(([k, v]) => (
          <div key={k} className="flex items-center gap-1">
            <span
              className="inline-block w-3 h-3 rounded"
              style={{ backgroundColor: v.bg, border: `1px solid ${v.border}` }}
            />
            <span className="text-surface-600">{v.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
