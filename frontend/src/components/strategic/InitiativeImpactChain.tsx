import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GitBranch, ChevronRight, ChevronDown, Target, Wallet, Activity } from 'lucide-react';
import { clsx } from 'clsx';

interface ImpactNode {
  node_id: string;
  level: string;
  name: string;
  status: string;
  metric: number | null;
  unit: string;
  note: string;
  children: ImpactNode[];
}

const STATUS_STYLE: Record<string, { color: string; bg: string; border: string; icon: string; label: string }> = {
  active: { color: 'text-finance-700', bg: 'bg-finance-50/60', border: 'border-finance-300', icon: '○', label: '正常' },
  achieved: { color: 'text-compliance-700', bg: 'bg-compliance-50/60', border: 'border-compliance-300', icon: '✓', label: '已达成' },
  warning: { color: 'text-warning-700', bg: 'bg-warning-50/60', border: 'border-warning-300', icon: '!', label: '关注' },
  risk: { color: 'text-alert-700', bg: 'bg-alert-50/60', border: 'border-alert-300', icon: '✕', label: '风险' },
};

const LEVEL_ICON: Record<string, any> = {
  intent: Target,
  initiative: GitBranch,
  budget: Wallet,
  execution: Activity,
};

function ChainNode({ node, depth = 0 }: { node: ImpactNode; depth?: number }) {
  const [expanded, setExpanded] = useState(true);
  const style = STATUS_STYLE[node.status] || STATUS_STYLE.active;
  const Icon = LEVEL_ICON[node.level] || Target;
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className={clsx('relative', depth > 0 && 'ml-6 mt-2')}>
      {depth > 0 && (
        <div className="absolute -left-4 top-5 w-4 h-0.5 bg-surface-200" />
      )}
      <motion.button
        onClick={() => hasChildren && setExpanded(!expanded)}
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.2, delay: depth * 0.05 }}
        className={clsx(
          'w-full text-left rounded-lg border-2 p-3 transition-all',
          style.bg,
          style.border,
          hasChildren && 'hover:shadow-sm cursor-pointer'
        )}
      >
        <div className="flex items-center gap-2.5">
          <div className={clsx(
            'w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border',
            style.border,
            'bg-white'
          )}>
            <Icon size={14} className={style.color} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={clsx('text-[10px] font-bold uppercase tracking-wide', style.color)}>
                {node.level === 'intent' ? '战略意图' :
                 node.level === 'initiative' ? '举措' :
                 node.level === 'budget' ? '预算' : '执行'}
              </span>
              <span className="text-xs text-surface-400 font-mono">{node.node_id}</span>
            </div>
            <p className="text-sm font-medium text-surface-800 truncate">{node.name}</p>
            {node.note && <p className="text-[10px] text-surface-500 mt-0.5">{node.note}</p>}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {node.metric !== null && node.metric !== undefined && (
              <div className="text-right">
                <div className={clsx('text-lg font-bold font-display', style.color)}>
                  {node.metric.toFixed(0)}<span className="text-xs ml-0.5">{node.unit}</span>
                </div>
              </div>
            )}
            <span className={clsx(
              'px-1.5 py-0.5 rounded text-[10px] font-bold shrink-0',
              style.bg, style.color, 'border', style.border
            )}>
              {style.label}
            </span>
            {hasChildren && (
              <div className="text-surface-400 ml-1">
                {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </div>
            )}
          </div>
        </div>
      </motion.button>

      <AnimatePresence>
        {expanded && hasChildren && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="pl-2 border-l-2 border-surface-200 ml-3.5 space-y-1.5">
              {node.children.map((child) => (
                <ChainNode key={child.node_id} node={child} depth={depth + 1} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function InitiativeImpactChain({
  data,
  loading,
}: {
  data: ImpactNode | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="text-center py-8 text-surface-400 text-sm">
        <div className="inline-block w-5 h-5 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2"></div>
        正在构建影响链…
      </div>
    );
  }
  if (!data) {
    return (
      <div className="glass-card-static p-5 text-center text-surface-400 text-sm">
        <GitBranch size={20} className="mx-auto mb-2 opacity-40" />
        选择一个战略举措查看影响链
      </div>
    );
  }
  return (
    <div>
      <div className="text-xs text-surface-500 mb-2.5 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-finance-400" />
        影响链展示：战略意图 → 举措 → 预算分期 → 实际执行（4 层传导）
      </div>
      <ChainNode node={data} />
    </div>
  );
}
