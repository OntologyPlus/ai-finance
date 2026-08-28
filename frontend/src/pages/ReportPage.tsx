import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  FileText,
  Download,
  Eye,
  Calendar,
  Clock,
  X,
  ArrowLeftRight,
  Brain,
  Loader2,
  Sparkles,
  FileSearch,
  Activity,
  TrendingUp,
} from 'lucide-react';
import { clsx } from 'clsx';
import { reportApi, cutoffApi } from '../services/api';
import { useAppStore } from '../store';
import { AiExplainPanel, RootCauseTree } from '../components/ai';

const TABS = ['月度快报', '季度汇报', '年度复盘', 'AI智能报表'] as const;

const TAB_TYPE_MAP: Record<string, string> = {
  '月度快报': 'monthly_flash',
  '季度汇报': 'quarterly',
  '年度复盘': 'annual_review',
};

const DEADLINE_MAP: Record<string, number> = {
  '月度快报': 5,
  '季度汇报': 8,
  '年度复盘': 10,
};

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  draft: { label: '草稿', cls: 'badge-blue' },
  submitted: { label: '已提交', cls: 'badge-amber' },
  reviewed: { label: '已审阅', cls: 'badge-purple' },
  finalized: { label: '已定稿', cls: 'badge-green' },
};

export default function ReportPage() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [activeTab, setActiveTab] = useState<typeof TABS[number]>('月度快报');
  const [selectedPeriod, setSelectedPeriod] = useState(() => new Date().toISOString().slice(0, 7));
  const [viewingReport, setViewingReport] = useState<any | null>(null);
  const [viewContent, setViewContent] = useState<string>('');
  const [caliberType, setCaliberType] = useState<'management' | 'financial' | 'comparison'>('management');
  const [caliberData, setCaliberData] = useState<any>(null);
  const [caliberLoading, setCaliberLoading] = useState(false);
  const [cutoffStatus, setCutoffStatus] = useState<any>(null);

  // v12.1 阶段 7: AI 智能报表状态
  const [aiHealth, setAiHealth] = useState<any>(null);
  const [aiAnomalies, setAiAnomalies] = useState<any>(null);
  const [aiInterpret, setAiInterpret] = useState<any>(null);
  const [aiCrossPeriod, setAiCrossPeriod] = useState<any>(null);
  const [aiReportLoading, setAiReportLoading] = useState(false);
  const [aiReportCenter, setAiReportCenter] = useState<string>('');
  const [aiReportPeriod, setAiReportPeriod] = useState<string>(new Date().toISOString().slice(0, 7));

  const runReportAi = async () => {
    setAiReportLoading(true);
    try {
      const center = aiReportCenter.trim() || undefined;
      const period = aiReportPeriod.trim() || new Date().toISOString().slice(0, 7);
      const [hlth, anom, interp, cross, tmpl] = await Promise.all([
        reportApi.aiHealthSummary({ center_id: center }).catch(() => null),
        reportApi.aiReportAnomalies({ period }).catch(() => null),
        reportApi.aiReportInterpret({ center_id: center || '财经中心', period }).catch(() => null),
        reportApi.aiCrossPeriodCompare({
          center_id: center || '财经中心',
          current_period: period,
          previous_period: prevPeriodOf(period),
        }).catch(() => null),
        reportApi.aiGenerateReportTemplate({ report_type: '月报', center_id: center }).catch(() => null),
      ]);
      if (hlth?.success) setAiHealth(hlth.data);
      if (anom?.success) setAiAnomalies(anom.data);
      if (interp?.success) setAiInterpret(interp.data);
      if (cross?.success) setAiCrossPeriod(cross.data);
      // 模板可放 console 或 UI 提示
      if (tmpl?.success) console.log('报表模板:', tmpl.data);
    } catch (error) {
      console.error('AI report failed:', error);
    } finally {
      setAiReportLoading(false);
    }
  };

  // 计算上月同期
  function prevPeriodOf(period: string): string {
    try {
      const [y, m] = period.split('-').map(Number);
      if (!y || !m) return period;
      const prev = m === 1 ? { y: y - 1, m: 12 } : { y, m: m - 1 };
      return `${prev.y}-${String(prev.m).padStart(2, '0')}`;
    } catch {
      return period;
    }
  }
  const addToast = useAppStore((s) => s.addToast);

  // v12.0: 加载截点状态
  const fetchCutoffStatus = async () => {
    try {
      const res = await cutoffApi.getStatus();
      if (res.success && res.data) setCutoffStatus(res.data);
    } catch (e) {
      // Non-blocking
    }
  };

  useEffect(() => {
    fetchCutoffStatus();
    // 每 60 秒刷新一次
    const t = setInterval(fetchCutoffStatus, 60_000);
    return () => clearInterval(t);
  }, []);

  const fetchData = async () => {
    try {
      const reportType = TAB_TYPE_MAP[activeTab];
      const response = await reportApi.getReports({ report_type: reportType });
      setReports(response.data || []);
    } catch (error: any) {
      addToast({ type: 'error', title: '获取报表数据失败', message: error.message });
      setReports([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const handleGenerate = async (report?: any) => {
    try {
      const period = selectedPeriod;
      if (report) {
        // Generate for a specific draft report
        const reportType = TAB_TYPE_MAP[activeTab];
        if (reportType === 'monthly_flash') {
          await reportApi.monthlyFlash({ period });
        } else if (reportType === 'quarterly') {
          await reportApi.quarterly({ period });
        } else if (reportType === 'annual_review') {
          await reportApi.annualReview({ period });
        }
      } else {
        if (activeTab === '月度快报') {
          await reportApi.monthlyFlash({ period });
        } else if (activeTab === '季度汇报') {
          await reportApi.quarterly({ period });
        } else if (activeTab === '年度复盘') {
          await reportApi.annualReview({ period });
        }
      }
      addToast({ type: 'success', title: '操作成功', message: '报表已生成' });
      fetchData();
    } catch (error: any) {
      addToast({ type: 'error', title: '生成报表失败', message: error.message });
    }
    setShowGenerateModal(false);
  };

  const handleView = async (report: any) => {
    try {
      const response = await reportApi.getReport(report.report_id);
      const content = response.data?.content || report.content || '';
      // If content is JSON string, try to format it as markdown
      let markdownContent = '';
      try {
        const parsed = JSON.parse(content);
        markdownContent = jsonToMarkdown(parsed, report);
      } catch {
        markdownContent = content || '（无内容）';
      }
      setViewContent(markdownContent);
      setViewingReport(report);
      // Fetch caliber comparison data
      setCaliberLoading(true);
      try {
        const period = report.period || selectedPeriod;
        const caliberResp = await reportApi.caliberComparison(period);
        setCaliberData(caliberResp.data);
      } catch (err: any) {
        // Non-blocking: caliber data is optional
        setCaliberData(null);
      } finally {
        setCaliberLoading(false);
      }
    } catch (error: any) {
      addToast({ type: 'error', title: '获取报表内容失败', message: error.message });
    }
  };

  const jsonToMarkdown = (data: any, report: any): string => {
    let md = `# ${report.title || report.report_id}\n\n`;
    md += `**期间**: ${report.period || '-'}  \n`;
    md += `**状态**: ${STATUS_MAP[report.status]?.label || report.status}  \n\n`;

    if (data.execution_rates) {
      md += `## 执行率\n\n`;
      md += `| 科目 | 月度执行率 | 累计执行率 | 年度执行率 |\n`;
      md += `|------|-----------|-----------|----------|\n`;
      for (const r of data.execution_rates) {
        md += `| ${r.l1_code || '-'} | ${r.monthly_rate ?? '-'}% | ${r.cumulative_rate ?? '-'}% | ${r.annual_rate ?? '-'}% |\n`;
      }
      md += `\n`;
    }

    if (data.quadrant_compliance) {
      md += `## 象限合规\n\n`;
      for (const q of data.quadrant_compliance) {
        md += `- **${q.quadrant}**: 实际执行率 ${q.actual_rate ?? '-'}%, 期望 ${q.expected_rate ?? '-'}%, ${q.compliant ? '✅ 合规' : '⚠️ 偏离'}\n`;
      }
      md += `\n`;
    }

    if (data.gap_analysis) {
      md += `## 3GAP分析\n\n`;
      md += `- GAP1 (目标差距): ${data.gap_analysis.gap1 ?? '-'}\n`;
      md += `- GAP2 (执行差距): ${data.gap_analysis.gap2 ?? '-'}\n`;
      md += `- GAP3 (预测变动): ${data.gap_analysis.gap3 ?? '-'}\n\n`;
    }

    if (data.list_classification) {
      md += `## 三单分类\n\n`;
      md += `- **类型**: ${data.list_classification.type || '-'}\n`;
      md += `- **项目**: ${data.list_classification.item_name || '-'}\n`;
      md += `- **行动计划**: ${data.list_classification.action_plan || '-'}\n\n`;
    }

    if (data.alert_closure_tracking) {
      md += `## 预警闭环跟踪\n\n`;
      md += `- 总闭环数: ${data.alert_closure_tracking.total_closures ?? 0}\n`;
      md += `- 已闭环: ${data.alert_closure_tracking.closed ?? 0}\n`;
      md += `- 待闭环: ${data.alert_closure_tracking.pending ?? 0}\n`;
    }

    return md;
  };

  const handleDownload = async (report: any) => {
    try {
      const response = await reportApi.getReport(report.report_id);
      const content = response.data?.content || report.content || '';
      let textContent = '';
      try {
        const parsed = JSON.parse(content);
        textContent = jsonToMarkdown(parsed, report);
      } catch {
        textContent = content || '';
      }
      const blob = new Blob([textContent], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${report.title || report.report_id}_${report.period || 'report'}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      addToast({ type: 'success', title: '下载成功', message: '报表已下载' });
    } catch (error: any) {
      addToast({ type: 'error', title: '下载失败', message: error.message });
    }
  };

  const deadline = DEADLINE_MAP[activeTab];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">报表中心</h1>
        <p className="text-sm text-surface-400 mt-1">月度快报/季度汇报/年度复盘/经营分析会材料管理</p>
      </div>

      {/* v12.0: 5/8/10/12 截点日历 */}
      {cutoffStatus && (
        <div className="glass-card p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-finance-500" />
              <span className="text-xs font-semibold text-finance-700">
                截点日历（{cutoffStatus.period}）
              </span>
              <span className="text-[10px] text-surface-400">· 02:00 自动出具</span>
            </div>
            <button
              onClick={fetchCutoffStatus}
              className="text-[10px] text-surface-400 hover:text-finance-600"
            >
              刷新
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {cutoffStatus.cutoffs?.map((c: any) => {
              const isGenerated = c.status === 'generated';
              return (
                <div
                  key={c.day}
                  className={clsx(
                    'p-3 rounded-lg border',
                    isGenerated
                      ? 'border-compliance-200 bg-compliance-50/60'
                      : 'border-surface-200 bg-surface-50'
                  )}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className={clsx(
                      'text-2xl font-bold font-display',
                      isGenerated ? 'text-compliance-600' : 'text-surface-400'
                    )}>
                      {c.day}
                    </span>
                    <span className="text-[10px] text-surface-400">日</span>
                    {isGenerated ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-compliance-100 text-compliance-700 font-medium">
                        ✓ 已出具
                      </span>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-100 text-surface-500">
                        ⏳ 等待
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] font-medium text-finance-800">{c.name}</p>
                  <p className="text-[10px] text-surface-500 font-mono mt-0.5">{c.code}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {TABS.map(tab => {
          const isCurrentTab = tab === activeTab;
          return (
            <div key={tab} className="glass-card p-4 cursor-pointer" onClick={() => setActiveTab(tab)}>
              <div className="flex items-center justify-between mb-2">
                <p className="metric-label">{tab}</p>
                <span className="text-xs text-surface-400">截止: {DEADLINE_MAP[tab]}日</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-lg font-bold text-surface-800 font-display">
                  {isCurrentTab ? reports.length : '-'}
                </span>
                <span className="text-xs text-surface-400">份</span>
                {isCurrentTab && reports.filter((r: any) => r.status === 'draft').length > 0 && (
                  <span className="badge-amber text-[10px]">{reports.filter((r: any) => r.status === 'draft').length} 待处理</span>
                )}
                {isCurrentTab && reports.filter((r: any) => r.status === 'finalized').length > 0 && (
                  <span className="badge-green text-[10px]">{reports.filter((r: any) => r.status === 'finalized').length} 已完成</span>
                )}
              </div>
            </div>
          );
        })}
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
                  layoutId="reportTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-finance-600"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          ))}
        </div>

        <div className="p-5">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-surface-400">加载中...</div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Calendar size={14} className="text-finance-500" />
                    <span className="text-sm text-surface-500">提交截止: 每月/季/年结束后第{deadline}个工作日</span>
                  </div>
                  <button className="btn-primary text-xs" onClick={() => setShowGenerateModal(true)}>
                    <FileText size={12} /> 生成报表
                  </button>
                </div>

                <div className="space-y-3">
                  {reports.map((report: any, idx: number) => (
                    <div
                      key={report.report_id ?? idx}
                      className="flex items-center justify-between p-4 rounded-xl border border-surface-200/60 hover:bg-finance-50/30 transition-colors"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-1">
                          <span className="font-mono text-xs text-finance-700">{report.report_id}</span>
                          <span className="font-medium text-surface-800">{report.title}</span>
                          <span className={STATUS_MAP[report.status]?.cls || 'badge-blue'}>
                            {STATUS_MAP[report.status]?.label || report.status}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-surface-400">
                          <span className="flex items-center gap-1">
                            <Clock size={10} /> 截止: {report.deadline}
                          </span>
                          {report.generated_at && (
                            <span>生成: {report.generated_at}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        {(report.status === 'finalized' || report.status === 'reviewed' || report.status === 'submitted') && (
                          <button
                            className="btn-secondary text-xs px-3 py-1.5"
                            onClick={() => handleView(report)}
                          >
                            <Eye size={12} /> 查看
                          </button>
                        )}
                        {(report.status === 'finalized' || report.status === 'reviewed' || report.status === 'submitted') && (
                          <button
                            className="btn-secondary text-xs px-3 py-1.5"
                            onClick={() => handleDownload(report)}
                          >
                            <Download size={12} /> 下载
                          </button>
                        )}
                        {report.status === 'draft' && (
                          <button
                            className="btn-primary text-xs px-3 py-1.5"
                            onClick={() => handleGenerate(report)}
                          >
                            生成
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>

              {/* v12.1: 阶段 7 — AI 智能报表 */}
              {activeTab === 'AI智能报表' && (
                <motion.div
                  key="ai-report"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="space-y-5"
                >
                  {/* 控制条 */}
                  <div className="glass-card p-4">
                    <div className="flex items-center gap-3 flex-wrap">
                      <div className="flex items-center gap-2">
                        <Brain size={16} className="text-finance-600" />
                        <span className="text-sm font-semibold text-finance-800">AI 智能报表</span>
                      </div>
                      <select
                        value={aiReportCenter}
                        onChange={e => setAiReportCenter(e.target.value)}
                        className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-sm"
                      >
                        <option value="">全集团</option>
                        <option value="财经中心">财经中心</option>
                        <option value="研发中心">研发中心</option>
                        <option value="市场中心">市场中心</option>
                      </select>
                      <input
                        type="text"
                        value={aiReportPeriod}
                        onChange={e => setAiReportPeriod(e.target.value)}
                        placeholder="YYYY-MM"
                        className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-sm w-28"
                      />
                      <button
                        onClick={runReportAi}
                        disabled={aiReportLoading}
                        className={clsx(
                          'px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1',
                          'bg-gradient-to-r from-finance-600 to-brand-600 text-white hover:opacity-90',
                          aiReportLoading && 'opacity-50 cursor-not-allowed'
                        )}
                      >
                        {aiReportLoading ? <><Loader2 size={14} className="animate-spin" /> 分析中…</> : <><Sparkles size={14} /> 一键运行 5 项 AI</>}
                      </button>
                    </div>
                  </div>

                  {/* 健康摘要 */}
                  {aiHealth && (
                    <div className={clsx(
                      'glass-card p-5',
                      aiHealth.total_score >= 80 ? 'border-l-4 border-compliance-500' :
                      aiHealth.total_score >= 60 ? 'border-l-4 border-brand-500' :
                      aiHealth.total_score >= 40 ? 'border-l-4 border-warning-500' : 'border-l-4 border-alert-500'
                    )}>
                      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                        <div className="text-center">
                          <p className="text-xs text-surface-500 mb-1">综合健康度</p>
                          <p className={clsx(
                            'text-3xl font-bold font-mono',
                            aiHealth.total_score >= 80 ? 'text-compliance-700' :
                            aiHealth.total_score >= 60 ? 'text-brand-700' :
                            aiHealth.total_score >= 40 ? 'text-warning-700' : 'text-alert-700'
                          )}>
                            {aiHealth.total_score}
                          </p>
                          <p className="text-sm font-semibold mt-1">{aiHealth.overall_health}</p>
                        </div>
                        {Object.entries(aiHealth.dimensions || {}).map(([k, v]: any) => {
                          const labelMap: Record<string, string> = { 执行: '执行', 战略: '战略', 风险: '风险', 调整: '调整' };
                          return (
                            <div key={k}>
                              <p className="text-[10px] text-surface-500 mb-0.5">{labelMap[k] || k}</p>
                              <p className="text-lg font-bold font-mono text-finance-700">{v}</p>
                              <div className="h-1.5 bg-surface-100 rounded-full overflow-hidden mt-1">
                                <div className={clsx(
                                  'h-full rounded-full',
                                  v >= 70 ? 'bg-compliance-500' : v >= 40 ? 'bg-warning-500' : 'bg-alert-500'
                                )} style={{ width: `${v}%` }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <p className="text-xs text-surface-700 mt-3 leading-relaxed">{aiHealth.summary}</p>
                    </div>
                  )}

                  {/* 自然语言解读 */}
                  {aiInterpret && (
                    <div className="glass-card p-4">
                      <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2 mb-2">
                        <FileSearch size={14} /> AI 自然语言解读（{aiInterpret.period}）
                      </h3>
                      <div className="p-3 rounded-lg bg-finance-50 border border-finance-200 mb-2">
                        <p className="text-xs text-finance-900 leading-relaxed whitespace-pre-line">{aiInterpret.interpretation}</p>
                      </div>
                      {aiInterpret.risks?.length > 0 && (
                        <ul className="space-y-1">
                          {aiInterpret.risks.map((r: string, i: number) => (
                            <li key={i} className="text-xs text-alert-700 px-2 py-1 rounded bg-alert-50/50">{r}</li>
                          ))}
                        </ul>
                      )}
                      {aiInterpret.metrics && (
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3">
                          {Object.entries(aiInterpret.metrics).map(([k, v]: any) => (
                            <div key={k} className="p-2 rounded bg-surface-50 text-center">
                              <p className="text-[10px] text-surface-500">{k}</p>
                              <p className="text-sm font-bold text-finance-700 font-mono">{typeof v === 'number' ? v.toFixed(1) : v}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 异常 + 跨期对比 */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {aiAnomalies && (
                      <div className="glass-card p-4">
                        <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2 mb-2">
                          <Activity size={14} className="text-alert-600" /> 报表异常
                          <span className="ml-auto text-[10px] text-surface-500">{aiAnomalies.anomaly_rate}%</span>
                        </h3>
                        <div className="text-center py-2 mb-2">
                          <p className="text-2xl font-bold text-alert-700 font-mono">{aiAnomalies.anomaly_count}</p>
                          <p className="text-[10px] text-surface-500">异常 / {aiAnomalies.total_items} 项</p>
                        </div>
                        <p className="text-xs text-surface-700">{aiAnomalies.recommendation}</p>
                        {aiAnomalies.anomalies?.length > 0 && (
                          <div className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                            {aiAnomalies.anomalies.slice(0, 5).map((a: any, i: number) => (
                              <div key={i} className={clsx(
                                'p-1.5 rounded border',
                                a.severity === '高' ? 'bg-alert-50 border-alert-200' : 'bg-warning-50 border-warning-200'
                              )}>
                                <div className="flex items-center gap-1">
                                  <span className="text-[10px] font-mono text-surface-700 truncate">{a.budget_name}</span>
                                  <span className="ml-auto text-[10px] font-mono font-semibold text-finance-700">{a.execution_rate}%</span>
                                </div>
                                <p className="text-[10px] text-surface-600">{a.type}（{a.severity}）</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {aiCrossPeriod && (
                      <div className="glass-card p-4">
                        <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2 mb-2">
                          <TrendingUp size={14} className="text-brand-600" /> 跨期对比
                        </h3>
                        <div className="text-center py-3 mb-2">
                          <p className="text-3xl font-bold font-mono text-finance-800">{aiCrossPeriod.current_rate}%</p>
                          <p className="text-[10px] text-surface-500 mt-1">本期 vs 上期 {aiCrossPeriod.previous_rate}%</p>
                        </div>
                        <div className={clsx(
                          'p-2 rounded text-center mb-2',
                          aiCrossPeriod.change_pp > 0 ? 'bg-warning-50' : aiCrossPeriod.change_pp < 0 ? 'bg-brand-50' : 'bg-surface-50'
                        )}>
                          <p className={clsx(
                            'text-sm font-bold',
                            aiCrossPeriod.change_pp > 0 ? 'text-warning-700' :
                            aiCrossPeriod.change_pp < 0 ? 'text-brand-700' : 'text-finance-700'
                          )}>
                            {aiCrossPeriod.trend} {aiCrossPeriod.change_pp > 0 ? '+' : ''}{aiCrossPeriod.change_pp}pp
                          </p>
                        </div>
                        <p className="text-xs text-surface-700">{aiCrossPeriod.recommendation}</p>
                      </div>
                    )}
                  </div>

                  {/* v12.2: AI 解释面板 + 根因可视化 */}
                  {(aiHealth || aiAnomalies) && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      <AiExplainPanel
                        title="报表健康度多维评估引擎"
                        summary="AI 综合执行 / 战略 / 风险 / 调整 4 维指标评估本期报表健康度"
                        model="ReportHealthScorer v1"
                        caliber={aiHealth?.caliber || '管理口径'}
                        confidence={aiHealth?.confidence ?? (aiHealth?.total_score ? Math.min(95, aiHealth.total_score) : 80)}
                        ruleIds={['SR-REP-01', 'SR-REP-02', 'TPL-REPORT-M']}
                        inputs={[
                          `评估期间：${aiReportPeriod || '本期'}`,
                          `中心范围：${aiReportCenter || '全集团'}`,
                          `异常项数：${aiAnomalies?.anomaly_count ?? '-'} / ${aiAnomalies?.total_items ?? '-'}`,
                          `跨期变化：${aiCrossPeriod?.change_pp ?? '-'}pp`,
                        ]}
                        steps={[
                          { step: '执行健康', detail: '本期各 L1 预算执行率 + 偏离度', weight: 0.3 },
                          { step: '战略对齐', detail: '本期支出与战略主题映射吻合度', weight: 0.25 },
                          { step: '风险敞口', detail: '红色/橙色预警覆盖率', weight: 0.25 },
                          { step: '调整合理性', detail: '预算调整频次 + 偏差幅度', weight: 0.2 },
                        ]}
                        conclusion={aiHealth ? `综合健康分 ${aiHealth.total_score} → ${aiHealth.overall_health}` : undefined}
                      />

                      <RootCauseTree
                        title="报表异常根因追溯"
                        topic={aiAnomalies?.anomalies?.[0]?.type || '报表异常根因'}
                        layerLabels={['科目层', '执行层', '归因层', '趋势层', '对标层']}
                        nodes={[
                          {
                            label: aiAnomalies?.anomalies?.[0]?.budget_name || 'L1 科目',
                            value: aiAnomalies?.anomalies?.[0]?.execution_rate ? `${aiAnomalies.anomalies[0].execution_rate}%` : '科目',
                            tone: 'alert',
                            children: [
                              { label: 'L2 业务招待', tone: 'warning' },
                              { label: 'L2 差旅', tone: 'brand' },
                            ],
                          },
                          {
                            label: '执行',
                            value: '进度',
                            tone: 'warning',
                            children: [
                              { label: '月度执行率 142%', tone: 'alert' },
                              { label: '季度预测 +28%', tone: 'warning' },
                            ],
                          },
                          {
                            label: '归因',
                            value: '业务',
                            tone: 'brand',
                            children: [
                              { label: '临时项目', tone: 'warning' },
                              { label: '战略投入', tone: 'finance' },
                            ],
                          },
                          {
                            label: '趋势',
                            value: '连升',
                            tone: 'alert',
                            children: [
                              { label: '近 3 月连升', tone: 'alert' },
                              { label: '预测月末 ¥210万', tone: 'warning' },
                            ],
                          },
                          {
                            label: '对标',
                            value: '同业',
                            tone: 'finance',
                            children: [
                              { label: '高于行业 P50', tone: 'warning' },
                              { label: '低于 P90', tone: 'compliance' },
                            ],
                          },
                        ]}
                        caption="科目 → 执行 → 归因 → 趋势 → 对标"
                      />
                    </div>
                  )}

                  {!aiHealth && !aiAnomalies && !aiInterpret && !aiCrossPeriod && !aiReportLoading && (
                    <div className="glass-card-static p-10 text-center text-surface-400">
                      <Brain size={40} className="mx-auto mb-3 opacity-30" />
                      <p className="text-sm">点击「一键运行 5 项 AI」启动智能报表分析</p>
                      <p className="text-xs mt-2">异常检测 / 自然语言解读 / 跨期对比 / 模板生成 / 健康摘要</p>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          )}
        </div>
      </div>

      {showGenerateModal && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => setShowGenerateModal(false)}>
          <div className="bg-white rounded-2xl p-6 shadow-xl max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-surface-800 mb-4">确认生成{activeTab}？</h3>
            <p className="text-sm text-surface-500 mb-4">将基于当前数据生成{activeTab}报表</p>
            <div className="mb-6">
              <label className="block text-sm font-medium text-surface-700 mb-1">选择期间</label>
              <input
                type="month"
                value={selectedPeriod}
                onChange={e => setSelectedPeriod(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
              />
            </div>
            <div className="flex justify-end gap-3">
              <button className="btn-secondary" onClick={() => setShowGenerateModal(false)}>取消</button>
              <button className="btn-primary" onClick={() => handleGenerate()}>确认生成</button>
            </div>
          </div>
        </div>
      )}

      {viewingReport && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={() => { setViewingReport(null); setCaliberData(null); }}>
          <div className="bg-white rounded-2xl p-6 shadow-xl max-w-4xl w-full mx-4 max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-finance-800">{viewingReport.title || viewingReport.report_id}</h3>
              <button onClick={() => { setViewingReport(null); setCaliberData(null); }} className="text-surface-400 hover:text-surface-600">
                <X size={18} />
              </button>
            </div>

            {/* Caliber toggle buttons */}
            <div className="flex items-center gap-2 mb-4 p-2 rounded-xl bg-surface-50/80 border border-surface-200/60">
              <ArrowLeftRight size={14} className="text-finance-600" />
              <span className="text-xs text-surface-500 mr-1">口径视图:</span>
              {([
                { key: 'management', label: '管理口径' },
                { key: 'financial', label: '财务口径' },
                { key: 'comparison', label: '对比视图' },
              ] as const).map(opt => (
                <button
                  key={opt.key}
                  onClick={() => setCaliberType(opt.key)}
                  className={clsx(
                    'px-3 py-1 rounded-lg text-xs font-medium transition-colors',
                    caliberType === opt.key
                      ? 'bg-finance-600 text-white'
                      : 'bg-white text-surface-600 border border-surface-200 hover:bg-finance-50'
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto">
              {/* Caliber comparison view */}
              {caliberType === 'comparison' && caliberData && !caliberLoading && (
                <div className="mb-6">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm border border-surface-200/60 rounded-xl">
                      <thead>
                        <tr className="bg-surface-50">
                          <th className="text-left py-2 px-3 metric-label">科目</th>
                          <th className="text-right py-2 px-3 metric-label">财务口径</th>
                          <th className="text-right py-2 px-3 metric-label">管理口径</th>
                          <th className="text-right py-2 px-3 metric-label">差异</th>
                          <th className="text-left py-2 px-3 metric-label">差异说明</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(caliberData.differences || []).map((diff: any, idx: number) => (
                          <tr key={idx} className={clsx(
                            'border-t border-surface-100',
                            Math.abs(diff.difference_amount) > 0 && 'bg-yellow-50/50'
                          )}>
                            <td className="py-2 px-3 font-medium text-surface-800">{diff.l1_name || diff.l1_code}</td>
                            <td className="py-2 px-3 text-right font-mono">¥{(diff.financial_amount / 100).toLocaleString()}</td>
                            <td className="py-2 px-3 text-right font-mono">¥{(diff.management_amount / 100).toLocaleString()}</td>
                            <td className={clsx(
                              'py-2 px-3 text-right font-mono font-medium',
                              diff.difference_amount > 0 ? 'text-amber-600' : diff.difference_amount < 0 ? 'text-blue-600' : 'text-surface-400'
                            )}>
                              {diff.difference_amount > 0 ? '+' : ''}¥{(diff.difference_amount / 100).toLocaleString()}
                            </td>
                            <td className="py-2 px-3 text-xs text-surface-500">{diff.difference_reason}</td>
                          </tr>
                        ))}
                        <tr className="border-t-2 border-surface-200 bg-surface-50/50 font-medium">
                          <td className="py-2 px-3">合计</td>
                          <td className="py-2 px-3 text-right font-mono">¥{(caliberData.total_financial || 0).toLocaleString()}</td>
                          <td className="py-2 px-3 text-right font-mono">¥{(caliberData.total_management || 0).toLocaleString()}</td>
                          <td className={clsx(
                            'py-2 px-3 text-right font-mono',
                            (caliberData.total_difference || 0) > 0 ? 'text-amber-600' : 'text-blue-600'
                          )}>
                            {(caliberData.total_difference || 0) > 0 ? '+' : ''}¥{(caliberData.total_difference || 0).toLocaleString()}
                          </td>
                          <td className="py-2 px-3"></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  {caliberData.reconciliation_note && (
                    <div className="mt-3 p-3 rounded-xl border border-finance-100 bg-finance-50/30 text-xs text-surface-600">
                      {caliberData.reconciliation_note}
                    </div>
                  )}
                </div>
              )}

              {/* Caliber note */}
              {caliberData?.caliber_note && caliberType !== 'comparison' && (
                <div className="mb-4 p-3 rounded-xl border border-finance-100 bg-finance-50/30 text-xs text-surface-600">
                  {caliberData.caliber_note}
                </div>
              )}

              {caliberLoading && caliberType === 'comparison' && (
                <div className="flex items-center justify-center py-8 text-surface-400 text-sm">加载口径对比数据...</div>
              )}

              {/* Main report content */}
              <div className="prose prose-sm prose-surface max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {viewContent}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
