import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  CheckSquare,
  Check,
  X,
  Clock,
  ArrowRight,
  Building2,
  Landmark,
} from 'lucide-react';
import { clsx } from 'clsx';
import { approvalApi } from '../services/api';
import { useAppStore } from '../store';
import Pagination from '../components/Pagination';
import RuleBadge from '../components/common/RuleBadge';

const TABS = ['待审批', '已审批', '审批统计'] as const;

function formatAmount(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '¥ 0';
  if (n >= 10000) return `¥ ${(n / 10000).toFixed(1)}万`;
  return `¥ ${n.toLocaleString()}`;
}

export default function ApprovalPage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('待审批');
  const [pendingList, setPendingList] = useState<any[]>([]);
  const [approvalStats, setApprovalStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedRecord, setSelectedRecord] = useState<any | null>(null);
  const [chainResult, setChainResult] = useState<any[]>([]);
  const [orgSteps, setOrgSteps] = useState<string[]>(['部门经理', '财务BP', '分管领导']);
  const [legalSteps, setLegalSteps] = useState<string[]>(['财务BP', '法人代表']);

  // 驳回弹窗
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectForm, setRejectForm] = useState({ approvalId: '', comment: '' });
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize] = useState(10);
  const addToast = useAppStore((s) => s.addToast);

  const fetchData = async () => {
    try {
      const [pendingRes, statsRes] = await Promise.all([
        approvalApi.getPending({ page: currentPage, page_size: pageSize }),
        approvalApi.getStats(),
      ]);
      const pendingData = Array.isArray(pendingRes.data) ? pendingRes.data : [];
      setPendingList(pendingData);
      if (pendingRes.total !== undefined) {
        setTotalPages(Math.max(1, Math.ceil(pendingRes.total / pageSize)));
      }
      setApprovalStats(statsRes.data);
      // Extract step names from pending approvals data
      const orgStepSet = new Set<string>();
      const legalStepSet = new Set<string>();
      (pendingRes.data || []).forEach((item: any) => {
        if (item.approval_line === 'org' && item.current_step) orgStepSet.add(item.current_step);
        if (item.approval_line === 'legal' && item.current_step) legalStepSet.add(item.current_step);
      });
      if (orgStepSet.size > 0) setOrgSteps(Array.from(orgStepSet));
      if (legalStepSet.size > 0) setLegalSteps(Array.from(legalStepSet));
    } catch (error: any) {
      addToast({ type: 'error', title: '获取审批数据失败', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [currentPage]);

  const handleApprove = async (approvalId: string) => {
    try {
      await approvalApi.approve(approvalId);
      addToast({ type: 'success', title: '操作成功', message: '审批已通过' });
      fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: '审批失败', message: error.message });
    }
  };

  const handleReject = async (approvalId: string) => {
    try {
      await approvalApi.reject(approvalId, { comment: '驳回' });
      addToast({ type: 'success', title: '操作成功', message: '审批已驳回' });
      fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: '驳回失败', message: error.message });
    }
  };

  const handleViewChain = async (expenseId: string) => {
    try {
      const response = await approvalApi.getChain(expenseId);
      setChainResult(response.data);
    } catch (error: any) {
      addToast({ type: 'error', title: '获取审批链失败', message: error.message });
    }
  };

  const pendingOrg = pendingList.filter(i => i.approval_line === 'org').length;
  const pendingLegal = pendingList.filter(i => i.approval_line === 'legal').length;
  const approvedList = approvalStats?.approved_list || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">审批工作台</h1>
        <p className="text-sm text-surface-400 mt-1">双线审批流程：组织管理线 + 法人架构线</p>
      </div>

      <div className="glass-card p-5">
        <div className="flex items-center gap-6">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-3">
              <Building2 size={16} className="text-brand-500" />
              <span className="text-sm font-semibold text-surface-700">组织管理线</span>
              <span className="badge-blue">{pendingOrg} 待审</span>
            </div>
            <div className="flex items-center gap-2">
              {orgSteps.map((step, i) => (
                <div key={step} className="flex items-center gap-2">
                  <div className={clsx(
                    'px-3 py-1.5 rounded-lg text-xs font-medium',
                    i === 0 ? 'bg-brand-100 text-brand-700' : 'bg-surface-100 text-surface-500'
                  )}>
                    {step}
                  </div>
                  {i < orgSteps.length - 1 && <ArrowRight size={12} className="text-surface-300" />}
                </div>
              ))}
            </div>
          </div>
          <div className="w-px h-16 bg-surface-200" />
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-3">
              <Landmark size={16} className="text-finance-600" />
              <span className="text-sm font-semibold text-surface-700">法人架构线</span>
              <span className="badge-amber">{pendingLegal} 待审</span>
            </div>
            <div className="flex items-center gap-2">
              {legalSteps.map((step, i) => (
                <div key={step} className="flex items-center gap-2">
                  <div className={clsx(
                    'px-3 py-1.5 rounded-lg text-xs font-medium',
                    i === 0 ? 'bg-finance-100 text-finance-700' : 'bg-surface-100 text-surface-500'
                  )}>
                    {step}
                  </div>
                  {i < legalSteps.length - 1 && <ArrowRight size={12} className="text-surface-300" />}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="glass-card">
        <div className="flex border-b border-surface-200/60">
          {TABS.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={clsx(
                'px-5 py-3 text-sm font-medium transition-colors relative',
                activeTab === tab ? 'text-finance-700' : 'text-surface-400 hover:text-surface-600'
              )}
            >
              {tab}
              {activeTab === tab && (
                <motion.div
                  layoutId="approvalTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === '待审批' && (
              <motion.div
                key="pending"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                {loading ? (
                  <div className="text-center py-10 text-surface-300">
                    <p className="text-sm">加载中...</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {pendingList.map(item => (
                      <div
                        key={item.expense_id || item.approval_id}
                        className={clsx(
                          'flex items-center justify-between p-4 rounded-xl border transition-colors',
                          item.is_overdue ? 'border-alert-200 bg-alert-50/30' : 'border-surface-200/60 hover:bg-finance-50/30',
                          selectedRecord?.expense_id === item.expense_id && 'bg-finance-50/50'
                        )}
                        onClick={() => { setSelectedRecord(item); handleViewChain(item.expense_id); }}
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-1">
                            <span className="font-mono text-xs text-finance-700">{item.expense_id}</span>
                            <span className="font-medium text-surface-800">{item.applicant_name}</span>
                            <span className={item.approval_line === 'org' ? 'badge-blue' : 'badge-amber'}>
                              {item.approval_line === 'org' ? '组织线' : '法人线'}
                            </span>
                            {item.is_overdue && <span className="badge-red">逾期</span>}
                            {item.rule_ids && item.rule_ids.length > 0 && (
                              <div className="flex flex-wrap items-center gap-1">
                                {item.rule_ids.slice(0, 2).map((rid: string) => (
                                  <RuleBadge key={rid} rule_id={rid} size="xs" />
                                ))}
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-sm text-surface-500">
                            <span>{item.description}</span>
                            <span className="font-mono text-surface-700">{formatAmount(item.amount)}</span>
                            <span className="flex items-center gap-1">
                              <Clock size={12} /> 当前: {item.current_step}
                            </span>
                            <span>截止: {item.deadline}</span>
                          </div>
                        </div>
                        <div className="flex gap-2 ml-4" onClick={e => e.stopPropagation()}>
                          <button
                            onClick={() => handleApprove(item.approval_id || item.expense_id)}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-compliance-50 text-compliance-700 border border-compliance-200 hover:bg-compliance-100 transition-colors"
                          >
                            <Check size={12} /> 通过
                          </button>
                          <button
                            onClick={() => {
                              setRejectForm({ approvalId: item.approval_id || item.expense_id, comment: '' });
                              setShowRejectModal(true);
                            }}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-alert-50 text-alert-700 border border-alert-200 hover:bg-alert-100 transition-colors"
                          >
                            <X size={12} /> 驳回
                          </button>
                        </div>
                      </div>
                    ))}
                    {pendingList.length === 0 && (
                      <div className="text-center py-10 text-surface-300">
                        <CheckSquare size={40} className="mx-auto mb-3 opacity-30" />
                        <p className="text-sm">暂无待审批项目</p>
                      </div>
                    )}
                    {selectedRecord && chainResult.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="p-4 rounded-xl border border-finance-100 bg-finance-50/30"
                      >
                        <p className="text-sm font-medium text-finance-700 mb-2">
                          {selectedRecord.expense_id} 审批链
                        </p>
                        <div className="flex items-center gap-2 flex-wrap">
                          {chainResult.map((node, i) => (
                            <div key={i} className="flex items-center gap-2">
                              <div className="flex flex-col items-center gap-1">
                                <div className={clsx(
                                  'px-3 py-1.5 rounded-lg text-xs font-medium',
                                  node.status === 'approved' ? 'bg-compliance-100 text-compliance-700' :
                                  node.status === 'pending' ? 'bg-amber-100 text-amber-700' :
                                  'bg-surface-100 text-surface-500'
                                )}>
                                  {node.approver_name || node.approver_id} ({node.status === 'approved' ? '已通过' : node.status === 'pending' ? '待审批' : node.status})
                                </div>
                                {node.rule_ids && node.rule_ids.length > 0 && (
                                  <div className="flex flex-wrap items-center gap-1">
                                    {node.rule_ids.slice(0, 2).map((rid: string) => (
                                      <RuleBadge key={rid} rule_id={rid} size="xs" />
                                    ))}
                                  </div>
                                )}
                              </div>
                              {i < chainResult.length - 1 && <ArrowRight size={12} className="text-surface-300" />}
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </div>
                )}
                <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={setCurrentPage} pageSize={pageSize} />
              </motion.div>
            )}

            {activeTab === '已审批' && (
              <motion.div
                key="approved"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-surface-200/60">
                        <th className="text-left py-3 px-3 metric-label">报销单号</th>
                        <th className="text-left py-3 px-3 metric-label">申请人</th>
                        <th className="text-right py-3 px-3 metric-label">金额</th>
                        <th className="text-left py-3 px-3 metric-label">描述</th>
                        <th className="text-center py-3 px-3 metric-label">审批线</th>
                        <th className="text-center py-3 px-3 metric-label">结果</th>
                        <th className="text-left py-3 px-3 metric-label">时间</th>
                      </tr>
                    </thead>
                    <tbody>
                      {approvedList.map((item: any) => (
                        <tr key={item.expense_id} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                          <td className="py-3 px-3 font-mono text-xs text-finance-700">{item.expense_id}</td>
                          <td className="py-3 px-3 font-medium text-surface-800">{item.applicant_name}</td>
                          <td className="py-3 px-3 text-right font-mono">{formatAmount(item.amount)}</td>
                          <td className="py-3 px-3 text-surface-600">{item.description}</td>
                          <td className="py-3 px-3 text-center">
                            <span className={item.action_line === 'org' ? 'badge-blue' : 'badge-amber'}>
                              {item.action_line === 'org' ? '组织线' : '法人线'}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-center">
                            <span className={item.action === 'approve' ? 'badge-green' : 'badge-red'}>
                              {item.action === 'approve' ? '通过' : '驳回'}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-surface-500 text-xs">{item.action_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {activeTab === '审批统计' && (
              <motion.div
                key="stats"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    { label: '本月审批总量', value: approvalStats?.total_count ?? '-', color: 'from-finance-500 to-finance-700' },
                    { label: '通过率', value: approvalStats?.approval_rate ?? '-', color: 'from-compliance-500 to-health-600' },
                    { label: '平均审批时长', value: approvalStats?.avg_duration ?? '-', color: 'from-brand-500 to-finance-600' },
                    { label: '逾期率', value: approvalStats?.overdue_rate ?? '-', color: 'from-warning-500 to-alert-500' },
                  ].map(card => (
                    <div key={card.label} className="glass-card-static p-4">
                      <p className="metric-label mb-1">{card.label}</p>
                      <p className="metric-value text-xl">
                        <span className={`bg-gradient-to-r ${card.color} bg-clip-text text-transparent`}>
                          {card.value}
                        </span>
                      </p>
                    </div>
                  ))}
                </div>
                <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="glass-card-static p-5">
                    <h3 className="text-sm font-semibold text-surface-700 mb-4">审批趋势</h3>
                    <ReactECharts
                      option={{
                        tooltip: { trigger: 'axis' as const },
                        grid: { left: 40, right: 20, bottom: 30, top: 20 },
                        xAxis: {
                          type: 'category' as const,
                          data: approvalStats?.trend?.map((t: any) => t.period) || ['1月', '2月', '3月', '4月', '5月', '6月'],
                          axisLabel: { color: '#94a3b8', fontSize: 10 },
                          axisLine: { lineStyle: { color: '#e2e8f0' } },
                        },
                        yAxis: {
                          type: 'value' as const,
                          axisLabel: { color: '#94a3b8', fontSize: 10 },
                          splitLine: { lineStyle: { color: '#f1f5f9' } },
                        },
                        series: [{
                          name: '审批量',
                          type: 'line' as const,
                          data: approvalStats?.trend?.map((t: any) => t.count) || [12, 18, 15, 22, 20, 25],
                          smooth: true,
                          symbol: 'circle',
                          symbolSize: 6,
                          lineStyle: { width: 2, color: '#3b82f6' },
                          itemStyle: { color: '#3b82f6' },
                          areaStyle: {
                            color: {
                              type: 'linear' as const, x: 0, y: 0, x2: 0, y2: 1,
                              colorStops: [
                                { offset: 0, color: '#3b82f620' },
                                { offset: 1, color: '#3b82f605' },
                              ],
                            },
                          },
                        }],
                      }}
                      style={{ height: '220px' }}
                      notMerge={true}
                      lazyUpdate={true}
                      showLoading={!approvalStats}
                    />
                  </div>
                  <div className="glass-card-static p-5">
                    <h3 className="text-sm font-semibold text-surface-700 mb-4">按角色统计</h3>
                    <ReactECharts
                      option={{
                        tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
                        grid: { left: 60, right: 20, bottom: 30, top: 20 },
                        xAxis: {
                          type: 'category' as const,
                          data: (Array.isArray(approvalStats?.by_role) ? approvalStats.by_role : Object.entries(approvalStats?.by_role || {}).map(([role, count]) => ({ role, count }))).map((r: any) => r.role),
                          axisLabel: { color: '#94a3b8', fontSize: 10 },
                          axisLine: { lineStyle: { color: '#e2e8f0' } },
                        },
                        yAxis: {
                          type: 'value' as const,
                          axisLabel: { color: '#94a3b8', fontSize: 10 },
                          splitLine: { lineStyle: { color: '#f1f5f9' } },
                        },
                        series: [{
                          name: '审批量',
                          type: 'bar' as const,
                          data: (Array.isArray(approvalStats?.by_role) ? approvalStats.by_role : Object.entries(approvalStats?.by_role || {}).map(([role, count]) => ({ role, count }))).map((r: any) => r.count),
                          itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] },
                          barWidth: 24,
                        }],
                      }}
                      style={{ height: '220px' }}
                      notMerge={true}
                      lazyUpdate={true}
                      showLoading={!approvalStats}
                    />
                  </div>
                  <div className="glass-card-static p-5">
                    <h3 className="text-sm font-semibold text-surface-700 mb-4">超时率</h3>
                    <ReactECharts
                      option={{
                        tooltip: { trigger: 'item' as const },
                        legend: {
                          orient: 'vertical' as const,
                          right: 10,
                          top: 'center',
                          textStyle: { color: '#94a3b8', fontSize: 11 },
                        },
                        series: [{
                          type: 'pie' as const,
                          radius: ['45%', '70%'],
                          center: ['35%', '50%'],
                          avoidLabelOverlap: false,
                          label: { show: false },
                          emphasis: { label: { show: true, fontWeight: 'bold' } },
                          data: [
                            {
                              value: approvalStats?.overdue_count ?? 5,
                              name: '超时',
                              itemStyle: { color: '#ef4444' },
                            },
                            {
                              value: (approvalStats?.total_count ?? 88) - (approvalStats?.overdue_count ?? 5),
                              name: '准时',
                              itemStyle: { color: '#10b981' },
                            },
                          ],
                        }],
                      }}
                      style={{ height: '220px' }}
                      notMerge={true}
                      lazyUpdate={true}
                      showLoading={!approvalStats}
                    />
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* 驳回原因弹窗 */}
      <AnimatePresence>
        {showRejectModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => setShowRejectModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-md mx-4"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-finance-800">驳回审批</h3>
                <button onClick={() => setShowRejectModal(false)} className="text-surface-400 hover:text-surface-600"><X size={18} /></button>
              </div>
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1">驳回原因 <span className="text-alert-500">*</span></label>
                <textarea
                  value={rejectForm.comment}
                  onChange={e => setRejectForm(f => ({ ...f, comment: e.target.value }))}
                  rows={3}
                  placeholder="请输入驳回原因（至少5个字符）..."
                  className={`w-full px-3 py-2 rounded-xl border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-none ${
                    rejectForm.comment.length > 0 && rejectForm.comment.length < 5 ? 'border-alert-300' : 'border-surface-200'
                  }`}
                />
                {rejectForm.comment.length > 0 && rejectForm.comment.length < 5 && (
                  <p className="text-xs text-alert-600 mt-1">驳回原因至少需要5个字符</p>
                )}
              </div>
              <div className="flex gap-3 justify-end mt-5">
                <button onClick={() => setShowRejectModal(false)} className="btn-secondary">取消</button>
                <button
                  onClick={async () => {
                    await handleReject(rejectForm.approvalId, { comment: rejectForm.comment });
                    setShowRejectModal(false);
                  }}
                  disabled={rejectForm.comment.length < 5}
                  className={`btn-primary ${rejectForm.comment.length < 5 ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <X size={14} /> 确认驳回
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
