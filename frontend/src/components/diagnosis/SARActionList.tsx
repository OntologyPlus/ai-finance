/**
 * SARActionList — SAR 行动建议列表
 * v4.0 新增：第四部分"行动建议"
 *
 * SAR 框架：战略 (Strategy) → 行动 (Action) → 结果 (Result)
 */
import { Target, Zap, BarChart2, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';

export type ActionPriority = 'high' | 'medium' | 'low';

export interface SARAction {
  id?: string;
  strategy?: string;       // 战略对齐
  action: string;          // 关键行动
  expected_result?: string;// 预期结果
  owner?: string;          // 责任人
  deadline?: string;       // 截止日
  pending_question?: string;
  priority: ActionPriority;
  source_card?: string;    // 来源诊断卡
}

export interface SARActionListProps {
  actions: SARAction[];
}

const PRIORITY_STYLE: Record<string, { bg: string; text: string; border: string; label: string }> = {
  high: { bg: 'bg-alert-50', text: 'text-alert-700', border: 'border-alert-200', label: '高' },
  medium: { bg: 'bg-warning-50', text: 'text-warning-700', border: 'border-warning-200', label: '中' },
  low: { bg: 'bg-brand-50', text: 'text-brand-700', border: 'border-brand-200', label: '低' },
};

export default function SARActionList({ actions }: SARActionListProps) {
  if (!actions || actions.length === 0) {
    return (
      <div className="p-6 rounded-xl border border-surface-200 bg-white text-center text-surface-400 text-sm">
        暂无行动建议
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {actions.map((a, i) => {
        const style = PRIORITY_STYLE[a.priority] || PRIORITY_STYLE.medium;
        return (
          <div
            key={a.id || i}
            className={clsx('p-4 rounded-xl border bg-white', style.border)}
          >
            <div className="flex items-start gap-3">
              <div className={clsx('flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center', style.bg)}>
                <span className={clsx('text-xs font-bold', style.text)}>{i + 1}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-semibold', style.bg, style.text)}>
                    {style.label}优先级
                  </span>
                  {a.source_card && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-100 text-surface-500">
                      来自：{a.source_card}
                    </span>
                  )}
                  {a.owner && (
                    <span className="text-[10px] text-surface-500">责任人：{a.owner}</span>
                  )}
                  {a.deadline && (
                    <span className="text-[10px] text-surface-500">截止：{a.deadline}</span>
                  )}
                </div>

                {a.strategy && (
                  <div className="flex items-start gap-2 mb-1.5">
                    <Target size={12} className="text-brand-500 flex-shrink-0 mt-1" />
                    <div className="flex-1">
                      <span className="text-[10px] font-semibold text-surface-500 mr-1">战略</span>
                      <span className="text-xs text-finance-700">{a.strategy}</span>
                    </div>
                  </div>
                )}

                <div className="flex items-start gap-2 mb-1.5">
                  <Zap size={12} className="text-warning-500 flex-shrink-0 mt-1" />
                  <div className="flex-1">
                    <span className="text-[10px] font-semibold text-surface-500 mr-1">行动</span>
                    <span className="text-sm text-finance-800 font-medium">{a.action}</span>
                  </div>
                </div>

                {a.expected_result && (
                  <div className="flex items-start gap-2">
                    <BarChart2 size={12} className="text-compliance-500 flex-shrink-0 mt-1" />
                    <div className="flex-1">
                      <span className="text-[10px] font-semibold text-surface-500 mr-1">预期结果</span>
                      <span className="text-xs text-finance-700">{a.expected_result}</span>
                    </div>
                  </div>
                )}

                {a.pending_question && (
                  <div className="mt-2 flex items-start gap-2 px-2 py-1.5 rounded bg-warning-50/60 border border-warning-100">
                    <AlertCircle size={12} className="text-warning-600 flex-shrink-0 mt-0.5" />
                    <span className="text-[11px] text-warning-800">
                      <span className="font-semibold">待确认：</span>
                      {a.pending_question}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
