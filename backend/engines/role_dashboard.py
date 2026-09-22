"""
角色化 Dashboard 引擎 — v8.0 模块 H
按 `经营分析方法论.md` §4.6 角色化运营深化
- CFO 视图：9 卡九宫格 + 4 框架 + Top 5 预警
- 中心负责人视图：中心健康度 + 3GAP/3List + 预算进度
- 品种经理视图：产品收入/毛利/份额 + ROI + 政策风险
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem
from models.alert import AlertRecord
from models.analysis import ExecutionRate
from models.expense import ExpenseReport
from models.approval import ApprovalRecord
from models.strategic import StrategicInitiative

# DiagnosisEngine card_type → CFO 九宫格 key / 展示名
_CARD_UI: Dict[str, Tuple[str, str]] = {
    "revenue_health": ("revenue_health", "营收健康"),
    "gross_margin": ("gross_margin", "毛利质量"),
    "expense_pacing": ("expense_pacing", "费用节奏"),
    "product_mix": ("product_mix", "产品组合"),
    "channel_split": ("channel_split", "渠道分布"),
    "profit_authenticity": ("profit_authenticity", "利润真实性"),
    "commercialization_efficiency": ("commercialization", "商业化效率"),
    "policy_risk": ("policy_risk", "政策风险"),
    "cashflow_quality": ("cashflow_quality", "现金流质量"),
}

_STUB_DIAGNOSIS_CARDS: Dict[str, Dict[str, Any]] = {
    ui_key: {"status": "green", "value": 0, "label": label, "reason": "", "card_type": card_type}
    for card_type, (ui_key, label) in _CARD_UI.items()
}

_DIAG_CACHE: Dict[str, Tuple[float, Dict[str, Dict[str, Any]]]] = {}
_DIAG_TTL_SEC = 90.0


def _default_period(period: Optional[str]) -> str:
    if period and len(period) >= 7:
        return period[:7]
    return datetime.now().strftime("%Y-%m")


def _fmt_cny(amount: float) -> str:
    n = abs(float(amount or 0))
    if n >= 10000:
        return f"¥{n / 10000:.1f}万"
    return f"¥{n:,.0f}"


def _pick_metric_value(metrics: Any) -> float:
    if not isinstance(metrics, dict):
        return 0.0
    for key in (
        "ytd_progress_pct",
        "progress_deviation_pp",
        "budget_achievement_pct",
        "budget_gap_pp",
        "promo_progress",
        "roi",
        "execution_rate",
        "non_operating_pct",
    ):
        val = metrics.get(key)
        if isinstance(val, (int, float)) and float(val) != 0:
            return round(float(val), 1)
    for val in metrics.values():
        if isinstance(val, (int, float)) and float(val) != 0:
            return round(float(val), 1)
    return 0.0


# ─── 角色定义 ─────────────────────────────────────

SUPPORTED_ROLES = ("cfo", "center_lead", "product_manager")


class RoleDashboardEngine:
    """角色化数据聚合引擎：按 user.role 输出定制视图"""

    def __init__(self):
        pass

    async def build(
        self,
        role: str,
        db: AsyncSession,
        center_id: Optional[str] = None,
        l1_code: Optional[str] = None,
        period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """根据角色生成 Dashboard 数据"""
        if role not in SUPPORTED_ROLES:
            raise ValueError(
                f"Unsupported role: {role}. Supported: {SUPPORTED_ROLES}"
            )

        if role == "cfo":
            return await self._build_cfo(db, period)
        elif role == "center_lead":
            return await self._build_center_lead(db, center_id, period)
        else:  # product_manager
            return await self._build_product_manager(db, l1_code, period)

    # ═══════════════════════════════════════════════════════════════
    # CFO 视图：9 卡九宫格 + 4 框架 + Top 5 预警
    # ═══════════════════════════════════════════════════════════════

    async def _build_cfo(
        self, db: AsyncSession, period: Optional[str]
    ) -> Dict[str, Any]:
        """CFO 视图：经营全景 + 战略 + 风险"""
        budget_summary = await self._aggregate_budget_summary(db, center_id=None)
        alerts = await self._top_alerts(db, limit=5)

        # 4 框架概览
        framework_overview = {
            "dupont": "ROE = 销售净利率 × 资产周转率 × 权益乘数",
            "bridge": "本期-上期差异 = 价格/数量/结构/汇率/其他",
            "bcg": "市场份额×增长率 → 发展/收缩/稳定/探索",
            "sar": "战略(S) → 行动(A) → 结果(R) 闭环",
        }

        # 战略举措
        stmt_si = select(StrategicInitiative).where(
            StrategicInitiative.status == "active"
        )
        result_si = await db.execute(stmt_si)
        initiatives = result_si.scalars().all()

        strategic_summary = {
            "active_count": len(initiatives),
            "by_priority": {"high": 0, "medium": 0, "low": 0},
            "by_intent": {},
        }
        for si in initiatives:
            p = getattr(si, "priority", "medium") or "medium"
            strategic_summary["by_priority"][p] = (
                strategic_summary["by_priority"].get(p, 0) + 1
            )
            intent = getattr(si, "strategic_intent_l1", "未分类") or "未分类"
            strategic_summary["by_intent"][intent] = (
                strategic_summary["by_intent"].get(intent, 0) + 1
            )

        period_key = _default_period(period)
        diagnosis_cards = await self._live_diagnosis_cards(db, period_key)
        decision_brief = await self.build_decision_brief(
            db, period=period_key, diagnosis_cards=diagnosis_cards
        )

        return {
            "role": "cfo",
            "title": "CFO 经营全景",
            "subtitle": "战略 · 预算 · 风险 · 现金流",
            "period": period_key,
            "kpis": {
                "total_budget": budget_summary["total_budget"],
                "total_used": budget_summary["total_used"],
                "execution_rate": budget_summary["execution_rate"],
                "open_alerts": sum(1 for a in alerts if a["status"] != "已闭环"),
                "active_strategies": strategic_summary["active_count"],
            },
            "budget_summary": budget_summary,
            "diagnosis_cards": diagnosis_cards,
            "decision_brief": decision_brief,
            "frameworks": framework_overview,
            "strategic_summary": strategic_summary,
            "top_alerts": alerts,
        }

    # ═══════════════════════════════════════════════════════════════
    # 中心负责人视图：3GAP/3List + 预算进度 + 中心对比
    # ═══════════════════════════════════════════════════════════════

    async def _build_center_lead(
        self, db: AsyncSession, center_id: Optional[str], period: Optional[str]
    ) -> Dict[str, Any]:
        """中心负责人视图：聚焦自己中心的健康度"""
        if not center_id:
            # 取第一个中心作为默认
            stmt = select(BudgetItem.center_id).distinct().limit(1)
            result = await db.execute(stmt)
            center_id = result.scalar_one_or_none() or "C01"

        budget_summary = await self._aggregate_budget_summary(db, center_id=center_id)
        alerts = await self._top_alerts(db, limit=10, center_id=center_id)

        # 3GAP（基于 ExecutionRate）
        gap_data = await self._compute_3gap(db, center_id, period)

        # 3List 分类（基于执行率偏差）
        list_data = await self._compute_3list(db, center_id)

        # 待审批
        pending = await self._pending_approvals(db, center_id)

        return {
            "role": "center_lead",
            "title": "中心健康度",
            "subtitle": f"中心 {center_id} · 3GAP/3List · 预算进度",
            "center_id": center_id,
            "kpis": {
                "total_budget": budget_summary["total_budget"],
                "total_used": budget_summary["total_used"],
                "execution_rate": budget_summary["execution_rate"],
                "open_alerts": sum(1 for a in alerts if a["status"] != "已闭环"),
                "pending_approvals": pending,
            },
            "budget_summary": budget_summary,
            "three_gap": gap_data,
            "three_list": list_data,
            "alerts": alerts,
            "pending_approvals_count": pending,
        }

    # ═══════════════════════════════════════════════════════════════
    # 品种经理视图：产品维度 + ROI + 政策风险
    # ═══════════════════════════════════════════════════════════════

    async def _build_product_manager(
        self, db: AsyncSession, l1_code: Optional[str], period: Optional[str]
    ) -> Dict[str, Any]:
        """品种经理视图：聚焦单一 L1 科目（产品）"""
        if not l1_code:
            l1_code = "01"  # 默认第一个

        # 该 L1 的预算项
        stmt = select(BudgetItem).where(
            BudgetItem.l1_code == l1_code,
            BudgetItem.status.in_(["已授予", "执行中"]),
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        annual = sum(float(i.annual_amount or 0) for i in items)
        used = sum(float(i.used_amount or 0) for i in items)
        execution_rate = round(used / annual * 100, 2) if annual > 0 else 0

        # 该 L1 下的预警
        alerts = await self._top_alerts(db, limit=10, l1_code=l1_code)

        # ROI / 政策风险（简化：基于执行率偏差和象限）
        roi_data = self._compute_roi(items)
        policy_risk = self._assess_policy_risk(items, alerts)

        # 产品维度的执行率分布
        product_distribution = []
        for item in items:
            rate = (
                round(float(item.used_amount or 0) / float(item.annual_amount or 1) * 100, 2)
                if float(item.annual_amount or 0) > 0
                else 0
            )
            product_distribution.append({
                "budget_id": item.budget_id,
                "budget_name": item.budget_name,
                "quadrant": item.quadrant,
                "category": item.budget_category,
                "execution_rate": rate,
                "annual_amount": float(item.annual_amount or 0),
                "used_amount": float(item.used_amount or 0),
            })

        return {
            "role": "product_manager",
            "title": "产品经营分析",
            "subtitle": f"L1 科目 {l1_code} · 收入/毛利/份额/ROI",
            "l1_code": l1_code,
            "kpis": {
                "total_budget": annual,
                "total_used": used,
                "execution_rate": execution_rate,
                "open_alerts": sum(1 for a in alerts if a["status"] != "已闭环"),
                "product_count": len(items),
            },
            "roi_summary": roi_data,
            "policy_risk": policy_risk,
            "product_distribution": product_distribution,
            "alerts": alerts,
        }

    # ═══════════════════════════════════════════════════════════════
    # 通用聚合方法
    # ═══════════════════════════════════════════════════════════════

    async def _aggregate_budget_summary(
        self, db: AsyncSession, center_id: Optional[str]
    ) -> Dict[str, Any]:
        """预算汇总"""
        conditions = [BudgetItem.status.in_(["已授予", "执行中"])]
        if center_id:
            conditions.append(BudgetItem.center_id == center_id)

        stmt = select(BudgetItem).where(*conditions)
        result = await db.execute(stmt)
        items = result.scalars().all()

        total_budget = sum(float(i.annual_amount or 0) for i in items)
        total_used = sum(float(i.used_amount or 0) for i in items)
        total_available = sum(float(i.available_amount or 0) for i in items)
        execution_rate = round(
            total_used / total_budget * 100, 2
        ) if total_budget > 0 else 0

        return {
            "item_count": len(items),
            "total_budget": total_budget,
            "total_used": total_used,
            "total_available": total_available,
            "execution_rate": execution_rate,
        }

    async def _top_alerts(
        self,
        db: AsyncSession,
        limit: int = 10,
        center_id: Optional[str] = None,
        l1_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Top 预警"""
        conditions = [AlertRecord.alert_status != "已闭环"]
        if l1_code:
            conditions.append(AlertRecord.l1_code == l1_code)

        if center_id:
            # 通过 budget_id 关联
            budget_stmt = select(BudgetItem.budget_id).where(
                BudgetItem.center_id == center_id
            )
            budget_result = await db.execute(budget_stmt)
            budget_ids = [row[0] for row in budget_result.all()]
            if budget_ids:
                conditions.append(AlertRecord.budget_id.in_(budget_ids))
            else:
                return []

        stmt = select(AlertRecord).where(*conditions).order_by(
            AlertRecord.created_at.desc()
        ).limit(limit)
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        return [
            {
                "alert_id": a.alert_id,
                "level": a.alert_level,
                "type": a.alert_type,
                "status": a.alert_status,
                "l1_code": a.l1_code,
                "deviation_rate": float(a.deviation_rate) if a.deviation_rate else 0,
            }
            for a in alerts
        ]

    async def _compute_3gap(
        self, db: AsyncSession, center_id: str, period: Optional[str]
    ) -> Dict[str, Any]:
        """3GAP 分析（简化版）"""
        stmt = (
            select(ExecutionRate)
            .where(ExecutionRate.center_id == center_id)
            .order_by(ExecutionRate.period.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        latest = result.scalar_one_or_none()

        if latest:
            return {
                "gap1": float(latest.gap1) if latest.gap1 else 0,
                "gap2": float(latest.gap2) if latest.gap2 else 0,
                "gap3": float(latest.gap3) if latest.gap3 else 0,
                "period": latest.period,
            }
        return {
            "gap1": 0,
            "gap2": 0,
            "gap3": 0,
            "period": period or "current",
        }

    async def _compute_3list(
        self, db: AsyncSession, center_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """3List 分类（必赢/改善/资源）"""
        stmt = select(BudgetItem).where(
            BudgetItem.center_id == center_id,
            BudgetItem.status.in_(["已授予", "执行中"]),
        )
        result = await db.execute(stmt)
        items = result.scalars().all()

        must_win: List[Dict] = []
        improve: List[Dict] = []
        resource: List[Dict] = []

        for item in items:
            rate = (
                float(item.used_amount or 0) / float(item.annual_amount or 1) * 100
                if float(item.annual_amount or 0) > 0
                else 0
            )
            entry = {
                "budget_id": item.budget_id,
                "budget_name": item.budget_name,
                "execution_rate": round(rate, 2),
                "quadrant": item.quadrant,
            }
            # 必赢清单：发展象限且执行率 < 80%
            if item.quadrant == "发展" and rate < 80:
                must_win.append(entry)
            # 改善清单：稳定/发展象限但超支
            elif item.quadrant in ("发展", "稳定") and rate > 100:
                improve.append(entry)
            # 资源清单：收缩象限或执行率 < 30%
            elif item.quadrant == "收缩" or rate < 30:
                resource.append(entry)

        return {
            "must_win": must_win[:5],
            "improve": improve[:5],
            "resource": resource[:5],
        }

    async def _pending_approvals(
        self, db: AsyncSession, center_id: Optional[str]
    ) -> int:
        """待审批数"""
        stmt = select(func.count(ApprovalRecord.approval_id)).where(
            ApprovalRecord.approval_action == "待审批"
        )
        result = await db.execute(stmt)
        return int(result.scalar() or 0)

    @staticmethod
    def _compute_roi(items: List[BudgetItem]) -> Dict[str, Any]:
        """ROI 简化计算：基于执行率与象限

        ROI 分级（依据方法论 §4.6）：
        - 高：执行率 60-95% 的预算（资金使用有效）
        - 中：执行率 30-60% 或 95-110%（需关注）
        - 低：执行率 <30%（未启动）或 >110%（超支）
        """
        if not items:
            return {
                "avg_roi": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "items": [],
            }

        roi_items = []
        high_count = 0
        medium_count = 0
        low_count = 0
        for item in items:
            rate = (
                float(item.used_amount or 0) / float(item.annual_amount or 1) * 100
                if float(item.annual_amount or 0) > 0
                else 0
            )
            # 简化 ROI：执行率在 60-95% 视为高 ROI
            if 60 <= rate <= 95:
                roi = "高"
                high_count += 1
            elif rate < 30 or rate > 110:
                roi = "低"
                low_count += 1
            else:
                roi = "中"
                medium_count += 1
            roi_items.append({
                "budget_id": item.budget_id,
                "roi": roi,
                "execution_rate": round(rate, 2),
            })

        return {
            "avg_roi": round((high_count / len(items)) * 100, 2) if items else 0,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "items": roi_items[:10],
        }

    @staticmethod
    def _assess_policy_risk(
        items: List[BudgetItem], alerts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """政策风险评估（基于 L1 类型和预警）"""
        high_alerts = [a for a in alerts if a["level"] in ("红色", "橙色")]
        # L1-01 研发 + 红色预警 = 高政策风险
        has_rnd = any(i.l1_code == "01" for i in items)
        risk_level = "高" if (has_rnd and len(high_alerts) > 0) else (
            "中" if len(high_alerts) > 0 else "低"
        )
        return {
            "risk_level": risk_level,
            "high_alert_count": len(high_alerts),
            "factors": [
                f"研发类预算: {has_rnd}",
                f"高优先级预警: {len(high_alerts)}",
            ],
        }

    # ═══════════════════════════════════════════════════════════════
    # 本周拍板 + 活诊断九卡（失败回退 stub，不拖垮驾驶舱）
    # ═══════════════════════════════════════════════════════════════

    async def _live_diagnosis_cards(
        self, db: AsyncSession, period: str
    ) -> Dict[str, Dict[str, Any]]:
        """跑 9 张 diagnose_*（无 LLM），映射到 CFO 九宫格。90s 缓存。"""
        cached = _DIAG_CACHE.get(period)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]

        cards = {k: dict(v) for k, v in _STUB_DIAGNOSIS_CARDS.items()}
        try:
            from engines.business_diagnosis import NINE_CARDS, DiagnosisEngine

            engine = DiagnosisEngine()
            for meta in NINE_CARDS:
                card_type = meta["type"]
                ui_key, label = _CARD_UI.get(card_type, (card_type, meta["name"]))
                method = getattr(engine, f"diagnose_{card_type}", None)
                if method is None:
                    continue
                try:
                    result = await method(period, db)
                except Exception as exc:
                    logger.warning(f"[role_dashboard] diagnose_{card_type} failed: {exc}")
                    result = {}
                light = result.get("signal_light") or "green"
                if light not in ("red", "yellow", "green"):
                    light = "green"
                metrics = result.get("metrics_json") or {}
                reason = (result.get("light_reason") or "")[:160]
                nums = [
                    float(v)
                    for v in (metrics.values() if isinstance(metrics, dict) else [])
                    if isinstance(v, (int, float))
                ]
                if metrics.get("error") or (
                    light != "green" and nums and all(n == 0 for n in nums)
                ):
                    light = "green"
                    reason = "本期尚无足够实际数，信号灯暂不点亮"
                cards[ui_key] = {
                    "status": light,
                    "value": _pick_metric_value(metrics),
                    "label": label,
                    "reason": reason,
                    "card_type": card_type,
                }
        except Exception as exc:
            logger.warning(f"[role_dashboard] live diagnosis unavailable: {exc}")

        _DIAG_CACHE[period] = (now + _DIAG_TTL_SEC, cards)
        return cards

    async def build_decision_brief(
        self,
        db: AsyncSession,
        period: Optional[str] = None,
        diagnosis_cards: Optional[Dict[str, Dict[str, Any]]] = None,
        limit: int = 3,
    ) -> Dict[str, Any]:
        """本周拍板：红黄诊断 / 大额待审报销 / 红橙预警 / B 类超进度，按金额与严重度取 Top 3。"""
        period_key = _default_period(period)
        ranked: List[Dict[str, Any]] = []

        if diagnosis_cards is None:
            diagnosis_cards = await self._live_diagnosis_cards(db, period_key)

        for key, card in (diagnosis_cards or {}).items():
            status = card.get("status")
            if status not in ("red", "yellow"):
                continue
            ranked.append({
                "id": f"card-{key}",
                "source": "diagnosis",
                "severity": status,
                "title": card.get("label") or key,
                "money_label": card.get("reason") or "诊断灯",
                "money_value": float(card.get("value") or 0),
                "action": "打开经营分析看证据",
                "why": card.get("reason") or "诊断信号灯需复核",
                "href": "/analysis",
                "secondary_href": "/impact",
                "score": 88 if status == "red" else 58,
            })

        try:
            alerts = await self._top_alerts(db, limit=20)
            for alert in alerts:
                if alert.get("level") not in ("红色", "橙色"):
                    continue
                deviation = abs(float(alert.get("deviation_rate") or 0))
                is_red = alert["level"] == "红色"
                ranked.append({
                    "id": f"alert-{alert['alert_id']}",
                    "source": "alert",
                    "severity": "red" if is_red else "orange",
                    "title": f"{alert.get('type') or '预警'} · {alert.get('alert_id')}",
                    "money_label": f"偏离 {deviation:.1f}%",
                    "money_value": deviation,
                    "action": "处理预警并看影响面",
                    "why": f"{alert['level']} · 状态{alert.get('status')}",
                    "href": "/alert",
                    "secondary_href": "/impact",
                    "score": (92 if is_red else 74) + min(deviation, 20) * 0.2,
                })
        except Exception as exc:
            logger.warning(f"[role_dashboard] brief alerts skipped: {exc}")

        try:
            pending_statuses = ("待审批", "组织线审批中", "法人线审批中")
            stmt = (
                select(ExpenseReport)
                .where(ExpenseReport.status.in_(pending_statuses))
                .order_by(ExpenseReport.amount.desc())
                .limit(5)
            )
            result = await db.execute(stmt)
            for exp in result.scalars().all():
                amount = float(exp.amount or 0)
                ranked.append({
                    "id": f"exp-{exp.expense_id}",
                    "source": "expense",
                    "severity": "red" if amount >= 100000 else "yellow",
                    "title": f"大额报销 {exp.expense_id} 待终审",
                    "money_label": _fmt_cny(amount),
                    "money_value": amount,
                    "action": "看影响面后批 / 驳",
                    "why": (
                        f"{exp.control_tag or '未标管控'} · 预算 {exp.budget_id}"
                        + (f" · {(exp.description or '')[:36]}" if exp.description else "")
                    ),
                    "href": "/expense",
                    "secondary_href": "/impact",
                    "score": 200.0 + amount / 1000.0,
                })
        except Exception as exc:
            logger.warning(f"[role_dashboard] brief expenses skipped: {exc}")

        try:
            month_num = int(period_key.split("-")[1])
            expected = month_num / 12.0
            stmt = select(BudgetItem).where(
                BudgetItem.budget_category == "B",
                BudgetItem.status.in_(["已授予", "执行中"]),
            )
            result = await db.execute(stmt)
            for item in result.scalars().all():
                annual = float(item.annual_amount or 0)
                used = float(item.used_amount or 0)
                if annual <= 0:
                    continue
                rate = used / annual
                if rate < expected + 0.15:
                    continue
                ranked.append({
                    "id": f"b-{item.budget_id}",
                    "source": "budget",
                    "severity": "orange",
                    "title": f"{item.budget_name} · B类节奏偏快",
                    "money_label": f"执行 {rate:.0%} / 时点 {expected:.0%}",
                    "money_value": used,
                    "action": "冻结增量，转里程碑后再放",
                    "why": "B 类无证据占用，建议看影响面后决定是否 B→A",
                    "href": "/budget",
                    "secondary_href": "/impact",
                    "score": 62.0 + rate * 25.0,
                })
        except Exception as exc:
            logger.warning(f"[role_dashboard] brief B-class skipped: {exc}")

        try:
            from models.hcp_compliance import HCP

            stmt = (
                select(HCP)
                .where(HCP.annual_payment_total > 0)
                .order_by(HCP.annual_payment_total.desc())
                .limit(3)
            )
            result = await db.execute(stmt)
            for hcp in result.scalars().all():
                paid = float(hcp.annual_payment_total or 0)
                limit_amt = float(hcp.payment_limit or 50000)
                remaining = max(limit_amt - paid, 0)
                headroom = remaining / limit_amt if limit_amt else 1
                if headroom > 0.35:
                    continue
                ranked.append({
                    "id": f"hcp-{hcp.hcp_id}",
                    "source": "hcp",
                    "severity": "red" if headroom < 0.1 else "yellow",
                    "title": f"{hcp.name} · 年度付款将触顶",
                    "money_label": f"已付 {_fmt_cny(paid)} / 限额 {_fmt_cny(limit_amt)}",
                    "money_value": paid,
                    "action": "核对现场证据后再付",
                    "why": f"剩余 {_fmt_cny(remaining)}，付款前确认签到与知情同意",
                    "href": "/hcp",
                    "secondary_href": "/impact",
                    "score": 70.0 + (1 - headroom) * 20.0,
                })
        except Exception as exc:
            logger.warning(f"[role_dashboard] brief HCP skipped: {exc}")

        try:
            from models.expense_ops import ThreeFlowMismatch

            stmt = select(func.count()).select_from(ThreeFlowMismatch).where(
                ThreeFlowMismatch.status == "pending"
            )
            pending_count = int((await db.execute(stmt)).scalar() or 0)
            if pending_count > 0:
                ranked.append({
                    "id": "three-flow-pending",
                    "source": "expense",
                    "severity": "yellow",
                    "title": f"{pending_count} 笔三流不一致待确认",
                    "money_label": f"{pending_count} 张发票",
                    "money_value": float(pending_count),
                    "action": "核对销方/收款人/商户",
                    "why": "销方、收款人、水单商户不一致，过白名单或退单后再付",
                    "href": "/expense",
                    "secondary_href": "/impact",
                    "score": 64.0 + min(pending_count, 10),
                })
        except Exception as exc:
            logger.warning(f"[role_dashboard] brief three-flow skipped: {exc}")

        ranked.sort(key=lambda row: float(row.get("score") or 0), reverse=True)
        top = ranked[: max(1, min(limit, 3))]
        for idx, item in enumerate(top, start=1):
            item["rank"] = idx
            item.pop("score", None)

        return {
            "period": period_key,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "items": top,
        }
