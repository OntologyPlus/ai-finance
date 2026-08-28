/**
 * DiagnosisCard — 单张诊断卡（折叠面板 + 四段式）
 * v4.0 新增：第二部分"9 张经营诊断卡"
 *
 * 四段式：判断 → 证据 → 根因 → 建议
 */
import { useState } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import SignalLightBadge, { SignalLight } from './SignalLightBadge';

export interface DiagnosisCardData {
  id?: string;
  card_type: string;
  card_number: number;
  card_name: string;
  signal_light: SignalLight | string;
  light_reason?: string;
  judgment?: string;        // 1. 核心判断
  evidence?: string;        // 2. 数据证据
  root_cause?: string;      // 3. 根因分析
  actions?: string;         // 4. 行动建议
  pending_question?: string;
  framework_ref?: string;
  ai_quality_level?: string;
  metrics_json?: Record<string, any>;
  threshold_json?: Record<string, any>;
}

export interface DiagnosisCardProps {
  card: DiagnosisCardData;
  defaultExpanded?: boolean;
}

export default function DiagnosisCard({ card, defaultExpanded = false }: DiagnosisCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const isRed = card.signal_light === 'red';
  const isYellow = card.signal_light === 'yellow';
  const isDegraded = card.ai_quality_level === 'L2' || card.ai_quality_level === 'L1';

  return (
    <div
      className={clsx(
        'rounded-xl border bg-white overflow-hidden transition-all',
        isRed
          ? 'border-alert-200 shadow-sm'
          : isYellow
          ? 'border-warning-200'
          : 'border-surface-200',
      )}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-surface-50 transition-colors"
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <span className="text-[10px] font-mono text-surface-400 flex-shrink-0">
            卡 {card.card_number}
          </span>
          <h3 className="text-sm font-semibold text-finance-800 flex-shrink-0">
            {card.card_name}
          </h3>
          <SignalLightBadge
            light={card.signal_light}
            reason={card.light_reason}
            size="sm"
            showLabel
          />
          {card.framework_ref && (
            <span className="hidden md:inline text-[10px] px-1.5 py-0.5 rounded bg-brand-50 text-brand-600 font-medium">
              {card.framework_ref}
            </span>
          )}
          {isDegraded && (
            <span className="hidden md:inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-surface-100 text-surface-500">
              <AlertTriangle size={10} />
              降级版
            </span>
          )}
          {card.judgment && !expanded && (
            <span className="hidden lg:inline text-xs text-surface-500 truncate flex-1 ml-2">
              {card.judgment}
            </span>
          )}
        </div>
        {expanded ? <ChevronUp size={16} className="text-surface-400" /> : <ChevronDown size={16} className="text-surface-400" />}
      </button>

      {/* Body — 四段式 */}
      {expanded && (
        <div className="border-t border-surface-100 p-4 space-y-3">
          {!card.judgment && !card.evidence && !card.root_cause && !card.actions && (
            <div className="text-center text-surface-400 text-sm py-4">暂无数据</div>
          )}

          {card.judgment && (
            <Section title="1. 核心判断" tone="primary">
              {card.judgment}
            </Section>
          )}

          {card.evidence && (
            <Section title="2. 数据证据" tone="info">
              {card.evidence}
            </Section>
          )}

          {card.root_cause && (
            <Section title="3. 根因分析" tone="warning">
              {card.root_cause}
            </Section>
          )}

          {card.actions && (
            <Section title="4. 行动建议" tone="success">
              {card.actions}
            </Section>
          )}

          {card.pending_question && (
            <div className="mt-3 px-3 py-2 rounded-lg bg-warning-50 border border-warning-200 text-xs text-warning-800">
              <span className="font-semibold">待确认：</span>
              {card.pending_question}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  children,
  tone,
}: {
  title: string;
  children: React.ReactNode;
  tone: 'primary' | 'info' | 'warning' | 'success';
}) {
  const TONE_STYLE: Record<string, string> = {
    primary: 'border-l-brand-500',
    info: 'border-l-blue-400',
    warning: 'border-l-warning-500',
    success: 'border-l-compliance-500',
  };
  return (
    <div className={clsx('pl-3 border-l-2', TONE_STYLE[tone])}>
      <div className="text-[11px] font-semibold text-surface-500 mb-0.5">{title}</div>
      <div className="text-sm text-finance-700 leading-relaxed whitespace-pre-wrap">{children}</div>
    </div>
  );
}
