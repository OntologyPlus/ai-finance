/**
 * CrossPeriodImpactChart — 跨期影响链可视化（v9.0 E.4）
 *
 * 输入：压力测试结果（base/stressed + impact 变化率）
 * 输出：
 *   1. 折线图：T+0/T+3/T+6/T+12 月的利润轨迹（基准 vs 压力）
 *   2. 累计影响条：每个期间的累计损失
 *   3. 风险等级标签：每月度健康度
 *
 * 方法论：
 *   - 压力冲击会随时间衰减/放大（业务量回升、成本粘性）
 *   - 累计净影响 = Σ(单期损失 × 折现因子)
 *   - 关键节点：T+1（首月冲击）→ T+3（成本固化）→ T+6（趋势成型）→ T+12（年度回顾）
 */
import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Clock, TrendingDown, AlertCircle, Calendar } from 'lucide-react';
import { clsx } from 'clsx';

export interface CrossPeriodImpact {
  periods: Array<{
    label: string;        // T+0, T+3, T+6, T+12
    months: number;       // 月数
    base_profit: number;  // 该期基准利润
    stressed_profit: number; // 该期压力下利润
    cumulative_loss: number; // 累计损失
    risk_level: 'low' | 'medium' | 'high' | 'critical';
    notes?: string;       // 阶段性观察
  }>;
  summary: {
    max_loss_period: string;    // 最大损失期间
    max_loss_amount: number;    // 最大损失金额
    total_cumulative_loss: number; // 12个月累计损失
    recovery_month?: number;    // 恢复月份（可选）
  };
}

export interface CrossPeriodImpactChartProps {
  data: CrossPeriodImpact | null;
  scenarioName?: string;
  baseProfit?: number;        // 用于派生（如未提供 data）
  profitChangePct?: number;   // 利润变动百分比
  loading?: boolean;
}

const RISK_STYLE: Record<string, { bg: string; border: string; color: string; label: string }> = {
  low: { bg: 'bg-compliance-50/60', border: 'border-compliance-200', color: 'text-compliance-700', label: '稳健' },
  medium: { bg: 'bg-brand-50/60', border: 'border-brand-200', color: 'text-brand-700', label: '关注' },
  high: { bg: 'bg-warning-50/60', border: 'border-warning-200', color: 'text-warning-700', label: '高风险' },
  critical: { bg: 'bg-alert-50/60', border: 'border-alert-200', color: 'text-alert-700', label: '严重' },
};

/**
 * 从压力测试结果派生跨期影响链
 * 模型：
 *   T+0: 立即冲击 = stressed_profit
 *   T+3: 部分恢复（业务量回升 30%）
 *   T+6: 大幅恢复（70%）
 *   T+12: 全面恢复（95%）
 *   累计损失 = Σ 月度损失
 */
export function deriveCrossPeriodImpact(
  baseProfit: number,
  stressedProfit: number,
): CrossPeriodImpact {
  const shock = stressedProfit - baseProfit; // 负数 = 损失
  const recoveryCurve = [1.0, 0.7, 0.3, 0.05]; // T+0, T+3, T+6, T+12 剩余冲击比例

  const months = [0, 3, 6, 12];
  const labels = ['T+0 (本月)', 'T+3 (季度)', 'T+6 (半年)', 'T+12 (年度)'];

  const periods = months.map((m, idx) => {
    const monthlyShock = shock * recoveryCurve[idx];
    const stressed = baseProfit + monthlyShock;
    const cumulativeLoss = Math.abs(monthlyShock) * (m === 0 ? 1 : m); // 累计
    const ratio = baseProfit === 0 ? 0 : Math.abs(monthlyShock) / Math.abs(baseProfit);
    const risk_level: 'low' | 'medium' | 'high' | 'critical' =
      ratio > 0.5 ? 'critical' : ratio > 0.3 ? 'high' : ratio > 0.15 ? 'medium' : 'low';

    const notesMap = [
      '压力即刻落地，业务节奏骤变',
      '成本结构固化，弹性恢复有限',
      '业务回升，但年度目标承压',
      '全面恢复至接近基线',
    ];

    return {
      label: labels[idx],
      months: m,
      base_profit: baseProfit,
      stressed_profit: stressed,
      cumulative_loss: cumulativeLoss,
      risk_level,
      notes: notesMap[idx],
    };
  });

  const totalLoss = periods.reduce((s, p) => s + Math.max(0, p.base_profit - p.stressed_profit), 0);
  const maxLossPeriod = periods.reduce((max, p) => (p.cumulative_loss > max.cumulative_loss ? p : max), periods[0]);

  return {
    periods,
    summary: {
      max_loss_period: maxLossPeriod.label,
      max_loss_amount: maxLossPeriod.cumulative_loss,
      total_cumulative_loss: totalLoss,
    },
  };
}

function formatWan(n: number): string {
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}万`;
  return n.toLocaleString();
}

export default function CrossPeriodImpactChart({
  data,
  scenarioName,
  baseProfit,
  profitChangePct,
  loading = false,
}: CrossPeriodImpactChartProps) {
  // 如果没有 data 但有 baseProfit/profitChangePct，自动派生
  const effective = useMemo<CrossPeriodImpact | null>(() => {
    if (data) return data;
    if (baseProfit != null && profitChangePct != null) {
      const stressed = baseProfit * (1 + profitChangePct / 100);
      return deriveCrossPeriodImpact(baseProfit, stressed);
    }
    return null;
  }, [data, baseProfit, profitChangePct]);

  if (loading) {
    return (
      <div className="text-center py-10 text-surface-400 text-sm">
        <div className="inline-block w-5 h-5 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2" />
        正在计算跨期影响…
      </div>
    );
  }

  if (!effective) {
    return (
      <div className="p-6 rounded-xl border border-dashed border-surface-300 bg-white/50 text-center">
        <Clock size={20} className="mx-auto mb-2 text-surface-300" />
        <p className="text-sm text-surface-500">请先执行压力测试，跨期影响链将自动生成</p>
        <p className="text-[11px] text-surface-400 mt-1">支持 T+0 / T+3 / T+6 / T+12 月的传导路径分析</p>
      </div>
    );
  }

  const { periods, summary } = effective;

  // ECharts 折线图：基准 vs 压力轨迹
  const lineOption = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any[]) => {
        const lines = params.map(p =>
          `<div style="display:flex;justify-content:space-between;gap:12px"><span>${p.marker} ${p.seriesName}</span><b>¥ ${formatWan(p.value)}</b></div>`
        ).join('');
        return `<div style="padding:4px 0"><b>${params[0].axisValue}</b></div>${lines}</div>`;
      },
    },
    legend: {
      data: ['基准利润轨迹', '压力下利润轨迹'],
      textStyle: { color: '#64748b', fontSize: 11 },
      top: 4,
    },
    grid: { left: 60, right: 20, bottom: 30, top: 36 },
    xAxis: {
      type: 'category' as const,
      data: periods.map(p => p.label),
      axisLabel: { color: '#94a3b8', fontSize: 10 },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        color: '#94a3b8',
        fontSize: 10,
        formatter: (v: number) => `¥ ${formatWan(v)}`,
      },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    series: [
      {
        name: '基准利润轨迹',
        type: 'line' as const,
        smooth: true,
        symbolSize: 8,
        data: periods.map(p => p.base_profit),
        lineStyle: { color: '#3b82f6', width: 2 },
        itemStyle: { color: '#3b82f6' },
        areaStyle: { color: 'rgba(59,130,246,0.08)' },
      },
      {
        name: '压力下利润轨迹',
        type: 'line' as const,
        smooth: true,
        symbolSize: 8,
        data: periods.map(p => p.stressed_profit),
        lineStyle: { color: '#ef4444', width: 2, type: 'dashed' as const },
        itemStyle: { color: '#ef4444' },
        areaStyle: { color: 'rgba(239,68,68,0.08)' },
      },
    ],
  };

  return (
    <div className="space-y-4">
      {/* 顶部摘要 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-finance-50/40 border border-finance-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1.5">
            <Calendar size={14} className="text-finance-600" />
            <span className="text-[11px] font-semibold text-finance-700">最大损失期间</span>
          </div>
          <p className="text-lg font-bold text-finance-800 font-display">{summary.max_loss_period}</p>
          <p className="text-[11px] text-surface-500 mt-0.5">累计损失 ¥ {formatWan(summary.max_loss_amount)}</p>
        </div>
        <div className="bg-alert-50/40 border border-alert-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1.5">
            <TrendingDown size={14} className="text-alert-600" />
            <span className="text-[11px] font-semibold text-alert-700">12 个月累计净影响</span>
          </div>
          <p className="text-lg font-bold text-alert-700 font-display">¥ {formatWan(summary.total_cumulative_loss)}</p>
          <p className="text-[11px] text-surface-500 mt-0.5">基于恢复曲线模型</p>
        </div>
        <div className="bg-brand-50/40 border border-brand-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-1.5">
            <Clock size={14} className="text-brand-600" />
            <span className="text-[11px] font-semibold text-brand-700">情景</span>
          </div>
          <p className="text-sm font-bold text-brand-800 truncate">{scenarioName || '未命名情景'}</p>
          <p className="text-[11px] text-surface-500 mt-0.5">跨期影响链 · 4 个时间锚点</p>
        </div>
      </div>

      {/* 折线图 */}
      <div className="bg-white rounded-xl border border-surface-200/60 p-4">
        <h4 className="text-sm font-semibold text-finance-800 mb-2 flex items-center gap-2">
          <TrendingDown size={14} className="text-finance-600" />
          利润轨迹：基准 vs 压力传导
        </h4>
        <ReactECharts option={lineOption} style={{ height: '300px' }} />
      </div>

      {/* 4 个时间锚点详细卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {periods.map((p) => {
          const style = RISK_STYLE[p.risk_level];
          const loss = p.base_profit - p.stressed_profit;
          return (
            <div
              key={p.label}
              className={clsx('rounded-xl border-2 p-3 transition-all', style.bg, style.border)}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-finance-800">{p.label}</span>
                <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold border', style.color, style.border, 'bg-white/60')}>
                  {style.label}
                </span>
              </div>
              <div className="space-y-1.5 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-surface-500">基准</span>
                  <span className="font-mono font-semibold text-finance-700">¥ {formatWan(p.base_profit)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-500">压力</span>
                  <span className="font-mono font-semibold text-alert-700">¥ {formatWan(p.stressed_profit)}</span>
                </div>
                <div className="flex justify-between border-t border-surface-200/60 pt-1">
                  <span className="text-surface-500">单期损失</span>
                  <span className="font-mono font-bold text-alert-700">¥ {formatWan(loss)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-500">累计</span>
                  <span className="font-mono font-bold text-alert-800">¥ {formatWan(p.cumulative_loss)}</span>
                </div>
              </div>
              {p.notes && (
                <p className="text-[10px] text-surface-600 mt-2 leading-relaxed border-t border-surface-200/60 pt-1.5">
                  {p.notes}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="p-3 rounded-lg bg-finance-50/40 border border-finance-200/60">
        <div className="flex items-start gap-2">
          <AlertCircle size={14} className="text-finance-600 shrink-0 mt-0.5" />
          <p className="text-[11px] text-finance-800 leading-relaxed">
            <b>模型说明：</b>跨期影响基于业务量恢复曲线（1.0→0.7→0.3→0.05）+ 成本结构粘性推导。
            实际经营中可能因应急资源调配、新业务补充、政策窗口而偏离预测。建议每季度滚动校准。
          </p>
        </div>
      </div>
    </div>
  );
}
