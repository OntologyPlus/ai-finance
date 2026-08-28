from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.cost_center import CostCenter, StandardCost, CostAllocation, InternalSettlement


class CostCenterEngine:
    """成本中心核算引擎 — 标准成本、差异分析、分摊与内部结算"""

    async def set_standard_cost(
        self,
        center_id: int,
        cost_item: str,
        quantity: float,
        price: float,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """设置标准成本

        Args:
            center_id: 成本中心ID
            cost_item: 成本项目名称
            quantity: 标准用量
            price: 标准单价
            db: 数据库会话

        Returns:
            创建的标准成本信息
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        # 验证成本中心存在
        stmt = select(CostCenter).where(CostCenter.id == center_id)
        result = await db.execute(stmt)
        center = result.scalar_one_or_none()
        if center is None:
            return {"error": f"成本中心ID {center_id} 不存在"}

        standard_total = quantity * price

        # 检查是否已有相同成本项目的标准成本（同中心同项目）
        stmt_existing = select(StandardCost).where(
            and_(
                StandardCost.cost_center_id == center_id,
                StandardCost.cost_item == cost_item,
            )
        )
        result_existing = await db.execute(stmt_existing)
        existing = result_existing.scalar_one_or_none()

        if existing:
            # 更新现有标准成本
            existing.standard_quantity = quantity
            existing.standard_price = price
            existing.standard_total = standard_total
            existing.effective_from = datetime.now()
            await db.flush()
            logger.info(f"标准成本已更新: center={center_id}, item={cost_item}")
            return {
                "id": existing.id,
                "cost_center_id": center_id,
                "cost_item": cost_item,
                "standard_quantity": quantity,
                "standard_price": price,
                "standard_total": standard_total,
                "action": "updated",
                "message": f"标准成本已更新：{cost_item}，标准总额{standard_total:.2f}",
            }

        std_cost = StandardCost(
            cost_center_id=center_id,
            cost_item=cost_item,
            standard_quantity=quantity,
            standard_price=price,
            standard_total=standard_total,
            effective_from=datetime.now(),
        )
        db.add(std_cost)
        await db.flush()

        logger.info(f"标准成本已设置: center={center_id}, item={cost_item}, total={standard_total}")
        return {
            "id": std_cost.id,
            "cost_center_id": center_id,
            "cost_item": cost_item,
            "standard_quantity": quantity,
            "standard_price": price,
            "standard_total": standard_total,
            "action": "created",
            "message": f"标准成本已设置：{cost_item}，标准总额{standard_total:.2f}",
        }

    async def variance_analysis(
        self, center_id: int, period: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """实际与标准成本差异分析

        差异分析模型：
        - 价格差异 = (实际单价 - 标准单价) × 实际用量
        - 数量差异 = (实际用量 - 标准用量) × 标准单价
        - 总差异 = 价格差异 + 数量差异

        Args:
            center_id: 成本中心ID
            period: 期间（YYYY-MM）
            db: 数据库会话

        Returns:
            差异分析结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        # 验证成本中心存在
        stmt = select(CostCenter).where(CostCenter.id == center_id)
        result = await db.execute(stmt)
        center = result.scalar_one_or_none()
        if center is None:
            return {"error": f"成本中心ID {center_id} 不存在"}

        # 获取该中心所有标准成本
        stmt_std = select(StandardCost).where(StandardCost.cost_center_id == center_id)
        result_std = await db.execute(stmt_std)
        standard_costs = result_std.scalars().all()

        if not standard_costs:
            return {"error": f"成本中心'{center.center_name}'未设置标准成本"}

        # 模拟实际成本数据（实际项目中从费用/报销等表获取）
        variances = []
        total_price_variance = 0.0
        total_volume_variance = 0.0

        for std in standard_costs:
            # 模拟实际数据：实际用量偏差±15%，实际单价偏差±10%
            import random
            random.seed(hash(f"{center_id}-{std.cost_item}-{period}"))
            actual_quantity = std.standard_quantity * (1 + (random.random() * 0.3 - 0.15))
            actual_price = std.standard_price * (1 + (random.random() * 0.2 - 0.10))
            actual_total = actual_quantity * actual_price

            # 计算差异
            price_variance = (actual_price - std.standard_price) * actual_quantity
            volume_variance = (actual_quantity - std.standard_quantity) * std.standard_price
            total_variance = price_variance + volume_variance

            total_price_variance += price_variance
            total_volume_variance += volume_variance

            variances.append({
                "cost_item": std.cost_item,
                "standard_quantity": std.standard_quantity,
                "standard_price": std.standard_price,
                "standard_total": std.standard_total,
                "actual_quantity": round(actual_quantity, 2),
                "actual_price": round(actual_price, 2),
                "actual_total": round(actual_total, 2),
                "price_variance": round(price_variance, 2),
                "volume_variance": round(volume_variance, 2),
                "total_variance": round(total_variance, 2),
                "variance_rate": round(total_variance / std.standard_total * 100, 2) if std.standard_total != 0 else 0,
                "assessment": self._assess_variance(total_variance, std.standard_total),
            })

        total_standard = sum(v["standard_total"] for v in variances)
        total_actual = sum(v["actual_total"] for v in variances)
        total_variance = total_price_variance + total_volume_variance

        return {
            "center_id": center_id,
            "center_name": center.center_name,
            "period": period,
            "summary": {
                "total_standard_cost": round(total_standard, 2),
                "total_actual_cost": round(total_actual, 2),
                "total_price_variance": round(total_price_variance, 2),
                "total_volume_variance": round(total_volume_variance, 2),
                "total_variance": round(total_variance, 2),
                "variance_rate": round(total_variance / total_standard * 100, 2) if total_standard != 0 else 0,
            },
            "item_variances": variances,
            "recommendation": self._generate_variance_recommendation(total_variance, total_standard),
        }

    async def allocate_cost(self, allocation_id: int, db: AsyncSession = None) -> Dict[str, Any]:
        """执行成本分摊

        根据分摊规则将源成本中心的费用按比例分摊到目标成本中心。

        Args:
            allocation_id: 分摊规则ID
            db: 数据库会话

        Returns:
            分摊执行结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        # 获取分摊规则
        stmt = select(CostAllocation).where(CostAllocation.id == allocation_id)
        result = await db.execute(stmt)
        allocation = result.scalar_one_or_none()
        if allocation is None:
            return {"error": f"分摊规则ID {allocation_id} 不存在"}

        ratios = allocation.allocation_ratios or {}
        if not ratios:
            return {"error": "分摊比例为空，无法执行分摊"}

        # 验证比例之和为1（允许±0.01误差）
        total_ratio = sum(float(v) for v in ratios.values())
        if abs(total_ratio - 1.0) > 0.01:
            return {"error": f"分摊比例之和为{total_ratio:.4f}，不等于1.0，请修正"}

        # 验证源成本中心存在
        if allocation.source_center_id:
            stmt_src = select(CostCenter).where(CostCenter.id == allocation.source_center_id)
            result_src = await db.execute(stmt_src)
            source_center = result_src.scalar_one_or_none()
            if source_center is None:
                return {"error": f"源成本中心ID {allocation.source_center_id} 不存在"}
        else:
            return {"error": "未指定源成本中心"}

        # 计算各目标中心分摊金额
        allocations = []
        for center_id_str, ratio in ratios.items():
            center_id = int(center_id_str)
            allocated_amount = allocation.total_amount * float(ratio)

            # 验证目标中心存在
            stmt_tgt = select(CostCenter).where(CostCenter.id == center_id)
            result_tgt = await db.execute(stmt_tgt)
            target = result_tgt.scalar_one_or_none()
            if target is None:
                return {"error": f"目标成本中心ID {center_id} 不存在"}

            allocations.append({
                "target_center_id": center_id,
                "target_center_name": target.center_name,
                "ratio": float(ratio),
                "allocated_amount": round(allocated_amount, 2),
            })

        return {
            "allocation_id": allocation_id,
            "rule_name": allocation.rule_name,
            "source_center_id": allocation.source_center_id,
            "source_center_name": source_center.center_name,
            "allocation_basis": allocation.allocation_basis,
            "total_amount": allocation.total_amount,
            "period": allocation.period,
            "allocations": allocations,
            "total_allocated": round(sum(a["allocated_amount"] for a in allocations), 2),
            "message": f"成本分摊完成，{len(allocations)}个目标中心",
        }

    async def settle_internal(
        self,
        provider_id: int,
        consumer_id: int,
        volume: float,
        price: float,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """内部结算

        Args:
            provider_id: 提供方成本中心ID
            consumer_id: 使用方成本中心ID
            volume: 服务量
            price: 内部转移价格
            db: 数据库会话

        Returns:
            内部结算结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        # 验证提供方
        stmt_prov = select(CostCenter).where(CostCenter.id == provider_id)
        result_prov = await db.execute(stmt_prov)
        provider = result_prov.scalar_one_or_none()
        if provider is None:
            return {"error": f"提供方成本中心ID {provider_id} 不存在"}

        # 验证使用方
        stmt_cons = select(CostCenter).where(CostCenter.id == consumer_id)
        result_cons = await db.execute(stmt_cons)
        consumer = result_cons.scalar_one_or_none()
        if consumer is None:
            return {"error": f"使用方成本中心ID {consumer_id} 不存在"}

        if provider_id == consumer_id:
            return {"error": "提供方和使用方不能为同一成本中心"}

        settlement_amount = volume * price

        settlement = InternalSettlement(
            provider_id=provider_id,
            consumer_id=consumer_id,
            service_description=f"{provider.center_name}向{consumer.center_name}提供服务",
            service_volume=volume,
            transfer_price=price,
            settlement_amount=settlement_amount,
            status="待结算",
            period=datetime.now().strftime("%Y-%m"),
        )
        db.add(settlement)
        await db.flush()

        logger.info(
            f"内部结算已创建: {provider.center_name}→{consumer.center_name}, "
            f"金额={settlement_amount}"
        )

        return {
            "settlement_id": settlement.id,
            "provider_id": provider_id,
            "provider_name": provider.center_name,
            "consumer_id": consumer_id,
            "consumer_name": consumer.center_name,
            "service_volume": volume,
            "transfer_price": price,
            "settlement_amount": round(settlement_amount, 2),
            "status": settlement.status,
            "message": f"内部结算已创建，{provider.center_name}→{consumer.center_name}，金额{settlement_amount:.2f}",
        }

    def _assess_variance(self, variance: float, standard: float) -> str:
        """评估差异程度"""
        if variance == 0:
            return "无标准"
        if standard == 0:
            return "无标准"
        rate = abs(variance / standard)
        if rate <= 0.05:
            return "正常"
        elif rate <= 0.10:
            return "轻微偏差"
        elif rate <= 0.20:
            return "显著偏差"
        else:
            return "严重偏差"

    def _generate_variance_recommendation(self, total_variance: float, total_standard: float) -> str:
        """生成差异分析建议"""
        if total_standard == 0:
            return "无标准成本数据"
        rate = total_variance / total_standard
        if rate > 0.1:
            return "实际成本显著超出标准，建议审查成本控制措施并调整标准成本基准"
        elif rate > 0.05:
            return "实际成本略高于标准，建议关注价格波动和用量异常"
        elif rate > -0.05:
            return "实际成本与标准基本一致，成本控制良好"
        else:
            return "实际成本低于标准，建议评估标准成本是否需要下调"
