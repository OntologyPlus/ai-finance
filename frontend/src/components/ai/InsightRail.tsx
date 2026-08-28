/**
 * InsightRail — 统一主动建议轨道（v10.0 新增）
 *
 * 替代 Dashboard 中 3 处独立 Insight 列表（ProactiveInsightBanner + analysisInsights + generateInsights）
 * - 按 priority 排序（critical > attention > info）
 * - 一句话摘要（去掉 expand 折叠）
 * - 配色统一：critical 红 / attention 橙 / info 蓝，无渐变
 * - 右侧 1 个"查看 →"链接
 */
import { ArrowRight, AlertTriangle, Clock, CheckCircle } from 'lucide-react';

export type InsightPriority = 'critical' | 'attention' | 'info';

export interface InsightItem {
  id: string;
  priority: InsightPriority;
  title: string;
  summary: string;     // 一句话摘要
  action_url?: string;
  action_label?: string;
}

const PRIORITY_STYLES: Record<InsightPriority, { dot: string; badge: string; label: string; Icon: typeof AlertTriangle }> = {
  critical: { dot: 'bg-alert-500', badge: 'badge-red', label: '紧急', Icon: AlertTriangle },
  attention: { dot: 'bg-warning-500', badge: 'badge-amber', label: '关注', Icon: Clock },
  info: { dot: 'bg-brand-500', badge: 'badge-blue', label: '提示', Icon: CheckCircle },
};

export default function InsightRail({
  insights,
  maxVisible = 3,
  onAction,
  emptyMessage = '今天没有需要特别处理的事项',
}: {
  insights: InsightItem[];
  maxVisible?: number;
  onAction?: (item: InsightItem) => void;
  emptyMessage?: string;
}) {
  // 去重（按 title 优先保留 priority 最高的）
  const seen = new Map<string, InsightItem>();
  const order: InsightPriority[] = ['critical', 'attention', 'info'];
  insights.forEach((it) => {
    const prev = seen.get(it.title);
    if (!prev || order.indexOf(it.priority) < order.indexOf(prev.priority)) {
      seen.set(it.title, it);
    }
  });
  const dedup = Array.from(seen.values())
    .sort((a, b) => order.indexOf(a.priority) - order.indexOf(b.priority))
    .slice(0, maxVisible);

  if (dedup.length === 0) {
    return (
      <div className="surface-card flex items-center gap-2 text-sm text-surface-500">
        <CheckCircle size={16} className="text-compliance-500" />
        <span>{emptyMessage}</span>
      </div>
    );
  }

  return (
    <div className="surface-card space-y-2">
      {dedup.map((it) => {
        const s = PRIORITY_STYLES[it.priority];
        const Icon = s.Icon;
        return (
          <div key={it.id} className="flex items-center gap-3 py-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${s.dot} flex-shrink-0`} />
            <Icon size={14} className="text-surface-400 flex-shrink-0" />
            <div className="flex-1 min-w-0 flex items-center gap-2">
              <span className={`${s.badge} flex-shrink-0`}>{s.label}</span>
              <span className="text-sm text-finance-800 truncate font-medium">{it.title}</span>
              {it.summary && (
                <span className="text-xs text-surface-500 truncate">· {it.summary}</span>
              )}
            </div>
            {(it.action_url || onAction) && (
              <button
                onClick={() => onAction ? onAction(it) : (it.action_url && (window.location.href = it.action_url))}
                className="flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 flex-shrink-0"
              >
                {it.action_label || '查看'}
                <ArrowRight size={12} />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
