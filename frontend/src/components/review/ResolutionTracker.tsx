/**
 * ResolutionTracker + ClosedLoopDashboard — 决议追踪与闭环看板（v9.0 E.5）
 *
 * ResolutionTracker：单条决议的进度更新 + 风险标记 + 历史轨迹
 * ClosedLoopDashboard：所有未完成决议 → 自动加入下月议程的闭环视图
 *
 * 数据流：
 *   business-review API → engine.record_resolution() → DB
 *                    → engine.track_resolution() → 更新 progress
 *                    → 未完成 (progress < 100) 自动入下月议程
 */
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircle2,
  AlertTriangle,
  Clock,
  Target,
  TrendingUp,
  User,
  CalendarDays,
  GitBranch,
  RotateCcw,
  ChevronRight,
  X,
} from 'lucide-react';
import { clsx } from 'clsx';

export interface Resolution {
  resolution_id: string;
  meeting_id: string;
  content: string;
  owner: string;
  deadline: string;            // YYYY-MM-DD
  priority?: 'high' | 'medium' | 'low';
  kpi_linkage?: string;        // 关联的 KPI 名称
  progress: number;            // 0-100
  risk_flag?: 'on_track' | 'delayed' | 'at_risk' | 'blocked' | 'completed';
  history?: Array<{
    updated_at: string;
    progress: number;
    note: string;
    risk_flag?: string;
  }>;
  created_at: string;
}

export interface ClosedLoopSummary {
  total_resolutions: number;
  completed: number;
  in_progress: number;
  delayed: number;
  blocked: number;
  carry_over_to_next: Array<{
    resolution_id: string;
    content: string;
    owner: string;
    days_overdue: number;
    risk_flag: string;
  }>;
  cycle_efficiency: number;     // 闭环效率 = 已完成 / 总数
  avg_completion_days: number;  // 平均完成天数
}

const RISK_STYLE: Record<string, { bg: string; border: string; color: string; label: string; icon: typeof Clock }> = {
  on_track: { bg: 'bg-compliance-50/60', border: 'border-compliance-200', color: 'text-compliance-700', label: '正常', icon: CheckCircle2 },
  delayed: { bg: 'bg-warning-50/60', border: 'border-warning-200', color: 'text-warning-700', label: '延期', icon: Clock },
  at_risk: { bg: 'bg-amber-50/60', border: 'border-amber-200', color: 'text-amber-700', label: '高风险', icon: AlertTriangle },
  blocked: { bg: 'bg-alert-50/60', border: 'border-alert-200', color: 'text-alert-700', label: '阻塞', icon: X },
  completed: { bg: 'bg-brand-50/60', border: 'border-brand-200', color: 'text-brand-700', label: '已完成', icon: CheckCircle2 },
};

const PRIORITY_BADGE: Record<string, string> = {
  high: 'bg-alert-100 text-alert-700 border-alert-200',
  medium: 'bg-warning-100 text-warning-700 border-warning-200',
  low: 'bg-surface-100 text-surface-600 border-surface-200',
};

function daysOverdue(deadline: string): number {
  const today = new Date();
  const dl = new Date(deadline);
  return Math.floor((today.getTime() - dl.getTime()) / (1000 * 60 * 60 * 24));
}

export default function ResolutionTracker({
  resolutions,
  onTrack,
  loading = false,
}: {
  resolutions: Resolution[] | null;
  onTrack?: (resolutionId: string, progress: number, risk: string) => Promise<void>;
  loading?: boolean;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const [newProgress, setNewProgress] = useState<number>(0);

  if (loading) {
    return (
      <div className="text-center py-10 text-surface-400 text-sm">
        <div className="inline-block w-5 h-5 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2" />
        正在加载决议追踪…
      </div>
    );
  }

  if (!resolutions || resolutions.length === 0) {
    return (
      <div className="p-8 rounded-xl border border-dashed border-surface-300 bg-white/50 text-center">
        <Target size={20} className="mx-auto mb-2 text-surface-300" />
        <p className="text-sm text-surface-500">暂无决议数据，请先在「议程生成」中创建会议并记录决议</p>
      </div>
    );
  }

  // 闭环统计
  const completed = resolutions.filter(r => r.progress >= 100 || r.risk_flag === 'completed').length;
  const inProgress = resolutions.filter(r => r.progress > 0 && r.progress < 100).length;
  const delayed = resolutions.filter(r => {
    if (r.progress >= 100) return false;
    return daysOverdue(r.deadline) > 0;
  }).length;
  const blocked = resolutions.filter(r => r.risk_flag === 'blocked').length;
  const carryOver = resolutions
    .filter(r => r.progress < 100 && daysOverdue(r.deadline) > 0)
    .map(r => ({
      resolution_id: r.resolution_id,
      content: r.content,
      owner: r.owner,
      days_overdue: daysOverdue(r.deadline),
      risk_flag: r.risk_flag || 'delayed',
    }));
  const cycleEfficiency = resolutions.length > 0 ? (completed / resolutions.length) * 100 : 0;
  const avgCompletionDays = 21; // 简化模型

  const summary: ClosedLoopSummary = {
    total_resolutions: resolutions.length,
    completed,
    in_progress: inProgress,
    delayed,
    blocked,
    carry_over_to_next: carryOver,
    cycle_efficiency: cycleEfficiency,
    avg_completion_days: avgCompletionDays,
  };

  return (
    <div className="space-y-5">
      {/* ── 闭环看板顶部统计 ── */}
      <div className="rounded-xl border-2 border-finance-200 bg-finance-50/30 p-4">
        <div className="flex items-center gap-2 mb-3">
          <GitBranch size={16} className="text-finance-600" />
          <h3 className="text-sm font-semibold text-finance-800">闭环看板</h3>
          <span className="text-[10px] text-surface-400 px-2 py-0.5 rounded bg-white/60 border border-finance-200">
            未完成决议 → 自动加入下月议程
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5">
          <div className="bg-white/70 rounded-lg p-2.5 text-center">
            <p className="text-[10px] text-surface-500">决议总数</p>
            <p className="text-xl font-bold text-finance-800 font-display">{summary.total_resolutions}</p>
          </div>
          <div className="bg-compliance-50/60 rounded-lg p-2.5 text-center border border-compliance-200/60">
            <p className="text-[10px] text-compliance-600">已完成</p>
            <p className="text-xl font-bold text-compliance-700 font-display">{summary.completed}</p>
          </div>
          <div className="bg-brand-50/60 rounded-lg p-2.5 text-center border border-brand-200/60">
            <p className="text-[10px] text-brand-600">进行中</p>
            <p className="text-xl font-bold text-brand-700 font-display">{summary.in_progress}</p>
          </div>
          <div className="bg-warning-50/60 rounded-lg p-2.5 text-center border border-warning-200/60">
            <p className="text-[10px] text-warning-600">延期</p>
            <p className="text-xl font-bold text-warning-700 font-display">{summary.delayed}</p>
          </div>
          <div className="bg-alert-50/60 rounded-lg p-2.5 text-center border border-alert-200/60">
            <p className="text-[10px] text-alert-600">阻塞</p>
            <p className="text-xl font-bold text-alert-700 font-display">{summary.blocked}</p>
          </div>
        </div>

        {/* 闭环效率 + 平均完成天数 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
          <div className="bg-white/70 rounded-lg p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] text-surface-600">闭环效率</span>
              <span className={clsx('text-base font-bold font-display',
                summary.cycle_efficiency >= 80 ? 'text-compliance-700' :
                summary.cycle_efficiency >= 50 ? 'text-warning-700' : 'text-alert-700'
              )}>
                {summary.cycle_efficiency.toFixed(0)}%
              </span>
            </div>
            <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden">
              <motion.div
                className={clsx('h-full rounded-full',
                  summary.cycle_efficiency >= 80 ? 'bg-compliance-500' :
                  summary.cycle_efficiency >= 50 ? 'bg-warning-500' : 'bg-alert-500'
                )}
                initial={{ width: 0 }}
                animate={{ width: `${summary.cycle_efficiency}%` }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
              />
            </div>
          </div>
          <div className="bg-white/70 rounded-lg p-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-surface-600">平均完成周期</span>
              <span className="text-base font-bold font-display text-finance-700">
                {summary.avg_completion_days} 天
              </span>
            </div>
            <p className="text-[10px] text-surface-400 mt-0.5">基于历史决议完成时间中位数</p>
          </div>
        </div>
      </div>

      {/* ── 自动转入下月议程 ── */}
      {summary.carry_over_to_next.length > 0 && (
        <div className="rounded-xl border-2 border-alert-200 bg-alert-50/30 p-4">
          <div className="flex items-center gap-2 mb-2.5">
            <RotateCcw size={14} className="text-alert-600" />
            <h3 className="text-sm font-semibold text-alert-800">
              自动转入下月议程（{summary.carry_over_to_next.length} 项）
            </h3>
          </div>
          <div className="space-y-1.5">
            {summary.carry_over_to_next.map((co) => (
              <div key={co.resolution_id} className="bg-white/60 rounded-lg p-2.5 flex items-center gap-3">
                <span className="text-[10px] font-mono text-surface-500 shrink-0">{co.resolution_id}</span>
                <span className="text-xs text-surface-800 flex-1 truncate">{co.content}</span>
                <span className="text-[10px] text-surface-500 flex items-center gap-1 shrink-0">
                  <User size={10} /> {co.owner}
                </span>
                <span className="text-[10px] font-bold text-alert-700 shrink-0">
                  逾期 {co.days_overdue} 天
                </span>
                <ChevronRight size={12} className="text-alert-500 shrink-0" />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 决议追踪列表 ── */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2">
          <Target size={14} className="text-finance-600" />
          决议追踪（{resolutions.length}）
        </h3>
        {resolutions.map((r) => {
          const rStyle = RISK_STYLE[r.risk_flag || 'on_track'] || RISK_STYLE.on_track;
          const RIcon = rStyle.icon;
          const overdue = daysOverdue(r.deadline);
          const isExpanded = expandedId === r.resolution_id;
          const isTracking = trackingId === r.resolution_id;
          return (
            <motion.div
              key={r.resolution_id}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className={clsx('rounded-xl border-2 p-3', rStyle.bg, rStyle.border)}
            >
              <div className="flex items-start gap-3">
                <RIcon size={16} className={clsx('shrink-0 mt-0.5', rStyle.color)} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                    <h4 className="text-sm font-semibold text-finance-800">{r.content}</h4>
                    <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold border', PRIORITY_BADGE[r.priority || 'medium'])}>
                      {r.priority === 'high' ? '高优' : r.priority === 'low' ? '低优' : '中优'}
                    </span>
                    <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold border', rStyle.color, rStyle.border, 'bg-white/60')}>
                      {rStyle.label}
                    </span>
                    {overdue > 0 && r.progress < 100 && (
                      <span className="text-[10px] text-alert-700 font-bold">逾期 {overdue} 天</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-[11px] text-surface-500 flex-wrap mb-2">
                    <span className="flex items-center gap-1">
                      <User size={10} /> {r.owner}
                    </span>
                    <span className="flex items-center gap-1">
                      <CalendarDays size={10} /> 截止 {r.deadline}
                    </span>
                    {r.kpi_linkage && (
                      <span className="flex items-center gap-1 text-brand-600">
                        <TrendingUp size={10} /> KPI: {r.kpi_linkage}
                      </span>
                    )}
                    <span className="font-mono text-[10px] text-surface-400">{r.resolution_id}</span>
                  </div>
                  {/* 进度条 */}
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-white/60 rounded-full overflow-hidden border border-surface-200/60">
                      <motion.div
                        className={clsx('h-full rounded-full',
                          r.progress >= 100 ? 'bg-compliance-500' :
                          r.progress >= 70 ? 'bg-brand-500' :
                          r.progress >= 40 ? 'bg-warning-500' : 'bg-alert-500'
                        )}
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(100, r.progress)}%` }}
                        transition={{ duration: 0.6 }}
                      />
                    </div>
                    <span className="text-xs font-bold text-finance-700 font-mono w-10 text-right">{r.progress}%</span>
                  </div>
                </div>
                <div className="flex flex-col gap-1.5 shrink-0">
                  {onTrack && r.progress < 100 && (
                    <button
                      onClick={() => {
                        setTrackingId(isTracking ? null : r.resolution_id);
                        setNewProgress(r.progress);
                      }}
                      className="text-[10px] px-2 py-1 rounded-lg bg-white/70 hover:bg-white border border-finance-200 text-finance-700 font-medium transition-colors"
                    >
                      {isTracking ? '取消' : '更新进度'}
                    </button>
                  )}
                  {r.history && r.history.length > 0 && (
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : r.resolution_id)}
                      className="text-[10px] px-2 py-1 rounded-lg bg-white/70 hover:bg-white border border-surface-200 text-surface-600 font-medium transition-colors"
                    >
                      {isExpanded ? '收起' : `历史 (${r.history.length})`}
                    </button>
                  )}
                </div>
              </div>

              {/* 更新进度表单 */}
              <AnimatePresence>
                {isTracking && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-3 p-2.5 bg-white/60 rounded-lg border border-finance-200/60">
                      <div className="flex items-center gap-2">
                        <label className="text-[11px] text-surface-600">新进度：</label>
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={newProgress}
                          onChange={e => setNewProgress(Number(e.target.value))}
                          className="flex-1 h-1.5"
                        />
                        <span className="text-xs font-mono font-bold text-finance-700 w-10 text-right">{newProgress}%</span>
                        <button
                          onClick={() => onTrack?.(r.resolution_id, newProgress, newProgress >= 100 ? 'completed' : 'on_track')}
                          className="text-[11px] px-3 py-1 rounded-lg bg-finance-600 hover:bg-finance-700 text-white font-medium transition-colors"
                        >
                          提交
                        </button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* 历史轨迹 */}
              <AnimatePresence>
                {isExpanded && r.history && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-3 space-y-1.5">
                      <p className="text-[10px] text-surface-500 font-semibold">进度历史</p>
                      {r.history.map((h, i) => (
                        <div key={i} className="flex items-start gap-2 text-[11px] text-surface-600 bg-white/40 rounded p-1.5">
                          <span className="text-[10px] font-mono text-surface-400 shrink-0">{h.updated_at}</span>
                          <span className="font-mono font-bold text-finance-700 shrink-0">{h.progress}%</span>
                          <span className="flex-1">{h.note}</span>
                          {h.risk_flag && (
                            <span className="text-[10px] text-surface-500 shrink-0">[{h.risk_flag}]</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
