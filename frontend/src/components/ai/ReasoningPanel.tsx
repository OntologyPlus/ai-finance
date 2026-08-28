/**
 * ReasoningPanel — v11.0 推理透明面板
 *
 * 让用户看到 Chat 答案的"决策依据"：
 * - matched scene（哪个场景被激活）
 * - activated rules（哪些规则被加载）
 * - activated behaviors / objects
 * - 置信度 + 推理耗时
 */
import { Brain, ChevronDown, Tag, Zap, Clock } from 'lucide-react';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export interface OntologyMeta {
  scene_id: string;
  scene_name: string;
  stage?: string;
  confidence: number;
  matched_objects?: string[];
  activated_rules?: string[];
  activated_behaviors?: string[];
  agent_name?: string;
  elapsed_ms?: number;
}

export default function ReasoningPanel({ meta }: { meta: OntologyMeta | null | undefined }) {
  const [open, setOpen] = useState(false);

  if (!meta) {
    return (
      <div className="mt-2 text-[11px] text-surface-400 flex items-center gap-1">
        <Brain size={11} />
        推理过程：未匹配到已知场景
      </div>
    );
  }

  const confColor =
    meta.confidence >= 0.7 ? 'text-compliance-600' :
    meta.confidence >= 0.4 ? 'text-warning-600' :
    'text-surface-500';

  return (
    <div className="mt-2 border-t border-surface-100 pt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-[11px] text-surface-500 hover:text-finance-600 transition-colors"
      >
        <Brain size={11} className="text-finance-500" />
        <span>
          推理：场景 <span className="font-mono text-finance-700">{meta.scene_name}</span>
          {meta.activated_rules && meta.activated_rules.length > 0 && (
            <> · 激活 <span className="font-mono">{meta.activated_rules.length}</span> 条规则</>
          )}
          {meta.elapsed_ms != null && (
            <> · <Clock size={9} className="inline" /> {meta.elapsed_ms}ms</>
          )}
        </span>
        <span className={`ml-1 font-mono ${confColor}`}>
          置信度 {(meta.confidence * 100).toFixed(0)}%
        </span>
        <ChevronDown
          size={11}
          className={`ml-auto transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
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
            <div className="mt-2 ml-4 space-y-2 text-[11px]">
              {meta.stage && (
                <div className="flex items-center gap-2">
                  <span className="text-surface-500 w-16 flex-shrink-0">阶段</span>
                  <span className="badge-gray">{meta.stage}</span>
                </div>
              )}
              {meta.agent_name && (
                <div className="flex items-center gap-2">
                  <span className="text-surface-500 w-16 flex-shrink-0">Agent</span>
                  <span className="font-mono text-finance-700">{meta.agent_name}</span>
                </div>
              )}
              {meta.activated_rules && meta.activated_rules.length > 0 && (
                <div className="flex items-start gap-2">
                  <Tag size={11} className="text-surface-400 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="text-surface-500">激活规则：</span>
                    <span className="font-mono text-finance-700">
                      {meta.activated_rules.join(' / ')}
                    </span>
                  </div>
                </div>
              )}
              {meta.matched_objects && meta.matched_objects.length > 0 && (
                <div className="flex items-start gap-2">
                  <Zap size={11} className="text-surface-400 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="text-surface-500">激活对象：</span>
                    <span className="font-mono text-surface-700">
                      {meta.matched_objects.slice(0, 4).join(' / ')}
                      {meta.matched_objects.length > 4 && ' 等'}
                    </span>
                  </div>
                </div>
              )}
              {meta.activated_behaviors && meta.activated_behaviors.length > 0 && (
                <div className="flex items-start gap-2">
                  <Zap size={11} className="text-surface-400 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <span className="text-surface-500">激活行为：</span>
                    <span className="font-mono text-surface-700">
                      {meta.activated_behaviors.slice(0, 3).join(' / ')}
                      {meta.activated_behaviors.length > 3 && ' 等'}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
