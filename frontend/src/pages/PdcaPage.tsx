import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  RotateCcw,
  Calendar,
  TrendingUp,
  ArrowRight,
  CheckCircle2,
  Save,
  Plus,
  X,
  Zap,
  Loader2,
  Sparkles,
  Target,
  Wallet,
  Brain,
  BookOpen,
  FileText,
  Activity,
} from 'lucide-react';
import { clsx } from 'clsx';
import { pdcaApi, analysisApi } from '../services/api';
import { AiExplainPanel, RootCauseTree } from '../components/ai';

const TABS = ['月度闭环', '季度复盘', '年度校准', 'AI复盘', '次年AI'] as const;

const TAB_KEY_MAP: Record<string, string> = {
  '月度闭环': 'monthly',
  '季度复盘': 'quarterly',
  '年度校准': 'yearly',
};

interface ImprovementAction {
  action_id: string;
  pdca_id: string;
  description: string;
  assignee: string;
  due_date: string;
  status: '待执行' | '执行中' | '已完成';
  note?: string;
}

function EditableSection({
  label,
  content,
  color,
  pdcaId,
  sectionKey,
}: {
  label: string;
  content: string;
  color: string;
  pdcaId: string;
  sectionKey: string;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(content);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValue(content);
  }, [content]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await pdcaApi.updateSection(pdcaId, { section: sectionKey, content: value });
      setEditing(false);
    } catch {}
    setSaving(false);
  };

  return (
    <div className="p-3 rounded-lg bg-surface-50">
      <div className="flex items-center justify-between mb-1">
        <p className={clsx('text-xs font-semibold', color)}>{label}</p>
        {!editing ? (
          <button
            onClick={() => setEditing(true)}
            className="text-[10px] text-finance-600 hover:text-finance-800 transition-colors"
          >
            编辑
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-0.5 text-[10px] text-compliance-600 hover:text-compliance-800 transition-colors"
            >
              <Save size={10} /> {saving ? '保存中...' : '保存'}
            </button>
            <button
              onClick={() => { setEditing(false); setValue(content); }}
              className="text-[10px] text-surface-400 hover:text-surface-600 transition-colors"
            >
              取消
            </button>
          </div>
        )}
      </div>
      {editing ? (
        <textarea
          value={value}
          onChange={e => setValue(e.target.value)}
          className="w-full min-h-[60px] px-2 py-1.5 rounded border border-surface-200 bg-white text-sm text-surface-700 focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500 resize-y"
        />
      ) : (
        <p className="text-sm text-surface-600 whitespace-pre-wrap">{content || '暂无内容，点击编辑添加'}</p>
      )}
    </div>
  );
}

function ActionList({ pdcaId }: { pdcaId: string }) {
  const [actions, setActions] = useState<ImprovementAction[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ description: '', assignee: '', due_date: '' });

  const fetchActions = useCallback(async () => {
    try {
      const res = await pdcaApi.getActions({ pdca_id: pdcaId });
      setActions(res.data || []);
    } catch {
      setActions([]);
    }
  }, [pdcaId]);

  useEffect(() => {
    fetchActions();
  }, [fetchActions]);

  const handleCreate = async () => {
    if (!form.description.trim()) return;
    try {
      await pdcaApi.createAction({
        pdca_id: pdcaId,
        description: form.description,
        assignee: form.assignee,
        due_date: form.due_date,
      });
      setForm({ description: '', assignee: '', due_date: '' });
      setShowForm(false);
      fetchActions();
    } catch {}
  };

  const handleStatusToggle = async (action: ImprovementAction) => {
    const nextStatus: Record<string, string> = {
      '待执行': '执行中',
      '执行中': '已完成',
      '已完成': '待执行',
    };
    try {
      await pdcaApi.updateAction(action.action_id, {
        status: nextStatus[action.status] || '待执行',
      });
      fetchActions();
    } catch {}
  };

  const statusBadge = (status: string) => {
    if (status === '已完成') return 'badge-green';
    if (status === '执行中') return 'badge-amber';
    return 'bg-surface-100 text-surface-500 text-[10px] px-1.5 py-0.5 rounded-md font-medium';
  };

  return (
    <div className="mt-4 p-4 rounded-lg bg-surface-50/50 border border-surface-100">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-surface-700">改进行动追踪</h4>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1 text-xs text-finance-600 hover:text-finance-800 transition-colors"
        >
          {showForm ? <X size={12} /> : <Plus size={12} />}
          {showForm ? '取消' : '新增行动'}
        </button>
      </div>

      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-3 p-3 rounded-lg bg-white border border-surface-200 space-y-2"
          >
            <input
              type="text"
              placeholder="行动描述"
              value={form.description}
              onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
              className="w-full px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                placeholder="负责人"
                value={form.assignee}
                onChange={e => setForm(prev => ({ ...prev, assignee: e.target.value }))}
                className="w-full px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
              />
              <input
                type="date"
                value={form.due_date}
                onChange={e => setForm(prev => ({ ...prev, due_date: e.target.value }))}
                className="w-full px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
              />
            </div>
            <button onClick={handleCreate} className="btn-primary text-xs">
              确认添加
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {actions.length === 0 ? (
        <p className="text-xs text-surface-400">暂无改进行动</p>
      ) : (
        <div className="space-y-2">
          {actions.map(action => (
            <div
              key={action.action_id}
              className="flex items-center gap-3 p-2 rounded-lg bg-white border border-surface-100"
            >
              <button
                onClick={() => handleStatusToggle(action)}
                className={clsx(
                  'flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors',
                  action.status === '已完成'
                    ? 'border-compliance-500 bg-compliance-500 text-white'
                    : action.status === '执行中'
                    ? 'border-warning-500 bg-warning-50'
                    : 'border-surface-300 bg-white'
                )}
              >
                {action.status === '已完成' && <CheckCircle2 size={12} />}
              </button>
              <div className="flex-1 min-w-0">
                <p className={clsx('text-sm', action.status === '已完成' && 'line-through text-surface-400')}>
                  {action.description}
                </p>
                <div className="flex items-center gap-2 mt-0.5 text-[10px] text-surface-400">
                  {action.assignee && <span>{action.assignee}</span>}
                  {action.due_date && <span>截止: {action.due_date}</span>}
                </div>
              </div>
              <span className={statusBadge(action.status)}>{action.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PdcaPage() {
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>('月度闭环');
  // v12.0: 3GAP+3List 工具集成
  const [threeGapListData, setThreeGapListData] = useState<any>(null);
  const [threeGapListLoading, setThreeGapListLoading] = useState(false);
  const [autoPeriod, setAutoPeriod] = useState<string>(() => {
    const now = new Date();
    const q = Math.floor(now.getMonth() / 3) + 1;
    return `${now.getFullYear()}-Q${q}`;
  });

  // v12.0: 自动跑 3GAP+3List
  const handleAuto3Gap3List = async () => {
    setThreeGapListLoading(true);
    try {
      const res = await analysisApi.auto3Gap3List({ period: autoPeriod, top_n: 5 });
      setThreeGapListData(res.data || res);
    } catch (e: any) {
      setThreeGapListData({ error: e?.message || '3GAP+3List 批跑失败' });
    } finally {
      setThreeGapListLoading(false);
    }
  };

  // v12.0: 阶段 8 — 次年采集反向输入
  const [harvestData, setHarvestData] = useState<any>(null);

  // v12.1 阶段 6: AI 复盘状态
  const [aiReview, setAiReview] = useState<any>(null);
  const [aiLesson, setAiLesson] = useState<any>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiReviewPeriod, setAiReviewPeriod] = useState<string>(String(new Date().getFullYear()));
  const [aiReviewCenter, setAiReviewCenter] = useState<string>('');

  // v12.1 阶段 8: 次年AI 状态
  const [nextCycleBudget, setNextCycleBudget] = useState<any>(null);
  const [nextCycleAlign, setNextCycleAlign] = useState<any>(null);
  const [nextCycleAnomalies, setNextCycleAnomalies] = useState<any>(null);
  const [nextCycleLoading, setNextCycleLoading] = useState(false);

  const loadAiReview = async () => {
    if (!aiReviewPeriod.trim()) return;
    setAiLoading(true);
    try {
      const res = await pdcaApi.aiGenerateReview({
        period: aiReviewPeriod,
        center_id: aiReviewCenter.trim() || undefined,
      });
      if (res.success) setAiReview(res.data);
    } catch (error) {
      console.error('AI review failed:', error);
    } finally {
      setAiLoading(false);
    }
  };

  const loadAiLesson = async () => {
    if (!aiReviewPeriod.trim()) return;
    try {
      const res = await pdcaApi.aiExtractLessons({ period: aiReviewPeriod });
      if (res.success) setAiLesson(res.data);
    } catch (error) {
      console.error('AI lesson failed:', error);
    }
  };

  const loadNextCycleAi = async () => {
    setNextCycleLoading(true);
    try {
      const [budget, align, anomalies] = await Promise.all([
        pdcaApi.aiNextCycleBudgetSuggestion({ center_id: undefined }).catch(() => null),
        pdcaApi.aiNextCycleStrategicAlignment().catch(() => null),
        pdcaApi.aiNextCycleHarvestAnomalies().catch(() => null),
      ]);
      if (budget?.success) setNextCycleBudget(budget.data);
      if (align?.success) setNextCycleAlign(align.data);
      if (anomalies?.success) setNextCycleAnomalies(anomalies.data);
    } catch (error) {
      console.error('Next cycle AI failed:', error);
    } finally {
      setNextCycleLoading(false);
    }
  };

  const [harvestLoading, setHarvestLoading] = useState(false);
  const [harvestYear, setHarvestYear] = useState<number>(() => new Date().getFullYear() - 1);
  const handleHarvest = async () => {
    setHarvestLoading(true);
    try {
      const res = await pdcaApi.harvestNextCycle({ year: harvestYear });
      setHarvestData(res.data || res);
    } catch (e: any) {
      setHarvestData({ error: e?.message || '次年采集失败' });
    } finally {
      setHarvestLoading(false);
    }
  };

  const fetchData = async () => {
    try {
      const periodType = TAB_KEY_MAP[activeTab];
      const response = await pdcaApi.getHistory({ period_type: periodType });
      setRecords(response.data || []);
    } catch {
      setRecords([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const handleMonthly = async () => {
    try {
      await pdcaApi.monthly({});
      fetchData();
    } catch {}
  };

  const handleQuarterly = async () => {
    try {
      await pdcaApi.quarterly({});
      fetchData();
    } catch {}
  };

  const handleYearly = async () => {
    try {
      await pdcaApi.yearly({});
      fetchData();
    } catch {}
  };

  // Extract structured content from record data
  const getPlanContent = (item: any) =>
    item.plan_summary || item.result?.deviation_improvement || item.result?.strategy_progress || '';
  const getDoContent = (item: any) =>
    item.do_summary || (Array.isArray(item.result?.action_items) ? item.result.action_items.join('\n') : '') || '';
  const getCheckContent = (item: any) =>
    item.check_summary || (item.result?.quadrant_compliance ? JSON.stringify(item.result.quadrant_compliance) : '') || '';
  const getActContent = (item: any) =>
    item.act_summary || item.result?.next_steps || item.result?.action_plan_adjustment || '';

  // Safely render structured list data (replaces fragile split('; '))
  const renderStructuredList = (data: string | string[] | undefined, icon: 'arrow' | 'check') => {
    if (!data) return null;
    const items: string[] = Array.isArray(data) ? data : [data];
    return (
      <div className="space-y-1">
        {items.map((s, i) => (
          <div key={i} className="flex items-start gap-2 text-sm text-surface-600">
            {icon === 'arrow' ? (
              <ArrowRight size={12} className="text-brand-500 mt-1 flex-shrink-0" />
            ) : (
              <CheckCircle2 size={12} className="text-warning-500 mt-1 flex-shrink-0" />
            )}
            <span>{s}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-finance-800 font-display">PDCA 复盘</h1>
        <p className="text-sm text-surface-400 mt-1">月度闭环(PDCA-A) · 季度复盘(PDCA-B) · 年度校准(PDCA-C)</p>
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
                  layoutId="pdcaTab"
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
              {activeTab === '月度闭环' && (
                <motion.div
                  key="monthly"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="space-y-4">
                    <div className="flex justify-end mb-2">
                      <button onClick={handleMonthly} className="btn-primary text-xs">
                        <Calendar size={12} /> 执行月度复盘
                      </button>
                    </div>
                    {records.map((item: any) => {
                      const pdcaId = item.pdca_id || item.trace_id || `pdca-${item.period}`;
                      return (
                        <div key={pdcaId} className="glass-card-static p-5">
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <Calendar size={16} className="text-finance-500" />
                              <span className="font-semibold text-surface-800">{item.period}</span>
                              <span className="text-sm text-surface-400">{item.org_name || ''}</span>
                              <span className={item.status === 'completed' ? 'badge-green' : item.status === 'in_progress' ? 'badge-amber' : 'badge-red'}>
                                {item.status === 'completed' ? '已完成' : item.status === 'in_progress' ? '进行中' : '逾期'}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 text-sm">
                              {item.budget_deviation !== 0 && item.budget_deviation !== undefined && (
                                <span className={item.budget_deviation < 0 ? 'text-alert-600' : 'text-compliance-600'}>
                                  偏差: {item.budget_deviation}%
                                </span>
                              )}
                              {item.alert_count > 0 && (
                                <span className="badge-amber">{item.alert_count} 预警</span>
                              )}
                            </div>
                          </div>
                          <div className="grid grid-cols-4 gap-4">
                            <EditableSection label="Plan" content={getPlanContent(item)} color="text-brand-600" pdcaId={pdcaId} sectionKey="plan" />
                            <EditableSection label="Do" content={getDoContent(item)} color="text-finance-600" pdcaId={pdcaId} sectionKey="do" />
                            <EditableSection label="Check" content={getCheckContent(item)} color="text-warning-600" pdcaId={pdcaId} sectionKey="check" />
                            <EditableSection label="Act" content={getActContent(item)} color="text-compliance-600" pdcaId={pdcaId} sectionKey="act" />
                          </div>
                          <ActionList pdcaId={pdcaId} />
                        </div>
                      );
                    })}
                  </div>
                </motion.div>
              )}

              {activeTab === '季度复盘' && (
                <motion.div
                  key="quarterly"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="space-y-4">
                    <div className="flex justify-end mb-2 gap-2">
                      <input
                        type="text"
                        value={autoPeriod}
                        onChange={e => setAutoPeriod(e.target.value)}
                        placeholder="2026-Q2"
                        className="px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-xs w-24 focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                      <button
                        onClick={handleAuto3Gap3List}
                        disabled={threeGapListLoading}
                        className="btn-primary text-xs"
                      >
                        {threeGapListLoading ? (
                          <><Loader2 size={12} className="animate-spin" /> 批跑中...</>
                        ) : (
                          <><Zap size={12} /> 自动跑 3GAP+3List</>
                        )}
                      </button>
                      <button onClick={handleQuarterly} className="btn-secondary text-xs">
                        <TrendingUp size={12} /> 执行季度复盘
                      </button>
                    </div>

                    {/* v12.0: 3GAP+3List 工具面板 */}
                    {threeGapListData && !threeGapListData.error && (
                      <div className="glass-card-static p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Sparkles size={14} className="text-finance-600" />
                          <h3 className="text-sm font-semibold text-finance-800">3GAP+3List 工具结果</h3>
                          <span className="text-[10px] text-surface-500 ml-auto">
                            批跑覆盖：<strong className="text-finance-700">{threeGapListData.centers_processed}/{threeGapListData.centers_total}</strong> 中心
                          </span>
                        </div>

                        {/* 3GAP 摘要 */}
                        {threeGapListData.gap_summary?.length > 0 && (
                          <div className="mb-3">
                            <p className="text-[10px] text-surface-500 font-semibold mb-1.5">3GAP 摘要（每中心取最大差距维度）</p>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                              {threeGapListData.gap_summary.slice(0, 6).map((g: any) => (
                                <div key={g.gap_id} className="rounded-lg border border-surface-200 p-2 text-[11px]">
                                  <div className="flex items-center justify-between">
                                    <span className="font-semibold text-surface-700">{g.center_id}</span>
                                    <span className={
                                      g.max_gap_dim.includes('GAP1') ? 'badge-amber' :
                                      g.max_gap_dim.includes('GAP2') ? 'badge-red' :
                                      'badge-blue'
                                    } style={{ fontSize: 9, padding: '1px 5px' }}>{g.max_gap_dim.split('-')[0]}</span>
                                  </div>
                                  <p className="text-surface-500 mt-0.5">G1: {g.gap1.toFixed(0)} · G2: {g.gap2.toFixed(0)} · G3: {g.gap3.toFixed(0)}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* 3List 归类 */}
                        {threeGapListData.list_summary && Object.keys(threeGapListData.list_summary).length > 0 && (
                          <div className="grid grid-cols-3 gap-2">
                            {(['必赢清单', '改善清单', '观察清单'] as const).map(listName => {
                              const items = threeGapListData.list_summary[listName] || [];
                              const cls = listName === '必赢清单' ? 'border-compliance-200 bg-compliance-50/40 text-compliance-700'
                                : listName === '改善清单' ? 'border-warning-200 bg-warning-50/40 text-warning-700'
                                : 'border-surface-200 bg-surface-50/40 text-surface-700';
                              return (
                                <div key={listName} className={clsx('rounded-lg border p-2', cls)}>
                                  <div className="flex items-center gap-1.5 mb-1.5">
                                    <Target size={11} />
                                    <span className="text-[11px] font-semibold">{listName}</span>
                                    <span className="text-[9px] ml-auto opacity-70">Top {items.length}</span>
                                  </div>
                                  {items.length === 0 ? (
                                    <p className="text-[10px] opacity-60">暂无</p>
                                  ) : (
                                    <ul className="space-y-1">
                                      {items.map((it: any) => (
                                        <li key={it.list_id} className="text-[10px] leading-tight">
                                          <span className="font-semibold">{it.item_name}</span>
                                          {it.action_plan && <p className="opacity-70 mt-0.5">→ {it.action_plan}</p>}
                                        </li>
                                      ))}
                                    </ul>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                    {threeGapListData?.error && (
                      <div className="text-xs text-amber-700 bg-amber-50 rounded-lg p-3">
                        ⚠ 3GAP+3List 批跑失败：{threeGapListData.error}
                      </div>
                    )}

                    {records.map((item: any) => {
                      const pdcaId = item.pdca_id || item.trace_id || `pdca-${item.period}`;
                      return (
                        <div key={pdcaId} className="glass-card-static p-5">
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <TrendingUp size={16} className="text-finance-500" />
                              <span className="font-semibold text-surface-800">{item.period}</span>
                              <span className={item.status === 'completed' ? 'badge-green' : 'badge-amber'}>
                                {item.status === 'completed' ? '已完成' : '进行中'}
                              </span>
                            </div>
                          </div>
                          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                            <div className="p-4 rounded-lg bg-brand-50/50 border border-brand-100">
                              <h4 className="text-sm font-semibold text-brand-700 mb-2">3GAP 分析</h4>
                              <EditableSection label="" content={item.gap_summary || getPlanContent(item)} color="text-brand-600" pdcaId={pdcaId} sectionKey="plan" />
                            </div>
                            <div className="p-4 rounded-lg bg-warning-50/50 border border-warning-100">
                              <h4 className="text-sm font-semibold text-warning-700 mb-2">3List 归类</h4>
                              <EditableSection label="" content={item.list_summary || getDoContent(item)} color="text-warning-600" pdcaId={pdcaId} sectionKey="do" />
                            </div>
                            <div className="p-4 rounded-lg bg-compliance-50/50 border border-compliance-100">
                              <h4 className="text-sm font-semibold text-compliance-700 mb-2">预算转换建议</h4>
                              <EditableSection label="" content={item.transfer_recommendation || getActContent(item)} color="text-compliance-600" pdcaId={pdcaId} sectionKey="act" />
                            </div>
                          </div>
                          <ActionList pdcaId={pdcaId} />
                        </div>
                      );
                    })}
                  </div>
                </motion.div>
              )}

              {activeTab === '年度校准' && (
                <motion.div
                  key="annual"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="space-y-4">
                    <div className="flex justify-end mb-2 gap-2">
                      {/* v12.0: 阶段 8 次年采集入口 */}
                      <input
                        type="number"
                        value={harvestYear}
                        onChange={e => setHarvestYear(Number(e.target.value))}
                        className="px-2.5 py-1.5 rounded-lg border border-surface-200 bg-white text-xs w-20 focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
                      />
                      <button
                        onClick={handleHarvest}
                        disabled={harvestLoading}
                        className="btn-secondary text-xs"
                      >
                        {harvestLoading ? (
                          <><Loader2 size={12} className="animate-spin" /> 采集中...</>
                        ) : (
                          <><Sparkles size={12} /> 次年采集反向输入</>
                        )}
                      </button>
                      <button onClick={handleYearly} className="btn-primary text-xs">
                        <RotateCcw size={12} /> 执行年度校准
                      </button>
                    </div>

                    {/* v12.0: 次年采集结果展示 */}
                    {harvestData && !harvestData.error && (
                      <div className="glass-card-static p-4 border-2 border-finance-200">
                        <div className="flex items-center gap-2 mb-3">
                          <Sparkles size={14} className="text-finance-600" />
                          <h3 className="text-sm font-semibold text-finance-800">
                            {harvestData.year}→{harvestData.next_year} 年 次年采集反向输入
                          </h3>
                          <span className="text-[10px] text-surface-500 ml-auto">
                            采集 <strong className="text-finance-700">{harvestData.harvested_count}</strong> 项 ·
                            整体执行率 <strong className={
                              harvestData.overall_execution_rate > 105 ? 'text-alert-700' :
                              harvestData.overall_execution_rate < 50 ? 'text-warning-700' :
                              'text-compliance-700'
                            }>{harvestData.overall_execution_rate?.toFixed(1)}%</strong>
                          </span>
                        </div>

                        {/* 联动行动 */}
                        {harvestData.linked_actions?.length > 0 && (
                          <div className="mb-3 p-3 rounded-lg bg-gradient-to-r from-finance-50 to-brand-50 border border-finance-200/60">
                            <p className="text-[10px] font-semibold text-finance-700 mb-1.5">
                              🔗 反向流入下年度的联动行动
                            </p>
                            <div className="space-y-1">
                              {harvestData.linked_actions.map((a: any, i: number) => (
                                <p key={i} className="text-[11px] text-surface-700">
                                  <span className={a.type === 'sp_objective_adjust' ? 'badge-blue' : 'badge-amber'} style={{ fontSize: 9, padding: '1px 4px' }}>
                                    {a.type === 'sp_objective_adjust' ? 'SP' : 'BP'}
                                  </span>
                                  <span className="ml-1.5">{a.next_step}</span>
                                </p>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {/* SP 战略建议 */}
                          <div className="rounded-lg border border-brand-200 bg-brand-50/30 p-3">
                            <p className="text-[11px] font-semibold text-brand-700 mb-2">
                              <Target size={11} className="inline mr-1" />
                              SP 战略目标调整建议（{harvestData.sp_suggestions?.length || 0}）
                            </p>
                            {harvestData.sp_suggestions?.length > 0 ? (
                              <ul className="space-y-1.5">
                                {harvestData.sp_suggestions.slice(0, 4).map((s: any, i: number) => (
                                  <li key={i} className="text-[11px] text-surface-700">
                                    <span className={s.priority === 'high' ? 'badge-red' : 'badge-amber'} style={{ fontSize: 9, padding: '1px 4px' }}>{s.priority}</span>
                                    <span className="ml-1.5">{s.suggestion}</span>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-[11px] text-surface-500">本年战略与执行匹配良好，无需调整</p>
                            )}
                          </div>

                          {/* BP 预算草稿 */}
                          <div className="rounded-lg border border-compliance-200 bg-compliance-50/30 p-3">
                            <p className="text-[11px] font-semibold text-compliance-700 mb-2">
                              <Wallet size={11} className="inline mr-1" />
                              BP 预算草稿（{harvestData.bp_draft?.length || 0}）
                            </p>
                            {harvestData.bp_draft?.length > 0 ? (
                              <div className="space-y-1 max-h-32 overflow-y-auto">
                                {harvestData.bp_draft.slice(0, 6).map((d: any) => (
                                  <div key={d.l1_code} className="flex items-center justify-between text-[11px]">
                                    <span className="font-mono text-surface-700">{d.l1_code}</span>
                                    <span className="text-surface-500">执行率 {d.execution_rate.toFixed(0)}%</span>
                                    <span className={clsx(
                                      'font-semibold',
                                      d.growth_pct > 0 ? 'text-compliance-700' :
                                      d.growth_pct < 0 ? 'text-alert-700' : 'text-surface-500'
                                    )}>{d.growth_pct > 0 ? '+' : ''}{d.growth_pct.toFixed(0)}%</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-[11px] text-surface-500">本年无L1分类数据</p>
                            )}
                          </div>
                        </div>

                        {harvestData.next_step && (
                          <p className="text-[10px] text-surface-500 mt-2 italic">
                            → {harvestData.next_step}
                          </p>
                        )}
                      </div>
                    )}
                    {harvestData?.error && (
                      <div className="text-xs text-amber-700 bg-amber-50 rounded-lg p-3">
                        ⚠ 次年采集失败：{harvestData.error}
                      </div>
                    )}

                    {records.map((item: any) => {
                      const pdcaId = item.pdca_id || item.trace_id || `pdca-${item.period}`;
                      return (
                        <div key={pdcaId} className="glass-card-static p-5">
                          <div className="flex items-center gap-3 mb-4">
                            <RotateCcw size={16} className="text-finance-500" />
                            <span className="font-semibold text-surface-800">{item.period}</span>
                            <span className="badge-green">已完成</span>
                          </div>
                          <div className="space-y-4">
                            <div className="p-4 rounded-lg bg-finance-50/50 border border-finance-100">
                              <h4 className="text-sm font-semibold text-finance-700 mb-2">校准结果</h4>
                              <EditableSection label="" content={item.calibration_result || getCheckContent(item)} color="text-finance-600" pdcaId={pdcaId} sectionKey="check" />
                            </div>
                            <div className="p-4 rounded-lg bg-brand-50/50 border border-brand-100">
                              <h4 className="text-sm font-semibold text-brand-700 mb-2">下年度建议</h4>
                              {renderStructuredList(
                                item.next_year_suggestions || item.next_year_suggestion,
                                'arrow'
                              ) || (
                                <EditableSection label="" content={getActContent(item)} color="text-brand-600" pdcaId={pdcaId} sectionKey="act" />
                              )}
                            </div>
                            <div className="p-4 rounded-lg bg-warning-50/50 border border-warning-100">
                              <h4 className="text-sm font-semibold text-warning-700 mb-2">经验教训</h4>
                              {renderStructuredList(
                                item.lessons_learned_list || item.lessons_learned,
                                'check'
                              ) || (
                                <EditableSection label="" content="" color="text-warning-600" pdcaId={pdcaId} sectionKey="do" />
                              )}
                            </div>
                          </div>
                          <ActionList pdcaId={pdcaId} />
                        </div>
                      );
                    })}
                  </div>
                </motion.div>
              )}

              {/* v12.1: 阶段 6 — AI 复盘 */}
              {activeTab === 'AI复盘' && (
                <motion.div
                  key="ai-pdca"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="space-y-5"
                >
                  <div className="glass-card p-4">
                    <div className="flex items-center gap-3 flex-wrap">
                      <div className="flex items-center gap-2">
                        <Brain size={16} className="text-finance-600" />
                        <span className="text-sm font-semibold text-finance-800">AI 复盘引擎</span>
                      </div>
                      <input
                        type="text"
                        value={aiReviewPeriod}
                        onChange={e => setAiReviewPeriod(e.target.value)}
                        placeholder="YYYY"
                        className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-sm w-24"
                      />
                      <input
                        type="text"
                        value={aiReviewCenter}
                        onChange={e => setAiReviewCenter(e.target.value)}
                        placeholder="中心 ID (可选)"
                        className="px-3 py-1.5 rounded-lg border border-surface-200 bg-white text-sm w-40"
                      />
                      <button
                        onClick={loadAiReview}
                        disabled={aiLoading}
                        className={clsx(
                          'px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1',
                          'bg-gradient-to-r from-finance-600 to-brand-600 text-white hover:opacity-90',
                          aiLoading && 'opacity-50 cursor-not-allowed'
                        )}
                      >
                        {aiLoading ? <><Loader2 size={14} className="animate-spin" /> 生成中…</> : <><Sparkles size={14} /> 生成复盘</>}
                      </button>
                      <button
                        onClick={loadAiLesson}
                        className="px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1 bg-brand-50 text-brand-700 border border-brand-200 hover:bg-brand-100"
                      >
                        <BookOpen size={14} /> 经验沉淀
                      </button>
                    </div>
                  </div>

                  {/* 复盘报告 */}
                  {aiReview && (
                    <div className="glass-card p-5 space-y-3">
                      <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2">
                        <FileText size={14} /> 4 段式复盘报告（{aiReview.period}）
                      </h3>
                      <div className="p-3 rounded-lg bg-finance-50 border border-finance-200">
                        <p className="text-[10px] font-semibold text-finance-700 mb-1">📋 完整复盘</p>
                        <p className="text-xs text-finance-900 leading-relaxed">{aiReview.review}</p>
                      </div>
                      {aiReview.highlights?.length > 0 && (
                        <div className="p-3 rounded-lg bg-compliance-50 border border-compliance-200">
                          <p className="text-[10px] font-semibold text-compliance-700 mb-1">✅ 亮点</p>
                          <ul className="text-xs text-compliance-900 space-y-0.5">
                            {aiReview.highlights.map((h: string, i: number) => <li key={i}>• {h}</li>)}
                          </ul>
                        </div>
                      )}
                      {aiReview.issues?.length > 0 && (
                        <div className="p-3 rounded-lg bg-alert-50 border border-alert-200">
                          <p className="text-[10px] font-semibold text-alert-700 mb-1">🚨 问题</p>
                          <ul className="text-xs text-alert-900 space-y-0.5">
                            {aiReview.issues.map((it: string, i: number) => <li key={i}>• {it}</li>)}
                          </ul>
                        </div>
                      )}
                      {aiReview.improvements?.length > 0 && (
                        <div className="p-3 rounded-lg bg-brand-50 border border-brand-200">
                          <p className="text-[10px] font-semibold text-brand-700 mb-1">💡 改进</p>
                          <ul className="text-xs text-brand-900 space-y-0.5">
                            {aiReview.improvements.map((im: string, i: number) => <li key={i}>• {im}</li>)}
                          </ul>
                        </div>
                      )}
                      {aiReview.metrics && (
                        <div className="grid grid-cols-3 md:grid-cols-6 gap-2 pt-2">
                          {Object.entries(aiReview.metrics).map(([k, v]: any) => (
                            <div key={k} className="p-2 rounded bg-surface-50 text-center">
                              <p className="text-[10px] text-surface-500">{k}</p>
                              <p className="text-sm font-bold text-finance-700 font-mono">{typeof v === 'number' ? (v < 10 ? v.toFixed(1) : Math.round(v)) : v}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 经验沉淀 */}
                  {aiLesson && (
                    <div className="glass-card p-4">
                      <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2 mb-2">
                        <BookOpen size={14} /> 经验沉淀（{aiLesson.lesson_count} 条 / {aiLesson.gap_count} 个GAP）
                      </h3>
                      {aiLesson.lessons?.length > 0 ? (
                        <div className="space-y-1.5">
                          {aiLesson.lessons.map((l: any) => (
                            <div key={l.gap_id} className="p-2 rounded bg-brand-50/50 border border-brand-200">
                              <div className="flex items-center gap-2 mb-0.5">
                                <span className="text-[10px] font-mono text-surface-500">{l.period}</span>
                                <span className="text-[10px] text-surface-400">{l.gap_id}</span>
                              </div>
                              <p className="text-xs text-surface-700">{l.lesson}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-surface-400 text-center py-3">该期间无经验记录</p>
                      )}
                    </div>
                  )}

                  {/* v12.2: AI 解释面板 + 根因可视化（PDCA 5-Why） */}
                  {aiReview && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      <AiExplainPanel
                        title="PDCA 4 段式复盘生成器"
                        summary="AI 按 Plan / Do / Check / Act 4 段结构化生成复盘报告，并提炼亮点/问题/改进"
                        model="PDCA-Narrator v1"
                        caliber="管理口径"
                        confidence={aiReview.confidence ?? 82}
                        ruleIds={['SR-PDCA-01', 'SR-PDCA-02', 'TPL-REVIEW-Q']}
                        inputs={[
                          `复盘期间：${aiReview.period}`,
                          `中心范围：${aiReviewCenter || '全集团'}`,
                          `GAP 数：${aiLesson?.gap_count ?? '-'} 个`,
                          `执行/战略/风险多维指标：${aiReview.metrics ? Object.keys(aiReview.metrics).length : 0} 项`,
                        ]}
                        steps={[
                          { step: 'Plan 对照', detail: '将期初战略主题与实际执行对齐', weight: 0.25 },
                          { step: 'Do 摘要', detail: '汇总本期实际执行情况与关键里程碑', weight: 0.25 },
                          { step: 'Check 差异', detail: '识别 3GAP（目标/执行/预测）与根因', weight: 0.3 },
                          { step: 'Act 改进', detail: '输出可落地的改进行动 + 下期建议', weight: 0.2 },
                        ]}
                        conclusion={`亮点 ${aiReview.highlights?.length || 0} 条 / 问题 ${aiReview.issues?.length || 0} 条 / 改进 ${aiReview.improvements?.length || 0} 条`}
                      />

                      <RootCauseTree
                        title="5-Why 根因追溯"
                        topic={aiReview.issues?.[0] || '关键偏差根因'}
                        layerLabels={['Why-1', 'Why-2', 'Why-3', 'Why-4', 'Why-5']}
                        nodes={[
                          {
                            label: 'Why-1 直接原因',
                            value: '执行偏差',
                            tone: 'alert',
                            children: [
                              { label: 'Why-2 流程原因', tone: 'warning' },
                              { label: 'Why-2 系统原因', tone: 'warning' },
                            ],
                          },
                          {
                            label: 'Why-3 组织原因',
                            value: '权责',
                            tone: 'brand',
                            children: [
                              { label: 'Why-4 跨部门协同', tone: 'brand' },
                              { label: 'Why-4 考核导向', tone: 'warning' },
                            ],
                          },
                          {
                            label: 'Why-4 战略原因',
                            value: '对齐',
                            tone: 'finance',
                            children: [
                              { label: 'Why-5 主题模糊', tone: 'alert' },
                              { label: 'Why-5 资源错配', tone: 'warning' },
                            ],
                          },
                          {
                            label: 'Why-5 根因',
                            value: '根因',
                            tone: 'alert',
                            reason: '可执行的根因结论',
                          },
                        ]}
                        caption="从执行偏差一路追溯到战略根因"
                      />
                    </div>
                  )}

                  {!aiReview && !aiLesson && !aiLoading && (
                    <div className="glass-card-static p-10 text-center text-surface-400">
                      <Brain size={40} className="mx-auto mb-3 opacity-30" />
                      <p className="text-sm">点击「生成复盘」启动 AI 复盘分析</p>
                      <p className="text-xs mt-2">PDCA 4 段式 + 经验沉淀</p>
                    </div>
                  )}
                </motion.div>
              )}

              {/* v12.1: 阶段 8 — 次年AI */}
              {activeTab === '次年AI' && (
                <motion.div
                  key="next-cycle"
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="space-y-5"
                >
                  <div className="glass-card p-4">
                    <div className="flex items-center gap-3 flex-wrap">
                      <div className="flex items-center gap-2">
                        <Activity size={16} className="text-finance-600" />
                        <span className="text-sm font-semibold text-finance-800">次年采集 AI 引擎</span>
                      </div>
                      <button
                        onClick={loadNextCycleAi}
                        disabled={nextCycleLoading}
                        className={clsx(
                          'ml-auto px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-1',
                          'bg-gradient-to-r from-finance-600 to-brand-600 text-white hover:opacity-90',
                          nextCycleLoading && 'opacity-50 cursor-not-allowed'
                        )}
                      >
                        {nextCycleLoading ? <><Loader2 size={14} className="animate-spin" /> 分析中…</> : <><Sparkles size={14} /> 一键分析</>}
                      </button>
                    </div>
                  </div>

                  {/* 预算建议摘要 */}
                  {nextCycleBudget && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div className="glass-card p-4 text-center">
                        <p className="text-[10px] text-surface-500 mb-1">本年总额</p>
                        <p className="text-xl font-bold text-finance-700 font-mono">¥{(nextCycleBudget.total_this_year / 10000).toFixed(0)}万</p>
                      </div>
                      <div className="glass-card p-4 text-center">
                        <p className="text-[10px] text-surface-500 mb-1">次年建议</p>
                        <p className="text-xl font-bold text-brand-700 font-mono">¥{(nextCycleBudget.total_next_year / 10000).toFixed(0)}万</p>
                      </div>
                      <div className="glass-card p-4 text-center">
                        <p className="text-[10px] text-surface-500 mb-1">变化幅度</p>
                        <p className={clsx(
                          'text-xl font-bold font-mono',
                          nextCycleBudget.delta_pct > 0 ? 'text-warning-700' : nextCycleBudget.delta_pct < 0 ? 'text-compliance-700' : 'text-finance-700'
                        )}>
                          {nextCycleBudget.delta_pct > 0 ? '+' : ''}{nextCycleBudget.delta_pct}%
                        </p>
                      </div>
                    </div>
                  )}

                  {/* 战略对齐 + 采集异常 */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {nextCycleAlign && (
                      <div className="glass-card p-4">
                        <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2 mb-2">
                          <Target size={14} /> 战略对齐度
                        </h3>
                        <div className={clsx(
                          'p-3 rounded-lg text-center mb-2',
                          nextCycleAlign.alignment_score >= 80 ? 'bg-compliance-100' :
                          nextCycleAlign.alignment_score >= 60 ? 'bg-warning-100' : 'bg-alert-100'
                        )}>
                          <p className="text-2xl font-bold font-mono text-finance-800">{nextCycleAlign.alignment_score}</p>
                          <p className="text-xs text-surface-600 mt-1">战略项目占比 {nextCycleAlign.strategic_ratio}%</p>
                        </div>
                        <p className="text-xs text-surface-700">{nextCycleAlign.recommendation}</p>
                        {Object.keys(nextCycleAlign.intent_distribution || {}).length > 0 && (
                          <div className="mt-2 space-y-1">
                            {Object.entries(nextCycleAlign.intent_distribution).map(([k, v]: any) => (
                              <div key={k} className="flex items-center justify-between text-[10px]">
                                <span className="text-surface-600">{k}</span>
                                <span className="font-mono font-semibold text-finance-700">{v} 项</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {nextCycleAnomalies && (
                      <div className="glass-card p-4">
                        <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2 mb-2">
                          <Zap size={14} /> 采集异常扫描
                          <span className="ml-auto text-[10px] text-surface-500">完整度 {nextCycleAnomalies.completeness}%</span>
                        </h3>
                        <div className="text-center py-2 mb-2">
                          <p className="text-2xl font-bold text-finance-700 font-mono">{nextCycleAnomalies.anomaly_count}</p>
                          <p className="text-[10px] text-surface-500">异常 / {nextCycleAnomalies.total_items} 项</p>
                        </div>
                        <p className="text-xs text-surface-700">{nextCycleAnomalies.recommendation}</p>
                        {nextCycleAnomalies.anomalies?.length > 0 && (
                          <div className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                            {nextCycleAnomalies.anomalies.slice(0, 5).map((a: any, i: number) => (
                              <div key={i} className="p-1.5 rounded bg-amber-50/50 border border-amber-200">
                                <div className="flex items-center gap-1">
                                  <span className="text-[10px] font-mono text-surface-700 truncate">{a.budget_id}</span>
                                  <span className="ml-auto text-[10px] text-amber-700">{a.severity}</span>
                                </div>
                                <p className="text-[10px] text-amber-700">{a.type}：{a.detail}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* 预算建议清单 */}
                  {nextCycleBudget?.suggestions?.length > 0 && (
                    <div className="glass-card p-4">
                      <h3 className="text-sm font-semibold text-finance-800 flex items-center gap-2 mb-2">
                        <Wallet size={14} /> 预算调整建议（Top {Math.min(8, nextCycleBudget.suggestions.length)}）
                      </h3>
                      <div className="space-y-1.5">
                        {nextCycleBudget.suggestions.slice(0, 8).map((s: any) => (
                          <div key={s.budget_id} className={clsx(
                            'p-2 rounded border',
                            s.action === '追加' ? 'bg-warning-50 border-warning-200' :
                            s.action === '核减' ? 'bg-brand-50 border-brand-200' :
                            'bg-surface-50 border-surface-200'
                          )}>
                            <div className="flex items-center gap-2">
                              <span className={clsx(
                                'text-[10px] px-1.5 py-0.5 rounded font-semibold',
                                s.action === '追加' ? 'bg-warning-200 text-warning-800' :
                                s.action === '核减' ? 'bg-brand-200 text-brand-800' :
                                'bg-surface-200 text-surface-700'
                              )}>{s.action}</span>
                              <span className="text-xs text-surface-800 truncate flex-1">{s.budget_name}</span>
                              <span className="text-[10px] font-mono text-surface-500">{s.this_year_rate}%</span>
                            </div>
                            <p className="text-[10px] text-surface-600 mt-0.5">
                              本年 ¥{s.this_year_amount.toLocaleString()} → 次年建议 ¥{s.next_year_suggestion.toLocaleString()}（调整因子 {s.factor}）
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* v12.2: AI 解释面板 + 根因可视化（次年采集异常） */}
                  {(nextCycleBudget || nextCycleAnomalies) && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      <AiExplainPanel
                        title="次年预算智能建议引擎"
                        summary="AI 基于本年执行率、战略对齐度、采集完整度，给出次年预算追加 / 核减建议"
                        model="NextCycle-Budget v1"
                        caliber="次年规划口径"
                        confidence={nextCycleBudget?.confidence ?? 78}
                        ruleIds={['SR-NC-01', 'SR-NC-02', 'TPL-HARVEST']}
                        inputs={[
                          `本年总盘：${nextCycleBudget ? `¥${(nextCycleBudget.total_this_year / 10000).toFixed(0)}万` : '-'}`,
                          `次年建议：${nextCycleBudget ? `¥${(nextCycleBudget.total_next_year / 10000).toFixed(0)}万` : '-'}`,
                          `采集完整度：${nextCycleAnomalies?.completeness ?? '-'}%`,
                          `战略对齐分：${nextCycleAlign?.alignment_score ?? '-'}`,
                        ]}
                        steps={[
                          { step: '执行率映射', detail: '本年实际执行率 → 调整因子', weight: 0.35 },
                          { step: '战略加成', detail: '关联战略主题的预算项加权', weight: 0.25 },
                          { step: 'GAP 残差', detail: '本期未消化的 3GAP 转结次年', weight: 0.2 },
                          { step: '异常回写', detail: '采集异常项进入风险折扣', weight: 0.2 },
                        ]}
                        conclusion={nextCycleBudget ? `本年 → 次年变化 ${nextCycleBudget.delta_pct > 0 ? '+' : ''}${nextCycleBudget.delta_pct}%` : undefined}
                      />

                      <RootCauseTree
                        title="采集异常根因追溯"
                        topic={nextCycleAnomalies?.anomalies?.[0]?.type || '采集异常根因'}
                        layerLabels={['数据层', '流程层', '组织层', '系统层', '战略层']}
                        nodes={[
                          {
                            label: '数据层',
                            value: '缺失',
                            tone: 'alert',
                            children: [
                              { label: '字段未填', tone: 'warning' },
                              { label: '金额缺失', tone: 'alert' },
                            ],
                          },
                          {
                            label: '流程层',
                            value: '时序',
                            tone: 'warning',
                            children: [
                              { label: '未按时提报', tone: 'warning' },
                              { label: '未审批', tone: 'brand' },
                            ],
                          },
                          {
                            label: '组织层',
                            value: '责任',
                            tone: 'brand',
                            children: [
                              { label: '责任人缺失', tone: 'alert' },
                              { label: '跨部门争议', tone: 'warning' },
                            ],
                          },
                          {
                            label: '系统层',
                            value: '集成',
                            tone: 'finance',
                            children: [
                              { label: '接口失败', tone: 'alert' },
                              { label: '主数据不一致', tone: 'warning' },
                            ],
                          },
                        ]}
                        caption="数据 → 流程 → 组织 → 系统 → 战略"
                      />
                    </div>
                  )}

                  {!nextCycleBudget && !nextCycleLoading && (
                    <div className="glass-card-static p-10 text-center text-surface-400">
                      <Activity size={40} className="mx-auto mb-3 opacity-30" />
                      <p className="text-sm">点击「一键分析」启动次年 AI 智能建议</p>
                      <p className="text-xs mt-2">预算建议 / 战略对齐 / 采集异常</p>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          )}
        </div>
      </div>
    </div>
  );
}
