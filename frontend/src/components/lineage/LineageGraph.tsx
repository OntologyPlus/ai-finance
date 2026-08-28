/**
 * v12.0: 血缘链路图组件
 * 可视化"一笔报销 → SP 战略举措"的完整链路
 */
import { useEffect, useRef } from 'react';
import ReactECharts from 'echarts-for-react';

export interface LineageNode {
  node_id: string;
  node_type: string;
  label: string;
  meta?: Record<string, any>;
}

export interface LineageEdge {
  source: string;
  target: string;
  relation: string;
  meta?: Record<string, any>;
}

export interface LineageData {
  nodes: LineageNode[];
  edges: LineageEdge[];
  summary: string;
  depth: number;
  total_nodes: number;
  total_edges: number;
}

// 节点类型 → 颜色
const NODE_TYPE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  sp_bp: { bg: '#e0e7ff', border: '#6366f1', text: '#3730a3' },
  initiative: { bg: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
  quadrant: { bg: '#fae8ff', border: '#a855f7', text: '#6b21a8' },
  l3: { bg: '#fef3c7', border: '#f59e0b', text: '#92400e' },
  budget: { bg: '#d1fae5', border: '#10b981', text: '#065f46' },
  expense: { bg: '#fee2e2', border: '#ef4444', text: '#991b1b' },
  alert: { bg: '#fed7aa', border: '#f97316', text: '#9a3412' },
  report: { bg: '#f3e8ff', border: '#8b5cf6', text: '#5b21b6' },
};

const NODE_TYPE_LABELS: Record<string, string> = {
  sp_bp: 'SP/BP 战略',
  initiative: '战略举措',
  quadrant: '象限',
  l3: 'L3 科目',
  budget: '预算项目',
  expense: '报销单',
  alert: '预警',
  report: '报告',
};

export default function LineageGraph({ data }: { data: LineageData | null | undefined }) {
  const echartsRef = useRef<any>(null);

  if (!data || !data.nodes || data.nodes.length === 0) {
    return (
      <div className="py-8 text-center text-xs text-surface-400">
        暂无血缘数据
      </div>
    );
  }

  // 按类型分组
  const categories = Object.keys(NODE_TYPE_LABELS).map((key) => ({
    name: NODE_TYPE_LABELS[key],
    itemStyle: {
      color: NODE_TYPE_COLORS[key]?.border || '#94a3b8',
    },
  }));

  // 节点
  const nodes = data.nodes.map((n) => {
    const type = n.node_type;
    const colors = NODE_TYPE_COLORS[type] || { border: '#94a3b8', text: '#475569' };
    return {
      id: n.node_id,
      name: n.label,
      category: NODE_TYPE_LABELS[type] || type,
      symbolSize: type === 'expense' || type === 'budget' ? 60 : 50,
      label: {
        show: true,
        fontSize: 10,
        color: colors.text,
        formatter: (params: any) => {
          const lines = n.label.split(/[·/]/).filter(Boolean);
          return lines.slice(0, 2).join('\n');
        },
      },
      itemStyle: {
        color: colors.bg,
        borderColor: colors.border,
        borderWidth: 2,
      },
    };
  });

  // 边
  const links = data.edges.map((e) => ({
    source: e.source,
    target: e.target,
    label: {
      show: true,
      formatter: e.relation,
      fontSize: 9,
      color: '#64748b',
    },
    lineStyle: {
      color: '#cbd5e1',
      width: 1.5,
      curveness: 0.2,
    },
  }));

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const node = data.nodes.find((n) => n.node_id === params.data.id);
          if (!node) return '';
          const metaStr = node.meta
            ? Object.entries(node.meta)
                .filter(([, v]) => v != null && v !== '')
                .map(([k, v]) => `${k}: ${v}`)
                .join('<br/>')
            : '';
          return `<b>${node.label}</b><br/>类型: ${NODE_TYPE_LABELS[node.node_type] || node.node_type}${metaStr ? '<br/>' + metaStr : ''}`;
        }
        return `${params.data.relation || ''}`;
      },
    },
    legend: [
      {
        data: categories.map((c) => c.name),
        top: 0,
        textStyle: { fontSize: 10 },
        itemWidth: 10,
        itemHeight: 10,
      },
    ],
    series: [
      {
        type: 'graph',
        layout: 'LR',
        roam: true,
        draggable: true,
        symbolSize: 50,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [4, 8],
        label: {
          show: true,
          position: 'bottom',
        },
        categories,
        data: nodes,
        links,
        lineStyle: {
          opacity: 0.7,
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3 },
        },
        animationDuration: 800,
      },
    ],
  };

  return (
    <div>
      {/* 摘要条 */}
      <div className="mb-3 p-2 rounded-lg bg-finance-50 border border-finance-100 flex items-center gap-2 text-[11px] text-finance-700">
        <span className="font-semibold">血缘追溯</span>
        <span className="text-surface-500">·</span>
        <span className="font-mono">{data.summary}</span>
        <span className="ml-auto text-[10px] text-surface-400">
          深度 {data.depth} 跳 · {data.total_nodes} 节点 · {data.total_edges} 关系
        </span>
      </div>
      <ReactECharts
        ref={echartsRef}
        option={option}
        style={{ height: '360px' }}
        notMerge={true}
      />
    </div>
  );
}
