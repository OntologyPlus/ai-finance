from typing import Optional
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse, APIPageResponse
from models.budget import BudgetSubjectL1, BudgetSubjectL2, BudgetSubjectL3, BudgetItem
from models.alert import AlertRecord
from models.transfer import BudgetTransferRequest
from engines.budget_planning import BudgetPlanningEngine
from engines.budget_grant import BudgetGrantEngine
from engines.budget_adjustment import BudgetAdjustmentEngine
from engines.notification_engine import NotificationEngine
from services.budget_cognitive import (
    drill_down_root_cause,
    generate_proactive_suggestions,
    compute_business_linkage,
)

from api.permission_middleware import (
    get_role_from_request,
    filter_response_fields,
    check_data_scope,
    get_user_center_from_request,
    get_user_dept_from_request,
)
from api.deps import get_current_user, get_center_filter_for_user
from models.user import User

router = APIRouter()

planning_engine = BudgetPlanningEngine()
grant_engine = BudgetGrantEngine()
adjustment_engine = BudgetAdjustmentEngine()
notification_engine = NotificationEngine()

_PK_SESSIONS: list[dict] = []


@router.get("/budget/subjects", response_model=APIResponse)
async def list_budget_subjects(
    level: Optional[str] = Query(None, description="科目层级: L1/L2/L3"),
    db: AsyncSession = Depends(get_db),
):
    try:
        if level == "L1" or level is None:
            stmt = select(BudgetSubjectL1)
            result = await db.execute(stmt)
            l1_list = result.scalars().all()
            data = [{"level": "L1", **{c: getattr(r, c) for c in r.__table__.columns.keys()}} for r in l1_list]
        elif level == "L2":
            stmt = select(BudgetSubjectL2)
            result = await db.execute(stmt)
            l2_list = result.scalars().all()
            data = [{"level": "L2", **{c: getattr(r, c) for c in r.__table__.columns.keys()}} for r in l2_list]
        elif level == "L3":
            stmt = select(BudgetSubjectL3)
            result = await db.execute(stmt)
            l3_list = result.scalars().all()
            data = [{"level": "L3", **{c: getattr(r, c) for c in r.__table__.columns.keys()}} for r in l3_list]
        else:
            raise HTTPException(status_code=400, detail=f"Invalid level: {level}")

        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/subjects/{l1_code}", response_model=APIResponse)
async def get_budget_subject(
    l1_code: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        l1 = await db.get(BudgetSubjectL1, l1_code)
        if l1 is None:
            raise HTTPException(status_code=404, detail=f"L1 subject {l1_code} not found")

        stmt_l2 = select(BudgetSubjectL2).where(BudgetSubjectL2.l1_code == l1_code)
        result_l2 = await db.execute(stmt_l2)
        l2_list = result_l2.scalars().all()

        l2_data = []
        for l2 in l2_list:
            stmt_l3 = select(BudgetSubjectL3).where(BudgetSubjectL3.l2_code == l2.l2_code)
            result_l3 = await db.execute(stmt_l3)
            l3_list = result_l3.scalars().all()
            l2_data.append({
                **{c: getattr(l2, c) for c in l2.__table__.columns.keys()},
                "children": [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in l3_list],
            })

        stmt_l3_direct = select(BudgetSubjectL3).where(
            and_(BudgetSubjectL3.l1_code == l1_code, BudgetSubjectL3.l2_code.is_(None))
        )
        result_l3_direct = await db.execute(stmt_l3_direct)
        l3_direct = result_l3_direct.scalars().all()

        data = {
            **{c: getattr(l1, c) for c in l1.__table__.columns.keys()},
            "l2_children": l2_data,
            "l3_direct_children": [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in l3_direct],
        }

        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/items", response_model=APIPageResponse)
async def list_budget_items(
    request: Request,
    center_id: Optional[str] = Query(None),
    quadrant: Optional[str] = Query(None),
    category: Optional[str] = Query(None, description="A/B"),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_center_filter = get_center_filter_for_user(current_user)
    try:
        conditions = []
        # Apply center-based data permission
        if user_center_filter:
            conditions.append(BudgetItem.center_id == user_center_filter)
        if center_id:
            conditions.append(BudgetItem.center_id == center_id)
        if quadrant:
            conditions.append(BudgetItem.quadrant == quadrant)
        if category:
            conditions.append(BudgetItem.budget_category == category)
        if status:
            conditions.append(BudgetItem.status == status)

        stmt = select(BudgetItem).where(and_(*conditions)) if conditions else select(BudgetItem)
        result = await db.execute(stmt)
        items = result.scalars().all()

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in page_items]

        role_type = get_role_from_request(request)
        data = [filter_response_fields(role_type, "BudgetItem", d) for d in data]

        return APIPageResponse(
            success=True,
            total=total,
            page=page,
            page_size=page_size,
            data=data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/items/{budget_id}", response_model=APIResponse)
async def get_budget_item(
    budget_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await db.get(BudgetItem, budget_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Budget item {budget_id} not found")

        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        role_type = get_role_from_request(request)
        data = filter_response_fields(role_type, "BudgetItem", data)
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/items", response_model=APIResponse)
async def create_budget_item(
    budget_data: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        budget_id = budget_data.get("budget_id")
        if not budget_id:
            raise HTTPException(status_code=400, detail="budget_id is required")

        existing = await db.get(BudgetItem, budget_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"Budget item {budget_id} already exists")

        item = BudgetItem(**budget_data)
        db.add(item)
        await db.flush()

        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="Budget item created", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/budget/items/{budget_id}", response_model=APIResponse)
async def update_budget_item(
    budget_id: str,
    update_data: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await db.get(BudgetItem, budget_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Budget item {budget_id} not found")

        for key, value in update_data.items():
            if hasattr(item, key) and key != "budget_id":
                setattr(item, key, value)

        await db.flush()

        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="Budget item updated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/items/{budget_id}/grant-a", response_model=APIResponse)
async def grant_a_class(
    budget_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await grant_engine.grant_a_class(budget_id, db)
        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="A-class budget granted", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/items/{budget_id}/grant-b", response_model=APIResponse)
async def grant_b_class(
    budget_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await grant_engine.grant_b_class(budget_id, db)
        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="B-class budget processed", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/items/{budget_id}/b2a-preview", response_model=APIResponse)
async def b2a_preview(
    budget_id: str,
    db: AsyncSession = Depends(get_db),
):
    """v12.0: B→A 转换预览（不落库），三维度综合验证

    返回结构：
    - can_convert: True=可转换 / False=被红色拦截
    - risk_level: 蓝色/黄色/橙色/红色
    - dimensions: 三维度（时间/费用/累计）独立验证结果
    - milestones: 当前里程碑状态明细
    - conversion_preview: 转换后字段值（granted/frozen/available/percentage）
    - committee_report_required: 黄色风险是否需上报管委会
    """
    try:
        from models.milestone import Milestone
        from decimal import Decimal as _D

        item = await db.get(BudgetItem, budget_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Budget item {budget_id} not found")
        if item.budget_category != "B":
            raise HTTPException(
                status_code=400,
                detail=f"该预算为{item.budget_category}类，无需B→A转换",
            )

        stmt = select(Milestone).where(Milestone.budget_id == budget_id).order_by(Milestone.quarter)
        result = await db.execute(stmt)
        milestones = result.scalars().all()

        completed = [ms for ms in milestones if ms.status == "completed"]
        completed_count = len(completed)

        # 三维度验证（与 budget_grant.b2a_convert 一致）
        LEVEL_PRIORITY = {"蓝色": 1, "黄色": 2, "橙色": 3, "红色": 4}
        max_level = "蓝色"
        max_reasons: list = []
        dimension_results: dict = {
            "时间": {"max_level": "蓝色", "items": []},
            "费用": {"max_level": "蓝色", "items": []},
            "累计": {"max_level": "蓝色", "items": []},
        }

        for ms in completed:
            # 维度1：时间偏差
            time_level = None
            time_reason = None
            if ms.actual_date and ms.planned_date:
                deviation_days = (ms.actual_date - ms.planned_date).days
                if deviation_days > 60:
                    time_level = "红色"
                    time_reason = f"时间偏差{deviation_days}天>60天"
                elif deviation_days > 30:
                    time_level = "黄色"
                    time_reason = f"时间偏差{deviation_days}天(31-60天)"
                elif deviation_days > 20:
                    time_level = "蓝色"
                    time_reason = f"时间偏差{deviation_days}天(21-30天)"
                if time_level:
                    dimension_results["时间"]["items"].append({
                        "milestone_id": ms.milestone_id,
                        "level": time_level,
                        "reason": time_reason,
                    })
                    if LEVEL_PRIORITY.get(time_level, 0) > LEVEL_PRIORITY.get(dimension_results["时间"]["max_level"], 0):
                        dimension_results["时间"]["max_level"] = time_level

            # 维度2：费用偏差
            cost_level = None
            cost_reason = None
            if ms.evidence:
                if "严重超支" in ms.evidence or "重大超支" in ms.evidence:
                    cost_level = "红色"
                    cost_reason = "里程碑证据标注严重超支"
                elif "超支" in ms.evidence or "超额" in ms.evidence:
                    cost_level = "黄色"
                    cost_reason = "里程碑证据标注超支"
                if cost_level:
                    dimension_results["费用"]["items"].append({
                        "milestone_id": ms.milestone_id,
                        "level": cost_level,
                        "reason": cost_reason,
                    })
                    if LEVEL_PRIORITY.get(cost_level, 0) > LEVEL_PRIORITY.get(dimension_results["费用"]["max_level"], 0):
                        dimension_results["费用"]["max_level"] = cost_level

            # 维度3：累计进度（基于 amount_release 与 evidence 中数字推算）
            cum_level = None
            cum_reason = None
            if ms.amount_release and ms.evidence:
                # 若 evidence 包含 "完成率"，尝试解析
                import re
                m = re.search(r"完成率[::\s]*(\d+(?:\.\d+)?)\s*%", ms.evidence)
                if m:
                    completion_rate = float(m.group(1))
                    if completion_rate > 110:
                        cum_level = "黄色"
                        cum_reason = f"累计完成率{completion_rate}%>110%"
                    elif completion_rate > 105:
                        cum_level = "蓝色"
                        cum_reason = f"累计完成率{completion_rate}%>105%"
                    if cum_level:
                        dimension_results["累计"]["items"].append({
                            "milestone_id": ms.milestone_id,
                            "level": cum_level,
                            "reason": cum_reason,
                        })
                        if LEVEL_PRIORITY.get(cum_level, 0) > LEVEL_PRIORITY.get(dimension_results["累计"]["max_level"], 0):
                            dimension_results["累计"]["max_level"] = cum_level

        # 汇总最高级别
        for dim_name, dim_data in dimension_results.items():
            if LEVEL_PRIORITY.get(dim_data["max_level"], 0) > LEVEL_PRIORITY.get(max_level, 0):
                max_level = dim_data["max_level"]
                max_reasons.append(f"[{dim_name}] {dim_data['max_level']}信号")

        can_convert = max_level != "红色" and completed_count >= 2

        annual = float(item.annual_amount or 0)
        conversion_preview = {
            "pre_state": {
                "category": item.budget_category,
                "grant_percentage": float(item.grant_percentage or 0),
                "granted_amount": float(item.granted_amount or 0),
                "frozen_amount": float(item.frozen_amount or 0),
                "available_amount": float(item.available_amount or 0),
                "status": item.status,
            },
            "post_state": {
                "category": "A",
                "grant_percentage": 100.0,
                "granted_amount": annual,
                "frozen_amount": annual,
                "available_amount": annual,
                "status": "已授予",
            },
        }

        return APIResponse(
            success=True,
            data={
                "can_convert": can_convert,
                "risk_level": max_level,
                "reasons": max_reasons,
                "completed_milestones": completed_count,
                "required_milestones": 2,
                "milestones_summary": [
                    {
                        "milestone_id": ms.milestone_id,
                        "quarter": ms.quarter,
                        "status": ms.status,
                        "planned_date": ms.planned_date.isoformat() if ms.planned_date else None,
                        "actual_date": ms.actual_date.isoformat() if ms.actual_date else None,
                        "has_evidence": bool(ms.evidence and ms.evidence.strip()),
                    }
                    for ms in milestones
                ],
                "dimensions": dimension_results,
                "conversion_preview": conversion_preview,
                "committee_report_required": (max_level == "黄色"),
                "block_reasons": [] if can_convert else (
                    [f"完成里程碑{completed_count}/2（至少2个）"] if completed_count < 2 else
                    [f"三维度存在红色信号：{'; '.join(max_reasons)}"]
                ),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"b2a-preview 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# v12.1: 阶段 2 — B→A 智能预判（AI 增强）
# ══════════════════════════════════════════════════════════════════════════
@router.get("/budget/items/{budget_id}/b2a-predict", response_model=APIResponse)
async def b2a_predict(
    budget_id: str,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: 单个 B 类预算的 B→A 转换预判

    返回 5 维评分（完成度/时间/费用/证据/逾期）+ 风险因子 + 修复建议
    """
    try:
        engine = BudgetGrantEngine()
        result = await engine.predict_b2a_conversion(budget_id, db)
        return APIResponse(
            success=True,
            message=f"预判完成：{result['predicted_outcome']}（就绪度 {result['ready_score']}）",
            data=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"b2a-predict 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/b2a-risk-dashboard", response_model=APIResponse)
async def b2a_risk_dashboard(
    top_n: int = Query(10, ge=1, le=50, description="每个分类返回的 Top N"),
    db: AsyncSession = Depends(get_db),
):
    """v12.1: B→A 转换风险仪表盘（批量扫描所有 B 类预算）

    返回：
    - summary: 总览（总 B 项数 / 可转换 / 黄色风险 / 红色拦截）
    - ready_to_convert: Top N 高就绪度项（建议立即提交转换）
    - at_risk: Top N 高风险项（红色拦截 + 黄色风险）
    - by_center / by_l1: 按中心 / L1 聚合
    """
    try:
        engine = BudgetGrantEngine()
        result = await engine.batch_scan_b2a_risk(db, top_n=top_n)
        s = result["summary"]
        return APIResponse(
            success=True,
            message=(
                f"扫描完成：{s['total_b_items']} 个 B 类预算，"
                f"可转换 {s['ready_count']} / 黄色风险 {s['yellow_risk_count']} / 红色拦截 {s['red_blocked_count']}"
            ),
            data=result,
        )
    except Exception as e:
        logger.error(f"b2a-risk-dashboard 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# v12.1: 阶段 1 — 战略主题→举措→预算 自动拆分
# ══════════════════════════════════════════════════════════════════════════
@router.post("/budget/auto-decompose", response_model=APIResponse)
async def auto_decompose_strategy(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: 阶段 1 — 战略主题自动分解为举措+预算项

    请求体：
    {
        "theme": "战略主题描述（必填）",
        "year": 2026,
        "total_budget": 10000000,
        "strategic_intent_l1": "全渠道商业化" (可选，自动推断)
    }

    返回：分解结果（不写入数据库），前端预览后可调用 /apply-decomposition 落库
    """
    try:
        from engines.budget_planning import BudgetPlanningEngine

        theme = body.get("theme", "").strip()
        if not theme:
            raise HTTPException(status_code=400, detail="theme 不能为空")
        year = int(body.get("year", 0)) or datetime.now().year
        total_budget = float(body.get("total_budget", 0))
        if total_budget <= 0:
            raise HTTPException(status_code=400, detail="total_budget 必须 > 0")
        intent = body.get("strategic_intent_l1")

        engine = BudgetPlanningEngine()
        result = await engine.auto_decompose_strategy(theme, year, total_budget, intent, db)
        return APIResponse(
            success=True,
            message=f"战略主题「{theme}」分解完成：{result['summary']['total_initiatives']}个举措 / {result['summary']['total_budget_items']}个预算项",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"auto-decompose 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/apply-decomposition", response_model=APIResponse)
async def apply_decomposition(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: 把 /auto-decompose 的结果真正写入数据库（举措+预算项）"""
    try:
        from engines.budget_planning import BudgetPlanningEngine

        decomposition = body.get("decomposition")
        if not decomposition:
            raise HTTPException(status_code=400, detail="decomposition 不能为空")
        year = body.get("year")

        engine = BudgetPlanningEngine()
        result = await engine.create_budget_from_decomposition(decomposition, db, year)
        await db.commit()

        return APIResponse(
            success=True,
            message=f"已生成 {result['created_initiatives']} 个举措 + {result['created_budget_items']} 个预算项",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"apply-decomposition 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/items/{budget_id}/b2a-convert", response_model=APIResponse)
async def b2a_convert(
    budget_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        milestone_evidence = body.get("milestone_evidence", "")
        if not milestone_evidence:
            raise HTTPException(status_code=400, detail="milestone_evidence is required")

        item = await grant_engine.b2a_convert(budget_id, milestone_evidence, db)
        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="B→A conversion complete", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/items/{budget_id}/approve", response_model=APIResponse)
async def approve_budget_item(
    budget_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await db.get(BudgetItem, budget_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Budget item {budget_id} not found")

        role = body.get("role", "")
        if role == "管委会":
            item.status = "已授予"
        else:
            item.status = "审批中"

        await db.flush()

        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="Budget approved", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/items/{budget_id}/reject", response_model=APIResponse)
async def reject_budget_item(
    budget_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await db.get(BudgetItem, budget_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Budget item {budget_id} not found")

        item.status = "已驳回"
        await db.flush()

        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="Budget rejected", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/cycle/start", response_model=APIResponse)
async def start_budget_cycle(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        year = body.get("year")
        initiated_by = body.get("initiated_by", "财经中心预算管理部")
        if not year:
            raise HTTPException(status_code=400, detail="year is required")

        prev_year = year - 1
        stmt = select(AlertRecord).where(
            and_(
                AlertRecord.alert_status.in_(["开放", "响应中", "待闭环确认", "已升级"]),
            )
        )
        result = await db.execute(stmt)
        open_alerts = result.scalars().all()

        for alert in open_alerts:
            alert.alert_status = "待解决"

        await db.flush()

        pending_items = []
        for alert in open_alerts:
            pending_items.append({
                "item_id": f"PI-ALERT-{alert.alert_id}",
                "source": "未闭环预警",
                "description": alert.description or "",
                "responsible": alert.responsible_person or "",
                "status": "待解决",
            })

        try:
            await notification_engine.push(
                {"type": "新循环启动", "description": f"{year}年度预算循环已启动", "notification_targets": ["财经中心", "运营中心", "人力中心"]},
                ["in_app", "websocket"],
                db,
            )
        except Exception:
            pass

        cycle_info = {
            "year": year,
            "initiated_by": initiated_by,
            "status": "已启动",
            "pending_alerts_carried_over": len(open_alerts),
            "pending_items": pending_items,
            "notifications_sent": True,
        }
        return APIResponse(success=True, message="Budget cycle started", data=cycle_info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/cycle/pending-items", response_model=APIResponse)
async def get_cycle_pending_items(
    year: int = Query(..., description="年度"),
    db: AsyncSession = Depends(get_db),
):
    try:
        prev_year = year - 1

        stmt_alert = select(AlertRecord).where(
            AlertRecord.alert_status.in_(["开放", "响应中", "待闭环确认", "已升级", "待解决"])
        )
        result_alert = await db.execute(stmt_alert)
        unclosed_alerts = result_alert.scalars().all()

        alert_data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in unclosed_alerts]

        data = {
            "year": year,
            "prev_year": prev_year,
            "unclosed_alerts": alert_data,
            "incomplete_pdca_actions": [],
        }
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/items/{budget_id}/release", response_model=APIResponse)
async def release_budget(
    budget_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        amount = body.get("amount")
        reason = body.get("reason", "")
        if amount is None:
            raise HTTPException(status_code=400, detail="amount is required")

        item = await grant_engine.release_budget(budget_id, float(amount), reason, db)
        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="Budget released", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/quadrants", response_model=APIResponse)
async def get_quadrant_summary(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(BudgetItem).where(BudgetItem.status.in_(["已授予", "执行中"]))
        result = await db.execute(stmt)
        items = result.scalars().all()

        quadrant_data = {"发展": [], "收缩": [], "稳定": [], "探索": []}
        for item in items:
            quadrant_data[item.quadrant].append(item)

        summary = {}
        for quadrant, q_items in quadrant_data.items():
            total_annual = sum(float(i.annual_amount or 0) for i in q_items)
            total_used = sum(float(i.used_amount or 0) for i in q_items)
            total_available = sum(float(i.available_amount or 0) for i in q_items)
            summary[quadrant] = {
                "item_count": len(q_items),
                "total_annual": total_annual,
                "total_used": total_used,
                "total_available": total_available,
                "execution_rate": round(total_used / total_annual * 100, 2) if total_annual > 0 else 0,
            }

        return APIResponse(success=True, data=summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/adjustments", response_model=APIResponse)
async def request_budget_adjustment(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        adjustment_type = body.get("adjustment_type")
        if adjustment_type == "transfer":
            from_id = body.get("from_budget_id")
            to_id = body.get("to_budget_id")
            amount = body.get("amount")
            if not all([from_id, to_id, amount]):
                raise HTTPException(status_code=400, detail="from_budget_id, to_budget_id, amount are required")
            result = await adjustment_engine.request_transfer(from_id, to_id, float(amount), db)
        elif adjustment_type in ("increase", "decrease"):
            budget_id = body.get("budget_id")
            amount = body.get("amount")
            reason = body.get("reason", "")
            if not all([budget_id, amount]):
                raise HTTPException(status_code=400, detail="budget_id and amount are required")
            result = await adjustment_engine.request_adjustment(
                budget_id,
                adjustment_type,
                float(amount),
                reason,
                db,
                formula_text=body.get("formula_text"),
                parameter_json=body.get("parameter_json"),
                source_json=body.get("source_json"),
                module_code=body.get("module_code"),
                risk_text=body.get("risk_text"),
                created_by=body.get("created_by"),
            )
        else:
            raise HTTPException(status_code=400, detail="adjustment_type must be 'transfer', 'increase', or 'decrease'")

        return APIResponse(success=True, message="Adjustment request submitted", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/pk/sessions", response_model=APIResponse)
async def create_pk_session(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    year = body.get("year")
    round_num = body.get("round", 1)
    initiated_by = body.get("initiated_by", "财经中心")
    if not year:
        raise HTTPException(status_code=400, detail="year is required")
    try:
        session = {
            "session_id": f"PK-{year}-{round_num}",
            "year": year,
            "round": round_num,
            "initiated_by": initiated_by,
            "status": "进行中",
            "submissions": [],
            "reviews": [],
        }
        _PK_SESSIONS.append(session)
        return APIResponse(success=True, message="PK session created", data=session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/pk/sessions/{session_id}/submit", response_model=APIResponse)
async def submit_pk_budget(
    session_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    org_id = body.get("org_id")
    items = body.get("items", [])
    justification = body.get("justification", "")
    if not org_id:
        raise HTTPException(status_code=400, detail="org_id is required")
    try:
        session = next((s for s in _PK_SESSIONS if s["session_id"] == session_id), None)
        if session is None:
            raise HTTPException(status_code=404, detail=f"PK session {session_id} not found")
        submission = {
            "session_id": session_id,
            "org_id": org_id,
            "items": items,
            "justification": justification,
            "status": "已提交",
        }
        session["submissions"].append(submission)
        return APIResponse(success=True, message="PK budget submitted", data=submission)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/pk/sessions/{session_id}/review", response_model=APIResponse)
async def review_pk_budget(
    session_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    reviewer = body.get("reviewer")
    adjustments = body.get("adjustments", [])
    comments = body.get("comments", "")
    if not reviewer:
        raise HTTPException(status_code=400, detail="reviewer is required")
    try:
        session = next((s for s in _PK_SESSIONS if s["session_id"] == session_id), None)
        if session is None:
            raise HTTPException(status_code=404, detail=f"PK session {session_id} not found")
        review = {
            "session_id": session_id,
            "reviewer": reviewer,
            "adjustments": adjustments,
            "comments": comments,
            "status": "已审核",
        }
        session["reviews"].append(review)
        return APIResponse(success=True, message="PK budget reviewed", data=review)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/pk/sessions/{session_id}/finalize", response_model=APIResponse)
async def finalize_pk_session(
    session_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    approved_by = body.get("approved_by")
    final_items = body.get("final_items", [])
    if not approved_by:
        raise HTTPException(status_code=400, detail="approved_by is required")
    try:
        session = next((s for s in _PK_SESSIONS if s["session_id"] == session_id), None)
        if session is None:
            raise HTTPException(status_code=404, detail=f"PK session {session_id} not found")
        session["status"] = "已锁定"
        result = {
            "session_id": session_id,
            "approved_by": approved_by,
            "final_items": final_items,
            "status": "已锁定",
        }
        return APIResponse(success=True, message="PK session finalized", data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/pk/sessions", response_model=APIResponse)
async def list_pk_sessions(
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        sessions = _PK_SESSIONS
        if year:
            sessions = [s for s in sessions if s.get("year") == year]
        return APIResponse(success=True, data=sessions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


_BUDGET_TEMPLATES = [
    {
        "template_id": "TPL-STD-001",
        "name": "标准预算模板",
        "description": "适用于常规业务部门的预算编制模板",
        "subject_system": "L1-L2-L3三级科目体系",
        "fill_instructions": "按科目逐级填报，B类预算需附里程碑计划",
        "strategic_intent_options": ["全渠道商业化", "创新研发", "国际化"],
        "quadrant_options": ["发展", "收缩", "稳定", "探索"],
    },
    {
        "template_id": "TPL-PROJ-001",
        "name": "项目化预算模板",
        "description": "适用于项目化管理科目的预算编制模板",
        "subject_system": "L1-L2-L3三级科目体系+项目维度",
        "fill_instructions": "按项目维度填报，需关联战略举措编号",
        "strategic_intent_options": ["全渠道商业化", "创新研发", "国际化"],
        "quadrant_options": ["发展", "探索"],
    },
]

_TEMPLATE_DISTRIBUTIONS: list[dict] = []


@router.get("/budget/templates", response_model=APIResponse)
async def list_budget_templates(
    db: AsyncSession = Depends(get_db),
):
    return APIResponse(success=True, data=_BUDGET_TEMPLATES)


@router.post("/budget/templates/{template_id}/distribute", response_model=APIResponse)
async def distribute_budget_template(
    template_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    year = body.get("year")
    target_orgs = body.get("target_orgs", [])
    deadline = body.get("deadline")
    if not year or not target_orgs or not deadline:
        raise HTTPException(status_code=400, detail="year, target_orgs and deadline are required")

    template = next((t for t in _BUDGET_TEMPLATES if t["template_id"] == template_id), None)
    if template is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    distribution = {
        "distribution_id": f"DIST-{year}-{template_id}",
        "template_id": template_id,
        "year": year,
        "target_orgs": target_orgs,
        "deadline": deadline,
        "status": "已下发",
        "org_status": {org: "待填报" for org in target_orgs},
    }
    _TEMPLATE_DISTRIBUTIONS.append(distribution)
    return APIResponse(success=True, message="Template distributed", data=distribution)


@router.get("/budget/templates/distribution-status", response_model=APIResponse)
async def get_template_distribution_status(
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    distributions = _TEMPLATE_DISTRIBUTIONS
    if year:
        distributions = [d for d in distributions if d.get("year") == year]
    return APIResponse(success=True, data=distributions)


@router.get("/budget/b2a-report", response_model=APIResponse)
async def get_b2a_report(
    period: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await grant_engine.generate_b2a_report(db, period)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/milestones/{budget_id}", response_model=APIResponse)
async def get_milestones(
    budget_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get milestones for a budget item."""
    try:
        from models.milestone import Milestone
        stmt = select(Milestone).where(Milestone.budget_id == budget_id).order_by(Milestone.quarter)
        result = await db.execute(stmt)
        milestones = result.scalars().all()

        data = [
            {
                "milestone_id": ms.milestone_id,
                "budget_id": ms.budget_id,
                "name": ms.name,
                "planned_date": ms.planned_date.isoformat() if ms.planned_date else None,
                "actual_date": ms.actual_date.isoformat() if ms.actual_date else None,
                "status": ms.status,
                "evidence": ms.evidence,
                "quarter": ms.quarter,
                "amount_release": float(ms.amount_release) if ms.amount_release else None,
                "created_at": ms.created_at.isoformat() if ms.created_at else None,
                "updated_at": ms.updated_at.isoformat() if ms.updated_at else None,
            }
            for ms in milestones
        ]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/budget/milestones/{milestone_id}/complete", response_model=APIResponse)
async def complete_milestone(
    milestone_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Mark milestone as completed with evidence."""
    try:
        from models.milestone import Milestone
        milestone = await db.get(Milestone, milestone_id)
        if milestone is None:
            raise HTTPException(status_code=404, detail=f"Milestone {milestone_id} not found")

        evidence = body.get("evidence", "")
        if not evidence:
            raise HTTPException(status_code=400, detail="evidence is required")

        milestone.status = "completed"
        milestone.evidence = evidence
        milestone.actual_date = datetime.now()

        # Release amount to budget item upon milestone completion
        if milestone.amount_release:
            budget_item = await db.get(BudgetItem, milestone.budget_id)
            if budget_item:
                release = Decimal(str(milestone.amount_release))
                budget_item.available_amount = Decimal(str(budget_item.available_amount)) + release
                budget_item.granted_amount = Decimal(str(budget_item.granted_amount)) + release
                budget_item.frozen_amount = Decimal(str(budget_item.frozen_amount)) + release

        await db.flush()

        data = {
            "milestone_id": milestone.milestone_id,
            "budget_id": milestone.budget_id,
            "name": milestone.name,
            "status": milestone.status,
            "evidence": milestone.evidence,
            "actual_date": milestone.actual_date.isoformat() if milestone.actual_date else None,
            "quarter": milestone.quarter,
            "amount_release": float(milestone.amount_release) if milestone.amount_release else None,
        }
        return APIResponse(success=True, message="Milestone completed", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 调拨管理端点 ──────────────────────────────────────────


@router.post("/budgets/transfers", response_model=APIResponse)
async def create_transfer(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """创建调拨请求"""
    from_budget_id = body.get("from_budget_id")
    to_budget_id = body.get("to_budget_id")
    amount = body.get("amount")
    if not all([from_budget_id, to_budget_id, amount]):
        raise HTTPException(status_code=400, detail="from_budget_id, to_budget_id, amount are required")
    try:
        result = await adjustment_engine.request_transfer(from_budget_id, to_budget_id, float(amount), db)
        return APIResponse(success=True, message="调拨请求已创建", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budgets/transfers", response_model=APIResponse)
async def list_transfers(
    status: Optional[str] = Query(None, description="调拨状态筛选"),
    db: AsyncSession = Depends(get_db),
):
    """查询调拨列表"""
    try:
        stmt = select(BudgetTransferRequest).order_by(BudgetTransferRequest.created_at.desc())
        if status:
            stmt = stmt.where(BudgetTransferRequest.status == status)
        result = await db.execute(stmt)
        transfers = result.scalars().all()
        data = [
            {
                "transfer_id": t.transfer_id,
                "from_budget_id": t.from_budget_id,
                "to_budget_id": t.to_budget_id,
                "from_quadrant": t.from_quadrant,
                "to_quadrant": t.to_quadrant,
                "amount": float(t.amount) if t.amount else 0,
                "same_quadrant": t.same_quadrant,
                "approval_required": t.approval_required,
                "status": t.status,
                "requested_by": t.requested_by,
                "approved_by": t.approved_by,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "executed_at": t.executed_at.isoformat() if t.executed_at else None,
            }
            for t in transfers
        ]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budgets/transfers/{transfer_id}/approve", response_model=APIResponse)
async def approve_transfer(
    transfer_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """审批调拨"""
    try:
        transfer = await db.get(BudgetTransferRequest, transfer_id)
        if transfer is None:
            raise HTTPException(status_code=404, detail=f"Transfer {transfer_id} not found")
        if transfer.status != "待审批":
            raise HTTPException(status_code=400, detail=f"Transfer {transfer_id} status is '{transfer.status}', cannot approve")

        transfer.status = "已审批"
        transfer.approved_by = body.get("approved_by", "")
        await db.flush()

        data = {
            "transfer_id": transfer.transfer_id,
            "status": transfer.status,
            "approved_by": transfer.approved_by,
        }
        return APIResponse(success=True, message="调拨已审批", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budgets/transfers/{transfer_id}/execute", response_model=APIResponse)
async def execute_transfer(
    transfer_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """执行调拨"""
    approved_by = body.get("approved_by", "")
    try:
        result = await adjustment_engine.execute_transfer(transfer_id, approved_by, db)
        return APIResponse(success=True, message="调拨已执行", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === v4.1 新增：预算健康度 + 调拨模拟 ===

@router.get("/budget/health-score", response_model=APIResponse)
async def get_health_score(
    period: str = Query(..., description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    """预算健康度评分（0-100，5 维度加权）

    - execution (25%): 执行率偏离时间进度
    - alignment (25%): A 类执行率 + 战略覆盖度
    - risk (20%): 超支项数 + 敞口金额
    - transfer (15%): 调拨频次 + 方向合理性
    - data (15%): 必填字段完整率
    """
    try:
        score = await planning_engine.calculate_budget_health_score(period, db)
        return APIResponse(success=True, data=score, message="预算健康度计算完成")
    except Exception as e:
        logger.error(f"health-score 计算失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/budget/simulate-transfer", response_model=APIResponse)
async def simulate_transfer(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """模拟预算调拨的连锁影响

    body: {from_id, to_id, amount}
    返回：源/目标执行率变化 + 触发预警预测 + 方向合理性
    """
    try:
        result = await planning_engine.simulate_transfer_impact(
            body.get("from_id", ""),
            body.get("to_id", ""),
            float(body.get("amount", 0)),
            db,
        )
        if "error" in result and "from_id" not in result:
            raise HTTPException(status_code=400, detail=result.get("error", "参数错误"))
        return APIResponse(success=True, data=result, message="调拨影响模拟完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"simulate-transfer 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Module E.2：预算认知深度（5 层根因下钻 + 主动建议 + 业务联动） ===


@router.get("/budget/cognitive/root-cause/{budget_id}", response_model=APIResponse)
async def get_budget_root_cause(
    budget_id: str,
    db: AsyncSession = Depends(get_db),
):
    """预算项 5 层根因下钻分析。

    5 层结构：
    - L1 现象：执行率与状态（超支/偏高/偏低/正常）
    - L2 量化：与同 L1 科目横向对比
    - L3 结构：A/B 类别 + 象限
    - L4 时间：纵向趋势（vs 上期）
    - L5 关联：同类问题项目的解决方案参考
    """
    try:
        item = await db.get(BudgetItem, budget_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Budget item {budget_id} not found")

        # 拉同 L1 科目所有项做横向对比
        stmt = select(BudgetItem)
        result = await db.execute(stmt)
        all_items = result.scalars().all()

        drill = drill_down_root_cause(item, list(all_items))
        return APIResponse(success=True, data=drill.to_dict(), message="根因下钻完成")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"budget root-cause 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/cognitive/suggestions", response_model=APIResponse)
async def get_budget_proactive_suggestions(
    period: Optional[str] = Query(None, description="评估期间 YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    """基于预算执行数据生成主动建议。

    触发规则：
    - 超支预警（critical）
    - 执行滞后提醒（attention）
    - 跨象限调拨建议
    - A/B 比例结构建议
    - 季度规划窗口提醒
    """
    try:
        stmt = select(BudgetItem).where(BudgetItem.status.in_(["已授予", "执行中", "active"]))
        result = await db.execute(stmt)
        items = result.scalars().all()

        period_label = period or "本月"
        suggestions = generate_proactive_suggestions(list(items), period=period_label)
        return APIResponse(
            success=True,
            data={
                "period": period_label,
                "total": len(suggestions),
                "critical_count": sum(1 for s in suggestions if s.priority == "critical"),
                "attention_count": sum(1 for s in suggestions if s.priority == "attention"),
                "info_count": sum(1 for s in suggestions if s.priority == "info"),
                "suggestions": [s.to_dict() for s in suggestions],
            },
            message="主动建议生成完成",
        )
    except Exception as e:
        logger.error(f"budget suggestions 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/cognitive/business-linkage", response_model=APIResponse)
async def get_budget_business_linkage(
    db: AsyncSession = Depends(get_db),
):
    """预算执行与业务活动联动分析。

    联动指标：
    - 预算执行率 vs 报销笔数
    - 高频低额 vs 低频高额风险对
    - 执行率-报销集中度匹配度
    """
    try:
        from models.expense import ExpenseReport

        # 拉所有预算项
        stmt_b = select(BudgetItem)
        result_b = await db.execute(stmt_b)
        items = result_b.scalars().all()

        # 拉所有报销（用 budget_id 关联）
        stmt_e = select(ExpenseReport)
        result_e = await db.execute(stmt_e)
        expenses = result_e.scalars().all()

        linkage = compute_business_linkage(list(items), list(expenses))
        return APIResponse(success=True, data=linkage, message="业务联动分析完成")
    except Exception as e:
        logger.error(f"budget business-linkage 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
