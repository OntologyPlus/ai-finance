/**
 * TopJudgmentsList — Top 3-5 核心判断（高密度文字卡片）
 * v4.0 新增：替代传统"摘要"页
 */
import { Lightbulb } from 'lucide-react';

export interface Judgment {
  title: string;
  detail?: string;
  level?: 'critical' | 'attention' | 'info';
  source_card?: string;  // 来自哪张诊断卡
}

export interface TopJudgmentsListProps {
  judgments: Judgment[];
  title?: string;
}

const LEVEL_STYLE: Record<string, string> = {
  critical: 'border-l-alert-500 bg-alert-50/40',
  attention: 'border-l-warning-500 bg-warning-50/40',
  info: 'border-l-brand-500 bg-brand-50/40',
};

export default function TopJudgmentsList({
  judgments,
  title = '核心判断（Top 3-5）',
}: TopJudgmentsListProps) {
  if (!judgments || judgments.length === 0) {
    return (
      <div className="p-6 rounded-xl border border-surface-200 bg-white text-center text-surface-400 text-sm">
        暂无核心判断数据
      </div>
    );
  }

  return (
    <div className="p-5 rounded-xl border border-surface-200 bg-white">
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb size={16} className="text-brand-500" />
        <h3 className="text-sm font-semibold text-finance-800">{title}</h3>
      </div>
      <ul className="space-y-2">
        {judgments.map((j, i) => (
          <li
            key={i}
            className={`pl-3 pr-3 py-2.5 border-l-4 rounded-r-lg ${
              LEVEL_STYLE[j.level || 'info']
            }`}
          >
            <div className="flex items-start gap-2">
              <span className="text-xs font-bold text-surface-400 mt-0.5 w-4">
                {i + 1}
              </span>
              <div className="flex-1">
                <p className="text-sm font-semibold text-finance-800">{j.title}</p>
                {j.detail && (
                  <p className="text-xs text-surface-600 mt-1 leading-relaxed">{j.detail}</p>
                )}
                {j.source_card && (
                  <span className="inline-block mt-1.5 text-[10px] px-1.5 py-0.5 rounded bg-surface-100 text-surface-500">
                    来自：{j.source_card}
                  </span>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
