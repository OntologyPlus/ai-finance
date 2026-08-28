/**
 * RuleBadge — v11.0 规则徽章
 *
 * 用于业务页面（Alert/Expense/Approval）显示"依据 HR-001 / SR-001"
 * 灰色背景 + 等宽字体 + 可选 tooltip 显示规则名
 */
import clsx from 'clsx';
import { Scale } from 'lucide-react';

export interface RuleBadgeProps {
  rule_id: string;
  rule_name?: string;
  className?: string;
  size?: 'sm' | 'xs';
  onClick?: () => void;
}

export default function RuleBadge({
  rule_id,
  rule_name,
  className = '',
  size = 'sm',
  onClick,
}: RuleBadgeProps) {
  return (
    <span
      onClick={onClick}
      title={rule_name || rule_id}
      className={clsx(
        'inline-flex items-center gap-1 rounded border border-surface-200 bg-surface-50 text-surface-700 font-mono',
        size === 'xs' ? 'text-[10px] px-1.5 py-0' : 'text-[11px] px-1.5 py-0.5',
        onClick && 'cursor-pointer hover:bg-surface-100 hover:border-surface-300 transition-colors',
        className,
      )}
    >
      <Scale size={size === 'xs' ? 9 : 10} className="text-surface-400" />
      <span>依据 {rule_id}</span>
    </span>
  );
}
