/**
 * AlertClosureCard — 预警双签闭环卡
 * 业务响应 + 财经BP确认 完整流程可视化
 * 文档 §4.4.6 双签闭环确认流程
 */
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Check, Clock, AlertCircle, Loader2, Shield, User } from 'lucide-react';
import { clsx } from 'clsx';
import { alertApi } from '../../services/api';
import { useAppStore } from '../../store';
import RuleBadge from '../common/RuleBadge';

interface Props {
  alertId: string;
  alertLevel?: string;
  onUpdate?: () => void;
}

interface ClosureData {
  closure_id: string;
  alert_id: string;
  business_response?: string;
  business_responder?: string;
  business_response_at?: string;
  bp_confirmation?: string;
  bp_confirmer?: string;
  bp_confirmation_at?: string;
  closure_status: string;
  retention_period?: number;
}

const LEVEL_RESPONSE_HOURS: Record<string, number> = {
  蓝色: 72,
  黄色: 48,
  橙色: 24,
  红色: 0,
};

function timeAgo(iso?: string): string {
  if (!iso) return '-';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return '刚刚';
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}分钟前`;
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}小时前`;
  return `${Math.floor(diff / 86400_000)}天前`;
}

export default function AlertClosureCard({ alertId, alertLevel, onUpdate }: Props) {
  const [closures, setClosures] = useState<ClosureData[]>([]);
  const [loading, setLoading] = useState(true);
  const [respondText, setRespondText] = useState('');
  const [bpText, setBpText] = useState('');
  const [submitting, setSubmitting] = useState<'respond' | 'bp' | null>(null);
  const addToast = useAppStore((s) => s.addToast);

  const fetchClosures = async () => {
    setLoading(true);
    try {
      const res = await alertApi.getAlert(alertId);
      const data = res?.data;
      if (data?.closures && data.closures.length > 0) {
        setClosures(data.closures);
      } else {
        setClosures([]);
      }
    } catch {
      setClosures([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (alertId) fetchClosures();
  }, [alertId]);

  const handleBusinessRespond = async () => {
    if (respondText.trim().length < 20) {
      addToast({ type: 'error', title: '响应内容过短', message: '业务整改方案内容不得少于20字(HR-013)' });
      return;
    }
    setSubmitting('respond');
    try {
      await alertApi.respond(alertId, {
        action_description: respondText,
      });
      addToast({ type: 'success', title: '业务响应已提交', message: '等待财经BP确认' });
      setRespondText('');
      await fetchClosures();
      onUpdate?.();
    } catch (e: any) {
      addToast({ type: 'error', title: '提交失败', message: e?.message });
    } finally {
      setSubmitting(null);
    }
  };

  const handleBpConfirm = async () => {
    if (bpText.trim().length < 10) {
      addToast({ type: 'error', title: '确认意见过短', message: 'BP确认意见不得少于10字' });
      return;
    }
    setSubmitting('bp');
    try {
      await alertApi.confirmClosure(alertId, {
        confirmer_id: 'BP-财经',
        comment: bpText,
      });
      addToast({ type: 'success', title: '财经BP已确认', message: '预警双签完成，已闭环' });
      setBpText('');
      await fetchClosures();
      onUpdate?.();
    } catch (e: any) {
      addToast({ type: 'error', title: '确认失败', message: e?.message });
    } finally {
      setSubmitting(null);
    }
  };

  const latest = closures[0];
  const isBusinessDone = !!latest?.business_responder;
  const isBpDone = !!latest?.bp_confirmer;
  const isClosed = latest?.closure_status === '已闭环';
  const hours = LEVEL_RESPONSE_HOURS[alertLevel || '蓝色'] ?? 72;

  return (
    <div className="rounded-xl border border-surface-200 bg-gradient-to-br from-white to-finance-50/30 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-surface-200/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield size={14} className="text-finance-600" />
          <span className="text-xs font-semibold text-finance-700">双签闭环</span>
          <span className="text-[10px] text-surface-400">HR-013</span>
        </div>
        <div className="flex items-center gap-1.5">
          {isClosed ? (
            <span className="badge-green text-[10px]">✓ 已闭环</span>
          ) : (
            <span className="badge-amber text-[10px]">⏳ 进行中</span>
          )}
        </div>
      </div>

      {loading ? (
        <div className="p-6 text-center text-surface-400 text-xs">
          <Loader2 size={20} className="mx-auto mb-2 animate-spin text-finance-500" />
          加载闭环状态…
        </div>
      ) : (
        <div className="p-4 space-y-4">
          {/* 时间线 */}
          <div className="relative pl-7 space-y-4">
            {/* 业务响应节点 */}
            <div className="relative">
              <div
                className={clsx(
                  'absolute -left-7 top-0 w-5 h-5 rounded-full flex items-center justify-center text-white text-[10px] font-bold',
                  isBusinessDone ? 'bg-compliance-500' : 'bg-surface-300'
                )}
              >
                {isBusinessDone ? <Check size={10} /> : '1'}
              </div>
              <div className="text-[10px] text-surface-400 mb-0.5">业务响应</div>
              {isBusinessDone ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-xs text-finance-700">
                    <User size={10} />
                    <span className="font-medium">{latest?.business_responder}</span>
                    <span className="text-[10px] text-surface-400">
                      {timeAgo(latest?.business_response_at)}
                    </span>
                  </div>
                  <p className="text-[11px] text-surface-600 bg-white rounded p-2 border border-surface-100">
                    {latest?.business_response}
                  </p>
                </div>
              ) : (
                <div className="text-[11px] text-amber-600 bg-amber-50 rounded p-2 border border-amber-200/60 flex items-start gap-1.5">
                  <Clock size={12} className="mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-medium">等待业务响应</div>
                    <div className="text-[10px] text-amber-500">
                      响应时限：{hours === 0 ? '即时' : `${hours}小时`}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 财经BP确认节点 */}
            <div className="relative">
              <div
                className={clsx(
                  'absolute -left-7 top-0 w-5 h-5 rounded-full flex items-center justify-center text-white text-[10px] font-bold',
                  isBpDone ? 'bg-compliance-500' : isBusinessDone ? 'bg-amber-400' : 'bg-surface-300'
                )}
              >
                {isBpDone ? <Check size={10} /> : '2'}
              </div>
              <div className="text-[10px] text-surface-400 mb-0.5">财经BP确认</div>
              {isBpDone ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-xs text-finance-700">
                    <User size={10} />
                    <span className="font-medium">{latest?.bp_confirmer}</span>
                    <span className="text-[10px] text-surface-400">
                      {timeAgo(latest?.bp_confirmation_at)}
                    </span>
                  </div>
                  <p className="text-[11px] text-surface-600 bg-white rounded p-2 border border-surface-100">
                    {latest?.bp_confirmation}
                  </p>
                </div>
              ) : isBusinessDone ? (
                <div className="text-[11px] text-amber-600 bg-amber-50 rounded p-2 border border-amber-200/60 flex items-start gap-1.5">
                  <Clock size={12} className="mt-0.5 flex-shrink-0" />
                  <div>等待财经BP确认（双签前不可关闭）</div>
                </div>
              ) : (
                <div className="text-[11px] text-surface-400 italic">
                  需业务响应完成后才能确认
                </div>
              )}
            </div>
          </div>

          {/* 操作区 */}
          {!isClosed && (
            <div className="border-t border-surface-200/60 pt-3 space-y-3">
              {!isBusinessDone && (
                <div>
                  <label className="text-[10px] font-semibold text-finance-700 mb-1 flex items-center gap-1">
                    <span>业务整改方案</span>
                    <RuleBadge rule_id="HR-013" size="xs" />
                  </label>
                  <textarea
                    value={respondText}
                    onChange={e => setRespondText(e.target.value)}
                    placeholder="原因分析 + 已采取措施 + 预期关闭时间（≥20字）"
                    className="w-full min-h-[60px] px-2 py-1.5 rounded border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-y"
                  />
                  <button
                    onClick={handleBusinessRespond}
                    disabled={submitting === 'respond'}
                    className="mt-1.5 w-full flex items-center justify-center gap-1 py-1.5 rounded-lg bg-finance-600 text-white text-xs font-medium hover:bg-finance-700 disabled:opacity-50"
                  >
                    {submitting === 'respond' ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                    提交业务响应
                  </button>
                </div>
              )}
              {isBusinessDone && !isBpDone && (
                <div>
                  <label className="text-[10px] font-semibold text-finance-700 mb-1 flex items-center gap-1">
                    <span>财经BP确认意见</span>
                    <RuleBadge rule_id="HR-005" size="xs" />
                  </label>
                  <textarea
                    value={bpText}
                    onChange={e => setBpText(e.target.value)}
                    placeholder="确认整改方案合理性（≥10字）"
                    className="w-full min-h-[50px] px-2 py-1.5 rounded border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-y"
                  />
                  <button
                    onClick={handleBpConfirm}
                    disabled={submitting === 'bp'}
                    className="mt-1.5 w-full flex items-center justify-center gap-1 py-1.5 rounded-lg bg-compliance-600 text-white text-xs font-medium hover:bg-compliance-700 disabled:opacity-50"
                  >
                    {submitting === 'bp' ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                    BP确认 → 双签闭环
                  </button>
                </div>
              )}
            </div>
          )}

          {isClosed && (
            <div className="border-t border-surface-200/60 pt-3 text-[11px] text-compliance-700 flex items-center gap-1.5 bg-compliance-50 rounded p-2">
              <Check size={12} />
              <span>双签完成，预警已闭环（存档 ≥{latest?.retention_period ?? 3} 年）</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
