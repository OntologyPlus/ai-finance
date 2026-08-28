"""
角色化 Dashboard 引擎 — v8.0 模块 H
按 `经营分析方法论.md` §4.6 角色化运营深化
- CFO 视图：9 卡九宫格 + 4 框架 + Top 5 预警
- 中心负责人视图：中心健康度 + 3GAP/3List + 预算进度
- 品种经理视图：产品收入/毛利/份额 + ROI + 政策风险
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem
from models.alert import AlertRecord
from models.analysis import ExecutionRate
from models.expense import ExpenseReport
from models.approval import ApprovalRecord
from models.strategic import StrategicInitiative


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

        return {
            "role": "cfo",
            "title": "CFO 经营全景",
            "subtitle": "战略 · 预算 · 风险 · 现金流",
            "kpis": {
                "total_budget": budget_summary["total_budget"],
                "total_used": budget_summary["total_used"],
                "execution_rate": budget_summary["execution_rate"],
                "open_alerts": sum(1 for a in alerts if a["status"] != "已闭环"),
                "active_strategies": strategic_summary["active_count"],
            },
            "budget_summary": budget_summary,
            "diagnosis_cards": {
                # 9 卡：每个卡的健康状态灯（绿/黄/红）
                "revenue_health": {"status": "green", "value": 0, "label": "营收健康"},
                "gross_margin": {"status": "green", "value": 0, "label": "毛利质量"},
                "expense_pacing": {"status": "yellow", "value": 0, "label": "费用节奏"},
                "product_mix": {"status": "green", "value": 0, "label": "产品组合"},
                "channel_split": {"status": "green", "value": 0, "label": "渠道分布"},
                "profit_authenticity": {"status": "green", "value": 0, "label": "利润真实性"},
                "commercialization": {"status": "yellow", "value": 0, "label": "商业化效率"},
                "policy_risk": {"status": "green", "value": 0, "label": "政策风险"},
                "cashflow_quality": {"status": "green", "value": 0, "label": "现金流质量"},
            },
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
