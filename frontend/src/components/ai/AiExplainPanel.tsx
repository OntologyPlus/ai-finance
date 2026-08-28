import { motion } from 'framer-motion';
import { Brain, Cpu, Lightbulb, ShieldCheck, Sparkles } from 'lucide-react';
import { clsx } from 'clsx';

export interface AiStep {
  step: string;
  detail: string;
  weight?: number;
}

export interface AiExplainPanelProps {
  /** 大标题，如「5 维度优先级评分引擎」 */
  title: string;
  /** 一句话能力说明 */
  summary: string;
  /** 推理步骤（每步含 step 简述 + detail 详细） */
  steps: AiStep[];
  /** 使用的输入数据源 */
  inputs?: string[];
  /** 输出结论（AI 给出的最终判断） */
  conclusion?: string;
  /** 置信度 0-100 */
  confidence?: number;
  /** 依据的规则/模型 ID，如 SR-xxx / TPL-xxx */
  ruleIds?: string[];
  /** 模型/算法名称 */
  model?: string;
  /** 触发的口径（管理/财务/对比） */
  caliber?: string;
  className?: string;
}

/**
 * v12.2 阶段 5-8 通用：AI 解释面板
 *
 * 统一展示「模型名 / 输入 / 推理步骤 / 置信度 / 规则依据 / 结论」
 * 让业务人员看清 AI 究竟做了什么、按什么逻辑得出建议
 */
export default function AiExplainPanel({
  title,
  summary,
  steps,
  inputs,
  conclusion,
  confidence,
  ruleIds,
  model,
  caliber,
  className,
}: AiExplainPanelProps) {
  const conf = typeof confidence === 'number' ? Math.max(0, Math.min(100, confidence)) : null;
  const confTone =
    conf === null
      ? 'text-surface-500'
      : conf >= 80
      ? 'text-compliance-700'
      : conf >= 60
      ? 'text-brand-700'
      : conf >= 40
      ? 'text-warning-700'
      : 'text-alert-700';

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className={clsx('glass-card p-4', className)}
    >
      {/* 头部 */}
      <div className="flex items-start gap-3 mb-3">
        <div className="p-2 rounded-lg bg-gradient-to-br from-finance-500 to-brand-500 text-white">
          <Brain size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-finance-800">{title}</h3>
            {model && (
              <span className="badge-blue text-[10px]">
                <Cpu size={10} className="inline mr-0.5" /> {model}
              </span>
            )}
            {caliber && <span className="badge-purple text-[10px]">{caliber}</span>}
            {conf !== null && (
              <span className={clsx('ml-auto text-xs font-mono font-bold', confTone)}>
                置信度 {conf}%
              </span>
            )}
          </div>
          <p className="text-xs text-surface-500 mt-1 leading-relaxed">{summary}</p>
        </div>
      </div>

      {/* 置信度进度条 */}
      {conf !== null && (
        <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden mb-3">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${conf}%` }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
            className={clsx(
              'h-full rounded-full',
              conf >= 80
                ? 'bg-compliance-500'
                : conf >= 60
                ? 'bg-brand-500'
                : conf >= 40
                ? 'bg-warning-500'
                : 'bg-alert-500',
            )}
          />
        </div>
      )}

      {/* 推理步骤 */}
      {steps.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-semibold text-finance-700 flex items-center gap-1">
            <Sparkles size={10} /> 推理步骤
          </p>
          <ol className="space-y-1.5">
            {steps.map((s, i) => (
              <li
                key={i}
                className="flex items-start gap-2 p-2 rounded-lg bg-surface-50/70 border border-surface-100"
              >
                <div className="flex-shrink-0 w-5 h-5 rounded-full bg-finance-100 text-finance-700 text-[10px] font-bold flex items-center justify-center mt-0.5">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-semibold text-finance-800">{s.step}</p>
                    {typeof s.weight === 'number' && (
                      <span className="text-[10px] font-mono text-surface-500">
                        权重 {(s.weight * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-surface-600 mt-0.5 leading-relaxed">{s.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* 输入 + 规则依据 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
        {inputs && inputs.length > 0 && (
          <div className="p-2 rounded-lg bg-brand-50/60 border border-brand-200">
            <p className="text-[10px] font-semibold text-brand-700 mb-1">📥 输入数据</p>
            <ul className="space-y-0.5">
              {inputs.map((inp, i) => (
                <li key={i} className="text-[11px] text-brand-900">• {inp}</li>
              ))}
            </ul>
          </div>
        )}
        {ruleIds && ruleIds.length > 0 && (
          <div className="p-2 rounded-lg bg-purple-50/60 border border-purple-200">
            <p className="text-[10px] font-semibold text-purple-700 mb-1 flex items-center gap-1">
              <ShieldCheck size={10} /> 规则依据
            </p>
            <div className="flex flex-wrap gap-1">
              {ruleIds.map(r => (
                <span
                  key={r}
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-100 text-purple-800"
                >
                  {r}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 结论 */}
      {conclusion && (
        <div className="mt-3 p-2.5 rounded-lg bg-finance-50 border border-finance-200">
          <p className="text-[10px] font-semibold text-finance-700 mb-1 flex items-center gap-1">
            <Lightbulb size={10} /> AI 结论
          </p>
          <p className="text-xs text-finance-900 leading-relaxed">{conclusion}</p>
        </div>
      )}
    </motion.div>
  );
}
