from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.rnd_pipeline import Pipeline, RnDProject, RnDMilestone, ClinicalTrial


class RnDBudgetEngine:
    """R&D项目制预算引擎 — 双口径预算、CRO付款追踪、多中心分摊与效率分析"""

    async def create_dual_budget(
        self,
        project_id: str,
        finance_amount: float,
        management_amount: float,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """创建双口径预算

        财务口径：按照会计准则确认的研发支出
        管理口径：按照项目管理需要归集的全部研发投入

        Args:
            project_id: 项目编号
            finance_amount: 财务口径预算金额
            management_amount: 管理口径预算金额
            db: 数据库会话

        Returns:
            双口径预算创建结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(RnDProject).where(RnDProject.project_id == project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()

        if project is None:
            return {"error": f"项目编号 {project_id} 不存在"}

        # 管理口径预算应大于等于财务口径（管理口径包含资本化+费用化）
        if management_amount < finance_amount:
            return {"error": f"管理口径预算({management_amount})不应小于财务口径预算({finance_amount})"}

        project.finance_budget = finance_amount
        project.management_budget = management_amount
        await db.flush()

        diff = management_amount - finance_amount
        logger.info(f"双口径预算已创建: project={project_id}, 财务={finance_amount}, 管理={management_amount}")

        return {
            "project_id": project_id,
            "name": project.name,
            "finance_budget": finance_amount,
            "management_budget": management_amount,
            "difference": diff,
            "difference_description": f"管理口径比财务口径多{diff:.0f}万元，主要为资本化支出",
            "message": f"双口径预算已创建：财务口径{finance_amount}万元，管理口径{management_amount}万元",
        }

    async def track_cro_payment(
        self, milestone_id: int, amount: float, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """追踪CRO付款（关联里程碑）

        Args:
            milestone_id: 里程碑ID
            amount: CRO付款金额
            db: 数据库会话

        Returns:
            CRO付款追踪结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(RnDMilestone).where(RnDMilestone.id == milestone_id)
        result = await db.execute(stmt)
        milestone = result.scalar_one_or_none()

        if milestone is None:
            return {"error": f"里程碑ID {milestone_id} 不存在"}

        # 获取关联项目
        stmt_project = select(RnDProject).where(RnDProject.project_id == milestone.project_id)
        result_project = await db.execute(stmt_project)
        project = result_project.scalar_one_or_none()

        if project is None:
            return {"error": f"关联项目 {milestone.project_id} 不存在"}

        # 检查预算是否充足（管理口径）
        remaining_management = project.management_budget - project.consumed_management
        if amount > remaining_management:
            return {
                "error": f"CRO付款{amount}万元超过项目剩余管理口径预算{remaining_management:.0f}万元",
                "milestone_id": milestone_id,
                "amount": amount,
                "remaining_budget": remaining_management,
            }

        # 更新项目消耗
        project.consumed_management += amount
        project.consumed_finance += amount  # CRO费用通常全部费用化

        # 更新里程碑关联CRO付款
        cro_payment_id = f"CRO-PAY-{milestone_id:04d}"
        milestone.cro_payment_id = cro_payment_id

        # 如果里程碑状态为"待完成"，更新为"已完成"
        if milestone.status == "待完成":
            milestone.status = "已完成"
            milestone.actual_date = datetime.now()

        await db.flush()

        logger.info(f"CRO付款追踪: milestone={milestone_id}, amount={amount}, payment_id={cro_payment_id}")

        return {
            "cro_payment_id": cro_payment_id,
            "milestone_id": milestone_id,
            "milestone_name": milestone.name,
            "project_id": milestone.project_id,
            "amount": amount,
            "finance_consumed": project.consumed_finance,
            "management_consumed": project.consumed_management,
            "finance_remaining": project.finance_budget - project.consumed_finance,
            "management_remaining": project.management_budget - project.consumed_management,
            "milestone_status": milestone.status,
            "message": f"CRO付款{amount}万元已追踪至里程碑'{milestone.name}'",
        }

    async def allocate_multi_center(
        self, trial_id: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """多中心临床试验成本分摊

        根据分摊协议将试验总费用分摊到各中心。

        Args:
            trial_id: 试验编号
            db: 数据库会话

        Returns:
            分摊结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(ClinicalTrial).where(ClinicalTrial.trial_id == trial_id)
        result = await db.execute(stmt)
        trial = result.scalar_one_or_none()

        if trial is None:
            return {"error": f"试验编号 {trial_id} 不存在"}

        ratios = trial.allocation_ratios or {}
        if not ratios:
            return {"error": f"试验 {trial_id} 未设置分摊协议"}

        # 验证比例之和
        total_ratio = sum(float(v) for v in ratios.values())
        if abs(total_ratio - 1.0) > 0.01:
            return {"error": f"分摊比例之和为{total_ratio:.4f}，不等于1.0"}

        # 计算各中心分摊金额
        allocations = []
        for center, ratio in ratios.items():
            allocated = trial.total_cost * float(ratio)
            allocations.append({
                "center": center,
                "ratio": float(ratio),
                "allocated_amount": round(allocated, 2),
            })

        # 按分摊金额降序排列
        allocations.sort(key=lambda x: x["allocated_amount"], reverse=True)

        return {
            "trial_id": trial_id,
            "trial_name": trial.name,
            "phase": trial.phase,
            "cro_vendor": trial.cro_vendor,
            "center_count": trial.center_count,
            "total_cost": trial.total_cost,
            "allocations": allocations,
            "total_allocated": round(sum(a["allocated_amount"] for a in allocations), 2),
            "message": f"多中心分摊完成，{len(allocations)}个中心",
        }

    async def analyze_efficiency(
        self, period: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """R&D效率分析

        分析指标：
        - 预算执行率（财务口径/管理口径）
        - 里程碑完成率
        - 管线推进效率
        - CRO费用占比

        Args:
            period: 分析期间（YYYY）
            db: 数据库会话

        Returns:
            R&D效率分析结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        # 获取所有活跃项目
        stmt_projects = select(RnDProject).where(RnDProject.status == "进行中")
        result_projects = await db.execute(stmt_projects)
        projects = result_projects.scalars().all()

        # 获取所有活跃管线
        stmt_pipelines = select(Pipeline).where(Pipeline.status == "活跃")
        result_pipelines = await db.execute(stmt_pipelines)
        pipelines = result_pipelines.scalars().all()

        # 项目预算执行分析
        project_analysis = []
        total_finance_budget = 0
        total_finance_consumed = 0
        total_management_budget = 0
        total_management_consumed = 0

        for project in projects:
            finance_rate = project.consumed_finance / project.finance_budget * 100 if project.finance_budget > 0 else 0
            management_rate = project.consumed_management / project.management_budget * 100 if project.management_budget > 0 else 0

            total_finance_budget += project.finance_budget
            total_finance_consumed += project.consumed_finance
            total_management_budget += project.management_budget
            total_management_consumed += project.consumed_management

            # 获取里程碑完成情况
            stmt_milestones = select(RnDMilestone).where(RnDMilestone.project_id == project.project_id)
            result_milestones = await db.execute(stmt_milestones)
            milestones = result_milestones.scalars().all()

            completed_milestones = sum(1 for m in milestones if m.status == "已完成")
            delayed_milestones = sum(1 for m in milestones if m.status == "已延期")
            total_milestones = len(milestones)

            project_analysis.append({
                "project_id": project.project_id,
                "name": project.name,
                "pipeline_id": project.pipeline_id,
                "finance_budget": project.finance_budget,
                "finance_consumed": project.consumed_finance,
                "finance_rate": round(finance_rate, 2),
                "management_budget": project.management_budget,
                "management_consumed": project.consumed_management,
                "management_rate": round(management_rate, 2),
                "milestone_completion_rate": round(completed_milestones / total_milestones * 100, 1) if total_milestones > 0 else 0,
                "milestone_delay_rate": round(delayed_milestones / total_milestones * 100, 1) if total_milestones > 0 else 0,
            })

        # 管线推进分析
        pipeline_analysis = []
        for pipeline in pipelines:
            budget_rate = pipeline.consumed_budget / pipeline.total_budget * 100 if pipeline.total_budget > 0 else 0
            pipeline_analysis.append({
                "pipeline_id": pipeline.pipeline_id,
                "name": pipeline.name,
                "current_stage": pipeline.current_stage,
                "go_nogo_status": pipeline.go_nogo_status,
                "budget_consumption_rate": round(budget_rate, 2),
            })

        # 汇总指标
        overall_finance_rate = total_finance_consumed / total_finance_budget * 100 if total_finance_budget > 0 else 0
        overall_management_rate = total_management_consumed / total_management_budget * 100 if total_management_budget > 0 else 0
        caliber_diff = total_management_consumed - total_finance_consumed

        # CRO费用统计
        stmt_cro = select(func.sum(RnDMilestone.cro_payment_id)).where(
            RnDMilestone.cro_payment_id.isnot(None)
        )
        # 简化：统计有CRO付款的里程碑数
        stmt_cro_count = select(func.count()).where(
            RnDMilestone.cro_payment_id.isnot(None),
            RnDMilestone.status == "已完成",
        )
        result_cro_count = await db.execute(stmt_cro_count)
        cro_milestone_count = result_cro_count.scalar() or 0

        return {
            "period": period,
            "summary": {
                "active_projects": len(projects),
                "active_pipelines": len(pipelines),
                "total_finance_budget": total_finance_budget,
                "total_finance_consumed": total_finance_consumed,
                "overall_finance_rate": round(overall_finance_rate, 2),
                "total_management_budget": total_management_budget,
                "total_management_consumed": total_management_consumed,
                "overall_management_rate": round(overall_management_rate, 2),
                "caliber_difference": round(caliber_diff, 2),
                "cro_milestone_count": cro_milestone_count,
            },
            "project_analysis": project_analysis,
            "pipeline_analysis": pipeline_analysis,
            "efficiency_assessment": self._assess_efficiency(
                overall_finance_rate, overall_management_rate, project_analysis
            ),
        }

    def _assess_efficiency(
        self, finance_rate: float, management_rate: float, project_analysis: List[Dict]
    ) -> Dict[str, Any]:
        """评估R&D效率"""
        # 预算执行效率
        if finance_rate <= 50:
            budget_efficiency = "偏低"
            budget_comment = "预算执行率低于50%，可能存在项目推进缓慢"
        elif finance_rate <= 80:
            budget_efficiency = "正常"
            budget_comment = "预算执行率在合理范围内"
        elif finance_rate <= 100:
            budget_efficiency = "较高"
            budget_comment = "预算执行率较高，需关注是否超预算"
        else:
            budget_efficiency = "超预算"
            budget_comment = "预算已超支，须立即审查"

        # 里程碑完成率
        if project_analysis:
            avg_completion = sum(p["milestone_completion_rate"] for p in project_analysis) / len(project_analysis)
            avg_delay = sum(p["milestone_delay_rate"] for p in project_analysis) / len(project_analysis)
        else:
            avg_completion = 0
            avg_delay = 0

        return {
            "budget_efficiency": budget_efficiency,
            "budget_comment": budget_comment,
            "avg_milestone_completion_rate": round(avg_completion, 1),
            "avg_milestone_delay_rate": round(avg_delay, 1),
            "recommendation": self._generate_efficiency_recommendation(
                budget_efficiency, avg_completion, avg_delay
            ),
        }

    def _generate_efficiency_recommendation(
        self, budget_efficiency: str, avg_completion: float, avg_delay: float
    ) -> str:
        """生成效率建议"""
        parts = []
        if budget_efficiency == "偏低":
            parts.append("建议加速项目推进，识别阻碍因素")
        elif budget_efficiency == "超预算":
            parts.append("建议审查超预算项目，评估是否需要追加预算或调整范围")

        if avg_completion < 50:
            parts.append("里程碑完成率偏低，建议审查项目计划合理性")
        if avg_delay > 20:
            parts.append("里程碑延期率较高，建议加强项目进度管控")

        if not parts:
            parts.append("R&D效率良好，维持现有管理措施")

        return "；".join(parts)
