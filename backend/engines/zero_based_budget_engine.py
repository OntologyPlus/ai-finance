from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.zero_based_budget import ZBBReview, ZBBDecisionUnit, ZBBPackage


class ZeroBasedBudgetEngine:
    """零基预算审视引擎 — 从零开始审视每一项支出的必要性"""

    async def initiate_zbb_review(
        self, period: str, total_budget_constraint: float, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """启动零基预算审视

        Args:
            period: 审视期（YYYY格式）
            total_budget_constraint: 总预算约束金额
            db: 数据库会话

        Returns:
            创建的审视记录信息
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        review = ZBBReview(
            period=period,
            status="启动",
            total_budget_constraint=total_budget_constraint,
            decision_unit_count=0,
        )
        db.add(review)
        await db.flush()

        logger.info(f"ZBB审视已启动: period={period}, constraint={total_budget_constraint}")
        return {
            "review_id": review.id,
            "period": review.period,
            "status": review.status,
            "total_budget_constraint": review.total_budget_constraint,
            "message": f"零基预算审视{period}已启动，总预算约束{total_budget_constraint}万元",
        }

    async def create_decision_unit(
        self, review_id: int, name: str, owner: str, scope: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """创建决策单元

        Args:
            review_id: 所属审视ID
            name: 单元名称
            owner: 负责人
            scope: 范围描述
            db: 数据库会话

        Returns:
            创建的决策单元信息
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        # 验证审视存在
        stmt = select(ZBBReview).where(ZBBReview.id == review_id)
        result = await db.execute(stmt)
        review = result.scalar_one_or_none()
        if review is None:
            return {"error": f"审视ID {review_id} 不存在"}

        if review.status not in ("启动", "编制中"):
            return {"error": f"审视状态为'{review.status}'，无法添加决策单元"}

        unit = ZBBDecisionUnit(
            review_id=review_id,
            name=name,
            owner=owner,
            scope=scope,
            rank=0,
            strategic_value_score=0,
        )
        db.add(unit)

        # 更新审视状态和决策单元计数
        review.status = "编制中"
        review.decision_unit_count += 1
        await db.flush()

        logger.info(f"决策单元已创建: review_id={review_id}, name={name}")
        return {
            "unit_id": unit.id,
            "review_id": review_id,
            "name": unit.name,
            "owner": unit.owner,
            "scope": unit.scope,
            "message": f"决策单元'{name}'已创建",
        }

    async def create_decision_package(
        self, unit_id: int, level: str, amount: float, justification: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """创建决策包

        Args:
            unit_id: 决策单元ID
            level: 包级别（最低/当前/增强）
            amount: 金额
            justification: 必要性说明
            db: 数据库会话

        Returns:
            创建的决策包信息
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        if level not in ("最低", "当前", "增强"):
            return {"error": f"无效的包级别'{level}'，必须为：最低/当前/增强"}

        # 验证决策单元存在
        stmt = select(ZBBDecisionUnit).where(ZBBDecisionUnit.id == unit_id)
        result = await db.execute(stmt)
        unit = result.scalar_one_or_none()
        if unit is None:
            return {"error": f"决策单元ID {unit_id} 不存在"}

        # 根据包级别计算战略对齐度
        strategic_alignment = self._calculate_strategic_alignment(level, unit.strategic_value_score)

        package = ZBBPackage(
            unit_id=unit_id,
            level=level,
            amount=amount,
            justification=justification,
            strategic_alignment=strategic_alignment,
        )
        db.add(package)
        await db.flush()

        logger.info(f"决策包已创建: unit_id={unit_id}, level={level}, amount={amount}")
        return {
            "package_id": package.id,
            "unit_id": unit_id,
            "level": level,
            "amount": amount,
            "justification": justification,
            "strategic_alignment": strategic_alignment,
            "message": f"决策包({level})已创建，金额{amount}万元",
        }

    async def rank_packages(self, review_id: int, db: AsyncSession = None) -> Dict[str, Any]:
        """对审视下所有决策包按战略价值排序

        排序规则：
        1. 先按包级别优先级（最低 > 当前 > 增强，最低优先保障）
        2. 同级别按战略对齐度降序
        3. 同对齐度按金额升序（性价比优先）

        Args:
            review_id: 审视ID
            db: 数据库会话

        Returns:
            排序结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        # 获取审视
        stmt = select(ZBBReview).where(ZBBReview.id == review_id)
        result = await db.execute(stmt)
        review = result.scalar_one_or_none()
        if review is None:
            return {"error": f"审视ID {review_id} 不存在"}

        # 获取所有决策单元
        stmt_units = select(ZBBDecisionUnit).where(ZBBDecisionUnit.review_id == review_id)
        result_units = await db.execute(stmt_units)
        units = result_units.scalars().all()

        if not units:
            return {"error": "该审视下无决策单元"}

        # 获取所有决策包
        unit_ids = [u.id for u in units]
        stmt_pkgs = select(ZBBPackage).where(ZBBPackage.unit_id.in_(unit_ids))
        result_pkgs = await db.execute(stmt_pkgs)
        packages = result_pkgs.scalars().all()

        if not packages:
            return {"error": "该审视下无决策包"}

        # 排序：级别优先级 + 战略对齐度 + 金额
        level_priority = {"最低": 1, "当前": 2, "增强": 3}
        sorted_packages = sorted(
            packages,
            key=lambda p: (level_priority.get(p.level, 99), -p.strategic_alignment, p.amount),
        )

        # 更新排序和决策单元的战略价值评分
        unit_map = {u.id: u for u in units}
        ranked_list = []
        cumulative_amount = 0.0

        for rank_idx, pkg in enumerate(sorted_packages, 1):
            cumulative_amount += pkg.amount
            within_constraint = cumulative_amount <= review.total_budget_constraint

            ranked_list.append({
                "rank": rank_idx,
                "package_id": pkg.id,
                "unit_id": pkg.unit_id,
                "unit_name": unit_map.get(pkg.unit_id, ZBBDecisionUnit()).name if pkg.unit_id in unit_map else "",
                "level": pkg.level,
                "amount": pkg.amount,
                "strategic_alignment": pkg.strategic_alignment,
                "justification": pkg.justification,
                "cumulative_amount": cumulative_amount,
                "within_constraint": within_constraint,
            })

        # 更新审视状态
        review.status = "排序中"
        await db.flush()

        # 找到约束线
        cutoff_rank = 0
        for item in ranked_list:
            if item["within_constraint"]:
                cutoff_rank = item["rank"]
            else:
                break

        return {
            "review_id": review_id,
            "period": review.period,
            "total_budget_constraint": review.total_budget_constraint,
            "total_packages": len(sorted_packages),
            "total_amount": sum(p.amount for p in sorted_packages),
            "cutoff_rank": cutoff_rank,
            "within_constraint_amount": sum(
                p.amount for p in sorted_packages[:cutoff_rank]
            ),
            "exceed_amount": max(0, sum(p.amount for p in sorted_packages) - review.total_budget_constraint),
            "ranked_packages": ranked_list,
            "message": f"排序完成，共{len(sorted_packages)}个决策包，约束线内{cutoff_rank}个",
        }

    async def synthesize_budget(
        self, review_id: int, total_budget: float, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """综合预算方案：基于排序结果，在总预算约束内合成最终预算

        Args:
            review_id: 审视ID
            total_budget: 可用总预算
            db: 数据库会话

        Returns:
            综合预算方案
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        # 获取审视
        stmt = select(ZBBReview).where(ZBBReview.id == review_id)
        result = await db.execute(stmt)
        review = result.scalar_one_or_none()
        if review is None:
            return {"error": f"审视ID {review_id} 不存在"}

        # 执行排序
        rank_result = await self.rank_packages(review_id, db=db)
        if "error" in rank_result:
            return rank_result

        ranked_packages = rank_result["ranked_packages"]
        accepted = []
        deferred = []

        remaining_budget = total_budget

        for item in ranked_packages:
            if item["amount"] <= remaining_budget:
                accepted.append(item)
                remaining_budget -= item["amount"]
            else:
                deferred.append(item)

        # 按决策单元汇总
        unit_summary = {}
        for item in accepted:
            uid = item["unit_id"]
            if uid not in unit_summary:
                unit_summary[uid] = {
                    "unit_id": uid,
                    "unit_name": item["unit_name"],
                    "accepted_packages": [],
                    "total_amount": 0.0,
                }
            unit_summary[uid]["accepted_packages"].append({
                "package_id": item["package_id"],
                "level": item["level"],
                "amount": item["amount"],
            })
            unit_summary[uid]["total_amount"] += item["amount"]

        # 更新审视状态
        review.status = "已审批"
        review.total_budget_constraint = total_budget
        await db.flush()

        return {
            "review_id": review_id,
            "period": review.period,
            "total_budget": total_budget,
            "allocated_budget": total_budget - remaining_budget,
            "remaining_budget": remaining_budget,
            "utilization_rate": (total_budget - remaining_budget) / total_budget if total_budget > 0 else 0,
            "accepted_count": len(accepted),
            "deferred_count": len(deferred),
            "unit_summary": list(unit_summary.values()),
            "deferred_packages": deferred,
            "message": f"预算综合完成，{len(accepted)}个包获批，{len(deferred)}个包暂缓",
        }

    def _calculate_strategic_alignment(self, level: str, unit_score: float) -> float:
        """根据包级别和单元战略价值计算战略对齐度

        最低包：战略对齐度 = 单元评分 * 0.8（基础保障，对齐度较高）
        当前包：战略对齐度 = 单元评分 * 1.0（维持现状）
        增强包：战略对齐度 = 单元评分 * 0.6（增量投入，需更高回报验证）
        """
        multipliers = {"最低": 0.8, "当前": 1.0, "增强": 0.6}
        multiplier = multipliers.get(level, 0.5)
        return round(unit_score * multiplier, 2)
