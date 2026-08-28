/**
 * FatigueDashboard — 预警疲劳度仪表盘
 * 5 维度指标卡片 + 合并/降级/取消建议列表
 */
import { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { Loader2, TrendingUp, Clock, AlertTriangle, CheckCircle2, XCircle, Merge, ArrowDown, Trash2 } from 'lucide-react';
import { alertApi } from '../../services/api';

interface FatigueMetrics {
  total_alerts?: number;
  closed_rate?: number;
  avg_response_hours?: number;
  p90_response_hours?: number;
  effectiveness_rate?: number;
  top_repeating_rules?: { rule: string; count: number }[];
  rule_type_distribution?: Record<string, number>;
}

interface Suggestion {
  rule: string;
  type: 'merge' | 'downgrade' | 'cancel';
  reason: string;
}

interface FatigueData {
  months?: number;
  metrics?: FatigueMetrics;
  suggestions?: Suggestion[];
}

interface Props {
  initialMonths?: number;
}

const SUGGESTION_STYLES: Record<string, { icon: any; bg: string; text: string; label: string }> = {
  merge: { icon: Merge, bg: 'bg-brand-50', text: 'text-brand-700', label: '建议合并' },
  downgrade: { icon: ArrowDown, bg: 'bg-warning-50', text: 'text-warning-700', label: '建议降级' },
  cancel: { icon: Trash2, bg: 'bg-alert-50', text: 'text-alert-700', label: '建议取消' },
};

export default function FatigueDashboard({ initialMonths = 3 }: Props) {
  const [data, setData] = useState<FatigueData | null>(null);
  const [loading, setLoading] = useState(false);
  const [months, setMonths] = useState<number>(initialMonths);

  const fetchFatigue = async (m: number) => {
    setLoading(true);
    try {
      const res: any = await alertApi.getAlertFatigue(m);
      const d = res?.data || res;
      setData(d);
    } catch (e: any) {
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFatigue(months);
  }, [months]);

  if (loading) {
    return (
      <div className="text-center py-12 text-surface-400 text-sm">
        <Loader2 size={24} className="mx-auto mb-2 animate-spin text-finance-500" />
        正在分析预警疲劳度…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12 text-surface-400 text-sm">
        <AlertTriangle size={24} className="mx-auto mb-2 text-surface-300" />
        暂无疲劳度数据
      </div>
    );
  }

  const m = data.metrics || {};
  const suggestions = data.suggestions || [];

  // 规则类型分布饼图
  const distributionEntries = Object.entries(m.rule_type_distribution || {});
  const distributionOption = distributionEntries.length > 0 ? {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      label: { show: false },
      data: distributionEntries.map(([k, v]) => ({ name: k, value: v })),
    }],
  } : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-finance-800">预警疲劳度分析</h3>
        <div className="flex items-center gap-1">
          {[1, 3, 6, 12].map(m => (
            <button
              key={m}
              onClick={() => setMonths(m)}
              className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                months === m
                  ? 'bg-finance-500 text-white'
                  : 'bg-surface-100 text-surface-600 hover:bg-surface-200'
              }`}
            >
              近 {m} 月
            </button>
          ))}
        </div>
      </div>

      {/* 5 维度指标卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard
          icon={TrendingUp}
          label="总预警数"
          value={m.total_alerts ?? 0}
          unit="条"
          color="text-finance-600"
        />
        <MetricCard
          icon={CheckCircle2}
          label="闭环率"
          value={((m.closed_rate ?? 0) * 100).toFixed(1)}
          unit="%"
          color={((m.closed_rate ?? 0) >= 0.7) ? 'text-compliance-600' : 'text-warning-600'}
        />
        <MetricCard
          icon={Clock}
          label="P90 响应时长"
          value={m.p90_response_hours?.toFixed(1) ?? '-'}
          unit="h"
          color={(m.p90_response_hours ?? 0) > 24 ? 'text-alert-600' : 'text-surface-700'}
        />
        <MetricCard
          icon={XCircle}
          label="误报率"
          value={(((1 - (m.effectiveness_rate ?? 1))) * 100).toFixed(0)}
          unit="%"
          color={((1 - (m.effectiveness_rate ?? 1)) > 0.5) ? 'text-alert-600' : 'text-compliance-600'}
        />
        <MetricCard
          icon={AlertTriangle}
          label="建议数"
          value={suggestions.length}
          unit="条"
          color={suggestions.length > 5 ? 'text-warning-600' : 'text-surface-700'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 规则类型分布 */}
        {distributionOption && (
          <div className="bg-white rounded-xl border border-surface-200/60 p-4">
            <h4 className="text-xs font-semibold text-surface-700 mb-2">规则类型分布</h4>
            <ReactECharts option={distributionOption} style={{ height: 220 }} notMerge={true} lazyUpdate={true} />
          </div>
        )}

        {/* 合并/降级/取消建议 */}
        <div className="bg-white rounded-xl border border-surface-200/60 p-4">
          <h4 className="text-xs font-semibold text-surface-700 mb-3">疲劳度优化建议</h4>
          {suggestions.length === 0 ? (
            <div className="text-center py-6 text-xs text-surface-400">
              ✓ 当前规则运行良好，无需调整
            </div>
          ) : (
            <div className="space-y-2 max-h-[220px] overflow-y-auto">
              {suggestions.map((s, i) => {
                const style = SUGGESTION_STYLES[s.type] || SUGGESTION_STYLES.merge;
                const Icon = style.icon;
                return (
                  <div
                    key={i}
                    className={`flex items-start gap-2 p-2.5 rounded-lg border ${style.bg} ${style.text}`}
                  >
                    <Icon size={14} className="flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-white/60">
                          {style.label}
                        </span>
                        <span className="text-xs font-medium truncate">{s.rule}</span>
                      </div>
                      <p className="text-[11px] text-surface-600 mt-0.5 leading-relaxed">
                        {s.reason}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, unit, color }: any) {
  return (
    <div className="bg-white rounded-xl border border-surface-200/60 p-3">
      <div className="flex items-center gap-1.5 text-[11px] text-surface-500 mb-1">
        <Icon size={12} />
        <span>{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`text-2xl font-bold ${color}`}>{value}</span>
        <span className="text-[10px] text-surface-400">{unit}</span>
      </div>
    </div>
  );
}
