import { motion, useSpring, useTransform } from 'framer-motion';
import { AlertTriangle, Lightbulb, Info, ChevronDown, ChevronRight, Sparkles } from 'lucide-react';
import { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import AnimatedNumber from './AnimatedNumber';

interface Insight {
  priority: 'critical' | 'attention' | 'info';
  title: string;
  analysis: string;
  suggestion: string;
}

interface AIViewPanelProps {
  title: string;
  insights: Insight[];
  summary?: string;
  score?: { value: number; label: string; max?: number };
  children?: React.ReactNode;
}

const PRIORITY_CONFIG = {
  critical: {
    icon: AlertTriangle,
    bg: 'bg-alert-50/50',
    border: 'border-alert-200',
    titleColor: 'text-alert-700',
    iconColor: 'text-alert-500',
    badgeBg: 'bg-alert-100',
    badgeText: 'text-alert-700',
    badgeLabel: '紧急',
  },
  attention: {
    icon: Lightbulb,
    bg: 'bg-warning-50/50',
    border: 'border-warning-200',
    titleColor: 'text-warning-700',
    iconColor: 'text-warning-500',
    badgeBg: 'bg-warning-100',
    badgeText: 'text-warning-700',
    badgeLabel: '注意',
  },
  info: {
    icon: Info,
    bg: 'bg-brand-50/50',
    border: 'border-brand-200',
    titleColor: 'text-brand-700',
    iconColor: 'text-brand-500',
    badgeBg: 'bg-brand-100',
    badgeText: 'text-brand-700',
    badgeLabel: '信息',
  },
};

function ScoreRing({ value, max = 100, label }: { value: number; max: number; label: string }) {
  const pct = Math.round((value / max) * 100);
  const color = pct >= 70 ? 'text-compliance-600' : pct >= 40 ? 'text-warning-600' : 'text-alert-600';
  const circumference = 2 * Math.PI * 36;
  
  // Spring animation for the ring
  const springValue = useSpring(0, {
    stiffness: 120,
    damping: 15,
    mass: 0.8,
  });
  
  const strokeDashoffset = useTransform(
    springValue,
    (val) => circumference - (val / 100) * circumference
  );

  useEffect(() => {
    springValue.set(pct);
  }, [pct, springValue]);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
          <circle cx="40" cy="40" r="36" fill="none" stroke="#e2e8f0" strokeWidth="6" />
          <motion.circle
            cx="40" cy="40" r="36" fill="none" strokeWidth="6"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{
              stroke: pct >= 70 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#ef4444',
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <AnimatedNumber
            value={value}
            className={clsx('text-lg font-bold', color)}
          />
          <span className="text-[10px] text-surface-400">/{max}</span>
        </div>
      </div>
      <span className="text-xs font-medium text-surface-600">{label}</span>
    </div>
  );
}

export default function AIViewPanel({ title, insights, summary, score, children }: AIViewPanelProps) {
  const [expandedInsights, setExpandedInsights] = useState<Set<number>>(new Set([0]));

  const toggleInsight = (idx: number) => {
    setExpandedInsights(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
      className="space-y-4"
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-1">
        <Sparkles size={16} className="text-finance-600" />
        <h3 className="text-sm font-semibold text-finance-800">{title}</h3>
        {summary && <span className="text-xs text-surface-400 ml-2">{summary}</span>}
      </div>

      {/* Score (if provided) */}
      {score && (
        <div className="flex items-center justify-center p-4">
          <ScoreRing value={score.value} max={score.max} label={score.label} />
        </div>
      )}

      {/* Insights */}
      {insights.length > 0 && (
        <div className="space-y-2">
          {insights.map((insight, idx) => {
            const config = PRIORITY_CONFIG[insight.priority];
            const Icon = config.icon;
            const isExpanded = expandedInsights.has(idx);

            return (
              <div
                key={idx}
                className={clsx('rounded-xl border overflow-hidden transition-colors', config.bg, config.border)}
              >
                <button
                  onClick={() => toggleInsight(idx)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left"
                >
                  <Icon size={14} className={config.iconColor} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold', config.badgeBg, config.badgeText)}>
                        {config.badgeLabel}
                      </span>
                      <span className={clsx('text-sm font-medium', config.titleColor)}>{insight.title}</span>
                    </div>
                  </div>
                  {isExpanded ? <ChevronDown size={14} className="text-surface-400" /> : <ChevronRight size={14} className="text-surface-400" />}
                </button>

                {isExpanded && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="px-4 pb-3 pt-0"
                  >
                    <div className="ml-6 space-y-2 text-sm">
                      <p className="text-surface-600">{insight.analysis}</p>
                      <div className="flex items-start gap-2 px-3 py-2 rounded-lg bg-white/60">
                        <Lightbulb size={12} className="text-finance-500 mt-0.5 shrink-0" />
                        <p className="text-surface-700">{insight.suggestion}</p>
                      </div>
                    </div>
                  </motion.div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Additional custom content */}
      {children}
    </motion.div>
  );
}
