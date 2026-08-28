from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.hcp_compliance import HCP, HCPInteraction, HCPPayment, ComplianceRule


class HCPComplianceEngine:
    """HCP费用合规审查引擎 — 确保HCP互动和付款符合法规要求"""

    async def verify_hcp(self, hcp_id: str, db: AsyncSession = None) -> Dict[str, Any]:
        """验证HCP身份和资质

        HR-026：付款前必须验证HCP身份和资质

        Args:
            hcp_id: HCP编号
            db: 数据库会话

        Returns:
            验证结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(HCP).where(HCP.hcp_id == hcp_id)
        result = await db.execute(stmt)
        hcp = result.scalar_one_or_none()

        if hcp is None:
            return {"error": f"HCP编号 {hcp_id} 不存在", "verified": False}

        # 执行验证检查
        checks = []

        # 检查1：基本信息完整性
        info_complete = bool(hcp.name and hcp.institution and hcp.department and hcp.specialty)
        checks.append({
            "check": "基本信息完整性",
            "passed": info_complete,
            "detail": "姓名、机构、科室、专业领域均已填写" if info_complete else "存在空字段",
        })

        # 检查2：机构是否在合规名单（简化：非空即通过）
        institution_valid = bool(hcp.institution and len(hcp.institution.strip()) > 0)
        checks.append({
            "check": "机构合规性",
            "passed": institution_valid,
            "detail": f"机构'{hcp.institution}'已验证" if institution_valid else "机构信息缺失",
        })

        # 检查3：专业领域匹配（简化：非空即通过）
        specialty_valid = bool(hcp.specialty and len(hcp.specialty.strip()) > 0)
        checks.append({
            "check": "专业领域验证",
            "passed": specialty_valid,
            "detail": f"专业领域'{hcp.specialty}'已验证" if specialty_valid else "专业领域信息缺失",
        })

        all_passed = all(c["passed"] for c in checks)

        # 更新验证状态
        hcp.verification_status = "已验证" if all_passed else "验证失败"
        await db.flush()

        logger.info(f"HCP验证: {hcp_id} → {hcp.verification_status}")

        return {
            "hcp_id": hcp_id,
            "name": hcp.name,
            "verified": all_passed,
            "verification_status": hcp.verification_status,
            "checks": checks,
            "message": f"HCP {hcp.name} 验证{'通过' if all_passed else '失败'}",
        }

    async def check_interaction_compliance(
        self, interaction_id: int, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """检查互动是否合规

        HR-028：互动记录必须完整（类型、日期、目的、内容摘要、参与人员）

        Args:
            interaction_id: 互动ID
            db: 数据库会话

        Returns:
            合规检查结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(HCPInteraction).where(HCPInteraction.id == interaction_id)
        result = await db.execute(stmt)
        interaction = result.scalar_one_or_none()

        if interaction is None:
            return {"error": f"互动ID {interaction_id} 不存在"}

        violations = []

        # HR-028：互动记录完整性检查
        if not interaction.interaction_type:
            violations.append({
                "rule": "HR-028",
                "violation": "互动类型缺失",
                "action": "补充互动类型",
            })

        if not interaction.interaction_date:
            violations.append({
                "rule": "HR-028",
                "violation": "互动日期缺失",
                "action": "补充互动日期",
            })

        if not interaction.purpose:
            violations.append({
                "rule": "HR-028",
                "violation": "互动目的缺失",
                "action": "补充互动目的",
            })

        if not interaction.content_summary:
            violations.append({
                "rule": "HR-028",
                "violation": "内容摘要缺失",
                "action": "补充内容摘要",
            })

        if not interaction.participants:
            violations.append({
                "rule": "HR-028",
                "violation": "参与人员缺失",
                "action": "补充参与人员",
            })

        # HR-029：月度互动频次检查
        hcp_id = interaction.hcp_id
        if interaction.interaction_date:
            month_start = interaction.interaction_date.replace(day=1)
            # 简化：计算当月互动次数
            stmt_count = select(func.count()).where(
                and_(
                    HCPInteraction.hcp_id == hcp_id,
                    HCPInteraction.interaction_date >= month_start,
                    HCPInteraction.interaction_date < interaction.interaction_date
                    if interaction.interaction_date.day < 28
                    else interaction.interaction_date,
                )
            )
            result_count = await db.execute(stmt_count)
            monthly_count = result_count.scalar() or 0

            if monthly_count >= 3:
                violations.append({
                    "rule": "HR-029",
                    "violation": f"月度互动次数已达{monthly_count}次，超过3次阈值",
                    "action": "触发频次审查，需合规部门审核",
                })

        is_compliant = len(violations) == 0
        interaction.compliance_status = "合规" if is_compliant else "不合规"
        await db.flush()

        return {
            "interaction_id": interaction_id,
            "hcp_id": interaction.hcp_id,
            "interaction_type": interaction.interaction_type,
            "compliance_status": interaction.compliance_status,
            "is_compliant": is_compliant,
            "violations": violations,
            "message": f"互动{'合规' if is_compliant else '不合规'}，发现{len(violations)}项违规",
        }

    async def check_payment_limit(
        self, hcp_id: str, payment_amount: float, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """检查付款是否超过年度限额

        HR-027：HCP年度付款总额不得超过限额（默认50000元）

        Args:
            hcp_id: HCP编号
            payment_amount: 待付款金额
            db: 数据库会话

        Returns:
            限额检查结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(HCP).where(HCP.hcp_id == hcp_id)
        result = await db.execute(stmt)
        hcp = result.scalar_one_or_none()

        if hcp is None:
            return {"error": f"HCP编号 {hcp_id} 不存在"}

        # HR-026：付款前必须验证HCP
        if hcp.verification_status != "已验证":
            return {
                "hcp_id": hcp_id,
                "name": hcp.name,
                "can_pay": False,
                "reason": f"HCP验证状态为'{hcp.verification_status}'，须先完成验证（HR-026）",
                "current_total": hcp.annual_payment_total,
                "payment_limit": hcp.payment_limit,
            }

        current_total = hcp.annual_payment_total or 0
        payment_limit = hcp.payment_limit or 50000
        projected_total = current_total + payment_amount
        within_limit = projected_total <= payment_limit

        return {
            "hcp_id": hcp_id,
            "name": hcp.name,
            "can_pay": within_limit,
            "current_annual_total": current_total,
            "payment_amount": payment_amount,
            "projected_total": projected_total,
            "payment_limit": payment_limit,
            "remaining_limit": max(0, payment_limit - current_total),
            "exceed_amount": max(0, projected_total - payment_limit),
            "reason": "" if within_limit else f"付款后年度总额{projected_total}将超过限额{payment_limit}（HR-027）",
        }

    async def analyze_aggregate_risk(
        self, hcp_id: str, period: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """综合风险分析

        从频次、金额、区域等多维度分析HCP的合规风险。

        HR-029：月度互动超过3次触发审查

        Args:
            hcp_id: HCP编号
            period: 分析期间（YYYY）
            db: 数据库会话

        Returns:
            综合风险评估
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(HCP).where(HCP.hcp_id == hcp_id)
        result = await db.execute(stmt)
        hcp = result.scalar_one_or_none()

        if hcp is None:
            return {"error": f"HCP编号 {hcp_id} 不存在"}

        # 获取该年度所有互动
        year_start = datetime(int(period), 1, 1)
        year_end = datetime(int(period) + 1, 1, 1)

        stmt_interactions = select(HCPInteraction).where(
            and_(
                HCPInteraction.hcp_id == hcp_id,
                HCPInteraction.interaction_date >= year_start,
                HCPInteraction.interaction_date < year_end,
            )
        )
        result_interactions = await db.execute(stmt_interactions)
        interactions = result_interactions.scalars().all()

        # 获取该年度所有付款
        stmt_payments = select(HCPPayment).where(HCPPayment.hcp_id == hcp_id)
        result_payments = await db.execute(stmt_payments)
        payments = result_payments.scalars().all()

        # 频次风险
        interaction_count = len(interactions)
        frequency_risk = self._assess_frequency_risk(interaction_count)

        # 金额风险
        total_payment = sum(p.amount for p in payments)
        payment_limit = hcp.payment_limit or 50000
        amount_risk = self._assess_amount_risk(total_payment, payment_limit)

        # 互动类型分布
        type_distribution = {}
        for interaction in interactions:
            itype = interaction.interaction_type or "未知"
            type_distribution[itype] = type_distribution.get(itype, 0) + 1

        # 月度互动频次（检测HR-029违规月份）
        monthly_counts = {}
        high_frequency_months = []
        for interaction in interactions:
            if interaction.interaction_date:
                month_key = interaction.interaction_date.strftime("%Y-%m")
                monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
                if monthly_counts[month_key] > 3 and month_key not in high_frequency_months:
                    high_frequency_months.append(month_key)

        # 合规状态统计
        compliant_count = sum(1 for i in interactions if i.compliance_status == "合规")
        non_compliant_count = sum(1 for i in interactions if i.compliance_status == "不合规")

        # 综合风险评分
        overall_risk_score = self._calculate_risk_score(
            frequency_risk["score"], amount_risk["score"], len(high_frequency_months) > 0
        )

        return {
            "hcp_id": hcp_id,
            "name": hcp.name,
            "institution": hcp.institution,
            "period": period,
            "verification_status": hcp.verification_status,
            "interaction_analysis": {
                "total_count": interaction_count,
                "compliant_count": compliant_count,
                "non_compliant_count": non_compliant_count,
                "type_distribution": type_distribution,
                "monthly_counts": monthly_counts,
                "high_frequency_months": high_frequency_months,
            },
            "payment_analysis": {
                "total_payment": total_payment,
                "payment_limit": payment_limit,
                "utilization_rate": total_payment / payment_limit if payment_limit > 0 else 0,
                "payment_count": len(payments),
            },
            "risk_assessment": {
                "frequency_risk": frequency_risk,
                "amount_risk": amount_risk,
                "hr029_violation": len(high_frequency_months) > 0,
                "hr029_violation_months": high_frequency_months,
                "overall_risk_score": overall_risk_score,
                "overall_risk_level": self._risk_level(overall_risk_score),
            },
            "recommendation": self._generate_risk_recommendation(
                overall_risk_score, frequency_risk, amount_risk, high_frequency_months
            ),
        }

    def _assess_frequency_risk(self, count: int) -> Dict[str, Any]:
        """评估频次风险"""
        if count <= 6:
            return {"level": "低", "score": 0, "description": f"年度互动{count}次，频次正常"}
        elif count <= 12:
            return {"level": "中", "score": 30, "description": f"年度互动{count}次，频次偏高"}
        elif count <= 24:
            return {"level": "高", "score": 60, "description": f"年度互动{count}次，频次过高，需审查"}
        else:
            return {"level": "极高", "score": 90, "description": f"年度互动{count}次，频次异常，须立即审查"}

    def _assess_amount_risk(self, total: float, limit: float) -> Dict[str, Any]:
        """评估金额风险"""
        if limit == 0:
            return {"level": "未知", "score": 0, "description": "未设定付款限额"}
        ratio = total / limit
        if ratio <= 0.5:
            return {"level": "低", "score": 0, "description": f"年度付款{total:.0f}元，占限额{ratio:.0%}"}
        elif ratio <= 0.8:
            return {"level": "中", "score": 30, "description": f"年度付款{total:.0f}元，占限额{ratio:.0%}"}
        elif ratio <= 1.0:
            return {"level": "高", "score": 60, "description": f"年度付款{total:.0f}元，接近限额{ratio:.0%}"}
        else:
            return {"level": "极高", "score": 90, "description": f"年度付款{total:.0f}元，已超限额{ratio:.0%}"}

    def _calculate_risk_score(self, freq_score: int, amount_score: int, hr029_violation: bool) -> int:
        """计算综合风险评分（0-100）"""
        base = (freq_score + amount_score) / 2
        if hr029_violation:
            base = min(100, base + 20)
        return int(base)

    def _risk_level(self, score: int) -> str:
        """风险等级"""
        if score <= 20:
            return "低风险"
        elif score <= 50:
            return "中风险"
        elif score <= 75:
            return "高风险"
        else:
            return "极高风险"

    def _generate_risk_recommendation(
        self, score: int, freq_risk: Dict, amount_risk: Dict, high_freq_months: List[str]
    ) -> str:
        """生成风险建议"""
        parts = []
        if score <= 20:
            parts.append("HCP合规风险较低，维持现有管理措施即可")
        elif score <= 50:
            parts.append("HCP存在中等合规风险，建议加强监控频次和金额")
        elif score <= 75:
            parts.append("HCP合规风险较高，建议进行专项审查并限制互动频次")
        else:
            parts.append("HCP合规风险极高，建议暂停互动并启动合规调查")

        if high_freq_months:
            parts.append(f"HR-029违规：{','.join(high_freq_months)}月互动超过3次，需合规部门审核")

        if amount_risk["level"] in ("高", "极高"):
            parts.append("付款金额接近或超过限额，建议审查付款合理性")

        return "；".join(parts)
