/**
 * SignalLightBadge — 🔴/🟡/🟢 信号灯徽章
 * v4.0 新增：9 张诊断卡的健康度指示
 */
import { clsx } from 'clsx';

export type SignalLight = 'red' | 'yellow' | 'green';

export interface SignalLightBadgeProps {
  light: SignalLight | string;
  reason?: string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

const COLOR_MAP: Record<string, { bg: string; text: string; ring: string; label: string; icon: string }> = {
  red: {
    bg: 'bg-alert-50',
    text: 'text-alert-700',
    ring: 'ring-alert-200',
    label: '红灯',
    icon: '🔴',
  },
  yellow: {
    bg: 'bg-warning-50',
    text: 'text-warning-700',
    ring: 'ring-warning-200',
    label: '黄灯',
    icon: '🟡',
  },
  green: {
    bg: 'bg-compliance-50',
    text: 'text-compliance-700',
    ring: 'ring-compliance-200',
    label: '绿灯',
    icon: '🟢',
  },
};

const SIZE_MAP = {
  sm: 'text-[10px] px-1.5 py-0.5',
  md: 'text-xs px-2 py-0.5',
  lg: 'text-sm px-2.5 py-1',
};

export default function SignalLightBadge({
  light,
  reason,
  size = 'md',
  showLabel = false,
  className,
}: SignalLightBadgeProps) {
  const color = COLOR_MAP[light] || COLOR_MAP.green;
  const sizeCls = SIZE_MAP[size];

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-md ring-1 font-medium',
        color.bg,
        color.text,
        color.ring,
        sizeCls,
        className,
      )}
      title={reason || color.label}
    >
      <span className="text-[10px] leading-none">{color.icon}</span>
      {showLabel && <span>{color.label}</span>}
    </span>
  );
}
