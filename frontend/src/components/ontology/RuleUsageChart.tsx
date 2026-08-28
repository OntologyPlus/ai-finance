/**
 * RuleUsageChart — v11.0 规则使用率图表
 *
 * 显示每条规则近 7 天调用次数，used 绿 / dead 灰
 */
import ReactECharts from 'echarts-for-react';

export interface RuleUsageItem {
  rule_id: string;
  name: string;
  rule_type: string;
  hit_count: number;
  is_dead: boolean;
}

export default function RuleUsageChart({ rules }: { rules: RuleUsageItem[] }) {
  if (!rules || rules.length === 0) {
    return (
      <div className="py-8 text-center text-xs text-surface-400">
        暂无规则使用数据
      </div>
    );
  }

  const sorted = [...rules].sort((a, b) => b.hit_count - a.hit_count);
  const data = sorted.map((r) => ({
    value: r.hit_count,
    itemStyle: { color: r.is_dead ? '#cbd5e1' : r.hit_count > 50 ? '#10b981' : r.hit_count > 10 ? '#3b82f6' : '#94a3b8' },
  }));

  return (
    <ReactECharts
      option={{
        tooltip: {
          trigger: 'axis',
          formatter: (p: any) => {
            const idx = p[0].dataIndex;
            const r = sorted[idx];
            return `<b>${r.rule_id}</b> ${r.name}<br/>类型: ${r.rule_type}<br/>调用: ${r.hit_count} 次<br/>${r.is_dead ? '⚠️ 死规则' : '✅ 在用'}`;
          },
        },
        grid: { left: 60, right: 20, top: 10, bottom: 80 },
        xAxis: {
          type: 'category',
          data: sorted.map((r) => r.rule_id),
          axisLabel: { rotate: 45, fontSize: 10 },
        },
        yAxis: { type: 'value', name: '调用次数', nameTextStyle: { fontSize: 10 } },
        series: [{
          type: 'bar',
          data,
          barWidth: '60%',
        }],
      }}
      style={{ height: '260px' }}
    />
  );
}
