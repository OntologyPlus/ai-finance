/**
 * 角色化 Dashboard 组件 — v8.0 模块 H
 * 提供 3 套角色化视图：CFO / 中心负责人 / 品种经理
 */
import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import clsx from 'clsx';
import {
  Briefcase,
  Building2,
  Package,
  TrendingUp,
  AlertTriangle,
  Target,
  Wallet,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';
import { dashboardApi } from '../../services/api';

// ─── 类型定义 ────────────────────────────────────

type RoleType = 'cfo' | 'center_lead' | 'product_manager';

interface RoleConfig {
  key: RoleType;
  label: string;
  icon: React.ReactNode;
  description: string;
  color: string;
}

const ROLE_CONFIGS: Record<RoleType, RoleConfig> = {
  cfo: {
    key: 'cfo',
    label: 'CFO 视图',
    icon: <Briefcase size={14} />,
    description: '战略全景 + 9 卡 + 4 框架',
    color: 'text-finance-600 bg-finance-50 border-finance-200',
  },
  center_lead: {
    key: 'center_lead',
    label: '中心负责人',
    icon: <Building2 size={14} />,
    description: '中心健康度 + 3GAP/3List',
    color: 'text-brand-600 bg-brand-50 border-brand-200',
  },
  product_manager: {
    key: 'product_manager',
    label: '品种经理',
    icon: <Package size={14} />,
    description: '产品 ROI + 政策风险',
    color: 'text-compliance-600 bg-compliance-50 border-compliance-200',
  },
};

// ─── 角色切换器 ────────────────────────────────────

export function RoleSwitcher({
  currentRole,
  onChange,
}: {
  currentRole: RoleType;
  onChange: (role: RoleType) => void;
}) {
  return (
    <div className="flex items-center gap-2 p-1 rounded-xl bg-surface-100">
      {Object.values(ROLE_CONFIGS).map((cfg) => (
        <button
          key={cfg.key}
          onClick={() => onChange(cfg.key)}
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
            currentRole === cfg.key
              ? 'bg-white text-finance-700 shadow-sm border border-surface-200'
              : 'text-surface-500 hover:text-surface-700'
          )}
          title={cfg.description}
        >
          {cfg.icon}
          {cfg.label}
        </button>
      ))}
    </div>
  );
}

// ─── 通用 KPI Card ────────────────────────────────────

function KpiCard({
  label,
  value,
  suffix = '',
  prefix = '',
  color = 'finance',
  icon,
}: {
  label: string;
  value: number;
  suffix?: string;
  prefix?: string;
  color?: 'finance' | 'brand' | 'compliance' | 'alert' | 'warning';
  icon?: React.ReactNode;
}) {
  const colorMap = {
    finance: 'from-finance-500 to-finance-700',
    brand: 'from-brand-500 to-brand-700',
    compliance: 'from-compliance-500 to-compliance-700',
    alert: 'from-alert-500 to-alert-700',
    warning: 'from-warning-500 to-warning-700',
  };
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-1">
        <p className="text-[10px] font-medium text-surface-400">{label}</p>
        {icon}
      </div>
      <p className="text-lg font-bold">
        <span className={clsx('bg-gradient-to-r bg-clip-text text-transparent', colorMap[color])}>
          {prefix}
          {typeof value === 'number' ? value.toLocaleString() : value}
          {suffix}
        </span>
      </p>
    </div>
  );
}

// ─── CFO 视图组件 ────────────────────────────────────

export function CFODashboard({ period }: { period?: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    dashboardApi
      .getRoleDashboard({ role: 'cfo', period })
      .then((res) => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [period]);

  if (loading || !data) {
    return (
      <div className="text-center text-surface-400 py-8 text-sm">CFO 视图加载中…</div>
    );
  }

  const kpis = data.kpis || {};
  const cards = data.diagnosis_cards || {};
  const strategic = data.strategic_summary || {};

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiCard label="总预算" value={kpis.total_budget} prefix="¥" color="finance" />
        <KpiCard label="已用" value={kpis.total_used} prefix="¥" color="brand" />
        <KpiCard label="执行率" value={kpis.execution_rate} suffix="%" color="compliance" />
        <KpiCard label="开放预警" value={kpis.open_alerts} color="alert" icon={<AlertTriangle size={14} className="text-alert-500" />} />
        <KpiCard label="战略举措" value={kpis.active_strategies} color="finance" icon={<Target size={14} className="text-finance-500" />} />
      </div>

      {/* 9 卡九宫格 */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-finance-700 mb-3">📊 9 卡九宫格（诊断信号灯）</h3>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(cards).map(([key, card]: [string, any]) => {
            const statusColors: Record<string, string> = {
              green: 'border-compliance-200 bg-compliance-50/30 text-compliance-700',
              yellow: 'border-warning-200 bg-warning-50/30 text-warning-700',
              red: 'border-alert-200 bg-alert-50/30 text-alert-700',
            };
            const statusIcons: Record<string, string> = {
              green: '🟢',
              yellow: '🟡',
              red: '🔴',
            };
            return (
              <div
                key={key}
                className={clsx(
                  'p-3 rounded-lg border text-center text-xs',
                  statusColors[card.status] || statusColors.green
                )}
              >
                <span className="text-base mr-1">{statusIcons[card.status]}</span>
                <span className="font-medium">{card.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4 框架概览 */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-finance-700 mb-3">🔧 4 框架概览</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          {Object.entries(data.frameworks || {}).map(([key, desc]: [string, any]) => (
            <div key={key} className="p-3 rounded-lg bg-surface-50 border border-surface-100">
              <p className="font-semibold text-finance-700 mb-1 uppercase">{key}</p>
              <p className="text-surface-500 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Top 预警 */}
      {data.top_alerts && data.top_alerts.length > 0 && (
        <div className="glass-card p-4">
          <h3 className="text-sm font-semibold text-finance-700 mb-3 flex items-center gap-2">
            <AlertTriangle size={14} className="text-alert-500" />
            Top {data.top_alerts.length} 预警
          </h3>
          <div className="space-y-2">
            {data.top_alerts.map((alert: any) => (
              <div
                key={alert.alert_id}
                className="flex items-center gap-3 p-2 rounded-lg bg-surface-50 border border-surface-100"
              >
                <span
                  className={clsx(
                    'text-[10px] font-semibold px-1.5 py-0.5 rounded',
                    alert.level === '红色' && 'bg-alert-100 text-alert-700',
                    alert.level === '橙色' && 'bg-warning-100 text-warning-700',
                    alert.level === '黄色' && 'bg-brand-100 text-brand-700',
                    alert.level === '蓝色' && 'bg-compliance-100 text-compliance-700'
                  )}
                >
                  {alert.level}
                </span>
                <span className="text-xs flex-1">{alert.type}</span>
                <span className="text-[10px] text-surface-400">{alert.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── 中心负责人视图 ────────────────────────────────────

export function CenterLeadDashboard({
  centerId,
  period,
}: {
  centerId?: string;
  period?: string;
}) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    dashboardApi
      .getRoleDashboard({ role: 'center_lead', center_id: centerId, period })
      .then((res) => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [centerId, period]);

  if (loading || !data) {
    return (
      <div className="text-center text-surface-400 py-8 text-sm">中心视图加载中…</div>
    );
  }

  const kpis = data.kpis || {};
  const gap = data.three_gap || {};
  const lists = data.three_list || {};

  return (
    <div className="space-y-4">
      <div className="text-xs text-surface-500">📍 中心 {data.center_id}</div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="中心总预算" value={kpis.total_budget} prefix="¥" color="finance" />
        <KpiCard label="已使用" value={kpis.total_used} prefix="¥" color="brand" />
        <KpiCard label="执行率" value={kpis.execution_rate} suffix="%" color="compliance" />
        <KpiCard label="待审批" value={kpis.pending_approvals || 0} color="warning" />
      </div>

      {/* 3GAP */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-finance-700 mb-3">📐 3GAP 分析（{gap.period}）</h3>
        <div className="grid grid-cols-3 gap-2">
          {[
            { key: 'gap1', label: '目标差距 (GAP1)', color: 'finance' },
            { key: 'gap2', label: '执行差距 (GAP2)', color: 'brand' },
            { key: 'gap3', label: '预测变动 (GAP3)', color: 'compliance' },
          ].map((g) => (
            <div
              key={g.key}
              className={clsx(
                'p-3 rounded-lg border text-center',
                g.color === 'finance' && 'bg-finance-50/40 border-finance-200',
                g.color === 'brand' && 'bg-brand-50/40 border-brand-200',
                g.color === 'compliance' && 'bg-compliance-50/40 border-compliance-200'
              )}
            >
              <p className="text-[10px] text-surface-500 mb-1">{g.label}</p>
              <p className="text-lg font-bold font-mono">
                {typeof gap[g.key] === 'number' ? gap[g.key].toFixed(2) : 0}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* 3List */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-finance-700 mb-3">📋 3List 清单</h3>
        <div className="grid grid-cols-3 gap-2">
          {[
            { key: 'must_win', label: '必赢清单', color: 'compliance' },
            { key: 'improve', label: '改善清单', color: 'warning' },
            { key: 'resource', label: '资源清单', color: 'alert' },
          ].map((l) => (
            <div key={l.key} className="border border-surface-200 rounded-lg p-2">
              <p className="text-[10px] font-semibold text-surface-600 mb-1">
                {l.label} ({(lists[l.key] || []).length})
              </p>
              <div className="space-y-1">
                {(lists[l.key] || []).slice(0, 3).map((item: any) => (
                  <div
                    key={item.budget_id}
                    className="text-[11px] px-2 py-1 bg-surface-50 rounded"
                  >
                    {item.budget_name}
                  </div>
                ))}
                {(lists[l.key] || []).length === 0 && (
                  <p className="text-[10px] text-surface-400">暂无</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── 品种经理视图 ────────────────────────────────────

export function ProductManagerDashboard({
  l1Code,
  period,
}: {
  l1Code?: string;
  period?: string;
}) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    dashboardApi
      .getRoleDashboard({ role: 'product_manager', l1_code: l1Code, period })
      .then((res) => setData(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [l1Code, period]);

  if (loading || !data) {
    return (
      <div className="text-center text-surface-400 py-8 text-sm">产品视图加载中…</div>
    );
  }

  const kpis = data.kpis || {};
  const roi = data.roi_summary || {};
  const policyRisk = data.policy_risk || {};
  const products = data.product_distribution || [];

  return (
    <div className="space-y-4">
      <div className="text-xs text-surface-500">📍 L1 科目 {data.l1_code}</div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="产品预算" value={kpis.total_budget} prefix="¥" color="finance" />
        <KpiCard label="已使用" value={kpis.total_used} prefix="¥" color="brand" />
        <KpiCard label="执行率" value={kpis.execution_rate} suffix="%" color="compliance" />
        <KpiCard label="产品数" value={kpis.product_count} color="warning" />
      </div>

      {/* ROI 概览 */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-finance-700 mb-3">💰 ROI 概览</h3>
        <div className="grid grid-cols-3 gap-2">
          {[
            { key: 'high_count', label: '高 ROI', color: 'compliance' },
            { key: 'medium_count', label: '中 ROI', color: 'warning' },
            { key: 'low_count', label: '低 ROI', color: 'alert' },
          ].map((r) => (
            <div
              key={r.key}
              className={clsx(
                'p-3 rounded-lg border text-center',
                r.color === 'compliance' && 'bg-compliance-50/40 border-compliance-200',
                r.color === 'warning' && 'bg-warning-50/40 border-warning-200',
                r.color === 'alert' && 'bg-alert-50/40 border-alert-200'
              )}
            >
              <p className="text-[10px] text-surface-500 mb-1">{r.label}</p>
              <p className="text-lg font-bold font-mono">{roi[r.key] || 0}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 政策风险 */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-finance-700 mb-3">⚠️ 政策风险评估</h3>
        <div className="flex items-center gap-3 mb-2">
          <span
            className={clsx(
              'text-[10px] font-semibold px-2 py-0.5 rounded',
              policyRisk.risk_level === '高' && 'bg-alert-100 text-alert-700',
              policyRisk.risk_level === '中' && 'bg-warning-100 text-warning-700',
              policyRisk.risk_level === '低' && 'bg-compliance-100 text-compliance-700'
            )}
          >
            风险等级：{policyRisk.risk_level}
          </span>
          <span className="text-[10px] text-surface-400">
            高优先级预警: {policyRisk.high_alert_count || 0}
          </span>
        </div>
        <div className="space-y-1">
          {(policyRisk.factors || []).map((f: string, i: number) => (
            <p key={i} className="text-xs text-surface-500">• {f}</p>
          ))}
        </div>
      </div>

      {/* 产品分布 */}
      <div className="glass-card p-4">
        <h3 className="text-sm font-semibold text-finance-700 mb-3">📦 产品分布</h3>
        <div className="space-y-1 max-h-60 overflow-y-auto">
          {products.slice(0, 10).map((p: any) => (
            <div
              key={p.budget_id}
              className="flex items-center gap-3 p-2 rounded-lg bg-surface-50 border border-surface-100"
            >
              <span className="text-xs flex-1 truncate">{p.budget_name}</span>
              <span
                className={clsx(
                  'text-[10px] font-semibold px-1.5 py-0.5 rounded',
                  p.execution_rate > 100
                    ? 'bg-alert-100 text-alert-700'
                    : p.execution_rate > 60
                    ? 'bg-compliance-100 text-compliance-700'
                    : 'bg-warning-100 text-warning-700'
                )}
              >
                {p.execution_rate}%
              </span>
              <span className="text-[10px] text-surface-400">{p.quadrant}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
