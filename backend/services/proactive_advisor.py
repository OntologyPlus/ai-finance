"""
主动建议引擎（Proactive Advisor）

按《经营分析方法论.md》§3.1 信号灯机制 + §4.1 经营全景诊断实现：
- 扫描 5 类信号源（diagnosis_red 实装 + 4 类 stub）
- 生成主动洞察并持久化到 proactive_insight 表
- 优先级排序：critical > attention > info

设计原则：
- 单个扫描器异常不影响其他扫描器
- 扫描器是幂等的（重复扫描不产生重复洞察：依赖 is_dismissed/is_read 状态管理）
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from engines.alert_monitor import AlertMonitorEngine
from engines.budget_planning import BudgetPlanningEngine
from engines.business_diagnosis import DiagnosisEngine
from models.analysis import ProactiveInsight

# 优先级映射（值越小越优先）
LIGHT_PRIORITY: Dict[str, int] = {"critical": 0, "attention": 1, "info": 2}


class ProactiveAdvisor:
    """主动建议引擎 - 跨模块扫描器

    按《经营分析方法论.md》§3.1 信号灯机制实现，把诊断/预警/预算/报告
    等模块的关键事件主动推送到用户面前。
    """

    def __init__(self) -> None:
        self.diagnosis = DiagnosisEngine()
        self.alert = AlertMonitorEngine()
        self.budget = BudgetPlanningEngine()

    async def scan_and_push_insights(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        period: Optional[str] = None,
    ) -> List[ProactiveInsight]:
        """扫描 5 类信号源并生成洞察。

        Args:
            db: 异步数据库会话
            user_id: 目标用户 ID（None 表示全用户）
            period: 统计期间 (YYYY-MM)

        Returns:
            生成的洞察列表（已持久化到数据库），按 critical > attention > info 排序
        """
        insights: List[ProactiveInsight] = []

        # 1. 诊断卡红灯扫描（实装）
        if period:
            try:
                insights.extend(await self._scan_diagnosis_red(db, period, user_id))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[advisor] diagnosis_red scan failed: {e}")

        # 2-5. 其余 4 类保留 stub（v5.0 已声明"简化版"）
        for stub_result in [
            await self._scan_budget_overrun(db, period, user_id),
            await self._scan_alert_timeout(db, user_id),
            await self._scan_report_pending(db, user_id),
            await self._scan_decision_sla(db, user_id),
        ]:
            insights.extend(stub_result)

        # 按 critical > attention > info 排序
        insights.sort(key=lambda x: LIGHT_PRIORITY.get(x.priority, 99))

        # 持久化（如果之前已存在相同 insight_type+related_object+未 dismiss 的洞察，跳过）
        persisted = await self._persist_insights(db, insights)
        return persisted

    async def _scan_diagnosis_red(
        self,
        db: AsyncSession,
        period: str,
        user_id: Optional[str],
    ) -> List[ProactiveInsight]:
        """诊断卡红灯扫描（实装）。

        读取当期诊断报告，找出所有红灯卡片，生成 critical 级别洞察。
        """
        try:
            report = await self.diagnosis.generate_diagnosis_report(period, db)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[advisor] generate_diagnosis_report failed: {e}")
            return []

        insights: List[ProactiveInsight] = []
        for card in report.get("part2_cards", []):
            if card.get("signal_light") != "red":
                continue
            card_type = card.get("card_type", "")
            card_name = card.get("card_name", "诊断卡")
            light_reason = card.get("light_reason", "")
            insights.append(
                ProactiveInsight(
                    id=uuid.uuid4().hex[:32],
                    user_id=user_id,
                    period=period,
                    insight_type="diagnosis_red",
                    priority="critical",
                    title=f"🔴 {card_name} 信号灯变红",
                    detail=light_reason,
                    action_label="查看诊断",
                    action_url=f"/analysis?card={card_type}",
                    related_object=card.get("id") or card_type,
                )
            )
        return insights

    # ───── 4 类 Stub 扫描器（保留签名，v6.0 阶段返回空 list）──────

    async def _scan_budget_overrun(
        self,
        db: AsyncSession,
        period: Optional[str],
        user_id: Optional[str],
    ) -> List[ProactiveInsight]:
        """预算超支扫描（Stub - 待 v6.x 实装）。

        计划实现：扫描各中心预算执行率 > 100% 的科目，生成 attention 洞察。
        """
        return []

    async def _scan_alert_timeout(
        self,
        db: AsyncSession,
        user_id: Optional[str],
    ) -> List[ProactiveInsight]:
        """预警超时扫描（Stub - 待 v6.x 实装）。

        计划实现：扫描超过 7 天未闭环的橙色/红色预警，生成 critical 洞察。
        """
        return []

    async def _scan_report_pending(
        self,
        db: AsyncSession,
        user_id: Optional[str],
    ) -> List[ProactiveInsight]:
        """报告待办扫描（Stub - 待 v6.x 实装）。

        计划实现：扫描月度/季度报告待编制/待签发状态，生成 attention 洞察。
        """
        return []

    async def _scan_decision_sla(
        self,
        db: AsyncSession,
        user_id: Optional[str],
    ) -> List[ProactiveInsight]:
        """决策 SLA 扫描（Stub - 待 v6.x 实装）。

        计划实现：扫描超过 SLA 时长未决的待办事项，生成 attention 洞察。
        """
        return []

    # ───── 持久化辅助 ─────

    async def _persist_insights(
        self,
        db: AsyncSession,
        insights: List[ProactiveInsight],
    ) -> List[ProactiveInsight]:
        """持久化洞察，避免重复。

        规则：同一用户/全用户 + insight_type + related_object 在未 dismissed 状态下
        已存在则跳过。
        """
        if not insights:
            return []

        # 收集所有需要去重检查的键
        existing_keys: set = set()
        for ins in insights:
            stmt = select(ProactiveInsight.id).where(
                and_(
                    ProactiveInsight.insight_type == ins.insight_type,
                    ProactiveInsight.related_object == ins.related_object,
                    ProactiveInsight.is_dismissed == False,  # noqa: E712
                    ProactiveInsight.period == ins.period,
                )
            )
            if ins.user_id is not None:
                stmt = stmt.where(ProactiveInsight.user_id == ins.user_id)
            else:
                stmt = stmt.where(ProactiveInsight.user_id.is_(None))
            rows = await db.execute(stmt)
            for row in rows.scalars():
                existing_keys.add(
                    (
                        ins.user_id,
                        ins.insight_type,
                        ins.related_object,
                        ins.period,
                    )
                )

        persisted: List[ProactiveInsight] = []
        for ins in insights:
            key = (
                ins.user_id,
                ins.insight_type,
                ins.related_object,
                ins.period,
            )
            if key in existing_keys:
                continue
            db.add(ins)
            persisted.append(ins)

        if persisted:
            await db.commit()
        return persisted
