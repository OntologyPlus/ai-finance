/**
 * ProactiveInsightBanner — 主动建议洞察横幅
 *
 * 按《经营分析方法论.md》§4.1 "经营全景诊断" 实现：
 * - 顶部最多展示 3 条 critical 洞察
 * - 30 秒轮询 /api/insights/active
 * - 优先级配色：🔴 critical / 🟡 attention / 🔵 info
 * - "查看诊断"按钮跳转 action_url
 * - "忽略"按钮调用 /api/insights/{id}/dismiss 持久化
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ExternalLink, Sparkles } from 'lucide-react';
import { insightsApi, ProactiveInsight } from '../../services/api';

const PRIORITY_STYLES: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  critical: { bg: 'bg-alert-50', border: 'border-alert-200', text: 'text-alert-700', icon: '🔴' },
  attention: { bg: 'bg-warning-50', border: 'border-warning-200', text: 'text-warning-700', icon: '🟡' },
  info: { bg: 'bg-brand-50', border: 'border-brand-200', text: 'text-brand-700', icon: '🔵' },
};

interface Props {
  pollInterval?: number;
  maxVisible?: number;
}

export default function ProactiveInsightBanner({
  pollInterval = 30000,
  maxVisible = 3,
}: Props) {
  const [insights, setInsights] = useState<ProactiveInsight[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchInsights = async () => {
      try {
        const res = await insightsApi.getActive();
        if (res.success) setInsights((res.data as ProactiveInsight[]) || []);
      } catch {
        // 静默失败：不影响主流程
      }
    };
    fetchInsights();
    const timer = setInterval(fetchInsights, pollInterval);
    return () => clearInterval(timer);
  }, [pollInterval]);

  const visible = insights
    .filter((i) => !i.is_dismissed)
    .slice(0, maxVisible);

  return (
    <AnimatePresence>
      {visible.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
          className="mb-4 space-y-2"
        >
          {visible.map((ins) => {
            const s = PRIORITY_STYLES[ins.priority] || PRIORITY_STYLES.info;
            return (
              <div
                key={ins.id}
                className={`flex items-start gap-3 px-4 py-3 rounded-xl border ${s.bg} ${s.border}`}
              >
                <span className="text-lg leading-none flex-shrink-0">{s.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${s.text}`}>{ins.title}</p>
                  {ins.detail && (
                    <p className="text-xs text-surface-600 mt-1 line-clamp-2">
                      {ins.detail}
                    </p>
                  )}
                </div>
                {ins.action_url && (
                  <button
                    onClick={() => navigate(ins.action_url as string)}
                    className="flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-md bg-white border border-surface-200 hover:bg-surface-50 flex-shrink-0"
                  >
                    {ins.action_label || '查看'}
                    <ExternalLink size={12} />
                  </button>
                )}
                <button
                  onClick={async () => {
                    try {
                      await insightsApi.dismiss(ins.id);
                    } catch {
                      // 静默：忽略失败不影响 UI
                    }
                    setInsights((prev) => prev.filter((i) => i.id !== ins.id));
                  }}
                  className="text-surface-400 hover:text-surface-600 flex-shrink-0"
                  title="忽略"
                >
                  <X size={14} />
                </button>
              </div>
            );
          })}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
