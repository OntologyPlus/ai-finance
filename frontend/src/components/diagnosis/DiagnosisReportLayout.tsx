/**
 * DiagnosisReportLayout — 4 部分整体布局容器
 * v4.0 新增；v9.0 重构：移除 9 卡信号灯九宫格重复，改为 1-9 卡一句话摘要
 *
 * 第一部分：经营全景（杜邦 + Top 判断 + 9 卡一句话摘要）
 * 第二部分：9 张诊断卡（详细展示）
 * 第三部分：产品组合（BCG）
 * 第四部分：行动建议（SAR）
 */
import { useState } from 'react';
import { ChevronDown, ChevronUp, Loader2, Sparkles } from 'lucide-react';
import { clsx } from 'clsx';
import DiagnosisCard, { DiagnosisCardData } from './DiagnosisCard';
import DupontWaterfallChart, { DupontData } from './DupontWaterfallChart';
import BCGMatrixChart, { BCGData } from './BCGMatrixChart';
import SARActionList, { SARAction } from './SARActionList';
import TopJudgmentsList, { Judgment } from './TopJudgmentsList';
import SignalLightBadge, { SignalLight } from './SignalLightBadge';

export interface DiagnosisReport {
  period: string;
  part1_overview?: {
    dupont?: DupontData;
    top_judgments?: Judgment[];
  };
  part2_cards?: DiagnosisCardData[];
  part3_bcg?: BCGData;
  part4_sar?: { actions?: SARAction[] };
  status?: string;
}

export interface DiagnosisReportLayoutProps {
  report: DiagnosisReport | null;
  loading?: boolean;
  onCardClick?: (card: DiagnosisCardData) => void;
  onActionClick?: (action: SARAction) => void;
}

export default function DiagnosisReportLayout({
  report,
  loading,
  onCardClick,
  onActionClick,
}: DiagnosisReportLayoutProps) {
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    part1: true,
    part2: true,
    part3: false,
    part4: false,
  });

  const toggle = (key: string) =>
    setExpandedSections((prev) => ({ ...prev, [key]: !prev[key] }));

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500 mb-3" />
        <p className="text-sm text-surface-500">正在生成诊断报告...</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="p-8 rounded-xl border border-dashed border-surface-300 bg-white/50 text-center">
        <Sparkles className="w-8 h-8 mx-auto mb-2 text-surface-300" />
        <p className="text-sm text-surface-500">请选择期间后点击"生成报告"</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Section
        title="第一部分：经营全景诊断"
        expanded={expandedSections.part1}
        onToggle={() => toggle('part1')}
        accent="brand"
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <DupontWaterfallChart data={report.part1_overview?.dupont || { layers: [] }} />
          <TopJudgmentsList
            judgments={report.part1_overview?.top_judgments || []}
            title="Top 核心判断"
          />
        </div>
        {/* v9.0: 9 卡一句话摘要（无信号灯九宫格，避免与第二部分重复） */}
        {report.part2_cards && report.part2_cards.length > 0 && (
          <div className="mt-4 p-4 rounded-xl border border-surface-200 bg-surface-50/40">
            <h4 className="text-xs font-semibold text-surface-600 mb-2.5">摘要</h4>
            <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {report.part2_cards.map((card) => (
                <li
                  key={card.card_type}
                  onClick={() => onCardClick?.(card)}
                  className="flex items-start gap-2 px-2.5 py-2 rounded-lg bg-white border border-surface-200 hover:border-brand-300 hover:shadow-sm transition-all cursor-pointer"
                >
                  <span className="shrink-0 mt-0.5">
                    <SignalLightBadge light={card.signal_light as SignalLight} size="sm" />
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-semibold text-finance-800 truncate">
                      卡 {card.card_number} · {card.card_name}
                    </p>
                    <p className="text-[11px] text-surface-500 mt-0.5 line-clamp-2 leading-relaxed">
                      {card.judgment || '数据待补充'}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      <Section
        title={`第二部分：经营诊断卡`}
        expanded={expandedSections.part2}
        onToggle={() => toggle('part2')}
        accent="finance"
      >
        {report.part2_cards && report.part2_cards.length > 0 ? (
          <div className="space-y-2">
            {report.part2_cards.map((card) => (
              <DiagnosisCard key={card.card_type} card={card} />
            ))}
          </div>
        ) : (
          <div className="p-6 text-center text-surface-400 text-sm">暂无诊断卡数据</div>
        )}
      </Section>

      <Section
        title="第三部分：产品组合诊断（BCG）"
        expanded={expandedSections.part3}
        onToggle={() => toggle('part3')}
        accent="brand"
      >
        <BCGMatrixChart data={report.part3_bcg || { products: [] }} />
      </Section>

      <Section
        title="第四部分：行动建议（SAR）"
        expanded={expandedSections.part4}
        onToggle={() => toggle('part4')}
        accent="compliance"
      >
        {report.part4_sar?.actions && report.part4_sar.actions.length > 0 ? (
          <SARActionList actions={report.part4_sar.actions} />
        ) : (
          <div className="p-6 text-center text-surface-400 text-sm">暂无行动建议</div>
        )}
      </Section>
    </div>
  );
}

function Section({
  title,
  expanded,
  onToggle,
  children,
  accent,
}: {
  title: string;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  accent: 'brand' | 'finance' | 'compliance';
}) {
  const ACCENT_BG: Record<string, string> = {
    brand: 'bg-brand-50 text-brand-700',
    finance: 'bg-finance-50 text-finance-700',
    compliance: 'bg-compliance-50 text-compliance-700',
  };
  return (
    <div className="rounded-xl border border-surface-200 bg-white overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-surface-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              'text-[10px] font-bold px-2 py-0.5 rounded-md',
              ACCENT_BG[accent],
            )}
          >
            {title.split('：')[0]}
          </span>
          <h2 className="text-sm font-semibold text-finance-800">
            {title.split('：')[1] || title}
          </h2>
        </div>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {expanded && <div className="border-t border-surface-100 p-4">{children}</div>}
    </div>
  );
}
