from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from models.rnd_pipeline import Pipeline, RnDProject, ClinicalTrial
from engines.pipeline_engine import PipelineEngine
from services.pipeline_cognitive import (
    evaluate_pipeline_value,
    compute_value_matrix,
    evaluate_go_nogo,
)

router = APIRouter()

engine = PipelineEngine()


@router.post("/pipelines/{pipeline_id}/advance", response_model=APIResponse)
async def advance_pipeline(
    pipeline_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        target_stage = body.get("target_stage")
        go_nogo = body.get("go_nogo")
        if target_stage is None or go_nogo is None:
            raise HTTPException(status_code=400, detail="target_stage and go_nogo are required")

        result = await engine.advance_pipeline(pipeline_id, target_stage, go_nogo, db)
        return APIResponse(success=True, message="Pipeline advanced", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pipelines/{pipeline_id}/terminate", response_model=APIResponse)
async def terminate_pipeline(
    pipeline_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        action = body.get("action")
        reason = body.get("reason", "")
        if not action:
            raise HTTPException(status_code=400, detail="action is required")

        result = await engine.terminate_pipeline(pipeline_id, action, reason, db)
        return APIResponse(success=True, message="Pipeline terminated", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipelines/{pipeline_id}/status", response_model=APIResponse)
async def get_pipeline_status(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.get_pipeline_status(pipeline_id, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Module E.3：管线认知深度（价值矩阵 + Go/No-Go 决策） ===


@router.get("/pipelines", response_model=APIResponse)
async def list_pipelines(
    status: Optional[str] = Query(None, description="状态筛选：活跃/已终止/已暂停"),
    db: AsyncSession = Depends(get_db),
):
    """拉取管线列表（用于价值矩阵和总览）。"""
    try:
        stmt = select(Pipeline)
        if status:
            stmt = stmt.where(Pipeline.status == status)
        result = await db.execute(stmt)
        items = result.scalars().all()
        data = [
            {
                "pipeline_id": p.pipeline_id,
                "name": p.name,
                "indication": p.indication,
                "current_stage": p.current_stage,
                "go_nogo_status": p.go_nogo_status,
                "total_budget": float(p.total_budget) if p.total_budget else 0,
                "consumed_budget": float(p.consumed_budget) if p.consumed_budget else 0,
                "status": p.status,
                "estimated_launch_date": p.estimated_launch_date.isoformat() if p.estimated_launch_date else None,
            }
            for p in items
        ]
        return APIResponse(success=True, data=data, message="管线列表拉取完成")
    except Exception as e:
        logger.error(f"list pipelines 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipelines/cognitive/value-matrix", response_model=APIResponse)
async def get_value_matrix(
    db: AsyncSession = Depends(get_db),
):
    """管线价值矩阵：所有管线的 rNPV + 上市概率 + 价值分层 + BCG 象限。

    价值评估公式：
    - 累计成功率 = 当前阶段→上市的行业连乘概率
    - 预期价值 = 累计成功率 × 峰值销售 × 净利率
    - rNPV = 预期价值 - 累计投入
    """
    try:
        stmt = select(Pipeline)
        result = await db.execute(stmt)
        items = result.scalars().all()

        matrix = compute_value_matrix(list(items))
        return APIResponse(success=True, data=matrix, message="价值矩阵计算完成")
    except Exception as e:
        logger.error(f"value-matrix 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipelines/cognitive/value/{pipeline_id}", response_model=APIResponse)
async def get_pipeline_value(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
):
    """单管线价值评估详情。"""
    try:
        stmt = select(Pipeline).where(Pipeline.pipeline_id == pipeline_id)
        result = await db.execute(stmt)
        pipeline = result.scalar_one_or_none()
        if pipeline is None:
            raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found")

        stmt_all = select(Pipeline)
        result_all = await db.execute(stmt_all)
        all_pipelines = result_all.scalars().all()

        val = evaluate_pipeline_value(pipeline, list(all_pipelines))
        return APIResponse(success=True, data=val.to_dict(), message="管线价值评估完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"pipeline value 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipelines/cognitive/go-nogo/{pipeline_id}", response_model=APIResponse)
async def get_go_nogo_decision(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
):
    """单管线 Go/No-Go 决策评估。

    5 因素加权评分：
    - 科学性 20% + 临床数据 25% + 竞争格局 15% + 商业前景 20% + 财务可行性 20%

    决策阈值：
    - 总分 ≥ 70: Go
    - 50 ≤ 总分 < 70: Conditional
    - 总分 < 50: No-Go
    """
    try:
        stmt = select(Pipeline).where(Pipeline.pipeline_id == pipeline_id)
        result = await db.execute(stmt)
        pipeline = result.scalar_one_or_none()
        if pipeline is None:
            raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found")

        stmt_p = select(RnDProject).where(RnDProject.pipeline_id == pipeline_id)
        result_p = await db.execute(stmt_p)
        projects = result_p.scalars().all()

        stmt_t = select(ClinicalTrial).where(ClinicalTrial.pipeline_id == pipeline_id)
        result_t = await db.execute(stmt_t)
        trials = result_t.scalars().all()

        decision = evaluate_go_nogo(pipeline, list(projects), list(trials))
        return APIResponse(success=True, data=decision.to_dict(), message="Go/No-Go 决策完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"go-nogo 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
