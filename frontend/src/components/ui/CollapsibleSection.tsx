/**
 * CollapsibleSection — 统一折叠容器（v10.0 新增）
 *
 * 200ms height auto 静态过渡，无 spring。
 * 替代 Dashboard 中 4 个图表区的手写展开/折叠。
 */
import { useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export interface CollapsibleSectionProps {
  title: string;
  icon?: typeof ChevronDown;
  badge?: string;
  defaultOpen?: boolean;
  children: ReactNode;
  className?: string;
}

export default function CollapsibleSection({
  title,
  icon: Icon,
  badge,
  defaultOpen = false,
  children,
  className = '',
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={`surface-card ${className}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between text-left"
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          {Icon && <Icon size={14} className="text-finance-600" />}
          <h3 className="section-title">{title}</h3>
          {badge && (
            <span className="text-[10px] text-surface-400 px-1.5 py-0.5 rounded bg-surface-50 border border-surface-200">
              {badge}
            </span>
          )}
        </div>
        <ChevronDown
          size={16}
          className={`text-surface-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className="pt-3">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
