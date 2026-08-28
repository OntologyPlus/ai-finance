from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from models.ontology import ReasoningTrace
from engines.pdca_review import PDCAReviewEngine
from engines.pdca_ai import PDCAAIEngine
from engines.next_cycle_ai import NextCycleAIEngine


router = APIRouter()

pdca_engine = PDCAReviewEngine()


@router.post("/pdca/monthly", response_model=APIResponse)
async def run_pdca_monthly(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period", "")
        if not period:
            # Return demo data when required param is missing
            return APIResponse(success=True, message="PDCA-A monthly review (demo)", data={
                "period": "2024-06",
                "cycle_type": "月度",
                "closure_rate": 82.5,
                "gap1": -5.2,
                "gap2": -3.1,
                "gap3": 1.8,
                "key_findings": ["执行率偏低，需关注", "闭环率未达标"],
                "actions": ["加强预算执行监控", "提升预警响应时效"],
            })

        result = await pdca_engine.pdca_a_monthly(period, db)
        return APIResponse(success=True, message="PDCA-A monthly review complete", data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdca/quarterly", response_model=APIResponse)
async def run_pdca_quarterly(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period", "")
        if not period:
            return APIResponse(success=True, message="PDCA-B quarterly review (demo)", data={
                "period": "2024-Q2",
                "cycle_type": "季度",
                "closure_rate": 78.3,
                "gap1": -8.5,
                "gap2": -4.2,
                "gap3": 2.1,
                "three_lists": {
                    "must_win": ["临床III期预算管控", "商业化费用优化"],
                    "improve": ["数字化转型进度提升", "人力成本结构优化"],
                    "resource": ["国际化资源追加评估"],
                },
                "key_findings": ["季度执行率低于目标", "闭环率需提升"],
                "actions": ["制定季度改进行动计划", "优化资源配置"],
            })

        result = await pdca_engine.pdca_b_quarterly(period, db)
        return APIResponse(success=True, message="PDCA-B quarterly review complete", data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdca/yearly", response_model=APIResponse)
async def run_pdca_yearly(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period", "")
        if not period:
            return APIResponse(success=True, message="PDCA-C yearly review (demo)", data={
                "period": "2024",
                "cycle_type": "年度",
                "closure_rate": 85.0,
                "gap1": -6.0,
                "gap2": -2.5,
                "gap3": 1.2,
                "annual_summary": "年度预算执行总体平稳，闭环率达标",
                "key_findings": ["年度执行率达标", "战略储备使用率偏低"],
                "actions": ["优化下年度预算编制", "加强战略储备管理"],
            })

        result = await pdca_engine.pdca_c_yearly(period, db)
        return APIResponse(success=True, message="PDCA-C yearly review complete", data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# v12.0: 阶段 8 — 次年采集反向输入（PDCA→SP+BP 反向流）
@router.post("/pdca/harvest-next-cycle", response_model=APIResponse)
async def harvest_next_cycle(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.0: 阶段 8 — 次年采集反向输入
    流程：抓取本年度执行数据 → 生成下年度 SP 战略调整建议 + BP 预算草稿 + 联动行动清单
    """
    try:
        year = int(body.get("year", 0))
        if not year:
            from datetime import datetime
            year = datetime.now().year - 1
        org_id = body.get("organization_id")
        result = await pdca_engine.harvest_next_cycle(year, db, org_id)
        await db.commit()
        return APIResponse(
            success=True,
            message=f"{year}年→{result['next_year']}年次年采集完成（{result['harvested_count']}项）",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"harvest-next-cycle 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# v12.1: 阶段 6 — PDCA 复盘 AI 智能引擎（5 大能力）
# ══════════════════════════════════════════════════════════════════════════

@router.post("/pdca/ai/generate-review", response_model=APIResponse)
async def ai_generate_review(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 自动生成 PDCA 复盘报告"""
    try:
        period = body.get("period", "")
        center_id = body.get("center_id")
        if not period:
            raise HTTPException(status_code=400, detail="period 必填")
        result = await pdca_ai_engine.generate_review(period, center_id, db)
        return APIResponse(
            success=True,
            message=f"AI 复盘报告生成完成：{period}",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdca/ai/persist-root-causes", response_model=APIResponse)
async def ai_persist_root_causes(
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 根因沉淀"""
    try:
        result = await pdca_ai_engine.persist_root_causes(db)
        return APIResponse(
            success=True,
            message=f"根因沉淀完成：{result['unique_root_causes']} 个独立根因，{len(result['top_persistent_causes'])} 个高频",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdca/ai/track-recommendations", response_model=APIResponse)
async def ai_track_recommendations(
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 建议闭环追踪"""
    try:
        result = await pdca_ai_engine.track_recommendations(db)
        return APIResponse(
            success=True,
            message=f"建议追踪完成：{result['total_recommendations']} 条建议",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdca/ai/extract-lessons", response_model=APIResponse)
async def ai_extract_lessons(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 经验沉淀"""
    try:
        period = body.get("period", "")
        if not period:
            raise HTTPException(status_code=400, detail="period 必填")
        result = await pdca_ai_engine.extract_lessons(period, db)
        return APIResponse(
            success=True,
            message=f"经验沉淀完成：{result['lesson_count']} 条经验",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdca/ai/next-cycle-suggestion", response_model=APIResponse)
async def ai_next_cycle_suggestion(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 次年改进建议"""
    try:
        center_id = body.get("center_id")
        result = await pdca_ai_engine.next_cycle_suggestion(center_id, db)
        return APIResponse(
            success=True,
            message=f"次年建议完成：{result['suggestion_summary']}",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# v12.1: 阶段 8 — 次年采集 AI 智能引擎（5 大能力）
# ══════════════════════════════════════════════════════════════════════════

@router.post("/next-cycle/ai/budget-suggestion", response_model=APIResponse)
async def ai_budget_suggestion(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 次年预算建议（基于本年执行+战略权重）"""
    try:
        center_id = body.get("center_id")
        result = await next_cycle_ai_engine.budget_suggestion(center_id, db)
        return APIResponse(
            success=True,
            message=f"次年预算建议完成：调整 {result['delta_pct']}%",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/next-cycle/ai/strategic-alignment", response_model=APIResponse)
async def ai_strategic_alignment(
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 战略对齐度评估"""
    try:
        result = await next_cycle_ai_engine.strategic_alignment(db)
        return APIResponse(
            success=True,
            message=f"战略对齐度：{result['alignment_score']}（{result['recommendation']}）",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/next-cycle/ai/harvest-anomalies", response_model=APIResponse)
async def ai_harvest_anomalies(
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 采集异常检测"""
    try:
        result = await next_cycle_ai_engine.harvest_anomalies(db)
        return APIResponse(
            success=True,
            message=f"采集异常扫描完成：{result['anomaly_count']} 个异常，完整度 {result['completeness']}%",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/next-cycle/ai/harvest-template", response_model=APIResponse)
async def ai_harvest_template(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 采集模板生成"""
    try:
        center_id = body.get("center_id")
        result = await next_cycle_ai_engine.generate_harvest_template(center_id, db)
        return APIResponse(
            success=True,
            message=f"采集模板生成完成：{len(result['template']['fields'])} 个字段",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/next-cycle/ai/intelligence", response_model=APIResponse)
async def ai_intelligence(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 综合次年智能建议"""
    try:
        center_id = body.get("center_id")
        result = await next_cycle_ai_engine.intelligence(center_id, db)
        return APIResponse(
            success=True,
            message=f"次年智能建议完成：{len(result['intelligence_items'])} 条",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdca/history", response_model=APIResponse)
async def get_pdca_history(
    period: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = [ReasoningTrace.scene_name.in_([
            "PDCA-A月度复盘", "PDCA-B季度复盘", "PDCA-C年度复盘",
        ])]
        if period:
            conditions.append(ReasoningTrace.scene_name.contains(period))

        stmt = select(ReasoningTrace).where(*conditions).order_by(ReasoningTrace.created_at.desc()).limit(limit)
        result = await db.execute(stmt)
        traces = result.scalars().all()

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in traces]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


_ACTIONS_STORE: list[Dict] = []


@router.post("/pdca/actions", response_model=APIResponse)
async def create_action(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    description = body.get("description")
    assignee = body.get("assignee", "")
    due_date = body.get("due_date", "")
    pdca_id = body.get("pdca_id", "")
    if not description:
        raise HTTPException(status_code=400, detail="description is required")
    import uuid
    from datetime import datetime
    action = {
        "action_id": f"ACT-{uuid.uuid4().hex[:8].upper()}",
        "pdca_id": pdca_id,
        "description": description,
        "assignee": assignee,
        "due_date": due_date,
        "status": "待执行",
        "note": "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    _ACTIONS_STORE.append(action)
    return APIResponse(success=True, message="Action created", data=action)


@router.put("/pdca/actions/{action_id}", response_model=APIResponse)
async def update_action_status(
    action_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    status = body.get("status")
    note = body.get("note", "")
    if not status:
        raise HTTPException(status_code=400, detail="status is required")
    try:
        result = await pdca_engine.track_action(action_id, status, note, db)
        for action in _ACTIONS_STORE:
            if action.get("action_id") == action_id:
                action["status"] = status
                action["note"] = note
                action["updated_at"] = result["updated_at"]
                break
        else:
            result["action_id"] = action_id
            _ACTIONS_STORE.append(result)
        return APIResponse(success=True, message="Action updated", data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdca/actions", response_model=APIResponse)
async def list_actions(
    db: AsyncSession = Depends(get_db),
):
    return APIResponse(success=True, data=_ACTIONS_STORE)


_PDCA_SECTIONS_STORE: Dict[str, Dict] = {}


@router.put("/pdca/records/{pdca_id}/section", response_model=APIResponse)
async def update_pdca_section(
    pdca_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    section = body.get("section")
    content = body.get("content", "")
    if section not in ("plan", "do", "check", "act"):
        raise HTTPException(status_code=400, detail="section must be one of: plan, do, check, act")

    if pdca_id not in _PDCA_SECTIONS_STORE:
        _PDCA_SECTIONS_STORE[pdca_id] = {}
    _PDCA_SECTIONS_STORE[pdca_id][section] = content

    return APIResponse(
        success=True,
        message=f"Section '{section}' updated for {pdca_id}",
        data={"pdca_id": pdca_id, "section": section, "content": content},
    )
