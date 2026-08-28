import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  TrendingUp,
  TrendingDown,
  Droplets,
  BarChart3,
  AlertTriangle,
  CheckCircle2,
  ArrowRightLeft,
  RefreshCw,
  Info,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAppStore } from '../store';
import Pagination from '../components/Pagination';

const TABS = ['现金流预测', '流动性分析', '利润现金流差异', '收支匹配'] as const;

// ── Inline API helpers (matching existing request pattern) ──
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

function getToken(): string | null {
  return localStorage.getItem('auth_token');
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
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

interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

const cashFlowApi = {
  forecast: (period: string, horizonMonths: number) =>
    request<ApiResponse<any>>(`/api/cashflow/forecast?period=${period}&horizon_months=${horizonMonths}`),
  liquidityGap: (period: string) =>
    request<ApiResponse<any>>(`/api/cashflow/liquidity-gap?period=${period}`),
  profitCashGap: (period: string) =>
    request<ApiResponse<any>>(`/api/cashflow/profit-cash-gap?period=${period}`),
  receiptPaymentMatch: (period: string) =>
    request<ApiResponse<any>>(`/api/cashflow/receipt-payment-match?period=${period}`),
};

// v9.0: MOCK 数据已废弃，全部接后端 API 真实数据
const EMPTY_FORECAST = { months: [], operating: [], investing: [], financing: [], total_inflow: 0, total_outflow: 0, net_cash_flow: 0, table: [] };
const EMPTY_LIQUIDITY = { has_gap: false, pool_balance: 0, gap_details: [], recommendation: '' };
const EMPTY_PROFIT_CASH = { profit_accrual: 0, cash_flow_actual: 0, gap_amount: 0, gap_ratio: 0, gap_sources: [], interpretation: '' };
const EMPTY_RECEIPT_PAYMENT = { total_payment: 0, total_receipt: 0, net: 0, weekly: [], risk_windows: [] };

function formatWan(n: number): string {
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}万`;
  return n.toLocaleString();
}

export default function CashFlowPage() {
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('现金流预测');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const addToast = useAppStore((s) => s.addToast);

  // Tab 1 state
  // v12.2: 修复默认 period 为 2026-06，匹配 seed/cash_flow.py 写入的演示数据
  const [period, setPeriod] = useState(() => new Date().toISOString().slice(0, 7));
  const [horizon, setHorizon] = useState(6);
  const [forecastData, setForecastData] = useState<any>(null);

  // Tab 2 state
  const [liquidityData, setLiquidityData] = useState<any>(null);

  // Tab 3 state
  const [profitCashData, setProfitCashData] = useState<any>(null);

  // Tab 4 state
  const [receiptPaymentData, setReceiptPaymentData] = useState<any>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize] = useState(5);

  const fetchForecast = async () => {
    setError(null);
    try {
      const res = await cashFlowApi.forecast(period, horizon);
      setForecastData(res.data);
    } catch (e: any) {
      setError(`现金流预测加载失败：${e.message}`);
      setForecastData(null);
    }
  };

  const fetchLiquidity = async () => {
    setError(null);
    try {
      const res = await cashFlowApi.liquidityGap(period);
      setLiquidityData(res.data);
    } catch (e: any) {
      setError(`流动性分析加载失败：${e.message}`);
      setLiquidityData(null);
    }
  };

  const fetchProfitCash = async () => {
    setError(null);
    try {
      const res = await cashFlowApi.profitCashGap(period);
      setProfitCashData(res.data);
    } catch (e: any) {
      setError(`利润现金流差异加载失败：${e.message}`);
      setProfitCashData(null);
    }
  };

  const fetchReceiptPayment = async () => {
    setError(null);
    try {
      const res = await cashFlowApi.receiptPaymentMatch(period);
      setReceiptPaymentData(res.data);
    } catch (e: any) {
      setError(`收支匹配加载失败：${e.message}`);
      setReceiptPaymentData(null);
    }
  };

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([fetchForecast(), fetchLiquidity(), fetchProfitCash(), fetchReceiptPayment()]);
      setLoading(false);
    };
    init();
  }, []);

  const handleRefresh = async () => {
    setLoading(true);
    await Promise.all([fetchForecast(), fetchLiquidity(), fetchProfitCash(), fetchReceiptPayment()]);
    setLoading(false);
    addToast({ type: 'success', title: '刷新成功', message: '现金流数据已更新' });
  };

  const handleForecastQuery = async () => {
    setLoading(true);
    await fetchForecast();
    setLoading(false);
  };

  if (loading && !forecastData) {
    return <div className="flex items-center justify-center h-64 text-surface-400">加载中...</div>;
  }

  const severityMap: Record<string, { label: string; cls: string }> = {
    low: { label: '低', cls: 'badge-green' },
    medium: { label: '中', cls: 'badge-amber' },
    high: { label: '高', cls: 'badge-red' },
  };

  const riskWindows = receiptPaymentData?.risk_windows || [];
  const pagedRiskWindows = riskWindows.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const riskTotalPages = Math.max(1, Math.ceil(riskWindows.length / pageSize));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-finance-800 font-display">现金流监控</h1>
          <p className="text-sm text-surface-400 mt-1">利润线+现金流线双轮驱动</p>
        </div>
        <button onClick={handleRefresh} className="btn-primary">
          <RefreshCw size={14} /> 刷新数据
        </button>
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
                  layoutId="cashFlowTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          <AnimatePresence mode="wait">
            {/* ── Tab 1: 现金流预测 ── */}
            {activeTab === '现金流预测' && (
              <motion.div
                key="forecast"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* Controls */}
                <div className="flex flex-wrap items-center gap-3 p-3 rounded-xl bg-surface-50/50 border border-surface-200/60">
                  <span className="text-sm text-surface-500">期间</span>
                  <input
                    type="month"
                    value={period}
                    onChange={e => setPeriod(e.target.value)}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  />
                  <span className="text-sm text-surface-500">预测周期</span>
                  <select
                    value={horizon}
                    onChange={e => setHorizon(Number(e.target.value))}
                    className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-xs focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                  >
                    <option value={3}>3个月</option>
                    <option value={6}>6个月</option>
                    <option value={12}>12个月</option>
                  </select>
                  <button onClick={handleForecastQuery} className="btn-primary text-xs">
                    查询
                  </button>
                </div>

                {/* Summary cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {[
                    { label: '总流入', value: forecastData?.total_inflow ?? 0, icon: <TrendingUp size={16} className="text-compliance-600" />, gradient: 'from-compliance-500 to-health-600' },
                    { label: '总流出', value: forecastData?.total_outflow ?? 0, icon: <TrendingDown size={16} className="text-alert-600" />, gradient: 'from-alert-500 to-alert-600' },
                    { label: '净现金流', value: forecastData?.net_cash_flow ?? 0, icon: <Droplets size={16} className="text-finance-600" />, gradient: 'from-finance-500 to-finance-700' },
                  ].map(card => (
                    <div key={card.label} className="glass-card p-5">
                      <div className="flex items-center gap-2 mb-2">
                        {card.icon}
                        <p className="metric-label">{card.label}</p>
                      </div>
                      <p className="metric-value">
                        <span className={`bg-gradient-to-r ${card.gradient} bg-clip-text text-transparent`}>
                          ¥ {formatWan(card.value)}
                        </span>
                      </p>
                    </div>
                  ))}
                </div>

                {/* Chart */}
                <div className="glass-card-static p-5">
                  <h3 className="text-sm font-semibold text-surface-700 mb-4">现金流预测趋势</h3>
                  <ReactECharts
                    option={{
                      tooltip: { trigger: 'axis' as const },
                      legend: { data: ['经营活动', '投资活动', '筹资活动'], textStyle: { color: '#94a3b8', fontSize: 11 } },
                      grid: { left: 50, right: 20, bottom: 30, top: 40 },
                      xAxis: {
                        type: 'category' as const,
                        data: forecastData?.months || EMPTY_FORECAST.months,
                        axisLabel: { color: '#94a3b8', fontSize: 10 },
                        axisLine: { lineStyle: { color: '#e2e8f0' } },
                      },
                      yAxis: {
                        type: 'value' as const,
                        axisLabel: { color: '#94a3b8', fontSize: 10, formatter: (v: number) => formatWan(v) },
                        splitLine: { lineStyle: { color: '#f1f5f9' } },
                      },
                      series: [
                        {
                          name: '经营活动',
                          type: 'line' as const,
                          data: forecastData?.operating || EMPTY_FORECAST.operating,
                          smooth: true,
                          symbol: 'circle',
                          symbolSize: 4,
                          lineStyle: { width: 2, color: '#10b981' },
                          itemStyle: { color: '#10b981' },
                          areaStyle: { color: '#10b98115' },
                        },
                        {
                          name: '投资活动',
                          type: 'line' as const,
                          data: forecastData?.investing || EMPTY_FORECAST.investing,
                          smooth: true,
                          symbol: 'circle',
                          symbolSize: 4,
                          lineStyle: { width: 2, color: '#f97316' },
                          itemStyle: { color: '#f97316' },
                          areaStyle: { color: '#f9731615' },
                        },
                        {
                          name: '筹资活动',
                          type: 'line' as const,
                          data: forecastData?.financing || EMPTY_FORECAST.financing,
                          smooth: true,
                          symbol: 'circle',
                          symbolSize: 4,
                          lineStyle: { width: 2, color: '#8b5cf6' },
                          itemStyle: { color: '#8b5cf6' },
                          areaStyle: { color: '#8b5cf615' },
                        },
                      ],
                    }}
                    style={{ height: '280px' }}
                    notMerge={true}
                    lazyUpdate={true}
                    showLoading={!forecastData}
                  />
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-surface-200/60">
                        <th className="text-left py-3 px-3 metric-label">月份</th>
                        <th className="text-right py-3 px-3 metric-label">经营活动</th>
                        <th className="text-right py-3 px-3 metric-label">投资活动</th>
                        <th className="text-right py-3 px-3 metric-label">筹资活动</th>
                        <th className="text-right py-3 px-3 metric-label">净现金流</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(forecastData?.table || EMPTY_FORECAST.table).map((row: any) => (
                        <tr key={row.month} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                          <td className="py-3 px-3 font-mono text-xs text-finance-700">{row.month}</td>
                          <td className="py-3 px-3 text-right font-mono text-compliance-600">¥ {formatWan(row.operating)}</td>
                          <td className="py-3 px-3 text-right font-mono text-orange-600">¥ {formatWan(row.investing)}</td>
                          <td className="py-3 px-3 text-right font-mono text-purple-600">¥ {formatWan(row.financing)}</td>
                          <td className={clsx('py-3 px-3 text-right font-mono', row.net >= 0 ? 'text-compliance-600' : 'text-alert-600')}>
                            ¥ {formatWan(row.net)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* ── Tab 2: 流动性分析 ── */}
            {activeTab === '流动性分析' && (
              <motion.div
                key="liquidity"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* Status cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className={clsx(
                    'rounded-xl border-2 p-5 transition-all',
                    liquidityData?.has_gap ? 'bg-alert-50/60 border-alert-300' : 'bg-compliance-50/60 border-compliance-300'
                  )}>
                    <div className="flex items-center gap-3 mb-2">
                      {liquidityData?.has_gap ? (
                        <AlertTriangle size={20} className="text-alert-600" />
                      ) : (
                        <CheckCircle2 size={20} className="text-compliance-600" />
                      )}
                      <h3 className="text-sm font-semibold text-surface-800">流动性缺口状态</h3>
                    </div>
                    <p className={clsx('text-2xl font-bold font-display', liquidityData?.has_gap ? 'text-alert-600' : 'text-compliance-600')}>
                      {liquidityData?.has_gap ? '存在缺口' : '无缺口'}
                    </p>
                    <p className="text-xs text-surface-400 mt-1">
                      {liquidityData?.has_gap ? '当前期间存在流动性缺口，请关注' : '当前期间流动性充足'}
                    </p>
                  </div>

                  <div className="glass-card p-5">
                    <div className="flex items-center gap-3 mb-2">
                      <Droplets size={20} className="text-finance-600" />
                      <h3 className="text-sm font-semibold text-surface-800">资金池余额</h3>
                    </div>
                    <p className="metric-value">
                      <span className="bg-gradient-to-r from-finance-500 to-finance-700 bg-clip-text text-transparent">
                        ¥ {formatWan(liquidityData?.pool_balance ?? 0)}
                      </span>
                    </p>
                    <p className="text-xs text-surface-400 mt-1">当前可用资金池余额</p>
                  </div>
                </div>

                {/* Gap details table */}
                <div className="glass-card-static p-5">
                  <h3 className="text-sm font-semibold text-surface-700 mb-4">缺口明细</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-surface-200/60">
                          <th className="text-left py-3 px-3 metric-label">期间</th>
                          <th className="text-right py-3 px-3 metric-label">缺口金额</th>
                          <th className="text-center py-3 px-3 metric-label">严重程度</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(liquidityData?.gap_details || []).map((row: any, idx: number) => (
                          <tr key={idx} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                            <td className="py-3 px-3 font-mono text-xs text-finance-700">{row.period}</td>
                            <td className={clsx('py-3 px-3 text-right font-mono', row.gap_amount < 0 ? 'text-alert-600' : 'text-compliance-600')}>
                              ¥ {formatWan(row.gap_amount)}
                            </td>
                            <td className="py-3 px-3 text-center">
                              <span className={severityMap[row.severity]?.cls || 'badge-blue'}>
                                {severityMap[row.severity]?.label || row.severity}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Recommendation */}
                <div className="p-4 rounded-xl border border-finance-100 bg-finance-50/30">
                  <div className="flex items-center gap-2 mb-2">
                    <Info size={16} className="text-finance-600" />
                    <h3 className="text-sm font-semibold text-finance-800">建议</h3>
                  </div>
                  <p className="text-sm text-surface-600">{liquidityData?.recommendation || '暂无建议'}</p>
                </div>
              </motion.div>
            )}

            {/* ── Tab 3: 利润现金流差异 ── */}
            {activeTab === '利润现金流差异' && (
              <motion.div
                key="profitCash"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* Two big metric cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="glass-card p-5">
                    <div className="flex items-center gap-2 mb-2">
                      <TrendingUp size={16} className="text-finance-600" />
                      <p className="metric-label">利润（权责发生制）</p>
                    </div>
                    <p className="metric-value">
                      <span className="bg-gradient-to-r from-finance-500 to-finance-700 bg-clip-text text-transparent">
                        ¥ {formatWan(profitCashData?.profit_accrual ?? 0)}
                      </span>
                    </p>
                  </div>
                  <div className="glass-card p-5">
                    <div className="flex items-center gap-2 mb-2">
                      <Droplets size={16} className="text-compliance-600" />
                      <p className="metric-label">现金流（收付实现制）</p>
                    </div>
                    <p className="metric-value">
                      <span className="bg-gradient-to-r from-compliance-500 to-health-600 bg-clip-text text-transparent">
                        ¥ {formatWan(profitCashData?.cash_flow_actual ?? 0)}
                      </span>
                    </p>
                  </div>
                </div>

                {/* Gap display */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="glass-card p-5">
                    <p className="metric-label mb-2">差异金额</p>
                    <p className="metric-value">
                      <span className="text-alert-600">¥ {formatWan(profitCashData?.gap_amount ?? 0)}</span>
                    </p>
                  </div>
                  <div className="glass-card p-5">
                    <p className="metric-label mb-2">差异比率</p>
                    <p className="metric-value">
                      <span className="text-alert-600">{profitCashData?.gap_ratio?.toFixed(1) ?? 0}%</span>
                    </p>
                  </div>
                </div>

                {/* Bar chart */}
                <div className="glass-card-static p-5">
                  <h3 className="text-sm font-semibold text-surface-700 mb-4">差异来源分析</h3>
                  <ReactECharts
                    option={{
                      tooltip: { trigger: 'axis' as const },
                      grid: { left: 80, right: 20, bottom: 30, top: 20 },
                      xAxis: {
                        type: 'value' as const,
                        axisLabel: { color: '#94a3b8', fontSize: 10, formatter: (v: number) => formatWan(v) },
                        splitLine: { lineStyle: { color: '#f1f5f9' } },
                      },
                      yAxis: {
                        type: 'category' as const,
                        data: (profitCashData?.gap_sources || EMPTY_PROFIT_CASH.gap_sources).map((s: any) => s.name),
                        axisLabel: { color: '#64748b', fontSize: 11 },
                        axisLine: { lineStyle: { color: '#e2e8f0' } },
                      },
                      series: [{
                        type: 'bar' as const,
                        data: (profitCashData?.gap_sources || EMPTY_PROFIT_CASH.gap_sources).map((s: any) => s.value),
                        barWidth: 24,
                        itemStyle: {
                          borderRadius: [0, 4, 4, 0],
                          color: {
                            type: 'linear' as const,
                            x: 0, y: 0, x2: 1, y2: 0,
                            colorStops: [
                              { offset: 0, color: '#f97316' },
                              { offset: 1, color: '#fb923c' },
                            ],
                          },
                        },
                        label: {
                          show: true,
                          position: 'right' as const,
                          formatter: (p: any) => `¥ ${formatWan(p.value)}`,
                          color: '#64748b',
                          fontSize: 10,
                        },
                      }],
                    }}
                    style={{ height: '220px' }}
                    notMerge={true}
                    lazyUpdate={true}
                    showLoading={!profitCashData}
                  />
                </div>

                {/* Interpretation */}
                <div className="p-4 rounded-xl border border-finance-100 bg-finance-50/30">
                  <div className="flex items-center gap-2 mb-2">
                    <Info size={16} className="text-finance-600" />
                    <h3 className="text-sm font-semibold text-finance-800">解读</h3>
                  </div>
                  <p className="text-sm text-surface-600">{profitCashData?.interpretation || '暂无解读'}</p>
                </div>
              </motion.div>
            )}

            {/* ── Tab 4: 收支匹配 ── */}
            {activeTab === '收支匹配' && (
              <motion.div
                key="receiptPayment"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="space-y-5"
              >
                {/* Summary cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {[
                    { label: '总支出', value: receiptPaymentData?.total_payment ?? 0, gradient: 'from-alert-500 to-alert-600', icon: <TrendingDown size={16} className="text-alert-600" /> },
                    { label: '总收入', value: receiptPaymentData?.total_receipt ?? 0, gradient: 'from-compliance-500 to-health-600', icon: <TrendingUp size={16} className="text-compliance-600" /> },
                    { label: '净额', value: receiptPaymentData?.net ?? 0, gradient: 'from-finance-500 to-finance-700', icon: <ArrowRightLeft size={16} className="text-finance-600" /> },
                  ].map(card => (
                    <div key={card.label} className="glass-card p-5">
                      <div className="flex items-center gap-2 mb-2">
                        {card.icon}
                        <p className="metric-label">{card.label}</p>
                      </div>
                      <p className="metric-value">
                        <span className={`bg-gradient-to-r ${card.gradient} bg-clip-text text-transparent`}>
                          ¥ {formatWan(card.value)}
                        </span>
                      </p>
                    </div>
                  ))}
                </div>

                {/* Bar chart */}
                <div className="glass-card-static p-5">
                  <h3 className="text-sm font-semibold text-surface-700 mb-4">周度收支对比</h3>
                  <ReactECharts
                    option={{
                      tooltip: { trigger: 'axis' as const },
                      legend: { data: ['支出', '收入'], textStyle: { color: '#94a3b8', fontSize: 11 } },
                      grid: { left: 50, right: 20, bottom: 30, top: 40 },
                      xAxis: {
                        type: 'category' as const,
                        data: (receiptPaymentData?.weekly || []).map((w: any) => w.week),
                        axisLabel: { color: '#94a3b8', fontSize: 10 },
                        axisLine: { lineStyle: { color: '#e2e8f0' } },
                      },
                      yAxis: {
                        type: 'value' as const,
                        axisLabel: { color: '#94a3b8', fontSize: 10, formatter: (v: number) => formatWan(v) },
                        splitLine: { lineStyle: { color: '#f1f5f9' } },
                      },
                      series: [
                        {
                          name: '支出',
                          type: 'bar' as const,
                          data: (receiptPaymentData?.weekly || []).map((w: any) => w.payment),
                          barWidth: 16,
                          itemStyle: { borderRadius: [4, 4, 0, 0], color: '#f97316' },
                        },
                        {
                          name: '收入',
                          type: 'bar' as const,
                          data: (receiptPaymentData?.weekly || []).map((w: any) => w.receipt),
                          barWidth: 16,
                          itemStyle: { borderRadius: [4, 4, 0, 0], color: '#10b981' },
                        },
                      ],
                    }}
                    style={{ height: '280px' }}
                    notMerge={true}
                    lazyUpdate={true}
                    showLoading={!receiptPaymentData}
                  />
                </div>

                {/* Risk windows table */}
                <div className="glass-card-static p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <AlertTriangle size={16} className="text-alert-600" />
                    <h3 className="text-sm font-semibold text-surface-700">风险窗口（净额为负的周次）</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-surface-200/60">
                          <th className="text-left py-3 px-3 metric-label">周次</th>
                          <th className="text-right py-3 px-3 metric-label">支出</th>
                          <th className="text-right py-3 px-3 metric-label">收入</th>
                          <th className="text-right py-3 px-3 metric-label">净额</th>
                          <th className="text-center py-3 px-3 metric-label">状态</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pagedRiskWindows.map((row: any) => (
                          <tr key={row.week} className="border-b border-surface-100 hover:bg-finance-50/30 transition-colors">
                            <td className="py-3 px-3 font-mono text-xs text-finance-700">{row.week}</td>
                            <td className="py-3 px-3 text-right font-mono text-orange-600">¥ {formatWan(row.payment)}</td>
                            <td className="py-3 px-3 text-right font-mono text-compliance-600">¥ {formatWan(row.receipt)}</td>
                            <td className="py-3 px-3 text-right font-mono text-alert-600">¥ {formatWan(row.net)}</td>
                            <td className="py-3 px-3 text-center">
                              <span className="badge-red">风险</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <Pagination currentPage={currentPage} totalPages={riskTotalPages} onPageChange={setCurrentPage} pageSize={pageSize} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
