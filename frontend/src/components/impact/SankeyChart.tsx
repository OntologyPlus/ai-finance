/**
 * SankeyChart 桑基图 — v8.0 Module I
 * 用于展示资金/影响/决策流的走向
 * 使用 ECharts 内置桑基图
 */
import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

export interface SankeyNode {
  name: string;
  itemStyle?: { color?: string };
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
  lineStyle?: { color?: string; opacity?: number };
}

export interface SankeyChartProps {
  nodes: SankeyNode[];
  links: SankeyLink[];
  height?: number | string;
  title?: string;
  className?: string;
}

export const SankeyChart: React.FC<SankeyChartProps> = ({
  nodes,
  links,
  height = 400,
  title,
  className,
}) => {
  const option = useMemo(() => {
    return {
      title: title
        ? {
            text: title,
            left: 'center',
            top: 8,
            textStyle: { fontSize: 14, fontWeight: 600, color: '#334155' },
          }
        : undefined,
      tooltip: {
        trigger: 'item',
        triggerOn: 'mousemove',
        formatter: (params: any) => {
          if (params.dataType === 'edge') {
            return `${params.data.source} → ${params.data.target}<br/>流量: ${params.data.value}`;
          }
          return `${params.name}`;
        },
      },
      series: [
        {
          type: 'sankey',
          left: 24,
          right: 120,
          top: title ? 40 : 16,
          bottom: 16,
          nodeWidth: 18,
          nodeGap: 12,
          nodeAlign: 'left',
          layoutIterations: 64,
          emphasis: { focus: 'adjacency' },
          data: nodes,
          links: links,
          lineStyle: {
            color: 'gradient',
            curveness: 0.5,
            opacity: 0.55,
          },
          label: {
            fontSize: 12,
            color: '#475569',
            fontWeight: 500,
          },
          itemStyle: {
            borderWidth: 0,
            borderColor: 'transparent',
          },
        },
      ],
    };
  }, [nodes, links, title]);

  if (!nodes.length || !links.length) {
    return (
      <div
        className={className}
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#94a3b8',
          fontSize: 13,
        }}
      >
        暂无数据
      </div>
    );
  }

  return (
    <ReactECharts
      option={option}
      style={{ height, width: '100%' }}
      className={className}
      opts={{ renderer: 'canvas' }}
    />
  );
};

export default SankeyChart;
