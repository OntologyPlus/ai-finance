/**
 * DupontWaterfallChart — 杜邦瀑布图
 * v4.0 新增：第一部分"经营全景"利润率结构拆解
 *
 * 经营利润率 = 毛利率 - 推广费 - 维持费 - 人力 - 研发
 */
import ReactECharts from 'echarts-for-react';
import { TrendingDown } from 'lucide-react';

export interface DupontLayer {
  name: string;
  value: number;      // pp
  type: 'base' | 'subtract' | 'total';  // 基值/扣减/合计
  color?: string;
}

export interface DupontData {
  layers: DupontLayer[];
  actual_operating_profit_rate?: number;  // 实际经营利润率 %
  budget_operating_profit_rate?: number;  // 预算经营利润率 %
  gross_margin?: number;                   // 毛利率 %
  deviation_pp?: number;                    // 偏差
}

export interface DupontWaterfallChartProps {
  data: DupontData;
  height?: number;
}

const DEFAULT_LAYER_COLORS = {
  base: '#3b82f6',     // blue
  subtract: '#ef4444', // red
  total: '#10b981',    // green
};

export default function DupontWaterfallChart({ data, height = 320 }: DupontWaterfallChartProps) {
  if (!data?.layers || data.layers.length === 0) {
    return (
      <div className="p-6 rounded-xl border border-surface-200 bg-white text-center text-surface-400 text-sm flex items-center justify-center gap-2" style={{ height }}>
        <TrendingDown size={14} />
        暂无杜邦数据
      </div>
    );
  }

  // 计算每个柱的起点和高度（瀑布图算法）
  const categories = data.layers.map((l) => l.name);
  const values: number[] = [];
  const bottoms: number[] = [];
  let runningTotal = 0;

  data.layers.forEach((layer, i) => {
    if (layer.type === 'base') {
      values.push(layer.value);
      bottoms.push(0);
      runningTotal = layer.value;
    } else if (layer.type === 'total') {
      values.push(layer.value);
      bottoms.push(0);
      runningTotal = layer.value;
    } else {
      // subtract
      values.push(Math.abs(layer.value));
      bottoms.push(runningTotal - layer.value);
      runningTotal -= layer.value;
    }
  });

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const item = params[0];
        const layer = data.layers[item.dataIndex];
        const sign = layer.type === 'subtract' ? '−' : '';
        return `<b>${layer.name}</b><br/>${sign}${Math.abs(layer.value).toFixed(2)} pp`;
      },
    },
    grid: { left: 50, right: 30, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: { fontSize: 10, interval: 0, rotate: categories.length > 5 ? 15 : 0 },
    },
    yAxis: {
      type: 'value',
      name: '%',
      axisLabel: { fontSize: 10 },
    },
    series: [
      {
        name: 'placeholder',
        type: 'bar',
        stack: 'total',
        itemStyle: { color: 'transparent' },
        emphasis: { itemStyle: { color: 'transparent' } },
        data: bottoms,
      },
      {
        name: '瀑布',
        type: 'bar',
        stack: 'total',
        label: {
          show: true,
          position: 'top',
          formatter: (p: any) => {
            const layer = data.layers[p.dataIndex];
            const sign = layer.type === 'subtract' ? '−' : '';
            return `${sign}${Math.abs(layer.value).toFixed(1)}`;
          },
          fontSize: 10,
        },
        data: data.layers.map((layer, i) => ({
          value: values[i],
          itemStyle: {
            color: layer.color || (
              layer.type === 'base'
                ? DEFAULT_LAYER_COLORS.base
                : layer.type === 'total'
                ? DEFAULT_LAYER_COLORS.total
                : DEFAULT_LAYER_COLORS.subtract
            ),
          },
        })),
      },
    ],
  };

  return (
    <div className="p-4 rounded-xl border border-surface-200 bg-white">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-finance-800">杜邦管理版：经营利润率分解</h3>
        {data.deviation_pp !== undefined && (
          <span className={`text-xs font-semibold ${data.deviation_pp < 0 ? 'text-alert-600' : 'text-compliance-600'}`}>
            实际 vs 预算：{data.deviation_pp > 0 ? '+' : ''}{data.deviation_pp.toFixed(2)} pp
          </span>
        )}
      </div>
      <ReactECharts option={option} style={{ height }} />
      <p className="text-[10px] text-surface-400 mt-1 text-center">
        经营利润率 = 毛利率 − 推广费 − 维持费 − 人力 − 研发
      </p>
    </div>
  );
}
