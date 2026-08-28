/**
 * OntologyPage — v11.0 语义仪表盘
 *
 * 重新定位：不再只是 CRUD viewer，而是"本体运行状态 + 业务决策依据"
 * 6 个区块：
 * 1. Header + 4 KPI（活跃场景/规则已用/健康度/覆盖率）
 * 2. 场景命中 TOP（24h 折线/柱状）
 * 3. 规则使用率（柱状 + 死规则列表）
 * 4. 健康度 5 维（已有 API）
 * 5. 本体技术债（已有 API）
 * 6. 最近推理链路
 */
import { useState, useEffect, useCallback } from 'react';
import {
  Network, ChevronDown, RefreshCw, Activity, Tag, Zap, Brain,
  AlertTriangle, CheckCircle, Clock, Database, Sparkles,
} from 'lucide-react';
import { clsx } from 'clsx';
import { motion, AnimatePresence } from 'framer-motion';
import { ontologyApi, ontologyRuntimeApi } from '../services/api';
import CollapsibleSection from '../components/ui/CollapsibleSection';
import RuleUsageChart, { type RuleUsageItem } from '../components/ontology/RuleUsageChart';
import SceneHitTimeline, { type SceneHitItem } from '../components/ontology/SceneHitTimeline';

interface RuntimeStats {
  active_scenes: number;
  total_scenes: number;
  total_hits_24h: number;
  rules_total: number;
  rules_used: number;
  rules_dead: number;
  coverage_rate_7d: number;
  total_events_7d: number;
  updated_at?: string;
}

export default function OntologyPage() {
  const [stats, setStats] = useState<RuntimeStats | null>(null);
  const [scenes, setScenes] = useState<SceneHitItem[]>([]);
  const [rulesUsage, setRulesUsage] = useState<RuleUsageItem[]>([]);
  const [deadRules, setDeadRules] = useState<RuleUsageItem[]>([]);
  const [healthScore, setHealthScore] = useState<any>(null);
  const [techDebt, setTechDebt] = useState<any>(null);
  const [traces, setTraces] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. 整体 stats
      const statsRes = await ontologyRuntimeApi.getStats();
      if (statsRes.success && statsRes.data) setStats(statsRes.data as RuntimeStats);

      // 2. 场景命中
      const scenesRes = await ontologyRuntimeApi.getScenes();
      if (scenesRes.success && scenesRes.data) {
        setScenes((scenesRes.data as any).scenes || []);
      }

      // 3. 规则使用率
      const rulesRes = await ontologyRuntimeApi.getRules();
      if (rulesRes.success && rulesRes.data) {
        const r = rulesRes.data as any;
        setRulesUsage(r.rules || []);
        setDeadRules(r.dead_rules || []);
      }

      // 4. 健康度
      const healthRes = await ontologyApi.getHealthScore();
      if (healthRes.success && healthRes.data) setHealthScore(healthRes.data);

      // 5. 技术债
      try {
        const debtRes = await fetch('/api/ontology/tech-debt').then(r => r.json());
        if (debtRes.success && debtRes.data) setTechDebt(debtRes.data);
      } catch {
        // optional
      }

      // 6. 最近 trace
      const traceRes = await ontologyRuntimeApi.getTraces(10);
      if (traceRes.success && traceRes.data) {
        setTraces((traceRes.data as any).traces || []);
      }
    } catch (e: any) {
      setError(e.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return (
    <div className="space-y-6 w-full min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-finance-800 font-display flex items-center gap-2">
            <Network size={20} className="text-finance-600" />
            本体语义中枢
          </h1>
          <p className="text-xs text-surface-500 mt-1">6 层架构 · 运行时观测 · AI 决策依据</p>
        </div>
        <div className="flex items-center gap-2">
          {stats?.updated_at && (
            <span className="text-[10px] text-surface-400">
              缓存更新: {new Date(stats.updated_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          <button
            onClick={async () => { await ontologyRuntimeApi.refresh(); fetchAll(); }}
            className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-surface-500 hover:text-finance-600 hover:bg-finance-50 transition-colors"
          >
            <RefreshCw size={11} /> 刷新
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-alert-50 border border-alert-200 text-xs text-alert-700">
          {error}
        </div>
      )}

      {/* 4 KPI */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="kpi-card">
          <div className="flex items-center gap-1.5">
            <Zap size={13} className="text-brand-500" />
            <span className="text-xs text-surface-500">活跃场景</span>
          </div>
          <div className="flex items-baseline gap-1.5">
            <p className="text-2xl font-bold text-brand-600 font-display">
              {stats?.active_scenes ?? '-'}
            </p>
            <span className="text-[10px] text-surface-400">/ {stats?.total_scenes ?? '-'} 总数</span>
          </div>
          <p className="text-[10px] text-surface-400">24h 命中 {stats?.total_hits_24h ?? 0} 次</p>
        </div>

        <div className="kpi-card">
          <div className="flex items-center gap-1.5">
            <Tag size={13} className="text-finance-500" />
            <span className="text-xs text-surface-500">规则使用</span>
          </div>
          <div className="flex items-baseline gap-1.5">
            <p className="text-2xl font-bold text-finance-600 font-display">
              {stats?.rules_used ?? '-'}
            </p>
            <span className="text-[10px] text-surface-400">/ {stats?.rules_total ?? '-'} 总数</span>
          </div>
          <p className="text-[10px] text-surface-400">死规则 {stats?.rules_dead ?? 0} 条</p>
        </div>

        <div className="kpi-card">
          <div className="flex items-center gap-1.5">
            <Brain size={13} className="text-compliance-500" />
            <span className="text-xs text-surface-500">健康度</span>
          </div>
          <div className="flex items-baseline gap-1.5">
            <p className={clsx(
              'text-2xl font-bold font-display',
              (healthScore?.total_score ?? 0) >= 80 ? 'text-compliance-600' :
              (healthScore?.total_score ?? 0) >= 60 ? 'text-warning-600' : 'text-alert-600',
            )}>
              {healthScore?.total_score?.toFixed(0) ?? '-'}
            </p>
            <span className="text-[10px] text-surface-400">/ 100</span>
          </div>
          <p className="text-[10px] text-surface-400">
            {healthScore?.maturity_level || '未计算'}
          </p>
        </div>

        <div className="kpi-card">
          <div className="flex items-center gap-1.5">
            <Activity size={13} className="text-warning-500" />
            <span className="text-xs text-surface-500">覆盖率</span>
          </div>
          <div className="flex items-baseline gap-1.5">
            <p className="text-2xl font-bold text-warning-600 font-display">
              {stats?.coverage_rate_7d?.toFixed(0) ?? '-'}
            </p>
            <span className="text-[10px] text-surface-400">%</span>
          </div>
          <p className="text-[10px] text-surface-400">业务事件 → 场景 (7d)</p>
        </div>
      </div>

      {/* v11.0: 本体价值说明 — 让用户知道"本体在做什么" */}
      <div className="p-4 rounded-xl bg-gradient-to-br from-finance-50 via-brand-50 to-compliance-50 border border-finance-200/60">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-finance-500 to-brand-600 flex items-center justify-center">
            <Sparkles size={14} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-finance-800 mb-1">本体价值说明（v11.0）</p>
            <p className="text-[11px] text-surface-600 leading-relaxed">
              本体是 AI-Finance 系统的<strong className="text-finance-700">规则与场景中枢</strong>，不是摆设：
              ① <strong>Chat 路由</strong> — 每次对话都先经过 <code className="px-1 bg-white rounded">match_scene_semantic</code> 匹配场景；
              ② <strong>业务规则</strong> — 8+ 引擎（预算/报销/预警/审批/HCP/管线）从 <code className="px-1 bg-white rounded">OntologyRule</code> 加载 HR/SR 规则；
              ③ <strong>LLM 上下文</strong> — 为 AI 注入 4-5 个本体事实块作为推理依据；
              ④ <strong>业务可解释</strong> — ChatPage 显示推理面板，AlertPage/ExpensePage/ApprovalPage 显示"依据 SR/HR-xxx"。
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-finance-700">
              <span className="flex items-center gap-1">
                <CheckCircle size={10} className="text-compliance-500" />
                过去 24h 驱动 <strong>{stats?.total_hits_24h ?? 0}</strong> 次 AI 推理
              </span>
              <span className="text-surface-300">·</span>
              <span className="flex items-center gap-1">
                <CheckCircle size={10} className="text-compliance-500" />
                激活 <strong>{stats?.active_scenes ?? 0}</strong> 个业务场景
              </span>
              <span className="text-surface-300">·</span>
              <span className="flex items-center gap-1">
                <CheckCircle size={10} className="text-compliance-500" />
                覆盖 <strong>{stats?.coverage_rate_7d?.toFixed(0) ?? 0}%</strong> 业务事件
              </span>
              <span className="text-surface-300">·</span>
              <span className="flex items-center gap-1">
                <CheckCircle size={10} className="text-compliance-500" />
                <strong>{stats?.rules_used ?? 0}</strong>/<strong>{stats?.rules_total ?? 0}</strong> 规则被实际使用
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 1. 场景命中 TOP */}
      <CollapsibleSection
        title="场景命中 TOP（24h）"
        icon={Zap}
        badge={`${scenes.length} 场景`}
        defaultOpen={true}
      >
        <SceneHitTimeline scenes={scenes} />
      </CollapsibleSection>

      {/* 2. 规则使用率 */}
      <CollapsibleSection
        title="规则使用率"
        icon={Tag}
        badge={`${rulesUsage.length} 规则`}
      >
        <div className="space-y-3">
          <RuleUsageChart rules={rulesUsage} />
          {deadRules.length > 0 && (
            <div className="p-3 rounded-lg bg-surface-50 border border-surface-200">
              <div className="flex items-center gap-1.5 mb-2">
                <AlertTriangle size={12} className="text-warning-500" />
                <span className="text-xs font-semibold text-finance-700">
                  死规则（{deadRules.length} 条从未被激活）
                </span>
                <span className="text-[10px] text-surface-400">— 建议下线或重新激活</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {deadRules.slice(0, 10).map((r) => (
                  <span
                    key={r.rule_id}
                    className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-surface-200 bg-white text-surface-500"
                    title={r.name}
                  >
                    {r.rule_id}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* 3. 健康度 5 维 */}
      <CollapsibleSection
        title="健康度 5 维评分"
        icon={Brain}
        badge={healthScore?.total_score ? `${healthScore.total_score.toFixed(0)} / 100` : ''}
      >
        {healthScore?.dimensions ? (
          <div className="space-y-2">
            {healthScore.dimensions.map((d: any) => (
              <div key={d.dimension_id} className="flex items-center gap-3">
                <span className="text-xs text-finance-700 w-32 truncate">{d.name}</span>
                <div className="flex-1 h-2 bg-surface-100 rounded-full overflow-hidden">
                  <div
                    className={clsx(
                      'h-full rounded-full transition-all',
                      d.score >= 80 ? 'bg-compliance-500' :
                      d.score >= 60 ? 'bg-warning-500' : 'bg-alert-500',
                    )}
                    style={{ width: `${d.score}%` }}
                  />
                </div>
                <span className="text-xs font-mono font-bold w-12 text-right">
                  {d.score.toFixed(0)}
                </span>
                <span className="text-[10px] text-surface-400 w-8">/{d.threshold}</span>
                {d.is_healthy ? (
                  <CheckCircle size={12} className="text-compliance-500" />
                ) : (
                  <AlertTriangle size={12} className="text-warning-500" />
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-surface-400 py-4 text-center">暂无健康度数据</p>
        )}
      </CollapsibleSection>

      {/* 4. 本体技术债 */}
      <CollapsibleSection
        title="本体技术债"
        icon={Database}
        badge="扫描"
      >
        {techDebt ? (
          <div className="space-y-2 text-xs">
            <div className="grid grid-cols-3 gap-2">
              <div className="p-2 rounded bg-surface-50 text-center">
                <p className="text-[10px] text-surface-500">总问题</p>
                <p className="text-lg font-bold text-finance-700">{techDebt.total_issues ?? '-'}</p>
              </div>
              <div className="p-2 rounded bg-surface-50 text-center">
                <p className="text-[10px] text-surface-500">高优先级</p>
                <p className="text-lg font-bold text-alert-600">{techDebt.high_priority ?? '-'}</p>
              </div>
              <div className="p-2 rounded bg-surface-50 text-center">
                <p className="text-[10px] text-surface-500">中优先级</p>
                <p className="text-lg font-bold text-warning-600">{techDebt.medium_priority ?? '-'}</p>
              </div>
            </div>
            {techDebt.recommendations && techDebt.recommendations.length > 0 && (
              <div className="mt-2">
                <p className="text-[11px] font-semibold text-finance-700 mb-1">改进建议：</p>
                <ul className="space-y-1">
                  {techDebt.recommendations.slice(0, 3).map((rec: string, i: number) => (
                    <li key={i} className="text-[11px] text-surface-600 flex gap-1.5">
                      <span className="text-finance-500">•</span>{rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-surface-400 py-4 text-center">技术债扫描中...</p>
        )}
      </CollapsibleSection>

      {/* 5. 最近推理链路 */}
      <CollapsibleSection
        title="最近推理链路"
        icon={Sparkles}
        badge={`${traces.length} 条`}
      >
        {traces.length > 0 ? (
          <div className="space-y-1.5">
            {traces.map((t) => (
              <div
                key={t.trace_id}
                className="flex items-center gap-3 px-2 py-1.5 rounded border border-surface-200 bg-white"
              >
                <div className="flex-shrink-0">
                  <Brain size={12} className="text-finance-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className="badge-gray">{t.scene_name || t.scene_id}</span>
                    {t.rule_ids && t.rule_ids.length > 0 && (
                      <span className="font-mono text-surface-600 truncate">
                        {t.rule_ids.slice(0, 3).join(' / ')}
                        {t.rule_ids.length > 3 && ' 等'}
                      </span>
                    )}
                  </div>
                  {t.conclusion && (
                    <p className="text-[10px] text-surface-500 truncate mt-0.5">{t.conclusion}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 text-[10px] text-surface-400 flex-shrink-0">
                  <span>{t.step_count || 0} 步</span>
                  {t.elapsed_ms != null && <span><Clock size={9} className="inline" /> {t.elapsed_ms}ms</span>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-surface-400 py-4 text-center">暂无推理记录</p>
        )}
      </CollapsibleSection>
    </div>
  );
}
