/**
 * AlertDetailDrawer — 预警详情抽屉
 * 右侧 480px 宽，顶部 AI 根因总结 + 5 层下钻时间线
 */
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Sparkles, Loader2, GitBranch } from 'lucide-react';
import { alertApi } from '../../services/api';
import DrillDownTimeline from './DrillDownTimeline';
import RuleBadge from '../common/RuleBadge';
import LineageDrawer from '../lineage/LineageDrawer';

interface Props {
  alertId: string | null;
  onClose: () => void;
}

export default function AlertDetailDrawer({ alertId, onClose }: Props) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lineageOpen, setLineageOpen] = useState(false);

  useEffect(() => {
    if (!alertId) {
      setData(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    const startTime = Date.now();
    // v11.0: 同时拉取 alert 详情（含 rule_ids）和 drill-down 分析
    Promise.all([
      alertApi.getAlert(alertId).catch(() => null),
      alertApi.drillDownAlert(alertId).catch(() => null),
    ])
      .then(([alertRes, drillRes]: any[]) => {
        const d = drillRes?.data || drillRes || {};
        if (alertRes?.data) {
          d.rule_ids = alertRes.data.rule_ids || [];
          d.alert_type = alertRes.data.alert_type;
        }
        if (d?.error && !d.rule_ids?.length) {
          setError(d.error);
        } else {
          setData(d);
        }
      })
      .catch((e: any) => {
        setError(e?.message || '加载失败');
      })
      .finally(() => {
        setLoading(false);
        const elapsed = Date.now() - startTime;
        if (elapsed > 5000) {
          console.warn(`[drill-down] ${alertId} 加载耗时 ${elapsed}ms`);
        }
      });
  }, [alertId]);

  return (
    <AnimatePresence>
      {alertId && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/30 z-40"
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'tween', duration: 0.25 }}
            className="fixed top-0 right-0 h-full w-full sm:w-[480px] bg-white shadow-2xl z-50 flex flex-col"
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-surface-200">
              <div>
                <h2 className="text-base font-semibold text-finance-800">预警根因下钻</h2>
                <p className="text-[11px] text-surface-500 mt-0.5">预警 ID: {alertId}</p>
                {data?.rule_ids && data.rule_ids.length > 0 && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] text-surface-500">依据本体规则：</span>
                    {data.rule_ids.map((rid: string) => (
                      <RuleBadge key={rid} rule_id={rid} size="xs" />
                    ))}
                  </div>
                )}
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-surface-400 hover:text-surface-600 hover:bg-surface-100"
              >
                <X size={18} />
              </button>
            </div>
            {/* v12.0: 血缘追溯按钮 */}
            <div className="px-5 pb-3">
              <button
                onClick={() => setLineageOpen(true)}
                className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg border border-finance-200 bg-finance-50 text-finance-700 text-[11px] font-medium hover:bg-finance-100 transition-colors"
              >
                <GitBranch size={12} />
                追溯血缘（SP→BP→战略举措→象限→预算）
              </button>
            </div>
            {lineageOpen && (
              <LineageDrawer
                kind="alert"
                resourceId={alertId}
                onClose={() => setLineageOpen(false)}
              />
            )}

            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {loading && (
                <div className="text-center py-12 text-surface-400 text-sm">
                  <Loader2 size={24} className="mx-auto mb-2 animate-spin text-finance-500" />
                  正在加载 5 层下钻分析…
                </div>
              )}

              {error && !loading && (
                <div className="text-xs text-alert-600 bg-alert-50 rounded-lg p-3">
                  ⚠ {error}
                </div>
              )}

              {data && !loading && (
                <>
                  {/* AI 根因总结 */}
                  {data.ai_root_cause && (
                    <div className="rounded-xl bg-gradient-to-br from-finance-50 to-brand-50 border border-finance-200/60 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Sparkles size={14} className="text-finance-600" />
                        <span className="text-xs font-semibold text-finance-700">AI 根因总结</span>
                      </div>
                      <p className="text-xs text-surface-700 leading-relaxed">
                        {data.ai_root_cause.length > 300
                          ? data.ai_root_cause.slice(0, 300) + '…'
                          : data.ai_root_cause}
                      </p>
                    </div>
                  )}

                  {/* 5 层下钻时间线 */}
                  <DrillDownTimeline data={data} />
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
