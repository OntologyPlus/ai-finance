/**
 * ViewModeToggle — 经典模式 / 决策模式 切换
 * v4.0 新增：保留旧 4-Tab 兼容旧用户
 */
import { clsx } from 'clsx';
import { LayoutGrid, Sparkles } from 'lucide-react';

export type ViewMode = 'classic' | 'modern';

export interface ViewModeToggleProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
  className?: string;
}

export default function ViewModeToggle({ value, onChange, className }: ViewModeToggleProps) {
  return (
    <div
      className={clsx(
        'inline-flex items-center p-1 rounded-xl bg-surface-100 border border-surface-200',
        className,
      )}
    >
      <button
        onClick={() => onChange('classic')}
        className={clsx(
          'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
          value === 'classic'
            ? 'bg-white text-finance-700 shadow-sm'
            : 'text-surface-500 hover:text-surface-700',
        )}
      >
        <LayoutGrid size={14} />
        经典模式
      </button>
      <button
        onClick={() => onChange('modern')}
        className={clsx(
          'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all',
          value === 'modern'
            ? 'bg-white text-brand-700 shadow-sm'
            : 'text-surface-500 hover:text-surface-700',
        )}
      >
        <Sparkles size={14} />
        决策模式
      </button>
    </div>
  );
}
