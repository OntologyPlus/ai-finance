/**
 * DiagnosisCardGrid — 9 张卡九宫格（3×3，紧凑视图）
 * v4.0 新增：第一部分"经营全景"的紧凑展示
 */
import { clsx } from 'clsx';
import SignalLightBadge, { SignalLight } from './SignalLightBadge';

export interface DiagnosisCardMini {
  card_type: string;
  card_name: string;
  card_number: number;
  signal_light: SignalLight | string;
  light_reason?: string;
  judgment?: string;
  framework?: string;
}

export interface DiagnosisCardGridProps {
  cards: DiagnosisCardMini[];
  onCardClick?: (card: DiagnosisCardMini) => void;
  className?: string;
}

export default function DiagnosisCardGrid({
  cards,
  onCardClick,
  className,
}: DiagnosisCardGridProps) {
  if (!cards || cards.length === 0) {
    return (
      <div className="p-6 rounded-xl border border-surface-200 bg-white text-center text-surface-400 text-sm">
        暂无诊断卡数据
      </div>
    );
  }

  return (
    <div
      className={clsx(
        'grid grid-cols-3 gap-2.5',
        className,
      )}
    >
      {cards.map((card) => (
        <button
          key={card.card_type}
          onClick={() => onCardClick?.(card)}
          className="group p-3 rounded-xl border border-surface-200 bg-white hover:border-brand-300 hover:shadow-md transition-all text-left"
        >
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[10px] font-mono text-surface-400">
              卡 {card.card_number}
            </span>
            <SignalLightBadge light={card.signal_light} size="sm" />
          </div>
          <h4 className="text-xs font-semibold text-finance-800 group-hover:text-brand-700 transition-colors line-clamp-1">
            {card.card_name}
          </h4>
          {card.judgment && (
            <p className="text-[11px] text-surface-500 mt-1 line-clamp-2 leading-relaxed">
              {card.judgment}
            </p>
          )}
        </button>
      ))}
    </div>
  );
}
