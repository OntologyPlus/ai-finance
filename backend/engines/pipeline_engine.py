from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.rnd_pipeline import Pipeline, RnDProject, RnDMilestone, ClinicalTrial


# 管线阶段定义（有序）
PIPELINE_STAGES = ["发现", "临床前", "I期临床", "II期临床", "III期临床", "注册申报", "上市"]


class PipelineEngine:
    """管线生命周期管理引擎 — 管线推进、终止与状态追踪"""

    async def advance_pipeline(
        self,
        pipeline_id: str,
        target_stage: str,
        go_nogo: str,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """推进管线阶段

        HR-030：管线阶段推进必须经过Go/No-Go决策
        HR-031：No-Go决策的管线须进入终止评估流程

        Args:
            pipeline_id: 管线编号
            target_stage: 目标阶段
            go_nogo: Go/No-Go决策（Go/No-Go）
            db: 数据库会话

        Returns:
            推进结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(Pipeline).where(Pipeline.pipeline_id == pipeline_id)
        result = await db.execute(stmt)
        pipeline = result.scalar_one_or_none()

        if pipeline is None:
            return {"error": f"管线编号 {pipeline_id} 不存在"}

        if pipeline.status != "活跃":
            return {"error": f"管线状态为'{pipeline.status}'，无法推进"}

        # HR-030：必须经过Go/No-Go决策
        if go_nogo not in ("Go", "No-Go"):
            return {"error": "必须明确Go/No-Go决策（HR-030）"}

        # HR-031：No-Go决策进入终止评估
        if go_nogo == "No-Go":
            pipeline.go_nogo_status = "No-Go"
            await db.flush()
            return {
                "pipeline_id": pipeline_id,
                "name": pipeline.name,
                "action": "terminate_evaluation",
                "current_stage": pipeline.current_stage,
                "go_nogo": "No-Go",
                "message": f"管线{pipeline.name}收到No-Go决策，须进入终止评估流程（HR-031）",
                "recommendation": "请调用terminate_pipeline执行终止或暂停操作",
            }

        # 验证目标阶段有效
        if target_stage not in PIPELINE_STAGES:
            return {"error": f"无效阶段'{target_stage}'，有效阶段：{', '.join(PIPELINE_STAGES)}"}

        current_idx = PIPELINE_STAGES.index(pipeline.current_stage) if pipeline.current_stage in PIPELINE_STAGES else -1
        target_idx = PIPELINE_STAGES.index(target_stage)

        if target_idx <= current_idx:
            return {"error": f"目标阶段'{target_stage}'不高于当前阶段'{pipeline.current_stage}'，无法推进"}

        # 执行推进
        pipeline.current_stage = target_stage
        pipeline.go_nogo_status = "Go"
        await db.flush()

        logger.info(f"管线推进: {pipeline_id} → {target_stage}")
        return {
            "pipeline_id": pipeline_id,
            "name": pipeline.name,
            "previous_stage": pipeline.current_stage if target_stage == pipeline.current_stage else PIPELINE_STAGES[current_idx] if current_idx >= 0 else "未知",
            "current_stage": target_stage,
            "go_nogo": "Go",
            "message": f"管线{pipeline.name}已推进至{target_stage}阶段",
        }

    async def terminate_pipeline(
        self,
        pipeline_id: str,
        action: str,
        reason: str,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """终止或暂停管线

        HR-032：终止管线须释放剩余预算
        HR-033：暂停管线保留预算但冻结执行

        Args:
            pipeline_id: 管线编号
            action: 操作类型（终止/暂停）
            reason: 原因说明
            db: 数据库会话

        Returns:
            操作结果
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        if action not in ("终止", "暂停"):
            return {"error": "操作类型必须为'终止'或'暂停'"}

        stmt = select(Pipeline).where(Pipeline.pipeline_id == pipeline_id)
        result = await db.execute(stmt)
        pipeline = result.scalar_one_or_none()

        if pipeline is None:
            return {"error": f"管线编号 {pipeline_id} 不存在"}

        if pipeline.status in ("已终止",):
            return {"error": f"管线已终止，无法再次操作"}

        remaining_budget = pipeline.total_budget - pipeline.consumed_budget

        if action == "终止":
            # HR-032：终止管线须释放剩余预算
            pipeline.status = "已终止"
            pipeline.go_nogo_status = "No-Go"
            released_budget = remaining_budget

            # 查找关联项目并更新状态
            stmt_projects = select(RnDProject).where(RnDProject.pipeline_id == pipeline_id)
            result_projects = await db.execute(stmt_projects)
            projects = result_projects.scalars().all()

            terminated_projects = []
            for project in projects:
                if project.status == "进行中":
                    project.status = "已终止"
                    terminated_projects.append(project.project_id)

            await db.flush()

            logger.info(f"管线终止: {pipeline_id}, 释放预算={released_budget}")
            return {
                "pipeline_id": pipeline_id,
                "name": pipeline.name,
                "action": "终止",
                "reason": reason,
                "released_budget": released_budget,
                "terminated_projects": terminated_projects,
                "message": f"管线{pipeline.name}已终止，释放预算{released_budget:.0f}万元（HR-032）",
            }

        else:  # 暂停
            # HR-033：暂停管线保留预算但冻结执行
            pipeline.status = "已暂停"

            stmt_projects = select(RnDProject).where(RnDProject.pipeline_id == pipeline_id)
            result_projects = await db.execute(stmt_projects)
            projects = result_projects.scalars().all()

            suspended_projects = []
            for project in projects:
                if project.status == "进行中":
                    project.status = "已暂停"
                    suspended_projects.append(project.project_id)

            await db.flush()

            logger.info(f"管线暂停: {pipeline_id}, 冻结预算={remaining_budget}")
            return {
                "pipeline_id": pipeline_id,
                "name": pipeline.name,
                "action": "暂停",
                "reason": reason,
                "frozen_budget": remaining_budget,
                "suspended_projects": suspended_projects,
                "message": f"管线{pipeline.name}已暂停，预算{remaining_budget:.0f}万元冻结保留（HR-033）",
            }

    async def get_pipeline_status(
        self, pipeline_id: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """获取管线状态及预算消耗情况

        Args:
            pipeline_id: 管线编号
            db: 数据库会话

        Returns:
            管线状态详情
        """
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(Pipeline).where(Pipeline.pipeline_id == pipeline_id)
        result = await db.execute(stmt)
        pipeline = result.scalar_one_or_none()

        if pipeline is None:
            return {"error": f"管线编号 {pipeline_id} 不存在"}

        # 获取关联项目
        stmt_projects = select(RnDProject).where(RnDProject.pipeline_id == pipeline_id)
        result_projects = await db.execute(stmt_projects)
        projects = result_projects.scalars().all()

        project_details = []
        for project in projects:
            # 获取里程碑
            stmt_milestones = select(RnDMilestone).where(RnDMilestone.project_id == project.project_id)
            result_milestones = await db.execute(stmt_milestones)
            milestones = result_milestones.scalars().all()

            project_details.append({
                "project_id": project.project_id,
                "name": project.name,
                "project_type": project.project_type,
                "manager": project.manager,
                "finance_budget": project.finance_budget,
                "management_budget": project.management_budget,
                "consumed_finance": project.consumed_finance,
                "consumed_management": project.consumed_management,
                "finance_execution_rate": project.consumed_finance / project.finance_budget * 100 if project.finance_budget > 0 else 0,
                "management_execution_rate": project.consumed_management / project.management_budget * 100 if project.management_budget > 0 else 0,
                "status": project.status,
                "milestones": [
                    {
                        "name": m.name,
                        "planned_date": m.planned_date.isoformat() if m.planned_date else None,
                        "actual_date": m.actual_date.isoformat() if m.actual_date else None,
                        "status": m.status,
                    }
                    for m in milestones
                ],
            })

        # 获取关联临床试验
        stmt_trials = select(ClinicalTrial).where(ClinicalTrial.pipeline_id == pipeline_id)
        result_trials = await db.execute(stmt_trials)
        trials = result_trials.scalars().all()

        trial_details = [
            {
                "trial_id": t.trial_id,
                "name": t.name,
                "phase": t.phase,
                "cro_vendor": t.cro_vendor,
                "center_count": t.center_count,
                "total_cost": t.total_cost,
                "status": t.status,
            }
            for t in trials
        ]

        budget_consumption_rate = pipeline.consumed_budget / pipeline.total_budget * 100 if pipeline.total_budget > 0 else 0

        return {
            "pipeline_id": pipeline.pipeline_id,
            "name": pipeline.name,
            "indication": pipeline.indication,
            "current_stage": pipeline.current_stage,
            "go_nogo_status": pipeline.go_nogo_status,
            "status": pipeline.status,
            "estimated_launch_date": pipeline.estimated_launch_date.isoformat() if pipeline.estimated_launch_date else None,
            "budget": {
                "total": pipeline.total_budget,
                "consumed": pipeline.consumed_budget,
                "remaining": pipeline.total_budget - pipeline.consumed_budget,
                "consumption_rate": round(budget_consumption_rate, 2),
            },
            "projects": project_details,
            "clinical_trials": trial_details,
            "stage_progress": self._calculate_stage_progress(pipeline.current_stage),
        }

    def _calculate_stage_progress(self, current_stage: str) -> Dict[str, Any]:
        """计算管线阶段进度"""
        if current_stage not in PIPELINE_STAGES:
            return {"progress": 0, "total_stages": len(PIPELINE_STAGES), "current_index": 0}

        current_idx = PIPELINE_STAGES.index(current_stage)
        progress = (current_idx + 1) / len(PIPELINE_STAGES) * 100

        return {
            "progress": round(progress, 1),
            "total_stages": len(PIPELINE_STAGES),
            "current_index": current_idx + 1,
            "stages": PIPELINE_STAGES,
            "completed_stages": PIPELINE_STAGES[:current_idx + 1],
            "remaining_stages": PIPELINE_STAGES[current_idx + 1:],
        }
