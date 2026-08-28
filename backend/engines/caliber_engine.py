from __future__ import annotations

import json
import re
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.caliber import CaliberMapping, CaliberDifference
from models.budget import BudgetItem

# 安全表达式正则：只允许 financial, 数字, 小数点, +, -, *, /, 空格, 括号
_SAFE_EXPR_RE = re.compile(r'^[\s\+\-\*\/\(\)\.0-9financial]+$')


def _eval_formula(formula: str, financial: float) -> float:
    """安全求值口径转换公式。

    支持的表达式格式：
    - ``financial * 1.15``   乘法
    - ``financial + 50000``  加法
    - ``financial``          1:1 映射
    - 非数值表达式（如"按产品线分组汇总"）→ 返回原值

    Args:
        formula: adjustment_formula 字段内容
        financial: 财务口径金额

    Returns:
        管理口径金额
    """
    formula = formula.strip()
    # 非数值表达式直接返回原值
    if not _SAFE_EXPR_RE.match(formula):
        return financial
    # 再次检查：表达式中必须包含 financial 或纯数字
    if 'financial' not in formula:
        # 纯数字表达式也视为非数值公式
        return financial
    try:
        return float(eval(formula, {"__builtins__": {}}, {"financial": financial}))
    except Exception as e:
        logger.warning(f"[CaliberEngine] Formula eval failed: {formula!r}, error: {e}")
        return financial


# 硬编码默认值（DB无CaliberMapping记录时回退）
_HARDCODED_MGMT_FACTORS: Dict[str, float] = {
    "B1": 1.10,
    "B2": 1.15,
    "B3": 1.0,
    "B4": 1.0,
    "B5": 1.0,
    "B6": 1.0,
    "B7": 1.0,
    "B8": 0.92,
    "B9": 0.70,
}


# Seed data: 9 mappings for B1-B9
SEED_CALIBER_MAPPINGS = [
    {
        "mapping_id": "CM-B1",
        "financial_code": "B1",
        "financial_name": "无形资产",
        "management_code": "M-B1",
        "management_name": "战略无形资产(含资本化)",
        "conversion_rule": "1:1",
        "adjustment_formula": "financial + 资本化部分",
        "difference_note": "管理口径包含资本化部分，财务口径不含",
        "sort_order": 1,
    },
    {
        "mapping_id": "CM-B2",
        "financial_code": "B2",
        "financial_name": "研发费用",
        "management_code": "M-B2",
        "management_name": "创新研发投入(含资本化)",
        "conversion_rule": "1:1",
        "adjustment_formula": "financial * 1.15",
        "difference_note": "管理口径按(1+资本化率0.15)放大，体现真实研发投入",
        "sort_order": 2,
    },
    {
        "mapping_id": "CM-B3",
        "financial_code": "B3",
        "financial_name": "业务费用",
        "management_code": "M-B3",
        "management_name": "业务运营费用",
        "conversion_rule": "1:1",
        "adjustment_formula": "financial",
        "difference_note": "1:1映射，两口径一致",
        "sort_order": 3,
    },
    {
        "mapping_id": "CM-B4",
        "financial_code": "B4",
        "financial_name": "管理费用",
        "management_code": "M-B4",
        "management_name": "管理运营费用",
        "conversion_rule": "1:1",
        "adjustment_formula": "financial",
        "difference_note": "1:1映射，两口径一致",
        "sort_order": 4,
    },
    {
        "mapping_id": "CM-B5",
        "financial_code": "B5",
        "financial_name": "市场费用",
        "management_code": "M-B5",
        "management_name": "市场推广(按产品线)",
        "conversion_rule": "N:1",
        "adjustment_formula": "按产品线分组汇总",
        "difference_note": "管理口径按产品线分组，财务口径按科目分组",
        "sort_order": 5,
    },
    {
        "mapping_id": "CM-B6",
        "financial_code": "B6",
        "financial_name": "人力成本",
        "management_code": "M-B6",
        "management_name": "人力资源投入",
        "conversion_rule": "1:1",
        "adjustment_formula": "financial",
        "difference_note": "1:1映射，两口径一致",
        "sort_order": 6,
    },
    {
        "mapping_id": "CM-B7",
        "financial_code": "B7",
        "financial_name": "生产成本",
        "management_code": "M-B7",
        "management_name": "生产运营(按品种)",
        "conversion_rule": "N:1",
        "adjustment_formula": "按品种分组汇总",
        "difference_note": "管理口径按品种分组，财务口径按科目分组",
        "sort_order": 7,
    },
    {
        "mapping_id": "CM-B8",
        "financial_code": "B8",
        "financial_name": "长期资产",
        "management_code": "M-B8",
        "management_name": "长期资产净值(扣折旧)",
        "conversion_rule": "1:1",
        "adjustment_formula": "financial - 折旧",
        "difference_note": "管理口径扣除折旧，体现资产净值",
        "sort_order": 8,
    },
    {
        "mapping_id": "CM-B9",
        "financial_code": "B9",
        "financial_name": "财务费用",
        "management_code": "M-B9",
        "management_name": "利息净支出",
        "conversion_rule": "N:1",
        "adjustment_formula": "仅含利息净支出",
        "difference_note": "管理口径仅含利息净支出，财务口径含全部财务费用(汇兑损益等)",
        "sort_order": 9,
    },
]


class CaliberEngine:
    """口径转换引擎: 财务口径 ↔ 管理口径 双口径报表系统"""

    def __init__(self):
        self.engine_name = "caliber"
        self._mappings_cache: Optional[Dict[str, CaliberMapping]] = None

    async def _get_mappings(self, db: AsyncSession) -> Dict[str, CaliberMapping]:
        """获取口径映射配置，优先从缓存读取"""
        if self._mappings_cache:
            return self._mappings_cache

        stmt = select(CaliberMapping).order_by(CaliberMapping.sort_order)
        result = await db.execute(stmt)
        mappings = result.scalars().all()

        if not mappings:
            # Seed default mappings
            for seed in SEED_CALIBER_MAPPINGS:
                mapping = CaliberMapping(**seed)
                db.add(mapping)
            await db.flush()

            result = await db.execute(stmt)
            mappings = result.scalars().all()

        self._mappings_cache = {m.financial_code: m for m in mappings}
        return self._mappings_cache

    async def convert_to_management_view(
        self, financial_data: Dict[str, Any], period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """将财务口径数据转换为管理口径视图

        管理口径按战略意图L1分组，而非会计科目层级
        包含预算偏差分析
        """
        mappings = await self._get_mappings(db)

        management_items = []
        total_financial = 0
        total_management = 0

        for l1_code, amount in financial_data.get("by_l1", {}).items():
            mapping = mappings.get(l1_code)
            financial_amount = amount if isinstance(amount, (int, float, Decimal)) else 0
            total_financial += float(financial_amount)

            management_amount = self._apply_management_conversion(
                l1_code, float(financial_amount), mapping
            )
            total_management += management_amount

            item = {
                "l1_code": l1_code,
                "financial_name": mapping.financial_name if mapping else l1_code,
                "management_name": mapping.management_name if mapping else l1_code,
                "financial_amount": float(financial_amount),
                "management_amount": management_amount,
                "difference": management_amount - float(financial_amount),
                "conversion_rule": mapping.conversion_rule if mapping else "1:1",
                "difference_note": mapping.difference_note if mapping else "",
            }
            management_items.append(item)

        # 按战略意图L1分组
        strategic_grouping = await self.get_strategic_grouping(
            financial_data.get("budget_items", [])
        )

        return {
            "period": period,
            "caliber_type": "management",
            "items": management_items,
            "total_financial": total_financial,
            "total_management": total_management,
            "total_difference": total_management - total_financial,
            "strategic_grouping": strategic_grouping,
            "caliber_note": self.generate_caliber_note("management"),
        }

    async def convert_to_financial_view(
        self, management_data: Dict[str, Any], period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """将管理口径数据转换为财务口径视图

        财务口径按会计科目层级分组
        """
        mappings = await self._get_mappings(db)

        financial_items = []
        total_management = 0
        total_financial = 0

        for l1_code, amount in management_data.get("by_l1", {}).items():
            mapping = mappings.get(l1_code)
            management_amount = amount if isinstance(amount, (int, float, Decimal)) else 0
            total_management += float(management_amount)

            financial_amount = self._apply_financial_conversion(
                l1_code, float(management_amount), mapping
            )
            total_financial += financial_amount

            item = {
                "l1_code": l1_code,
                "management_name": mapping.management_name if mapping else l1_code,
                "financial_name": mapping.financial_name if mapping else l1_code,
                "management_amount": float(management_amount),
                "financial_amount": financial_amount,
                "difference": float(management_amount) - financial_amount,
                "conversion_rule": mapping.conversion_rule if mapping else "1:1",
                "difference_note": mapping.difference_note if mapping else "",
            }
            financial_items.append(item)

        return {
            "period": period,
            "caliber_type": "financial",
            "items": financial_items,
            "total_management": total_management,
            "total_financial": total_financial,
            "total_difference": total_management - total_financial,
            "caliber_note": self.generate_caliber_note("financial"),
        }

    def _apply_management_conversion(
        self, l1_code: str, financial_amount: float, mapping: Optional[CaliberMapping],
        db: Optional[AsyncSession] = None,
    ) -> float:
        """根据映射规则将财务口径金额转换为管理口径。

        优先从 CaliberMapping.adjustment_formula 动态解析；
        若 DB 无映射记录则回退到硬编码默认值。
        """
        if not mapping:
            # 回退到硬编码默认值
            factor = _HARDCODED_MGMT_FACTORS.get(l1_code, 1.0)
            return financial_amount * factor

        formula = (mapping.adjustment_formula or "").strip()
        if formula:
            return _eval_formula(formula, financial_amount)

        # formula 为空时回退到硬编码默认值
        factor = _HARDCODED_MGMT_FACTORS.get(l1_code, 1.0)
        return financial_amount * factor

    def _apply_financial_conversion(
        self, l1_code: str, management_amount: float, mapping: Optional[CaliberMapping],
        db: Optional[AsyncSession] = None,
    ) -> float:
        """根据映射规则将管理口径金额转换为财务口径（逆向转换）。

        优先从 CaliberMapping.adjustment_formula 动态解析并求逆；
        若 DB 无映射记录则回退到硬编码默认值。
        """
        if not mapping:
            factor = _HARDCODED_MGMT_FACTORS.get(l1_code, 1.0)
            return management_amount / factor if factor != 0 else management_amount

        formula = (mapping.adjustment_formula or "").strip()
        if formula and _SAFE_EXPR_RE.match(formula) and 'financial' in formula:
            # 尝试逆向求解：management = f(financial) → financial = f⁻¹(management)
            # 对于简单线性公式 financial * k，逆向为 management / k
            try:
                # 先用 financial=1 求出系数 k
                k = _eval_formula(formula, 1.0)
                if k != 0:
                    return management_amount / k
            except Exception:
                pass
            # 如果逆向求解失败，回退到硬编码
            factor = _HARDCODED_MGMT_FACTORS.get(l1_code, 1.0)
            return management_amount / factor if factor != 0 else management_amount

        # 非数值公式或 formula 为空，回退到硬编码默认值
        factor = _HARDCODED_MGMT_FACTORS.get(l1_code, 1.0)
        return management_amount / factor if factor != 0 else management_amount

    async def reconcile_calibers(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """自动检测并解释两个口径之间的差异

        查询BudgetItem数据，计算两个口径视图，对比差异
        生成CaliberDifference记录
        """
        mappings = await self._get_mappings(db)

        # 查询活跃预算项
        stmt = select(BudgetItem).where(
            BudgetItem.status.in_(["已授予", "执行中", "已核销"]),
        )
        result = await db.execute(stmt)
        budget_items = result.scalars().all()

        # 按L1科目汇总
        by_l1: Dict[str, float] = {}
        for item in budget_items:
            l1 = item.l1_code
            if l1 not in by_l1:
                by_l1[l1] = 0
            by_l1[l1] += float(item.annual_amount or 0)

        # 计算双口径
        differences = []
        total_financial = 0
        total_management = 0

        for l1_code, financial_amount in by_l1.items():
            mapping = mappings.get(l1_code)
            management_amount = self._apply_management_conversion(
                l1_code, financial_amount, mapping
            )
            diff = management_amount - financial_amount
            total_financial += financial_amount
            total_management += management_amount

            reason = ""
            if mapping and mapping.difference_note:
                reason = mapping.difference_note
            elif abs(diff) > 0:
                reason = f"口径差异: 管理口径与财务口径金额不一致"

            diff_record = {
                "l1_code": l1_code,
                "l1_name": mapping.financial_name if mapping else l1_code,
                "financial_amount": int(financial_amount * 100),  # 转为分
                "management_amount": int(management_amount * 100),
                "difference_amount": int(diff * 100),
                "difference_reason": reason,
            }
            differences.append(diff_record)

            # 写入CaliberDifference记录
            existing_stmt = select(CaliberDifference).where(
                CaliberDifference.period == period,
                CaliberDifference.l1_code == l1_code,
            )
            existing_result = await db.execute(existing_stmt)
            existing = existing_result.scalars().first()

            if existing:
                existing.financial_amount = int(financial_amount * 100)
                existing.management_amount = int(management_amount * 100)
                existing.difference_amount = int(diff * 100)
                existing.difference_reason = reason
            else:
                diff_model = CaliberDifference(
                    diff_id=f"CD-{uuid.uuid4().hex[:8].upper()}",
                    period=period,
                    l1_code=l1_code,
                    financial_amount=int(financial_amount * 100),
                    management_amount=int(management_amount * 100),
                    difference_amount=int(diff * 100),
                    difference_reason=reason,
                )
                db.add(diff_model)

        await db.flush()

        return {
            "period": period,
            "differences": differences,
            "total_financial": total_financial,
            "total_management": total_management,
            "total_difference": total_management - total_financial,
            "reconciliation_note": self._generate_reconciliation_note(
                differences, total_financial, total_management
            ),
        }

    def generate_caliber_note(self, caliber_type: str) -> str:
        """生成口径标注文本"""
        if caliber_type == "management":
            return (
                "本报告按管理口径统计。管理口径与财务口径的主要差异："
                "研发费用含资本化部分(×1.15)；"
                "无形资产含资本化部分(+10%)；"
                "长期资产扣除折旧(-8%)；"
                "财务费用仅含利息净支出(约70%)；"
                "市场费用按产品线分组、生产成本按品种分组。"
            )
        elif caliber_type == "financial":
            return (
                "本报告按财务口径统计，遵循会计准则确认和计量要求。"
                "与管理口径的差异：研发费用不含资本化部分；"
                "无形资产不含资本化部分；"
                "长期资产含折旧；"
                "财务费用含汇兑损益等全部财务费用。"
            )
        else:
            return (
                "本报告为双口径对比视图。黄色标注为两口径差异项。"
                "管理口径侧重战略决策视角，财务口径遵循会计准则。"
            )

    def _generate_reconciliation_note(
        self, differences: List[Dict], total_financial: float, total_management: float
    ) -> str:
        """生成对账说明"""
        significant_diffs = [d for d in differences if abs(d["difference_amount"]) > 0]
        if not significant_diffs:
            return "本期两口径数据完全一致，无差异。"

        notes = [f"本期管理口径总额 ¥{total_management:,.0f}，财务口径总额 ¥{total_financial:,.0f}，"
                 f"差异 ¥{total_management - total_financial:,.0f}。"]
        for d in significant_diffs:
            notes.append(
                f"{d['l1_name']}: 差异 ¥{d['difference_amount']/100:,.0f}，原因: {d['difference_reason']}"
            )
        return " ".join(notes)

    async def get_strategic_grouping(
        self, budget_items: List[Any]
    ) -> Dict[str, Any]:
        """按战略意图L1分组预算项，用于管理口径视图

        支持传入ORM对象列表或Dict列表，统一转为Dict后处理。
        对缺失字段使用默认值容错。
        """
        by_intent: Dict[str, Dict] = {}

        for item in budget_items:
            # 统一转为Dict：支持ORM对象和dict
            if isinstance(item, dict):
                l1_code = item.get("l1_code", "")
                intent = item.get("strategic_intent_l1", None) or "未分类"
                annual_amount = item.get("annual_amount", 0)
                used_amount = item.get("used_amount", 0)
            else:
                # ORM对象
                l1_code = getattr(item, 'l1_code', '') or ''
                intent = getattr(item, 'strategic_intent_l1', None) or '未分类'
                annual_amount = getattr(item, 'annual_amount', 0) or 0
                used_amount = getattr(item, 'used_amount', 0) or 0

            if intent not in by_intent:
                by_intent[intent] = {
                    "total_budget": 0,
                    "total_used": 0,
                    "item_count": 0,
                    "l1_codes": set(),
                }
            by_intent[intent]["total_budget"] += float(annual_amount)
            by_intent[intent]["total_used"] += float(used_amount)
            by_intent[intent]["item_count"] += 1
            if l1_code:
                by_intent[intent]["l1_codes"].add(l1_code)

        result = {}
        for intent, data in by_intent.items():
            execution_rate = (
                round(data["total_used"] / data["total_budget"] * 100, 2)
                if data["total_budget"] > 0 else 0
            )
            result[intent] = {
                "total_budget": data["total_budget"],
                "total_used": data["total_used"],
                "execution_rate": execution_rate,
                "item_count": data["item_count"],
                "l1_codes": list(data["l1_codes"]),
            }

        return result
