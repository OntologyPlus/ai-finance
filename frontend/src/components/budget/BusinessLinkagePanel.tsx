import { motion } from 'framer-motion';
import { Link2, AlertCircle, Activity, ListTree } from 'lucide-react';
import { clsx } from 'clsx';

export interface LinkageItem {
  budget_id: string;
  name: string;
  l1_code: string | null;
  execution_rate: number;
  expense_count: number;
  expense_total: number;
  avg_per_expense: number;
  linkage_type: string;
}

export interface RiskPair {
  budget_id: string;
  name: string;
  linkage_type: string;
  risk_level: 'high' | 'medium' | 'low';
  rate: number;
  expense_count: number;
  avg_per_expense: number;
}

export interface BusinessLinkage {
  items: LinkageItem[];
  summary: string;
  risk_pairs: RiskPair[];
}

const TYPE_STYLE: Record<string, { color: string; bg: string; border: string }> = {
  高频低额: { color: 'text-alert-700', bg: 'bg-alert-50/60', border: 'border-alert-300' },
  低频高额: { color: 'text-warning-700', bg: 'bg-warning-50/60', border: 'border-warning-300' },
  正常: { color: 'text-compliance-700', bg: 'bg-compliance-50/60', border: 'border-compliance-300' },
};

const RISK_STYLE: Record<string, { color: string; bg: string }> = {
  high: { color: 'text-alert-700', bg: 'bg-alert-100' },
  medium: { color: 'text-warning-700', bg: 'bg-warning-100' },
  low: { color: 'text-compliance-700', bg: 'bg-compliance-100' },
};

function formatAmount(n: number): string {
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}万`;
  return n.toLocaleString();
}

export default function BusinessLinkagePanel({
  data,
  loading,
}: {
  data: BusinessLinkage | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="text-center py-10 text-surface-400 text-sm">
        <div className="inline-block w-5 h-5 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2" />
        正在分析业务联动…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-10 text-surface-400 text-sm">
        <Link2 size={20} className="mx-auto mb-2 opacity-40" />
        暂无业务联动数据
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 摘要 */}
      <div className="rounded-xl border-2 border-finance-200 bg-finance-50/40 p-4">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-finance-600" />
          <h4 className="text-sm font-semibold text-finance-800">联动分析摘要</h4>
        </div>
        <p className="text-xs text-surface-700 mt-1.5">{data.summary}</p>
      </div>

      {/* 风险对 */}
      {data.risk_pairs.length > 0 && (
        <div className="bg-alert-50/40 border border-alert-200 rounded-xl p-4">
          <h4 className="text-sm font-semibold text-alert-700 mb-2 flex items-center gap-2">
            <AlertCircle size={14} />
            执行-报销风险对（{data.risk_pairs.length} 项）
          </h4>
          <div className="space-y-1.5">
            {data.risk_pairs.map((rp, i) => {
              const typeStyle = TYPE_STYLE[rp.linkage_type] || TYPE_STYLE['正常'];
              const riskStyle = RISK_STYLE[rp.risk_level] || RISK_STYLE.low;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2, delay: i * 0.04 }}
                  className="bg-white/60 rounded-lg p-2.5 flex items-center gap-3 flex-wrap"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-surface-800 truncate">{rp.name}</p>
                    <p className="text-[10px] text-surface-500 font-mono">{rp.budget_id}</p>
                  </div>
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className={clsx('px-1.5 py-0.5 rounded font-semibold', typeStyle.bg, typeStyle.color)}>
                      {rp.linkage_type}
                    </span>
                    <span className="text-surface-500">执行率</span>
                    <span className="font-mono font-bold text-finance-700">{rp.rate}%</span>
                    <span className="text-surface-400">|</span>
                    <span className="text-surface-500">报销</span>
                    <span className="font-mono">{rp.expense_count}笔</span>
                    <span className="text-surface-400">|</span>
                    <span className="text-surface-500">均额</span>
                    <span className="font-mono">¥{formatAmount(rp.avg_per_expense)}</span>
                    <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold', riskStyle.bg, riskStyle.color)}>
                      {rp.risk_level === 'high' ? '高风险' : rp.risk_level === 'medium' ? '中风险' : '低风险'}
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      {/* 完整联动表 */}
      <div className="bg-white rounded-xl border border-surface-200/60 overflow-hidden">
        <div className="px-4 py-2 bg-surface-50/50 border-b border-surface-200/60 flex items-center gap-2">
          <ListTree size={14} className="text-finance-600" />
          <h4 className="text-xs font-semibold text-surface-700">预算-报销联动全表（{data.items.length} 项）</h4>
        </div>
        <div className="max-h-80 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white/95 backdrop-blur">
              <tr className="border-b border-surface-200/60 text-surface-500">
                <th className="text-left py-2 px-3 font-semibold">预算项</th>
                <th className="text-left py-2 px-3 font-semibold">L1</th>
                <th className="text-right py-2 px-3 font-semibold">执行率</th>
                <th className="text-right py-2 px-3 font-semibold">报销笔数</th>
                <th className="text-right py-2 px-3 font-semibold">报销总额</th>
                <th className="text-right py-2 px-3 font-semibold">均额</th>
                <th className="text-center py-2 px-3 font-semibold">联动类型</th>
              </tr>
            </thead>
            <tbody>
              {data.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-6 text-surface-400">
                    暂无联动数据
                  </td>
                </tr>
              ) : (
                data.items.map((it, i) => {
                  const style = TYPE_STYLE[it.linkage_type] || TYPE_STYLE['正常'];
                  return (
                    <tr
                      key={i}
                      className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors"
                    >
                      <td className="py-2 px-3">
                        <p className="font-medium text-surface-800 truncate max-w-[180px]">{it.name}</p>
                        <p className="text-[10px] text-surface-400 font-mono">{it.budget_id}</p>
                      </td>
                      <td className="py-2 px-3 text-surface-500">{it.l1_code || '—'}</td>
                      <td className="py-2 px-3 text-right font-mono">
                        <span
                          className={clsx(
                            it.execution_rate >= 100
                              ? 'text-alert-700 font-bold'
                              : it.execution_rate >= 80
                                ? 'text-warning-700 font-semibold'
                                : 'text-compliance-700'
                          )}
                        >
                          {it.execution_rate}%
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right font-mono">{it.expense_count}</td>
                      <td className="py-2 px-3 text-right font-mono">¥{formatAmount(it.expense_total)}</td>
                      <td className="py-2 px-3 text-right font-mono">¥{formatAmount(it.avg_per_expense)}</td>
                      <td className="py-2 px-3 text-center">
                        <span
                          className={clsx(
                            'px-1.5 py-0.5 rounded text-[10px] font-semibold',
                            style.bg,
                            style.color
                          )}
                        >
                          {it.linkage_type}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
