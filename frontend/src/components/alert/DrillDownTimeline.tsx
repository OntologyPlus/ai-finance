/**
 * DrillDownTimeline — 预警 5 层根因下钻时间线
 * L1 → L2 → Center → Trend → Peer 折叠面板
 */
import ReactECharts from 'echarts-for-react';
import { ChevronDown, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useState } from 'react';

interface DrillDownData {
  l1_node?: any;
  l2_node?: any;
  center_node?: any;
  trend_node?: any;
  peer_node?: any;
  ai_root_cause?: string;
}

interface Props {
  data: DrillDownData;
}

const PANELS = [
  { key: 'l1_node', title: 'L1 科目' },
  { key: 'l2_node', title: 'L2 子科目' },
  { key: 'center_node', title: '中心维度' },
  { key: 'trend_node', title: '趋势对比' },
  { key: 'peer_node', title: '同类对标' },
] as const;

export default function DrillDownTimeline({ data }: Props) {
  const [open, setOpen] = useState<Record<string, boolean>>({
    l1_node: true,
    l2_node: false,
    center_node: false,
    trend_node: false,
    peer_node: false,
  });

  const toggle = (k: string) => setOpen({ ...open, [k]: !open[k] });

  return (
    <div className="space-y-2">
      {PANELS.map(p => {
        const node = data[p.key];
        const isOpen = open[p.key];
        return (
          <div key={p.key} className="border border-surface-200 rounded-lg overflow-hidden">
            <button
              onClick={() => toggle(p.key)}
              className="w-full flex items-center justify-between px-4 py-2.5 bg-surface-50 hover:bg-surface-100 transition-colors"
            >
              <span className="text-sm font-semibold text-surface-700 flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-finance-100 text-finance-700 text-[10px] font-bold flex items-center justify-center">
                  {PANELS.findIndex(x => x.key === p.key) + 1}
                </span>
                {p.title}
              </span>
              <ChevronDown
                size={16}
                className={`text-surface-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
              />
            </button>
            {isOpen && (
              <div className="p-4 bg-white">
                {!node ? (
                  <div className="text-xs text-surface-400 text-center py-3">暂无数据</div>
                ) : (
                  <PanelContent kind={p.key} node={node} />
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function PanelContent({ kind, node }: { kind: string; node: any }) {
  // L1 科目
  if (kind === 'l1_node') {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-[10px] text-surface-500">科目名称</div>
            <div className="text-sm font-semibold text-surface-800">{node.subject || '未指定'}</div>
          </div>
          <div>
            <div className="text-[10px] text-surface-500">当期执行率</div>
            <div className="text-sm font-semibold text-finance-600">{node.rate?.toFixed(1) ?? '-'}%</div>
          </div>
          <div>
            <div className="text-[10px] text-surface-500">近 30 天告警次数</div>
            <div className="text-sm font-semibold text-alert-600">{node.alert_count_30d ?? 0}</div>
          </div>
        </div>
      </div>
    );
  }

  // L2 子科目 / 中心维度
  if (kind === 'l2_node' || kind === 'center_node') {
    const items: any[] = node.items || node.centers || [];
    if (items.length === 0) {
      return <div className="text-xs text-surface-400 text-center py-3">暂无数据</div>;
    }
    return (
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-surface-200">
            <th className="text-left py-1.5 px-2 text-surface-500">名称</th>
            <th className="text-right py-1.5 px-2 text-surface-500">执行率</th>
            <th className="text-right py-1.5 px-2 text-surface-500">偏差</th>
          </tr>
        </thead>
        <tbody>
          {items.slice(0, 5).map((it: any, i: number) => (
            <tr key={i} className="border-b border-surface-100 last:border-0">
              <td className="py-1.5 px-2 text-surface-700">{it.name || it.subject || it.center || '-'}</td>
              <td className="py-1.5 px-2 text-right font-medium text-finance-600">{Number(it.rate ?? it.value ?? 0).toFixed(1)}%</td>
              <td className={`py-1.5 px-2 text-right ${(it.delta ?? 0) >= 0 ? 'text-alert-600' : 'text-compliance-600'}`}>
                {(it.delta ?? 0) >= 0 ? '+' : ''}{it.delta?.toFixed(1) ?? 0}pp
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  // 趋势对比
  if (kind === 'trend_node') {
    const thisQ = node.this_quarter || {};
    const lastQ = node.last_quarter || {};
    const chartData = [
      { name: '执行率', this: thisQ.execution_rate ?? 0, last: lastQ.execution_rate ?? 0 },
      { name: '超支率', this: thisQ.overrun_rate ?? 0, last: lastQ.overrun_rate ?? 0 },
      { name: '进度', this: thisQ.progress ?? 0, last: lastQ.progress ?? 0 },
    ];
    return (
      <div>
        <ReactECharts
          option={{
            tooltip: { trigger: 'axis' },
            legend: { data: ['本季', '上季'], top: 0, textStyle: { fontSize: 11 } },
            grid: { top: 30, left: 50, right: 20, bottom: 30 },
            xAxis: { type: 'category', data: chartData.map(d => d.name) },
            yAxis: { type: 'value', axisLabel: { formatter: '{value}%', fontSize: 11 } },
            series: [
              { name: '上季', type: 'bar', data: chartData.map(d => d.last), itemStyle: { color: '#94a3b8' } },
              { name: '本季', type: 'bar', data: chartData.map(d => d.this), itemStyle: { color: '#0ea5e9' } },
            ],
          }}
          style={{ height: 180 }}
          notMerge={true}
          lazyUpdate={true}
        />
        {node.delta && (
          <div className="grid grid-cols-3 gap-2 mt-2 text-[10px]">
            {Object.entries(node.delta).map(([k, v]: [string, any]) => (
              <div key={k} className="flex items-center gap-1 px-2 py-1 rounded bg-surface-50">
                {v > 0 ? <TrendingUp size={12} className="text-alert-500" /> : v < 0 ? <TrendingDown size={12} className="text-compliance-500" /> : <Minus size={12} className="text-surface-400" />}
                <span className="text-surface-600">{k}：</span>
                <span className="font-medium text-surface-800">{(v as number) > 0 ? '+' : ''}{v}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // 同类对标
  if (kind === 'peer_node') {
    return (
      <div className="grid grid-cols-3 gap-3 text-xs">
        <div className="rounded-lg p-2 bg-surface-50">
          <div className="text-[10px] text-surface-500">同类平均</div>
          <div className="text-lg font-bold text-finance-600">{node.peer_avg?.toFixed(1) ?? '-'}%</div>
        </div>
        <div className="rounded-lg p-2 bg-surface-50">
          <div className="text-[10px] text-surface-500">本期</div>
          <div className="text-lg font-bold text-surface-800">{node.current?.toFixed(1) ?? '-'}%</div>
        </div>
        <div className="rounded-lg p-2 bg-surface-50">
          <div className="text-[10px] text-surface-500">偏差</div>
          <div className={`text-lg font-bold flex items-center gap-1 ${(node.deviation ?? 0) >= 0 ? 'text-alert-600' : 'text-compliance-600'}`}>
            {(node.deviation ?? 0) >= 0 ? '+' : ''}{node.deviation?.toFixed(1) ?? '-'}pp
            {Math.abs(node.deviation ?? 0) > 10 ? <AlertCircle size={14} /> : null}
          </div>
        </div>
      </div>
    );
  }

  return <pre className="text-[10px] text-surface-500 overflow-auto">{JSON.stringify(node, null, 2)}</pre>;
}
