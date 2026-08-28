import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileSignature,
  Plus,
  X,
  AlertTriangle,
  CreditCard,
} from 'lucide-react';
import { clsx } from 'clsx';
import { contractApi } from '../services/api';

const TABS = ['合同列表', '付款记录'] as const;

const CONTRACT_STATUS_MAP: Record<string, { label: string; cls: string }> = {
  '执行中': { label: '生效中', cls: 'badge-green' },
  '已完成': { label: '已到期', cls: 'badge-blue' },
  '已终止': { label: '已终止', cls: 'badge-red' },
};

function formatAmount(n: number | undefined | null): string {
  if (n == null || isNaN(n)) return '¥ 0';
  if (n >= 10000) return `¥ ${(n / 10000).toFixed(1)}万`;
  return `¥ ${n.toLocaleString()}`;
}

function isExpiringSoon(endDate: string): boolean {
  if (!endDate) return false;
  const end = new Date(endDate);
  const now = new Date();
  const diff = end.getTime() - now.getTime();
  const days = diff / (1000 * 60 * 60 * 24);
  return days > 0 && days <= 30;
}

function isExpired(endDate: string): boolean {
  if (!endDate) return false;
  return new Date(endDate) < new Date();
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-';
  return dateStr.split('T')[0];
}

interface ContractForm {
  contract_code: string;
  contract_name: string;
  contract_type: string;
  vendor_name: string;
  amount: number;
  start_date: string;
  end_date: string;
  department_id: string;
  responsible_person: string;
  description: string;
}

const emptyContractForm: ContractForm = {
  contract_code: '',
  contract_name: '',
  contract_type: '',
  vendor_name: '',
  amount: 0,
  start_date: '',
  end_date: '',
  department_id: '',
  responsible_person: '',
  description: '',
};

export default function ContractPage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('合同列表');
  const [contracts, setContracts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [form, setForm] = useState<ContractForm>(emptyContractForm);

  // Payment tab state
  const [selectedContract, setSelectedContract] = useState<any | null>(null);
  const [paymentRecords, setPaymentRecords] = useState<any[]>([]);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentForm, setPaymentForm] = useState({ amount: 0, payment_date: '', description: '' });

  const fetchContracts = async () => {
    try {
      const res = await contractApi.getContracts();
      setContracts(res.data || []);
    } catch (error) {
      console.error('Failed to fetch contracts:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContracts();
  }, []);

  const handleCreateContract = async () => {
    try {
      await contractApi.createContract(form);
      setShowCreateModal(false);
      setForm(emptyContractForm);
      fetchContracts();
    } catch (error) {
      console.error('Failed to create contract:', error);
    }
  };

  const handleSelectContract = async (contract: any) => {
    setSelectedContract(contract);
    setActiveTab('付款记录');
    // Load payment terms from contract data
    if (contract.payment_terms) {
      setPaymentRecords(contract.payment_terms);
    } else {
      try {
        const res = await contractApi.getPayments(contract.id);
        setPaymentRecords(res.data || []);
      } catch {
        setPaymentRecords([]);
      }
    }
  };

  const handleAddPayment = async () => {
    if (!selectedContract) return;
    try {
      await contractApi.addPayment(selectedContract.id, paymentForm);
      setShowPaymentModal(false);
      setPaymentForm({ amount: 0, payment_date: '', description: '' });
      fetchContracts();
      // Refresh selected contract
      const updated = contracts.find((c: any) => c.id === selectedContract.id);
      if (updated) {
        setSelectedContract(updated);
        setPaymentRecords(updated.payment_terms || []);
      }
    } catch (error) {
      console.error('Failed to add payment:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-surface-400">加载中...</div>
      </div>
    );
  }

  const totalAmount = contracts.reduce((s: number, c: any) => s + (c.amount || 0), 0);
  const totalPaid = contracts.reduce((s: number, c: any) => s + (c.paid_amount || 0), 0);
  const activeContracts = contracts.filter((c: any) => c.status === '执行中').length;
  const expiringContracts = contracts.filter((c: any) => isExpiringSoon(c.end_date)).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">合同管理</h1>
        <p className="text-sm text-surface-400 mt-1">合同台账、付款记录与到期预警</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: '合同总额', value: formatAmount(totalAmount), gradient: 'from-finance-500 to-finance-700' },
          { label: '已付金额', value: formatAmount(totalPaid), gradient: 'from-compliance-500 to-health-600' },
          { label: '执行中', value: activeContracts, gradient: 'from-brand-500 to-finance-600' },
          { label: '即将到期', value: expiringContracts, gradient: 'from-warning-500 to-alert-500' },
        ].map(card => (
          <div key={card.label} className="glass-card p-5">
            <p className="metric-label mb-2">{card.label}</p>
            <p className="metric-value">
              <span className={`bg-gradient-to-r ${card.gradient} bg-clip-text text-transparent`}>
                {card.value}
              </span>
            </p>
          </div>
        ))}
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
                  layoutId="contractTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === '合同列表' && (
              <motion.div
                key="list"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="flex justify-end mb-4">
                  <button
                    onClick={() => { setForm(emptyContractForm); setShowCreateModal(true); }}
                    className="btn-primary"
                  >
                    <Plus size={14} /> 新建合同
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-surface-200/60">
                        <th className="text-left py-3 px-3 metric-label">合同编号</th>
                        <th className="text-left py-3 px-3 metric-label">名称</th>
                        <th className="text-left py-3 px-3 metric-label">供应商</th>
                        <th className="text-right py-3 px-3 metric-label">金额</th>
                        <th className="text-left py-3 px-3 metric-label">开始日期</th>
                        <th className="text-left py-3 px-3 metric-label">结束日期</th>
                        <th className="text-center py-3 px-3 metric-label">状态</th>
                        <th className="text-center py-3 px-3 metric-label">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {contracts.map((contract: any) => {
                        const expiring = isExpiringSoon(contract.end_date);
                        const expired = isExpired(contract.end_date) && contract.status !== '已完成';
                        const status = expired ? '已到期' : contract.status;
                        const statusInfo = CONTRACT_STATUS_MAP[status] || { label: status, cls: 'badge-blue' };

                        return (
                          <tr
                            key={contract.id}
                            className={clsx(
                              'border-b border-surface-100 hover:bg-finance-50/30 transition-colors cursor-pointer',
                              expiring && 'bg-warning-50/30',
                              selectedContract?.id === contract.id && 'bg-finance-50/50'
                            )}
                            onClick={() => handleSelectContract(contract)}
                          >
                            <td className="py-3 px-3 font-mono text-xs text-finance-700">{contract.contract_code || contract.id}</td>
                            <td className="py-3 px-3 font-medium text-surface-800">
                              <div className="flex items-center gap-1.5">
                                {contract.contract_name}
                                {expiring && (
                                  <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-warning-100 text-warning-700 border border-warning-200">
                                    <AlertTriangle size={10} /> 即将到期
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-3 text-surface-600">{contract.vendor_name}</td>
                            <td className="py-3 px-3 text-right font-mono">{formatAmount(contract.amount)}</td>
                            <td className="py-3 px-3 text-surface-500 text-xs">{formatDate(contract.start_date)}</td>
                            <td className="py-3 px-3 text-surface-500 text-xs">{formatDate(contract.end_date)}</td>
                            <td className="py-3 px-3 text-center">
                              <span className={statusInfo.cls}>{statusInfo.label}</span>
                            </td>
                            <td className="py-3 px-3 text-center" onClick={e => e.stopPropagation()}>
                              <button
                                onClick={() => handleSelectContract(contract)}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium bg-brand-50 text-brand-700 border border-brand-200 hover:bg-brand-100 transition-colors"
                              >
                                <CreditCard size={10} /> 付款
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                      {contracts.length === 0 && (
                        <tr>
                          <td colSpan={8} className="py-10 text-center text-surface-400">
                            暂无合同数据
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {activeTab === '付款记录' && (
              <motion.div
                key="payments"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                {selectedContract ? (
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-base font-semibold text-finance-800">{selectedContract.contract_name}</h3>
                        <p className="text-xs text-surface-400 mt-0.5">
                          {selectedContract.contract_code} | {selectedContract.vendor_name}
                        </p>
                      </div>
                      <button
                        onClick={() => setShowPaymentModal(true)}
                        className="btn-primary"
                      >
                        <Plus size={14} /> 登记付款
                      </button>
                    </div>

                    <div className="grid grid-cols-3 gap-3 mb-4">
                      <div className="glass-card-static p-3">
                        <p className="metric-label">合同金额</p>
                        <p className="text-lg font-bold text-surface-800 font-display">{formatAmount(selectedContract.amount)}</p>
                      </div>
                      <div className="glass-card-static p-3">
                        <p className="metric-label">已付金额</p>
                        <p className="text-lg font-bold text-compliance-600 font-display">{formatAmount(selectedContract.paid_amount || 0)}</p>
                      </div>
                      <div className="glass-card-static p-3">
                        <p className="metric-label">付款进度</p>
                        <p className="text-lg font-bold text-finance-700 font-display">
                          {selectedContract.amount > 0
                            ? `${Math.round(((selectedContract.paid_amount || 0) / selectedContract.amount) * 100)}%`
                            : '0%'}
                        </p>
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-surface-200/60">
                            <th className="text-left py-3 px-3 metric-label">里程碑</th>
                            <th className="text-right py-3 px-3 metric-label">金额</th>
                            <th className="text-center py-3 px-3 metric-label">比例</th>
                            <th className="text-center py-3 px-3 metric-label">状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {paymentRecords.map((payment: any, idx: number) => (
                            <tr key={idx} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                              <td className="py-3 px-3 font-medium text-surface-800">{payment.milestone || `付款${idx + 1}`}</td>
                              <td className="py-3 px-3 text-right font-mono">{formatAmount(payment.amount)}</td>
                              <td className="py-3 px-3 text-center text-surface-500">{payment.percentage}%</td>
                              <td className="py-3 px-3 text-center">
                                <span className={payment.status === '已支付' ? 'badge-green' : 'badge-amber'}>
                                  {payment.status || '未支付'}
                                </span>
                              </td>
                            </tr>
                          ))}
                          {paymentRecords.length === 0 && (
                            <tr>
                              <td colSpan={4} className="py-10 text-center text-surface-400">
                                暂无付款记录
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-10 text-surface-400">
                    <FileSignature size={40} className="mx-auto mb-3 opacity-30" />
                    <p className="text-sm">请从合同列表中选择一个合同查看付款记录</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Create Contract Modal */}
      <AnimatePresence>
        {showCreateModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => setShowCreateModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-finance-800">新建合同</h3>
                <button onClick={() => setShowCreateModal(false)} className="text-surface-400 hover:text-surface-600">
                  <X size={18} />
                </button>
              </div>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 mb-1">合同编号 <span className="text-alert-500">*</span></label>
                    <input
                      type="text"
                      value={form.contract_code}
                      onChange={e => setForm(f => ({ ...f, contract_code: e.target.value }))}
                      placeholder="HT-2026-XXX"
                      className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-surface-700 mb-1">合同类型</label>
                    <select
                      value={form.contract_type}
                      onChange={e => setForm(f => ({ ...f, contract_type: e.target.value }))}
                      className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    >
                      <option value="">请选择</option>
                      <option value="服务合同">服务合同</option>
                      <option value="采购合同">采购合同</option>
                      <option value="咨询合同">咨询合同</option>
                      <option value="租赁合同">租赁合同</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">合同名称 <span className="text-alert-500">*</span></label>
                  <input
                    type="text"
                    value={form.contract_name}
                    onChange={e => setForm(f => ({ ...f, contract_name: e.target.value }))}
                    placeholder="请输入合同名称"
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">供应商 <span className="text-alert-500">*</span></label>
                  <input
                    type="text"
                    value={form.vendor_name}
                    onChange={e => setForm(f => ({ ...f, vendor_name: e.target.value }))}
                    placeholder="请输入供应商名称"
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">合同金额</label>
                  <input
                    type="number"
                    value={form.amount || ''}
                    onChange={e => setForm(f => ({ ...f, amount: Number(e.target.value) }))}
                    placeholder="请输入合同金额"
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-surface-700 mb-1">开始日期</label>
                    <input
                      type="date"
                      value={form.start_date}
                      onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))}
                      className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-surface-700 mb-1">结束日期</label>
                    <input
                      type="date"
                      value={form.end_date}
                      onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))}
                      className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">描述</label>
                  <textarea
                    value={form.description}
                    onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                    rows={2}
                    placeholder="请输入合同描述..."
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-none"
                  />
                </div>
              </div>
              <div className="flex gap-3 justify-end mt-5">
                <button onClick={() => setShowCreateModal(false)} className="btn-secondary">取消</button>
                <button
                  onClick={handleCreateContract}
                  disabled={!form.contract_code.trim() || !form.contract_name.trim() || !form.vendor_name.trim()}
                  className={clsx('btn-primary', (!form.contract_code.trim() || !form.contract_name.trim() || !form.vendor_name.trim()) && 'opacity-50 cursor-not-allowed')}
                >
                  创建合同
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Add Payment Modal */}
      <AnimatePresence>
        {showPaymentModal && selectedContract && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => setShowPaymentModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="glass-card p-6 w-full max-w-md mx-4"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-finance-800">登记付款</h3>
                <button onClick={() => setShowPaymentModal(false)} className="text-surface-400 hover:text-surface-600">
                  <X size={18} />
                </button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">付款金额 <span className="text-alert-500">*</span></label>
                  <input
                    type="number"
                    value={paymentForm.amount || ''}
                    onChange={e => setPaymentForm(f => ({ ...f, amount: Number(e.target.value) }))}
                    placeholder="请输入付款金额"
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">付款日期</label>
                  <input
                    type="date"
                    value={paymentForm.payment_date}
                    onChange={e => setPaymentForm(f => ({ ...f, payment_date: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-surface-700 mb-1">备注</label>
                  <textarea
                    value={paymentForm.description}
                    onChange={e => setPaymentForm(f => ({ ...f, description: e.target.value }))}
                    rows={2}
                    placeholder="请输入备注..."
                    className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-none"
                  />
                </div>
              </div>
              <div className="flex gap-3 justify-end mt-5">
                <button onClick={() => setShowPaymentModal(false)} className="btn-secondary">取消</button>
                <button
                  onClick={handleAddPayment}
                  disabled={paymentForm.amount <= 0}
                  className={clsx('btn-primary', paymentForm.amount <= 0 && 'opacity-50 cursor-not-allowed')}
                >
                  确认付款
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
