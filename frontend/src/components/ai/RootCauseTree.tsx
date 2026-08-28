import { motion } from 'framer-motion';
import { ChevronDown, GitBranch, AlertTriangle, Target, TrendingDown, Users } from 'lucide-react';
import { clsx } from 'clsx';
import { useState } from 'react';

export interface RootCauseNode {
  /** 节点名 */
  label: string;
  /** 节点值/比例，如 '38%' / '¥120万' */
  value?: string;
  /** 节点色调 */
  tone?: 'alert' | 'warning' | 'brand' | 'finance' | 'compliance';
  /** 子节点（递归） */
  children?: RootCauseNode[];
  /** 解释/依据 */
  reason?: string;
}

export interface RootCauseTreeProps {
  /** 标题 */
  title?: string;
  /** 根因主题（最右端） */
  topic: string;
  /** 根因节点树（从左到右展开） */
  nodes: RootCauseNode[];
  /** 维度标签，如 5M1E / 5-Why / 5 层下钻 */
  layerLabels?: string[];
  /** 补充说明 */
  caption?: string;
  className?: string;
}

const TONE_CLS: Record<NonNullable<RootCauseNode['tone']>, string> = {
  alert: 'bg-alert-100 border-alert-300 text-alert-800',
  warning: 'bg-warning-100 border-warning-300 text-warning-800',
  brand: 'bg-brand-100 border-brand-300 text-brand-800',
  finance: 'bg-finance-100 border-finance-300 text-finance-800',
  compliance: 'bg-compliance-100 border-compliance-300 text-compliance-800',
};

const ICON_MAP: Record<NonNullable<RootCauseNode['tone']>, any> = {
  alert: AlertTriangle,
  warning: TrendingDown,
  brand: Users,
  finance: GitBranch,
  compliance: Target,
};

function Node({
  node,
  depth,
  expanded,
  toggle,
}: {
  node: RootCauseNode;
  depth: number;
  expanded: Set<string>;
  toggle: (k: string) => void;
}) {
  const key = `${depth}:${node.label}`;
  const hasChildren = !!node.children?.length;
  const isOpen = expanded.has(key) || depth < 1; // 默认展开前两层
  const tone = node.tone || 'finance';
  const Icon = ICON_MAP[tone];

  return (
    <div className="relative">
      <div
        className={clsx(
          'flex items-center gap-2 px-2.5 py-1.5 rounded-lg border min-w-[140px]',
          TONE_CLS[tone],
        )}
      >
        <Icon size={12} className="flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-semibold truncate">{node.label}</p>
          {node.value && (
            <p className="text-[10px] font-mono opacity-80">{node.value}</p>
          )}
        </div>
        {hasChildren && (
          <button
            onClick={() => toggle(key)}
            className="p-0.5 rounded hover:bg-white/40"
          >
            <ChevronDown
              size={12}
              className={clsx('transition-transform', !isOpen && '-rotate-90')}
            />
          </button>
        )}
      </div>
      {node.reason && (
        <p className="text-[10px] text-surface-500 mt-0.5 pl-1 max-w-[200px] leading-tight">
          {node.reason}
        </p>
      )}
      {hasChildren && isOpen && (
        <div className="mt-1.5 ml-3 pl-3 border-l-2 border-dashed border-surface-200 space-y-1.5">
          {node.children!.map((c, i) => (
            <Node key={i} node={c} depth={depth + 1} expanded={expanded} toggle={toggle} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * v12.2 阶段 5-8 通用：根因可视化
 *
 * 支持 5-Why / 5 层下钻 / 鱼骨图风格的递归树状展示
 * 主题（最右端）→ 5 大维度 → 子原因
 */
export default function RootCauseTree({
  title = 'AI 根因下钻',
  topic,
  nodes,
  layerLabels,
  caption,
  className,
}: RootCauseTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (k: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className={clsx('glass-card p-4', className)}
    >
      <div className="flex items-center gap-2 mb-3">
        <GitBranch size={14} className="text-finance-700" />
        <h3 className="text-sm font-semibold text-finance-800">{title}</h3>
        {caption && <p className="ml-auto text-[10px] text-surface-400">{caption}</p>}
      </div>

      {/* 根因 + 维度树（横向鱼骨布局） */}
      <div className="overflow-x-auto">
        <div className="flex items-stretch gap-2 min-w-fit">
          {/* 维度列 */}
          <div className="flex flex-col gap-2 justify-around py-1">
            {layerLabels?.map((l, i) => (
              <div
                key={i}
                className="text-[10px] text-surface-500 font-semibold h-8 flex items-center px-2"
              >
                {l}
              </div>
            ))}
          </div>

          {/* 节点列（每个节点一列） */}
          <div className="flex gap-3">
            {nodes.map((n, i) => (
              <div
                key={i}
                className="flex flex-col items-center justify-center min-w-[160px] px-2 py-1.5 rounded-xl bg-surface-50/60 border border-surface-200"
              >
                <Node node={n} depth={0} expanded={expanded} toggle={toggle} />
              </div>
            ))}
          </div>

          {/* 鱼骨箭头 → 主题 */}
          <div className="flex items-center pl-3 pr-2">
            <div className="flex flex-col items-center">
              <p className="text-[10px] text-surface-400 mb-1">根因主题</p>
              <div className="px-3 py-2 rounded-lg bg-gradient-to-br from-alert-500 to-alert-600 text-white shadow-md">
                <p className="text-xs font-bold whitespace-nowrap">{topic}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <p className="text-[10px] text-surface-400 mt-2">
        点击节点右侧 ▾ 可展开 / 收起子原因
      </p>
    </motion.div>
  );
}
