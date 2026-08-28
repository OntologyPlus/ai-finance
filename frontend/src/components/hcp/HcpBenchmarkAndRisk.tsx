/**
 * IndustryBenchmark + RiskAlertPanel — 行业对标 + 风险预警（v9.0 E.6）
 *
 * IndustryBenchmark：HCP 接待费用率/单次成本 vs 行业基准（中位数/P25/P75）
 * RiskAlertPanel：超额/延期/缺失凭证 → 自动标红
 *
 * 数据契约：前端接受以下结构，无后端时降级使用内置基准数据
 */
import { useMemo } from 'react';
import { motion } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  TrendingUp,
  TrendingDown,
  AlertCircle,
  AlertTriangle,
  Clock,
  XCircle,
  Building2,
  Award,
  ShieldAlert,
  FileWarning,
} from 'lucide-react';
import { clsx } from 'clsx';

export interface BenchmarkMetric {
  metric: string;          // 指标名
  label: string;           // 展示名
  our_value: number;       // 我们的值
  industry_p25: number;    // 行业 P25
  industry_median: number; // 行业 P50
  industry_p75: number;    // 行业 P75
  unit: string;            // 单位（如 %、元）
  higher_is_better: boolean;
  status: 'better' | 'on_pace' | 'worse';
  deviation_pct: number;   // 偏离行业中位数的百分比
}

export interface IndustryBenchmarkProps {
  metrics: BenchmarkMetric[] | null;
  industry?: string;        // 行业名
  period?: string;
}

// 内置行业基准（无后端时使用）
const DEFAULT_METRICS: BenchmarkMetric[] = [
  {
    metric: 'hcp_hosting_rate',
    label: 'HCP 接待费用率',
    our_value: 4.8,
    industry_p25: 3.5,
    industry_median: 5.0,
    industry_p75: 6.8,
    unit: '%',
    higher_is_better: false,
    status: 'on_pace',
    deviation_pct: -4.0,
  },
  {
    metric: 'avg_cost_per_visit',
    label: '单次接待成本',
    our_value: 1850,
    industry_p25: 1200,
    industry_median: 1800,
    industry_p75: 2400,
    unit: '元',
    higher_is_better: false,
    status: 'on_pace',
    deviation_pct: 2.8,
  },
  {
    metric: 'speaker_fee_pct',
    label: '讲者费占比',
    our_value: 32.5,
    industry_p25: 25.0,
    industry_median: 35.0,
    industry_p75: 45.0,
    unit: '%',
    higher_is_better: true,
    status: 'on_pace',
    deviation_pct: -7.1,
  },
  {
    metric: 'gift_value_avg',
    label: '礼品均价',
    our_value: 280,
    industry_p25: 200,
    industry_median: 300,
    industry_p75: 450,
    unit: '元',
    higher_is_better: false,
    status: 'better',
    deviation_pct: -6.7,
  },
  {
    metric: 'venue_compliance',
    label: '场地合规率',
    our_value: 96.5,
    industry_p25: 88.0,
    industry_median: 92.0,
    industry_p75: 97.0,
    unit: '%',
    higher_is_better: true,
    status: 'better',
    deviation_pct: 4.9,
  },
  {
    metric: 'docs_completeness',
    label: '凭证完整率',
    our_value: 89.0,
    industry_p25: 80.0,
    industry_median: 85.0,
    industry_p75: 92.0,
    unit: '%',
    higher_is_better: true,
    status: 'better',
    deviation_pct: 4.7,
  },
];

const STATUS_STYLE: Record<string, { bg: string; color: string; icon: typeof TrendingUp; label: string }> = {
  better: { bg: 'bg-compliance-50/60 border-compliance-200', color: 'text-compliance-700', icon: TrendingUp, label: '优于行业' },
  on_pace: { bg: 'bg-brand-50/60 border-brand-200', color: 'text-brand-700', icon: TrendingUp, label: '与行业持平' },
  worse: { bg: 'bg-alert-50/60 border-alert-200', color: 'text-alert-700', icon: TrendingDown, label: '弱于行业' },
};

export default function IndustryBenchmark({
  metrics,
  industry = '生物医药',
  period = '2026-06',
}: IndustryBenchmarkProps) {
  const data = useMemo<BenchmarkMetric[]>(() => {
    if (metrics && metrics.length > 0) return metrics;
    return DEFAULT_METRICS;
  }, [metrics]);

  // 综合健康度 = 优于行业的指标占比
  const betterCount = data.filter(m => m.status === 'better').length;
  const onPaceCount = data.filter(m => m.status === 'on_pace').length;
  const worseCount = data.filter(m => m.status === 'worse').length;
  const healthScore = ((betterCount + onPaceCount * 0.5) / data.length) * 100;

  // 雷达图
  const radarOption = {
    tooltip: { trigger: 'item' },
    legend: {
      data: ['我方', '行业中位数', '行业 P75', '行业 P25'],
      textStyle: { color: '#64748b', fontSize: 10 },
      top: 4,
    },
    radar: {
      indicator: data.map(m => ({
        name: m.label,
        // 归一化到 0-100
        max: 100,
      })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#475569', fontSize: 10 },
      splitArea: { areaStyle: { color: ['#fafafa', '#f8fafc'] } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            name: '我方',
            value: data.map(m => normalize(m.our_value, m.industry_p25, m.industry_p75, m.higher_is_better)),
            areaStyle: { color: 'rgba(59,130,246,0.2)' },
            lineStyle: { color: '#3b82f6', width: 2 },
            itemStyle: { color: '#3b82f6' },
          },
          {
            name: '行业中位数',
            value: data.map(() => 50),
            areaStyle: { color: 'rgba(148,163,184,0.05)' },
            lineStyle: { color: '#94a3b8', width: 1, type: 'dashed' as const },
            itemStyle: { color: '#94a3b8' },
          },
          {
            name: '行业 P75',
            value: data.map(m => normalize(m.industry_p75, m.industry_p25, m.industry_p75, m.higher_is_better)),
            lineStyle: { color: '#cbd5e1', width: 1, type: 'dotted' as const },
            itemStyle: { color: '#cbd5e1' },
          },
          {
            name: '行业 P25',
            value: data.map(m => normalize(m.industry_p25, m.industry_p25, m.industry_p75, m.higher_is_better)),
            lineStyle: { color: '#cbd5e1', width: 1, type: 'dotted' as const },
            itemStyle: { color: '#cbd5e1' },
          },
        ],
      },
    ],
  };

  return (
    <div className="space-y-4">
      {/* 顶部健康度卡 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-finance-50/40 border border-finance-200 rounded-xl p-3 text-center">
          <p className="text-[10px] text-surface-500">行业</p>
          <p className="text-sm font-bold text-finance-800">{industry}</p>
        </div>
        <div className="bg-compliance-50/40 border border-compliance-200 rounded-xl p-3 text-center">
          <p className="text-[10px] text-compliance-600">优于行业</p>
          <p className="text-2xl font-bold text-compliance-700 font-display">{betterCount}</p>
        </div>
        <div className="bg-brand-50/40 border border-brand-200 rounded-xl p-3 text-center">
          <p className="text-[10px] text-brand-600">与行业持平</p>
          <p className="text-2xl font-bold text-brand-700 font-display">{onPaceCount}</p>
        </div>
        <div className={clsx('rounded-xl p-3 text-center border',
          worseCount > 0 ? 'bg-alert-50/40 border-alert-200' : 'bg-surface-50/40 border-surface-200'
        )}>
          <p className={clsx('text-[10px]', worseCount > 0 ? 'text-alert-600' : 'text-surface-500')}>
            弱于行业
          </p>
          <p className={clsx('text-2xl font-bold font-display', worseCount > 0 ? 'text-alert-700' : 'text-surface-400')}>
            {worseCount}
          </p>
        </div>
      </div>

      {/* 综合健康度评分 */}
      <div className="rounded-xl border-2 border-finance-200 bg-finance-50/30 p-4">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h4 className="text-sm font-semibold text-finance-800 flex items-center gap-2">
              <Building2 size={14} className="text-finance-600" />
              HCP 合规行业对标健康度
            </h4>
            <p className="text-[11px] text-surface-500 mt-0.5">
              基于 {data.length} 个核心指标（{period}）
            </p>
          </div>
          <div className="text-right">
            <div className={clsx('text-3xl font-bold font-display',
              healthScore >= 80 ? 'text-compliance-700' :
              healthScore >= 60 ? 'text-brand-700' :
              healthScore >= 40 ? 'text-warning-700' : 'text-alert-700'
            )}>
              {healthScore.toFixed(0)}
            </div>
            <div className="text-[10px] text-surface-500">综合得分</div>
          </div>
        </div>
        <div className="h-2 bg-white/60 rounded-full overflow-hidden">
          <motion.div
            className={clsx('h-full rounded-full',
              healthScore >= 80 ? 'bg-compliance-500' :
              healthScore >= 60 ? 'bg-brand-500' :
              healthScore >= 40 ? 'bg-warning-500' : 'bg-alert-500'
            )}
            initial={{ width: 0 }}
            animate={{ width: `${healthScore}%` }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* 雷达图 */}
      <div className="bg-white rounded-xl border border-surface-200/60 p-4">
        <h4 className="text-sm font-semibold text-finance-800 mb-2 flex items-center gap-2">
          <Award size={14} className="text-finance-600" />
          多维行业对标雷达
        </h4>
        <ReactECharts option={radarOption} style={{ height: '300px' }} />
      </div>

      {/* 指标对比列表 */}
      <div className="space-y-2">
        {data.map((m) => {
          const style = STATUS_STYLE[m.status];
          const Icon = style.icon;
          return (
            <motion.div
              key={m.metric}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className={clsx('rounded-xl border p-3', style.bg)}
            >
              <div className="flex items-center gap-3 flex-wrap">
                <Icon size={14} className={style.color} />
                <span className="text-sm font-semibold text-finance-800 flex-1 min-w-0">{m.label}</span>
                <div className="flex items-center gap-3 text-[11px]">
                  <span className="text-surface-500">P25</span>
                  <span className="font-mono text-surface-600">{m.industry_p25}{m.unit}</span>
                  <span className="text-surface-500">中位</span>
                  <span className="font-mono text-surface-600">{m.industry_median}{m.unit}</span>
                  <span className="text-surface-500">P75</span>
                  <span className="font-mono text-surface-600">{m.industry_p75}{m.unit}</span>
                </div>
                <div className="flex items-center gap-2 min-w-[120px] justify-end">
                  <span className={clsx('text-base font-bold font-mono', style.color)}>
                    {m.our_value}{m.unit}
                  </span>
                  <span className={clsx('text-[10px] font-bold px-1.5 py-0.5 rounded', style.color, 'bg-white/60 border border-current/20')}>
                    {m.deviation_pct > 0 ? '+' : ''}{m.deviation_pct.toFixed(1)}%
                  </span>
                </div>
              </div>
              {/* 进度条对比 */}
              <div className="mt-2 relative h-1.5 bg-white/60 rounded-full overflow-hidden">
                {/* P25 - P75 范围 */}
                <div
                  className="absolute h-full bg-surface-200/80 rounded-full"
                  style={{ left: '0%', width: '100%' }}
                />
                {/* 我方位置（基于归一化） */}
                <div
                  className={clsx('absolute h-full w-1.5 rounded-full -translate-x-1/2',
                    m.status === 'better' ? 'bg-compliance-500' :
                    m.status === 'on_pace' ? 'bg-brand-500' : 'bg-alert-500'
                  )}
                  style={{ left: `${normalize(m.our_value, m.industry_p25, m.industry_p75, m.higher_is_better)}%` }}
                />
                {/* 中位数线 */}
                <div className="absolute top-0 bottom-0 w-px bg-surface-400" style={{ left: '50%' }} />
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * 把指标值归一化到 0-100 区间
 * 假设值在 [P25, P75] 范围内
 * higher_is_better=true: 越大越好，所以 P25→0, P75→100
 * higher_is_better=false: 越小越好，所以 P25→100, P75→0（反转）
 */
function normalize(value: number, p25: number, p75: number, higherIsBetter: boolean): number {
  if (p75 === p25) return 50;
  const ratio = ((value - p25) / (p75 - p25)) * 100;
  const clamped = Math.max(0, Math.min(100, ratio));
  return higherIsBetter ? clamped : 100 - clamped;
}

// ── 风险预警面板 ─────────────────────────────────────────

export interface RiskAlert {
  alert_id: string;
  hcp_name: string;
  risk_type: 'overrun' | 'delay' | 'missing_doc' | 'frequency' | 'amount' | 'venue';
  risk_level: 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  amount?: number;
  deadline?: string;
  occurred_at: string;
  action_required?: string;
}

export interface RiskAlertPanelProps {
  alerts: RiskAlert[] | null;
  loading?: boolean;
  onResolve?: (alertId: string) => void;
}

const RISK_TYPE_STYLE: Record<string, { icon: typeof AlertCircle; label: string; color: string }> = {
  overrun: { icon: TrendingUp, label: '超额', color: 'text-alert-600' },
  delay: { icon: Clock, label: '延期', color: 'text-warning-600' },
  missing_doc: { icon: FileWarning, label: '缺凭证', color: 'text-amber-600' },
  frequency: { icon: AlertCircle, label: '频次异常', color: 'text-orange-600' },
  amount: { icon: AlertTriangle, label: '金额异常', color: 'text-rose-600' },
  venue: { icon: Building2, label: '场地异常', color: 'text-purple-600' },
};

const RISK_LEVEL_STYLE: Record<string, { bg: string; border: string; badge: string }> = {
  high: { bg: 'bg-alert-50/60', border: 'border-alert-300', badge: 'bg-alert-100 text-alert-700 border-alert-300' },
  medium: { bg: 'bg-warning-50/60', border: 'border-warning-300', badge: 'bg-warning-100 text-warning-700 border-warning-300' },
  low: { bg: 'bg-surface-50/60', border: 'border-surface-300', badge: 'bg-surface-100 text-surface-600 border-surface-300' },
};

// 内置示例告警（无后端时使用）
const DEFAULT_ALERTS: RiskAlert[] = [
  {
    alert_id: 'ALT-001',
    hcp_name: '张教授（北医三院）',
    risk_type: 'overrun',
    risk_level: 'high',
    title: '本季度 HCP 接待费用已超出预算 45%',
    detail: 'Q2 累计 ¥58,000，年度预算 ¥40,000。建议立即冻结新增接待并启动复核。',
    amount: 58000,
    occurred_at: '2026-06-20',
    action_required: '冻结新增 / 财务BP复核',
  },
  {
    alert_id: 'ALT-002',
    hcp_name: '李主任（协和医院）',
    risk_type: 'missing_doc',
    risk_level: 'medium',
    title: '3 笔报销缺少签到表或合规确认单',
    detail: '涉及金额 ¥12,500，需在 7 日内补齐凭证否则影响结账。',
    amount: 12500,
    deadline: '2026-06-28',
    occurred_at: '2026-06-18',
    action_required: '补齐凭证',
  },
  {
    alert_id: 'ALT-003',
    hcp_name: '王院长（同仁医院）',
    risk_type: 'frequency',
    risk_level: 'high',
    title: '近 30 天 HCP 互动频次达 8 次，超出合规上限',
    detail: '合规上限为 4 次/月，需评估是否构成不当互动。',
    occurred_at: '2026-06-15',
    action_required: '合规官介入核查',
  },
  {
    alert_id: 'ALT-004',
    hcp_name: '陈博士（阜外医院）',
    risk_type: 'venue',
    risk_level: 'medium',
    title: '会议场地为五星级酒店，单价超出公司标准',
    detail: '场地单价 ¥3,500/人，超出公司规定（≤¥2,000/人）。',
    amount: 28000,
    occurred_at: '2026-06-12',
    action_required: '场地变更 / 补特批',
  },
  {
    alert_id: 'ALT-005',
    hcp_name: '赵教授（301医院）',
    risk_type: 'delay',
    risk_level: 'low',
    title: '5 月份 HCP 接待备案延期提交',
    detail: '应于 5 月 31 日前提交，实际 6 月 8 日提交，延期 8 天。',
    occurred_at: '2026-06-08',
    action_required: '提醒备案责任人',
  },
  {
    alert_id: 'ALT-006',
    hcp_name: '刘教授（湘雅医院）',
    risk_type: 'amount',
    risk_level: 'high',
    title: '单笔礼品价值 ¥1,200，超出 ¥500 上限',
    detail: '根据公司礼品政策，单次礼品价值不得超过 ¥500。建议回收并整改。',
    amount: 1200,
    occurred_at: '2026-06-05',
    action_required: '礼品回收 / 责任人约谈',
  },
];

export function RiskAlertPanel({ alerts, loading, onResolve }: RiskAlertPanelProps) {
  const data = alerts && alerts.length > 0 ? alerts : DEFAULT_ALERTS;
  const highCount = data.filter(a => a.risk_level === 'high').length;
  const mediumCount = data.filter(a => a.risk_level === 'medium').length;
  const lowCount = data.filter(a => a.risk_level === 'low').length;

  if (loading) {
    return (
      <div className="text-center py-10 text-surface-400 text-sm">
        <div className="inline-block w-5 h-5 border-2 border-finance-500 border-t-transparent rounded-full animate-spin mr-2" />
        正在扫描风险…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 顶部统计 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-finance-50/40 border border-finance-200 rounded-xl p-3 text-center">
          <p className="text-[10px] text-surface-500">告警总数</p>
          <p className="text-2xl font-bold text-finance-800 font-display">{data.length}</p>
        </div>
        <div className="bg-alert-50/40 border border-alert-200 rounded-xl p-3 text-center">
          <p className="text-[10px] text-alert-600">高风险</p>
          <p className="text-2xl font-bold text-alert-700 font-display">{highCount}</p>
        </div>
        <div className="bg-warning-50/40 border border-warning-200 rounded-xl p-3 text-center">
          <p className="text-[10px] text-warning-600">中风险</p>
          <p className="text-2xl font-bold text-warning-700 font-display">{mediumCount}</p>
        </div>
        <div className="bg-surface-50/40 border border-surface-200 rounded-xl p-3 text-center">
          <p className="text-[10px] text-surface-500">低风险</p>
          <p className="text-2xl font-bold text-surface-600 font-display">{lowCount}</p>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="p-8 rounded-xl border border-dashed border-compliance-200 bg-compliance-50/30 text-center">
          <ShieldAlert size={20} className="mx-auto mb-2 text-compliance-400" />
          <p className="text-sm text-compliance-700 font-semibold">当前无 HCP 风险告警</p>
          <p className="text-[11px] text-surface-500 mt-1">系统已扫描所有 HCP 互动记录，未发现异常</p>
        </div>
      ) : (
        <div className="space-y-2">
          {data.map((alert) => {
            const typeStyle = RISK_TYPE_STYLE[alert.risk_type] || RISK_TYPE_STYLE.overrun;
            const levelStyle = RISK_LEVEL_STYLE[alert.risk_level] || RISK_LEVEL_STYLE.low;
            const TIcon = typeStyle.icon;
            return (
              <motion.div
                key={alert.alert_id}
                initial={{ opacity: 0, x: -4 }}
                animate={{ opacity: 1, x: 0 }}
                className={clsx('rounded-xl border-2 p-3', levelStyle.bg, levelStyle.border)}
              >
                <div className="flex items-start gap-3">
                  <TIcon size={16} className={clsx('shrink-0 mt-0.5', typeStyle.color)} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h4 className="text-sm font-semibold text-finance-800">{alert.title}</h4>
                      <span className={clsx('px-1.5 py-0.5 rounded text-[10px] font-bold border', levelStyle.badge)}>
                        {alert.risk_level === 'high' ? '高风险' : alert.risk_level === 'medium' ? '中风险' : '低风险'}
                      </span>
                      <span className="text-[10px] text-surface-500 px-1.5 py-0.5 rounded bg-white/60 border border-surface-200">
                        {typeStyle.label}
                      </span>
                    </div>
                    <p className="text-[11px] text-surface-500 mb-1.5">
                      <b className="text-surface-700">涉及：</b>{alert.hcp_name}
                    </p>
                    <p className="text-xs text-surface-700 leading-relaxed">{alert.detail}</p>
                    <div className="flex items-center gap-3 mt-2 text-[10px] text-surface-500 flex-wrap">
                      <span>告警 ID：<span className="font-mono">{alert.alert_id}</span></span>
                      <span>发生：{alert.occurred_at}</span>
                      {alert.deadline && (
                        <span className="text-warning-700 font-semibold">截止：{alert.deadline}</span>
                      )}
                      {alert.amount && (
                        <span>金额：<b className="text-finance-700">¥{alert.amount.toLocaleString()}</b></span>
                      )}
                    </div>
                    {alert.action_required && (
                      <div className="mt-2 flex items-center gap-2 p-1.5 rounded bg-white/60 border border-finance-200/60">
                        <XCircle size={12} className="text-finance-600 shrink-0" />
                        <span className="text-[11px] text-finance-800 font-medium">建议动作：{alert.action_required}</span>
                        {onResolve && (
                          <button
                            onClick={() => onResolve(alert.alert_id)}
                            className="ml-auto text-[10px] px-2 py-0.5 rounded bg-finance-600 hover:bg-finance-700 text-white font-medium transition-colors"
                          >
                            标记已处理
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
