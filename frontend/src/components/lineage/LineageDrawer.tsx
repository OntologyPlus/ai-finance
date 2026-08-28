/**
 * v12.0: 血缘追溯 Drawer
 * 集成到报销/预警/预算 3 个页面
 */
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, GitBranch, Loader2, Network } from 'lucide-react';
import LineageGraph from './LineageGraph';
import { lineageApi } from '../../services/api';

export type LineageKind = 'expense' | 'alert' | 'budget';

interface LineageDrawerProps {
  kind: LineageKind | null;
  resourceId: string | null;
  onClose: () => void;
}

const KIND_LABELS: Record<LineageKind, string> = {
  expense: '报销单血缘',
  alert: '预警血缘',
  budget: '预算血缘',
};

export default function LineageDrawer({ kind, resourceId, onClose }: LineageDrawerProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!kind || !resourceId) {
      setData(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    const fn = kind === 'expense' ? lineageApi.getExpenseLineage :
               kind === 'alert' ? lineageApi.getAlertLineage :
               lineageApi.getBudgetLineage;
    fn(resourceId)
      .then((res: any) => {
        if (res.success && res.data) {
          setData(res.data);
        } else {
          setError(res.message || '加载失败');
        }
      })
      .catch((e: any) => setError(e?.message || '加载失败'))
      .finally(() => setLoading(false));
  }, [kind, resourceId]);

  if (!kind || !resourceId) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/30"
        onClick={onClose}
      />
      <motion.div
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', damping: 30, stiffness: 250 }}
        className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-3xl bg-white shadow-xl flex flex-col"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-surface-200">
          <div className="flex items-center gap-2">
            <Network size={18} className="text-finance-600" />
            <div>
              <h2 className="text-base font-semibold text-finance-800">
                {KIND_LABELS[kind]}追溯
              </h2>
              <p className="text-[11px] text-surface-500 mt-0.5 font-mono">
                {kind.toUpperCase()}: {resourceId}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-surface-400 hover:text-surface-600 hover:bg-surface-100"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {loading && (
            <div className="flex items-center justify-center py-12 text-surface-400 text-sm gap-2">
              <Loader2 size={14} className="animate-spin" /> 加载血缘数据...
            </div>
          )}

          {error && (
            <div className="p-4 rounded-lg bg-alert-50 border border-alert-200 text-alert-700 text-xs">
              加载失败：{error}
            </div>
          )}

          {!loading && !error && data && (
            <LineageGraph data={data} />
          )}

          {!loading && !error && data && data.summary && (
            <div className="mt-4 p-3 rounded-lg bg-finance-50 border border-finance-200">
              <div className="text-[11px] font-semibold text-finance-700 mb-1.5 flex items-center gap-1">
                <GitBranch size={11} /> 八阶段贯通说明
              </div>
              <p className="text-[10px] text-surface-600 leading-relaxed">
                本血缘图展示了从 <strong>SP/BP 战略规划</strong> 经 <strong>战略举措→象限→预算项目→L3 科目</strong> 直至
                <strong> 报销 / 预警 </strong>的完整链路。任何一笔支出或预警都可追到战略意图，反之亦然。
                这是"数据自产自销、口径天然一致"设计哲学的可视化体现。
              </p>
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
