import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  ShieldCheck,
  UserCheck,
  MessageSquare,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Search,
  Activity,
  Building2,
  ShieldAlert,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAppStore } from '../store';
import IndustryBenchmark, { RiskAlertPanel } from '../components/hcp/HcpBenchmarkAndRisk';

const TABS = ['HCP验证', '互动合规', '付款限额', '现场证据', '行业对标', '风险预警'] as const;

// Inline API helpers
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function getToken(): string | null {
  return localStorage.getItem('auth_token');
}

async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const token = getToken();
  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
    ...options,
  };
  const response = await fetch(url, config);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }
  return response.json();
}

// v9.0 C: MOCK 数据已废弃，全部接后端 API 真实数据

export default function HcpCompliancePage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('HCP验证');
  const addToast = useAppStore((s) => s.addToast);

  // Tab 1 - HCP验证
  const [hcpId, setHcpId] = useState('');
  const [verifyResult, setVerifyResult] = useState<any>(null);
  const [verifyLoading, setVerifyLoading] = useState(false);

  // Tab 2 - 互动合规
  const [interactionId, setInteractionId] = useState('');
  const [complianceResult, setComplianceResult] = useState<any>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);

  // Tab 3 - 付款限额
  const [paymentHcpId, setPaymentHcpId] = useState('');
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentLimitResult, setPaymentLimitResult] = useState<any>(null);
  const [paymentLoading, setPaymentLoading] = useState(false);

  // Tab 4 - 风险分析
  const [riskHcpId, setRiskHcpId] = useState('');
  const [riskPeriod, setRiskPeriod] = useState('');
  const [riskResult, setRiskResult] = useState<any>(null);
  const [riskLoading, setRiskLoading] = useState(false);
  const [evidenceHcpId, setEvidenceHcpId] = useState('HCP-001');
  const [evidenceResult, setEvidenceResult] = useState<any>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  const handleVerify = async () => {
    if (!hcpId.trim()) {
      addToast({ type: 'error', title: '参数缺失', message: '请输入HCP ID' });
      return;
    }
    setVerifyLoading(true);
    try {
      const res = await apiRequest<any>(`/api/hcp/verify?hcp_id=${encodeURIComponent(hcpId)}`);
      setVerifyResult(res.data || res);
    } catch {
      // v9.0 C: 不再回退到 MOCK
      setVerifyResult(null);
      addToast({ type: 'warning', title: 'HCP 验证服务暂不可用', message: '请检查后端连接' });
    } finally {
      setVerifyLoading(false);
    }
  };

  const handleComplianceCheck = async () => {
    if (!interactionId.trim()) {
      addToast({ type: 'error', title: '参数缺失', message: '请输入互动ID' });
      return;
    }
    setComplianceLoading(true);
    try {
      const res = await apiRequest<any>(`/api/hcp/compliance-check?interaction_id=${encodeURIComponent(interactionId)}`);
      setComplianceResult(res.data || res);
    } catch {
      // v9.0 C: 不再回退到 MOCK
      setComplianceResult(null);
      addToast({ type: 'warning', title: '互动合规服务暂不可用', message: '请检查后端连接' });
    } finally {
      setComplianceLoading(false);
    }
  };

  const handlePaymentLimitCheck = async () => {
    if (!paymentHcpId.trim() || !paymentAmount.trim()) {
      addToast({ type: 'error', title: '参数缺失', message: '请输入HCP ID和付款金额' });
      return;
    }
    setPaymentLoading(true);
    try {
      const res = await apiRequest<any>('/api/hcp/payment-limit-check', {
        method: 'POST',
        body: JSON.stringify({ hcp_id: paymentHcpId, payment_amount: Number(paymentAmount) }),
      });
      setPaymentLimitResult(res.data || res);
    } catch {
      // v9.0 C: 不再回退到 MOCK
      setPaymentLimitResult(null);
      addToast({ type: 'warning', title: '付款限额服务暂不可用', message: '请检查后端连接' });
    } finally {
      setPaymentLoading(false);
    }
  };

  const handleRiskAnalysis = async () => {
    if (!riskHcpId.trim()) {
      addToast({ type: 'error', title: '参数缺失', message: '请输入HCP ID' });
      return;
    }
    setRiskLoading(true);
    try {
      const res = await apiRequest<any>('/api/hcp/risk-analysis', {
        method: 'POST',
        body: JSON.stringify({ hcp_id: riskHcpId, period: riskPeriod || undefined }),
      });
      setRiskResult(res.data || res);
    } catch {
      // v9.0 C: 不再回退到 MOCK
      setRiskResult(null);
      addToast({ type: 'warning', title: '风险分析服务暂不可用', message: '请检查后端连接' });
    } finally {
      setRiskLoading(false);
    }
  };

  const getRiskLevelBadge = (level: string) => {
    const map: Record<string, string> = {
      low: 'badge-green',
      medium: 'badge-amber',
      high: 'badge-red',
    };
    const labelMap: Record<string, string> = { low: '低', medium: '中', high: '高' };
    return <span className={map[level] || 'badge-blue'}>{labelMap[level] || level}</span>;
  };

  const getRiskGaugeOption = (score: number) => ({
    series: [{
      type: 'gauge' as const,
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: 100,
      splitNumber: 5,
      itemStyle: { color: score >= 70 ? '#f87171' : score >= 40 ? '#f59e0b' : '#22c55e' },
      progress: { show: true, width: 18 },
      pointer: { show: false },
      axisLine: { lineStyle: { width: 18, color: [[1, '#e2e8f0']] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: {
        valueAnimation: true,
        formatter: `{value}`,
        fontSize: 28,
        fontWeight: 'bold' as const,
        color: score >= 70 ? '#f87171' : score >= 40 ? '#f59e0b' : '#22c55e',
        offsetCenter: [0, '10%'],
      },
      data: [{ value: score, name: '风险评分' }],
      title: {
        offsetCenter: [0, '35%'],
        fontSize: 12,
        color: '#94a3b8',
      },
    }],
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">HCP合规管理</h1>
        <p className="text-sm text-surface-400 mt-1">医疗卫生专业人士互动合规审查</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'HCP验证', value: '实时', gradient: 'from-brand-500 to-finance-600', icon: <UserCheck size={16} /> },
          { label: '互动合规', value: 'HR-028/029', gradient: 'from-compliance-500 to-health-600', icon: <MessageSquare size={16} /> },
          { label: '付款限额', value: '¥50,000', gradient: 'from-finance-500 to-finance-700', icon: <DollarSign size={16} /> },
          { label: '风险分析', value: '动态评估', gradient: 'from-warning-500 to-alert-500', icon: <Activity size={16} /> },
        ].map(card => (
          <div key={card.label} className="glass-card p-5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-surface-400">{card.icon}</span>
              <p className="metric-label">{card.label}</p>
            </div>
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
                  layoutId="hcpTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {activeTab === 'HCP验证' && (
              <motion.div
                key="verify"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="max-w-2xl space-y-5">
                  <div className="flex items-end gap-3">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-surface-700 mb-1">HCP ID</label>
                      <input
                        type="text"
                        value={hcpId}
                        onChange={e => setHcpId(e.target.value)}
                        placeholder="请输入HCP编号，如 HCP-001"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <button
                      onClick={handleVerify}
                      disabled={verifyLoading}
                      className={clsx('btn-primary', verifyLoading && 'opacity-50 cursor-not-allowed')}
                    >
                      <Search size={14} /> {verifyLoading ? '验证中...' : '验证'}
                    </button>
                  </div>

                  {verifyResult && (
                    <div className="glass-card-static p-5 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <ShieldCheck size={18} className="text-finance-600" />
                          <span className="font-semibold text-finance-800">验证结果</span>
                          <span className="font-mono text-xs text-surface-400">{verifyResult.hcp_id}</span>
                        </div>
                        <span className={verifyResult.verification_status === 'verified' ? 'badge-green' : 'badge-red'}>
                          {verifyResult.verification_status === 'verified' ? '验证通过' : '验证未通过'}
                        </span>
                      </div>

                      <div className="space-y-3">
                        {(verifyResult.checks || []).map((check: any, idx: number) => (
                          <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-surface-50">
                            {check.status === 'pass' ? (
                              <CheckCircle2 size={18} className="text-compliance-500 mt-0.5 flex-shrink-0" />
                            ) : (
                              <XCircle size={18} className="text-alert-500 mt-0.5 flex-shrink-0" />
                            )}
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-surface-800">{check.check_name}</span>
                                <span className={check.status === 'pass' ? 'badge-green' : 'badge-red'}>
                                  {check.status === 'pass' ? '通过' : '未通过'}
                                </span>
                              </div>
                              <p className="text-xs text-surface-500 mt-1">{check.detail}</p>
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="p-3 rounded-lg bg-finance-50/50 border border-finance-100">
                        <div className="flex items-center gap-2">
                          <Activity size={14} className="text-finance-500" />
                          <span className="text-sm text-finance-700">
                            整体验证状态：
                            {verifyResult.verification_status === 'verified'
                              ? '所有关键项已通过验证'
                              : '存在未通过项，请处理后重新验证'}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === '互动合规' && (
              <motion.div
                key="compliance"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="max-w-2xl space-y-5">
                  <div className="flex items-end gap-3">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-surface-700 mb-1">互动 ID</label>
                      <input
                        type="text"
                        value={interactionId}
                        onChange={e => setInteractionId(e.target.value)}
                        placeholder="请输入互动编号，如 INT-001"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <button
                      onClick={handleComplianceCheck}
                      disabled={complianceLoading}
                      className={clsx('btn-primary', complianceLoading && 'opacity-50 cursor-not-allowed')}
                    >
                      <Search size={14} /> {complianceLoading ? '检查中...' : '检查'}
                    </button>
                  </div>

                  {complianceResult && (
                    <div className="glass-card-static p-5 space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <MessageSquare size={18} className="text-finance-600" />
                          <span className="font-semibold text-finance-800">合规检查结果</span>
                          <span className="font-mono text-xs text-surface-400">{complianceResult.interaction_id}</span>
                        </div>
                        <span className={complianceResult.compliance_status === 'compliant' ? 'badge-green' : 'badge-red'}>
                          {complianceResult.compliance_status === 'compliant' ? '合规' : '不合规'}
                        </span>
                      </div>

                      {(complianceResult.violations || []).length > 0 ? (
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-surface-700">违规事项</h4>
                          {complianceResult.violations.map((v: any, idx: number) => (
                            <div key={idx} className="p-3 rounded-lg bg-alert-50/50 border border-alert-100">
                              <div className="flex items-center gap-2 mb-1">
                                <AlertTriangle size={14} className="text-alert-500" />
                                <span className="text-sm font-bold text-alert-700">{v.rule_id}</span>
                              </div>
                              <p className="text-sm text-surface-700 ml-6">{v.description}</p>
                              <div className="ml-6 mt-2 flex items-center gap-1.5">
                                <span className="text-xs text-surface-400">要求操作：</span>
                                <span className="text-xs font-medium text-finance-700">{v.required_action}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="p-4 rounded-lg bg-compliance-50/50 border border-compliance-100 text-center">
                          <CheckCircle2 size={24} className="mx-auto mb-2 text-compliance-500" />
                          <p className="text-sm text-compliance-700">未发现违规事项，互动合规</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === '付款限额' && (
              <motion.div
                key="payment"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="max-w-2xl space-y-5">
                  <div className="flex items-end gap-3">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-surface-700 mb-1">HCP ID</label>
                      <input
                        type="text"
                        value={paymentHcpId}
                        onChange={e => setPaymentHcpId(e.target.value)}
                        placeholder="请输入HCP编号"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <div className="w-40">
                      <label className="block text-sm font-medium text-surface-700 mb-1">付款金额</label>
                      <input
                        type="number"
                        value={paymentAmount}
                        onChange={e => setPaymentAmount(e.target.value)}
                        placeholder="¥"
                        className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                    </div>
                    <button
                      onClick={handlePaymentLimitCheck}
                      disabled={paymentLoading}
                      className={clsx('btn-primary', paymentLoading && 'opacity-50 cursor-not-allowed')}
                    >
                      <DollarSign size={14} /> {paymentLoading ? '检查中...' : '检查'}
                    </button>
                  </div>

                  {paymentLimitResult && (
                    <div className="glass-card-static p-5 space-y-4">
                      <div className="flex items-center gap-2 mb-2">
                        <DollarSign size={18} className="text-finance-600" />
                        <span className="font-semibold text-finance-800">付款限额检查</span>
                        <span className="font-mono text-xs text-surface-400">{paymentLimitResult.hcp_id}</span>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">当前年度累计</p>
                          <p className="text-lg font-bold text-surface-800 font-display">¥ {paymentLimitResult.current_annual_total?.toLocaleString()}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">本次付款金额</p>
                          <p className="text-lg font-bold text-finance-700 font-display">¥ {paymentLimitResult.payment_amount?.toLocaleString()}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">预计年度总额</p>
                          <p className="text-lg font-bold text-surface-800 font-display">¥ {paymentLimitResult.projected_total?.toLocaleString()}</p>
                        </div>
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">年度限额</p>
                          <p className="text-lg font-bold text-surface-800 font-display">¥ {paymentLimitResult.payment_limit?.toLocaleString()}</p>
                        </div>
                      </div>

                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-sm text-surface-600">付款利用率</span>
                          <span className="text-sm font-bold text-finance-700">
                            {Math.round((paymentLimitResult.projected_total / paymentLimitResult.payment_limit) * 100)}%
                          </span>
                        </div>
                        <div className="w-full h-3 bg-surface-100 rounded-full overflow-hidden">
                          <div
                            className={clsx(
                              'h-full rounded-full transition-all',
                              paymentLimitResult.projected_total > paymentLimitResult.payment_limit
                                ? 'bg-alert-500'
                                : paymentLimitResult.projected_total > paymentLimitResult.payment_limit * 0.8
                                ? 'bg-warning-500'
                                : 'bg-compliance-500'
                            )}
                            style={{ width: `${Math.min(100, (paymentLimitResult.projected_total / paymentLimitResult.payment_limit) * 100)}%` }}
                          />
                        </div>
                      </div>

                      <div className="p-3 rounded-lg bg-surface-50">
                        <p className="metric-label">剩余限额</p>
                        <p className={clsx(
                          'text-lg font-bold font-display',
                          paymentLimitResult.remaining_limit < 0 ? 'text-alert-600' : 'text-compliance-600'
                        )}>
                          ¥ {paymentLimitResult.remaining_limit?.toLocaleString()}
                        </p>
                      </div>

                      {paymentLimitResult.remaining_limit < 0 && (
                        <div className="flex items-center gap-2 p-3 rounded-lg bg-alert-50 border border-alert-200">
                          <AlertTriangle size={16} className="text-alert-500 flex-shrink-0" />
                          <span className="text-sm text-alert-700 font-medium">警告：付款金额将超出年度限额！</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {activeTab === '现场证据' && (
              <motion.div
                key="evidence"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                <div className="glass-card p-6 space-y-4">
                  <div>
                    <h3 className="text-lg font-semibold text-finance-800">HCP 现场证据</h3>
                    <p className="text-sm text-surface-400 mt-1">
                      HR-035 签到、参会名单与知情书（生产审单中的 activity/sign 证据）
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={evidenceHcpId}
                      onChange={e => setEvidenceHcpId(e.target.value)}
                      className="flex-1 px-3 py-2 rounded-lg border border-surface-200"
                      placeholder="HCP ID"
                    />
                    <button
                      disabled={evidenceLoading}
                      onClick={async () => {
                        setEvidenceLoading(true);
                        try {
                          const res = await apiRequest<any>(`/api/hcp/${encodeURIComponent(evidenceHcpId)}/evidence`);
                          setEvidenceResult(res.data || res);
                        } catch (err: any) {
                          setEvidenceResult({ error: err.message });
                        } finally {
                          setEvidenceLoading(false);
                        }
                      }}
                      className="px-4 py-2 rounded-lg bg-finance-700 text-white"
                    >
                      {evidenceLoading ? '查询中…' : '查询'}
                    </button>
                  </div>
                  {evidenceResult?.error && (
                    <p className="text-sm text-alert-600">{evidenceResult.error}</p>
                  )}
                  {evidenceResult && !evidenceResult.error && (
                    <div className="space-y-3">
                      {evidenceResult.summary && (
                        <p className="text-xs text-surface-500">
                          签到有效 {evidenceResult.summary.has_valid_sign ? '是' : '否'} ·
                          参会 {evidenceResult.summary.guest_count || 0} ·
                          签到 {evidenceResult.summary.sign_count || 0} ·
                          知情书 {evidenceResult.summary.know_book_count || 0}
                        </p>
                      )}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">参会人</p>
                          <p className="text-lg font-bold">{evidenceResult.guests?.length || 0}</p>
                          {(evidenceResult.guests || []).slice(0, 5).map((g: any) => (
                            <p key={g.guest_id} className="text-xs text-surface-500">
                              {g.doctor_name} · {g.meet_role || '-'} · {g.is_sign === 'YES' ? '已签' : '未签'}
                            </p>
                          ))}
                        </div>
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">签到记录</p>
                          <p className="text-lg font-bold">{evidenceResult.signs?.length || 0}</p>
                          {(evidenceResult.signs || []).slice(0, 5).map((s: any) => (
                            <p key={s.sign_id} className="text-xs text-surface-500">
                              {s.address || '—'} · {s.valid ? '有效' : '无效'}
                            </p>
                          ))}
                        </div>
                        <div className="p-3 rounded-lg bg-surface-50">
                          <p className="metric-label">知情书</p>
                          <p className="text-lg font-bold">{evidenceResult.know_books?.length || 0}</p>
                          {(evidenceResult.know_books || []).slice(0, 5).map((k: any) => (
                            <p key={k.book_id} className="text-xs text-surface-500">
                              #{k.seq_no} · {k.file_url}
                            </p>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* v9.0 E.6：行业对标 */}
            {activeTab === '行业对标' && (
              <motion.div
                key="benchmark"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="mb-3 flex items-center gap-2">
                  <Building2 size={16} className="text-finance-600" />
                  <h2 className="text-sm font-semibold text-finance-800">行业对标分析</h2>
                  <span className="text-[10px] text-surface-400 px-2 py-0.5 rounded bg-finance-50/60 border border-finance-200">
                    AI · 行业基准
                  </span>
                </div>
                <IndustryBenchmark metrics={null} industry="生物医药" period="2026-06" />
              </motion.div>
            )}

            {/* v9.0 E.6：风险预警 */}
            {activeTab === '风险预警' && (
              <motion.div
                key="risk-alert"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="mb-3 flex items-center gap-2">
                  <ShieldAlert size={16} className="text-alert-600" />
                  <h2 className="text-sm font-semibold text-finance-800">HCP 风险预警面板</h2>
                  <span className="text-[10px] text-surface-400 px-2 py-0.5 rounded bg-alert-50/60 border border-alert-200">
                    AI · 自动扫描
                  </span>
                </div>
                <RiskAlertPanel
                  alerts={null}
                  onResolve={(id) => addToast({ type: 'success', title: '已标记处理', message: `告警 ${id} 已标记` })}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
