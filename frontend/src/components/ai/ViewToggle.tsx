import { Sparkles, Table2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { clsx } from 'clsx';

type ViewMode = 'ai' | 'data';

interface ViewToggleProps {
  mode: ViewMode;
  onToggle: (mode: ViewMode) => void;
}

export default function ViewToggle({ mode, onToggle }: ViewToggleProps) {
  return (
    <div className="inline-flex items-center gap-1 p-1 rounded-xl bg-surface-100 border border-surface-200/60">
      <button
        onClick={() => onToggle('ai')}
        className={clsx(
          'relative flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
          mode === 'ai' ? 'text-finance-700' : 'text-surface-400 hover:text-surface-600'
        )}
      >
        {mode === 'ai' && (
          <motion.div
            layoutId="viewToggle"
            className="absolute inset-0 bg-white rounded-lg shadow-sm border border-surface-200/60"
            transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          />
        )}
        <Sparkles size={12} className="relative z-10" />
        <span className="relative z-10">AI 视图</span>
      </button>
      <button
        onClick={() => onToggle('data')}
        className={clsx(
          'relative flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
          mode === 'data' ? 'text-finance-700' : 'text-surface-400 hover:text-surface-600'
        )}
      >
        {mode === 'data' && (
          <motion.div
            layoutId="viewToggle"
            className="absolute inset-0 bg-white rounded-lg shadow-sm border border-surface-200/60"
            transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          />
        )}
        <Table2 size={12} className="relative z-10" />
        <span className="relative z-10">数据视图</span>
      </button>
    </div>
  );
}
