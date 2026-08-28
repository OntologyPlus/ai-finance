/**
 * TransferSimulator — 调拨影响模拟器
 * 表单 + 实时影响预览（执行率变化 + 预警徽章 + 方向合理性）
 */
import { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { ArrowRightLeft, AlertCircle, CheckCircle2, Save } from 'lucide-react';
import { budgetApi } from '../../services/api';

interface Props {
  period: string;
  onMessage?: (type: 'success' | 'error', title: string, message: string) => void;
}

const DRAFT_KEY = 'budget_transfer_draft';

interface DraftForm {
  from_id: string;
  to_id: string;
  amount: string;
  from_label: string;
  to_label: string;
}

const DEFAULT_DRAFT: DraftForm = {
  from_id: '',
  to_id: '',
  amount: '50',
  from_label: '',
  to_label: '',
};

interface SimulateResult {
  from_rate_change?: { before: number; after: number; delta_pp: number };
  to_rate_change?: { before: number; after: number; delta_pp: number };
  predicted_alerts?: { level: string; item: string; reason: string }[];
  from_id?: string;
  to_id?: string;
  from_quadrant?: string;
  to_quadrant?: string;
  direction_reasonable?: boolean;
  reason?: string;
}

export default function TransferSimulator({ period, onMessage }: Props) {
  const [form, setForm] = useState<DraftForm>(DEFAULT_DRAFT);
  const [items, setItems] = useState<any[]>([]);
  const [result, setResult] = useState<SimulateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [draftSaved, setDraftSaved] = useState(false);

  // 加载预算项 + 恢复草稿
  useEffect(() => {
    const fetchItems = async () => {
      try {
        const res = await budgetApi.getItems({ year: new Date().getFullYear(), page: 1, page_size: 100 });
        const list = (res as any).data?.items || (res as any).data || [];
        setItems(Array.isArray(list) ? list : []);
      } catch (e) {
        // ignore
      }
    };
    fetchItems();

    try {
      const saved = localStorage.getItem(DRAFT_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && typeof parsed === 'object') {
          setForm({ ...DEFAULT_DRAFT, ...parsed });
          setDraftSaved(true);
        }
      }
    } catch (e) {
      // ignore
    }
  }, []);

  // 自动保存草稿
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
        setDraftSaved(true);
      } catch (e) {
        // ignore
      }
    }, 800);
    return () => clearTimeout(timer);
  }, [form]);

  const handleSubmit = async () => {
    if (!form.from_id || !form.to_id) {
      onMessage?.('error', '参数缺失', '请选择源预算项和目标预算项');
      return;
    }
    if (!form.amount || isNaN(Number(form.amount)) || Number(form.amount) <= 0) {
      onMessage?.('error', '金额无效', '请输入大于 0 的金额');
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await budgetApi.simulateTransfer(form.from_id, form.to_id, Number(form.amount));
      const data = (res as any).data || res;
      setResult(data);
      if (data?.error) {
        onMessage?.('error', '模拟失败', data.error);
      }
    } catch (e: any) {
      onMessage?.('error', '模拟失败', e?.message || '未知错误');
    } finally {
      setLoading(false);
    }
  };

  const handleClearDraft = () => {
    localStorage.removeItem(DRAFT_KEY);
    setForm(DEFAULT_DRAFT);
    setDraftSaved(false);
    setResult(null);
  };

  // 执行率对比条形图
  const chartOption = result?.from_rate_change && result?.to_rate_change ? {
    tooltip: { trigger: 'axis' },
    legend: { data: ['调拨前', '调拨后'], top: 0, textStyle: { fontSize: 11 } },
    grid: { top: 30, left: 60, right: 30, bottom: 30 },
    xAxis: { type: 'value', max: 120, axisLabel: { fontSize: 11, formatter: '{value}%' } },
    yAxis: {
      type: 'category',
      data: [
        `源：${result.from_quadrant || form.from_label || form.from_id}`,
        `目标：${result.to_quadrant || form.to_label || form.to_id}`,
      ],
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        name: '调拨前',
        type: 'bar',
        data: [result.from_rate_change.before, result.to_rate_change.before],
        itemStyle: { color: '#94a3b8' },
        label: { show: true, position: 'right', fontSize: 10, formatter: (p: any) => `${p.value.toFixed(1)}%` },
      },
      {
        name: '调拨后',
        type: 'bar',
        data: [result.from_rate_change.after, result.to_rate_change.after],
        itemStyle: { color: '#0ea5e9' },
        label: { show: true, position: 'right', fontSize: 10, formatter: (p: any) => `${p.value.toFixed(1)}%` },
      },
    ],
  } : null;

  return (
    <div className="bg-white rounded-xl border border-surface-200/60 p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-surface-700 flex items-center gap-2">
          <ArrowRightLeft size={16} className="text-finance-600" />
          调拨影响模拟器
        </h3>
        <span className="text-[11px] text-surface-500 flex items-center gap-1">
          {draftSaved ? <><Save size={11} /> 草稿已自动保存</> : null}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label className="text-xs text-surface-600 mb-1 block">源预算项</label>
          <select
            value={form.from_id}
            onChange={e => {
              const it = items.find((i: any) => i.budget_id === e.target.value);
              setForm({ ...form, from_id: e.target.value, from_label: it?.name || it?.budget_name || '' });
            }}
            className="w-full px-3 py-2 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
          >
            <option value="">请选择</option>
            {items.map((it: any) => (
              <option key={it.budget_id} value={it.budget_id}>
                {it.budget_id} - {it.name || it.budget_name || ''}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-surface-600 mb-1 block">目标预算项</label>
          <select
            value={form.to_id}
            onChange={e => {
              const it = items.find((i: any) => i.budget_id === e.target.value);
              setForm({ ...form, to_id: e.target.value, to_label: it?.name || it?.budget_name || '' });
            }}
            className="w-full px-3 py-2 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
          >
            <option value="">请选择</option>
            {items.map((it: any) => (
              <option key={it.budget_id} value={it.budget_id}>
                {it.budget_id} - {it.name || it.budget_name || ''}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-surface-600 mb-1 block">金额（万元）</label>
          <input
            type="number"
            value={form.amount}
            onChange={e => setForm({ ...form, amount: e.target.value })}
            className="w-full px-3 py-2 rounded-lg border border-surface-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-finance-500/20 focus:border-finance-500"
            min="0"
            step="0.1"
          />
        </div>
        <div className="flex items-end gap-2">
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 btn-primary text-sm py-2 disabled:opacity-50"
          >
            {loading ? '模拟中...' : '开始模拟'}
          </button>
          <button
            onClick={handleClearDraft}
            className="px-3 py-2 text-xs rounded-lg border border-surface-200 text-surface-600 hover:bg-surface-50"
            title="清空草稿"
          >
            清空
          </button>
        </div>
      </div>

      {result && !result.error && (
        <div className="space-y-3 pt-2 border-t border-surface-100">
          {chartOption && (
            <ReactECharts option={chartOption} style={{ height: 200 }} notMerge={true} lazyUpdate={true} />
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg p-3 bg-surface-50">
              <div className="text-[11px] text-surface-500 mb-1">源执行率变化</div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-surface-800">
                  {result.from_rate_change?.before.toFixed(1) ?? '-'}%
                </span>
                <span className="text-surface-400">→</span>
                <span className="text-2xl font-bold text-finance-600">
                  {result.from_rate_change?.after.toFixed(1) ?? '-'}%
                </span>
                <span className={`text-xs font-medium ${(result.from_rate_change?.delta_pp ?? 0) >= 0 ? 'text-alert-600' : 'text-compliance-600'}`}>
                  ({(result.from_rate_change?.delta_pp ?? 0) >= 0 ? '+' : ''}{result.from_rate_change?.delta_pp.toFixed(1)}pp)
                </span>
              </div>
            </div>
            <div className="rounded-lg p-3 bg-surface-50">
              <div className="text-[11px] text-surface-500 mb-1">目标执行率变化</div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold text-surface-800">
                  {result.to_rate_change?.before.toFixed(1) ?? '-'}%
                </span>
                <span className="text-surface-400">→</span>
                <span className="text-2xl font-bold text-finance-600">
                  {result.to_rate_change?.after.toFixed(1) ?? '-'}%
                </span>
                <span className={`text-xs font-medium ${(result.to_rate_change?.delta_pp ?? 0) >= 0 ? 'text-compliance-600' : 'text-alert-600'}`}>
                  ({(result.to_rate_change?.delta_pp ?? 0) >= 0 ? '+' : ''}{result.to_rate_change?.delta_pp.toFixed(1)}pp)
                </span>
              </div>
            </div>
          </div>

          {result.direction_reasonable !== undefined && (
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${result.direction_reasonable ? 'bg-compliance-50 text-compliance-700' : 'bg-warning-50 text-warning-700'}`}>
              {result.direction_reasonable ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
              <span className="text-xs font-medium">
                {result.reason || (result.direction_reasonable ? '调拨方向合理' : '调拨方向需关注')}
              </span>
            </div>
          )}

          {result.predicted_alerts && result.predicted_alerts.length > 0 && (
            <div className="rounded-lg border border-alert-200 bg-alert-50/40 p-3">
              <div className="text-[11px] font-semibold text-alert-700 mb-2">⚠ 触发预警预测</div>
              {result.predicted_alerts.map((a, i) => (
                <div key={i} className="flex items-center gap-2 text-xs mb-1">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                    a.level === 'red' ? 'bg-alert-500 text-white' : 'bg-warning-500 text-white'
                  }`}>
                    {a.level === 'red' ? '红' : '黄'}
                  </span>
                  <span className="text-surface-700">{a.reason}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {result?.error && (
        <div className="text-xs text-alert-600 bg-alert-50 rounded-lg p-3">
          ⚠ {result.error}
        </div>
      )}
    </div>
  );
}
