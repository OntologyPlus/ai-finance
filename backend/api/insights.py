"""
主动建议洞察 API

端点：
- GET  /api/insights/active           获取未读 + 未忽略的洞察
- POST /api/insights/{id}/read        标记已读
- POST /api/insights/{id}/dismiss     忽略洞察
- POST /api/insights/scan             手动触发扫描（body: {user_id, period}）
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.analysis import ProactiveInsight
from models.database import get_db
from models.schemas import APIResponse
from services.proactive_advisor import ProactiveAdvisor

router = APIRouter()
advisor = ProactiveAdvisor()


def _serialize(insight: ProactiveInsight) -> Dict[str, Any]:
    """将 ProactiveInsight ORM 对象序列化为 dict"""
    return {c: getattr(insight, c) for c in insight.__table__.columns.keys()}


@router.get("/insights/active", response_model=APIResponse)
async def get_active_insights(
    user_id: Optional[str] = Query(None, description="目标用户 ID（None 表示全用户）"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    db: AsyncSession = Depends(get_db),
):
    """获取未读 + 未忽略的洞察，按优先级 + 时间倒序排列"""
    try:
        stmt = select(ProactiveInsight).where(
            and_(
                ProactiveInsight.is_dismissed == False,  # noqa: E712
                ProactiveInsight.is_read == False,  # noqa: E712
            )
        )
        if user_id:
            stmt = stmt.where(ProactiveInsight.user_id == user_id)
        else:
            stmt = stmt.where(ProactiveInsight.user_id.is_(None))
        stmt = stmt.order_by(ProactiveInsight.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        insights = result.scalars().all()
        data = [_serialize(r) for r in insights]
        return APIResponse(success=True, message=f"返回 {len(data)} 条洞察", data=data)
    except Exception as e:  # noqa: BLE001
        logger.error(f"insights/active 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insights/{insight_id}/read", response_model=APIResponse)
async def mark_read(
    insight_id: str,
    db: AsyncSession = Depends(get_db),
):
    """标记洞察为已读"""
    try:
        result = await db.execute(
            update(ProactiveInsight)
            .where(ProactiveInsight.id == insight_id)
            .values(is_read=True)
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"洞察 {insight_id} 不存在")
        return APIResponse(success=True, message="已标记已读")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"insights/{insight_id}/read 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insights/{insight_id}/dismiss", response_model=APIResponse)
async def dismiss(
    insight_id: str,
    db: AsyncSession = Depends(get_db),
):
    """忽略洞察（持久化 dismissed=true）"""
    try:
        result = await db.execute(
            update(ProactiveInsight)
            .where(ProactiveInsight.id == insight_id)
            .values(is_dismissed=True)
        )
        await db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"洞察 {insight_id} 不存在")
        return APIResponse(success=True, message="已忽略")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"insights/{insight_id}/dismiss 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/insights/scan", response_model=APIResponse)
async def trigger_scan(
    body: Dict[str, Any] = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
):
    """手动触发扫描。

    Body:
        user_id: 目标用户 ID（可选）
        period:  统计期间 YYYY-MM（可选）
    """
    try:
        user_id = body.get("user_id")
        period = body.get("period")
        insights = await advisor.scan_and_push_insights(
            db, user_id=user_id, period=period
        )
        data = {
            "count": len(insights),
            "insights": [_serialize(r) for r in insights],
        }
        return APIResponse(
            success=True,
            message=f"扫描完成，新增 {len(insights)} 条洞察",
            data=data,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"insights/scan 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
