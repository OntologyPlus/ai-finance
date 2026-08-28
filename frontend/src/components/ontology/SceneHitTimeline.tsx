/**
 * SceneHitTimeline — v11.0 场景命中趋势
 *
 * 简单柱状图：横轴 = 场景名，纵轴 = 24h 命中次数
 * active 场景高亮，inactive 灰
 */
import ReactECharts from 'echarts-for-react';

export interface SceneHitItem {
  scene_id: string;
  name: string;
  stage: string;
  hit_count_24h: number;
  activated_rules_count: number;
  activated_objects_count: number;
}

export default function SceneHitTimeline({ scenes }: { scenes: SceneHitItem[] }) {
  if (!scenes || scenes.length === 0) {
    return (
      <div className="py-8 text-center text-xs text-surface-400">
        暂无场景命中数据
      </div>
    );
  }

  const sorted = [...scenes].sort((a, b) => b.hit_count_24h - a.hit_count_24h);
  const data = sorted.map((s) => ({
    value: s.hit_count_24h,
    itemStyle: { color: s.hit_count_24h > 0 ? '#3b82f6' : '#e2e8f0' },
  }));

  return (
    <ReactECharts
      option={{
        tooltip: {
          trigger: 'axis',
          formatter: (p: any) => {
            const idx = p[0].dataIndex;
            const s = sorted[idx];
            return `<b>${s.name}</b><br/>场景: ${s.scene_id}<br/>阶段: ${s.stage}<br/>24h 命中: ${s.hit_count_24h}<br/>激活对象: ${s.activated_objects_count} 个<br/>激活规则: ${s.activated_rules_count} 条`;
          },
        },
        grid: { left: 60, right: 20, top: 10, bottom: 100 },
        xAxis: {
          type: 'category',
          data: sorted.map((s) => s.name),
          axisLabel: { rotate: 30, fontSize: 10, interval: 0 },
        },
        yAxis: { type: 'value', name: '24h 命中', nameTextStyle: { fontSize: 10 } },
        series: [{
          type: 'bar',
          data,
          barWidth: '50%',
        }],
      }}
      style={{ height: '280px' }}
    />
  );
}
