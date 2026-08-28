/**
 * DiagnosisCardSkeleton — 加载占位（9 张卡的骨架屏）
 * v4.0 新增
 */
import { clsx } from 'clsx';

export interface DiagnosisCardSkeletonProps {
  count?: number;
  className?: string;
}

export default function DiagnosisCardSkeleton({ count = 9, className }: DiagnosisCardSkeletonProps) {
  return (
    <div className={clsx('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4', className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="p-4 rounded-xl border border-surface-200 bg-white/60 animate-pulse"
        >
          <div className="flex items-center justify-between mb-3">
            <div className="h-4 w-24 bg-surface-200 rounded" />
            <div className="h-5 w-12 bg-surface-200 rounded-md" />
          </div>
          <div className="space-y-2">
            <div className="h-3 w-full bg-surface-100 rounded" />
            <div className="h-3 w-5/6 bg-surface-100 rounded" />
            <div className="h-3 w-4/6 bg-surface-100 rounded" />
          </div>
          <div className="mt-3 flex gap-2">
            <div className="h-6 w-16 bg-surface-100 rounded" />
            <div className="h-6 w-20 bg-surface-100 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}
