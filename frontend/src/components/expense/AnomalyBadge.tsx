import { clsx } from 'clsx';
import { AlertTriangle, AlertCircle, Info, CheckCircle2 } from 'lucide-react';

export type AnomalySeverity = 'high' | 'medium' | 'low';
export type RiskBand = 'critical' | 'high' | 'medium' | 'low';

interface AnomalyBadgeProps {
  severity: AnomalySeverity;
  type?: string;
  count?: number;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const SEVERITY_CONFIG: Record<AnomalySeverity, {
  label: string;
  cls: string;
  icon: React.ComponentType<{ className?: string }>;
}> = {
  high: { label: '高', cls: 'bg-alert-100 text-alert-700 border-alert-300', icon: AlertTriangle },
  medium: { label: '中', cls: 'bg-warning-100 text-warning-700 border-warning-300', icon: AlertCircle },
  low: { label: '低', cls: 'bg-compliance-100 text-compliance-700 border-compliance-300', icon: Info },
};

const TYPE_LABELS: Record<string, string> = {
  single_amount: '金额异常',
  single_category: '品类异常',
  group_center: '中心异常',
  group_category: '品类群体',
  trend_period: '趋势异常',
  frequency: '频次异常',
  timing: '时段异常',
  duplicate_suspect: '疑似重复',
};

export function AnomalyBadge({
  severity,
  type,
  count,
  showLabel = true,
  size = 'md',
  className,
}: AnomalyBadgeProps) {
  const config = SEVERITY_CONFIG[severity];
  const Icon = config.icon;
  const typeLabel = type ? TYPE_LABELS[type] || type : '';

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full border font-medium',
        config.cls,
        size === 'sm' && 'px-1.5 py-0.5 text-xs',
        size === 'md' && 'px-2 py-0.5 text-xs',
        size === 'lg' && 'px-3 py-1 text-sm',
        className,
      )}
      title={typeLabel}
    >
      <Icon className={clsx(size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
      {showLabel && (
        <span>
          {config.label}
          {typeLabel && <span className="ml-1 opacity-80">· {typeLabel}</span>}
          {count != null && count > 1 && <span className="ml-1">×{count}</span>}
        </span>
      )}
    </span>
  );
}

interface RiskScoreBadgeProps {
  band: RiskBand;
  score: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const BAND_CONFIG: Record<RiskBand, {
  label: string;
  cls: string;
  icon: React.ComponentType<{ className?: string }>;
}> = {
  critical: { label: '严重', cls: 'bg-alert-600 text-white border-alert-700', icon: AlertTriangle },
  high: { label: '高风险', cls: 'bg-alert-100 text-alert-700 border-alert-300', icon: AlertTriangle },
  medium: { label: '中风险', cls: 'bg-warning-100 text-warning-700 border-warning-300', icon: AlertCircle },
  low: { label: '低风险', cls: 'bg-compliance-100 text-compliance-700 border-compliance-300', icon: CheckCircle2 },
};

export function RiskScoreBadge({ band, score, size = 'md', className }: RiskScoreBadgeProps) {
  const config = BAND_CONFIG[band];
  const Icon = config.icon;

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-full border font-medium',
        config.cls,
        size === 'sm' && 'px-1.5 py-0.5 text-xs',
        size === 'md' && 'px-2.5 py-0.5 text-xs',
        size === 'lg' && 'px-3 py-1 text-sm',
        className,
      )}
      title={`风险评分 ${score}`}
    >
      <Icon className={clsx(size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
      <span>{config.label}</span>
      <span className="opacity-80">({score.toFixed(1)})</span>
    </span>
  );
}
