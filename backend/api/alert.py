from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse, APIPageResponse
from models.alert import AlertRecord, AlertClosure
from engines.alert_monitor import AlertMonitorEngine
from api.deps import get_current_user, get_center_filter_for_user
from models.user import User
from models.budget import BudgetItem
from engines.alert_ai import AlertAIEngine

router = APIRouter()

alert_engine = AlertMonitorEngine()
alert_ai_engine = AlertAIEngine()


# v11.0: 预警类型 → 本体规则 ID 映射
# 让前端能展示"依据 SR-xxx"标签
ALERT_TYPE_RULE_MAP = {
    "月度执行进度": ["SR-001", "SR-002", "SR-003"],
    "季度滚动预测": ["SR-004", "SR-005", "SR-006"],
    "B类膨胀预警": ["SR-007"],
    "实时核销预警": ["SR-101"],
    "实时冻结预警": ["SR-102"],
    "实时释放预警": ["SR-103"],
    "实时授予预警": ["SR-104"],
    "实时事件预警": ["SR-105"],
    "预测超支": ["SR-201"],
    "资源闲置": ["SR-202"],
    "战略维度": ["SR-301"],
    "里程碑": ["SR-501"],
    "L1专项": ["SR-601"],
}


def _attach_rule_ids(rows: list[dict]) -> list[dict]:
    """v11.0: 给 alert 响应附加 rule_ids 字段"""
    for row in rows:
        atype = row.get("alert_type")
        if atype and atype in ALERT_TYPE_RULE_MAP:
            row["rule_ids"] = ALERT_TYPE_RULE_MAP[atype]
        else:
            row["rule_ids"] = []
    return rows


@router.get("/alerts/stats", response_model=APIResponse)
async def get_alert_stats(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(AlertRecord)
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        by_level = {"蓝色": 0, "黄色": 0, "橙色": 0, "红色": 0}
        by_status = {"开放": 0, "响应中": 0, "待闭环确认": 0, "已闭环": 0, "已升级": 0}

        for a in alerts:
            by_level[a.alert_level] = by_level.get(a.alert_level, 0) + 1
            by_status[a.alert_status] = by_status.get(a.alert_status, 0) + 1

        stats = {
            "total": len(alerts),
            "by_level": by_level,
            "by_status": by_status,
        }

        return APIResponse(success=True, data=stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/dashboard", response_model=APIResponse)
async def get_alert_dashboard(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(AlertRecord)
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        by_level = {"蓝色": 0, "黄色": 0, "橙色": 0, "红色": 0}
        by_status = {"开放": 0, "响应中": 0, "待闭环确认": 0, "已闭环": 0, "已升级": 0}
        by_type = {}

        for a in alerts:
            by_level[a.alert_level] = by_level.get(a.alert_level, 0) + 1
            by_status[a.alert_status] = by_status.get(a.alert_status, 0) + 1
            by_type[a.alert_type] = by_type.get(a.alert_type, 0) + 1

        high_priority_open = sum(
            1 for a in alerts
            if a.alert_level in ("红色", "橙色") and a.alert_status in ("开放", "响应中")
        )

        dashboard = {
            "total": len(alerts),
            "by_level": by_level,
            "by_status": by_status,
            "by_type": by_type,
            "high_priority_open": high_priority_open,
        }

        return APIResponse(success=True, data=dashboard)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/scan", response_model=APIResponse)
async def trigger_daily_scan(
    db: AsyncSession = Depends(get_db),
):
    try:
        alerts = await alert_engine.daily_scan(db)
        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in alerts]
        _attach_rule_ids(data)
        return APIResponse(success=True, message=f"Daily scan complete: {len(alerts)} alerts generated", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", response_model=APIPageResponse)
async def list_alerts(
    level: Optional[str] = Query(None, description="预警级别: 蓝色/黄色/橙色/红色"),
    status: Optional[str] = Query(None, description="预警状态"),
    l1_code: Optional[str] = Query(None),
    budget_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_center_filter = get_center_filter_for_user(current_user)
    try:
        conditions = []
        # Apply center-based data permission via join with BudgetItem
        if user_center_filter:
            stmt = select(AlertRecord).join(
                BudgetItem, AlertRecord.budget_id == BudgetItem.budget_id, isouter=True
            ).where(BudgetItem.center_id == user_center_filter)
        else:
            stmt = select(AlertRecord)

        if level:
            conditions.append(AlertRecord.alert_level == level)
        if status:
            conditions.append(AlertRecord.alert_status == status)
        if l1_code:
            conditions.append(AlertRecord.l1_code == l1_code)
        if budget_id:
            conditions.append(AlertRecord.budget_id == budget_id)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await db.execute(stmt)
        items = result.scalars().all()

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in page_items]
        _attach_rule_ids(data)

        return APIPageResponse(
            success=True,
            total=total,
            page=page,
            page_size=page_size,
            data=data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Static path must be registered before /alerts/{alert_id}, otherwise
# GET /alerts/fatigue is treated as alert_id="fatigue" and 404s.
@router.get("/alerts/fatigue", response_model=APIResponse)
async def fatigue(
    months: int = Query(3, description="近 N 月"),
    db: AsyncSession = Depends(get_db),
):
    """预警疲劳度分析

    返回 5 维度指标 + 合并/降级/取消建议
    """
    try:
        result = await alert_engine.analyze_alert_fatigue(db, months)
        return APIResponse(success=True, message="疲劳度分析完成", data=result)
    except Exception as e:
        logger.error(f"fatigue 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/{alert_id}", response_model=APIResponse)
async def get_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        alert = await db.get(AlertRecord, alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

        data = {c: getattr(alert, c) for c in alert.__table__.columns.keys()}
        _attach_rule_ids([data])

        stmt = select(AlertClosure).where(AlertClosure.alert_id == alert_id)
        result = await db.execute(stmt)
        closures = result.scalars().all()
        data["closures"] = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in closures]

        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/respond", response_model=APIResponse)
async def respond_alert(
    alert_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        response = body.get("response", "")
        responder = body.get("responder", "")
        if not response:
            raise HTTPException(status_code=400, detail="response is required")
        if not responder:
            raise HTTPException(status_code=400, detail="responder is required")
        if len(response.strip()) < 20:
            raise HTTPException(status_code=400, detail="业务整改方案内容不得少于20字(HR-013)")

        closure = await alert_engine.respond_alert(alert_id, response, responder, db)
        data = {c: getattr(closure, c) for c in closure.__table__.columns.keys()}
        return APIResponse(success=True, message="Alert responded", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/confirm-closure", response_model=APIResponse)
async def confirm_closure(
    alert_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        bp_confirmation = body.get("bp_confirmation", "")
        bp_confirmer = body.get("bp_confirmer", "")
        if not bp_confirmation:
            raise HTTPException(status_code=400, detail="bp_confirmation is required")
        if not bp_confirmer:
            raise HTTPException(status_code=400, detail="bp_confirmer is required")

        stmt = select(AlertClosure).where(AlertClosure.alert_id == alert_id)
        result = await db.execute(stmt)
        closure = result.scalars().first()
        if closure is None:
            raise HTTPException(status_code=404, detail=f"No closure record found for alert {alert_id}")

        if closure.business_responder and bp_confirmer == closure.business_responder:
            raise HTTPException(status_code=400, detail="财经BP确认人不能与业务响应人为同一人(HR-013)")

        updated = await alert_engine.confirm_closure(closure.closure_id, bp_confirmation, bp_confirmer, db)
        data = {c: getattr(updated, c) for c in updated.__table__.columns.keys()}
        return APIResponse(success=True, message="Closure confirmed", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/escalate", response_model=APIResponse)
async def escalate_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        escalation = await alert_engine.escalate_alert(alert_id, db)
        data = {c: getattr(escalation, c) for c in escalation.__table__.columns.keys()}
        return APIResponse(success=True, message="Alert escalated", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/cascade-risk", response_model=APIResponse)
async def cascade_risk_assess(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """级联风险评估：当L1科目触发红色预警时，评估对L2科目和战略意图的影响"""
    try:
        l1_code = body.get("l1_code")
        if not l1_code:
            raise HTTPException(status_code=400, detail="l1_code is required")
        data = await alert_engine.cascade_risk_assess(l1_code, db)
        return APIResponse(success=True, message="Cascade risk assessment complete", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === v12.0: 超时升级扫描（文档 §4.4.7） ===

@router.post("/alerts/scan-timeouts", response_model=APIResponse)
async def scan_alert_timeouts(
    db: AsyncSession = Depends(get_db),
):
    """扫描超时未响应的预警，按四色分级触发升级通知（蓝色3日/黄色2日/橙色1日/红色1小时）"""
    try:
        from engines.notification_engine import NotificationEngine
        notif_engine = NotificationEngine()
        escalations = await notif_engine.scan_timeouts(db)
        return APIResponse(
            success=True,
            message=f"扫描完成：发现 {len(escalations)} 条超时预警需升级",
            data={"escalations": escalations, "count": len(escalations)},
        )
    except Exception as e:
        logger.error(f"scan-timeouts 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/pattern-analysis", response_model=APIResponse)
async def alert_pattern_analysis(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """预警模式分析：识别系统性问题和反复出现的风险"""
    try:
        l1_code = body.get("l1_code")
        lookback_months = body.get("lookback_months", 6)
        data = await alert_engine.alert_pattern_analysis(l1_code, db, lookback_months)
        return APIResponse(success=True, message="Alert pattern analysis complete", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === v4.1 新增：5 层根因下钻 + 疲劳度分析 ===

@router.get("/alerts/{alert_id}/drill-down", response_model=APIResponse)
async def drill_down(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    """预警 5 层根因下钻

    返回 L1 → L2 → Center → Trend → Peer 5 层节点 + AI 根因总结
    """
    try:
        result = await alert_engine.drill_down_alert(alert_id, db)
        if "error" in result and "l1_node" not in result:
            raise HTTPException(status_code=404, detail=result.get("error", "预警不存在"))
        return APIResponse(success=True, message="下钻分析完成", data=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"drill-down 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# v12.1: 阶段 5 — 实时预警 AI 智能引擎（5 大能力）
# ══════════════════════════════════════════════════════════════════════════

@router.get("/alerts/ai/fatigue-detect", response_model=APIResponse)
async def ai_fatigue_detect(
    days: int = Query(7, ge=1, le=90),
    threshold: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 预警疲劳检测"""
    try:
        result = await alert_ai_engine.detect_fatigue(days, threshold, db)
        return APIResponse(
            success=True,
            message=f"疲劳检测完成：{result['fatigue_rule_count']} 个疲劳规则（{days} 天）",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/ai/cluster", response_model=APIResponse)
async def ai_alert_cluster(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 告警聚类（系统性风险识别）"""
    try:
        result = await alert_ai_engine.cluster_alerts(days, db)
        return APIResponse(
            success=True,
            message=f"聚类完成：{result['cluster_count']} 个聚类，{result['systemic_risk_count']} 个系统性风险",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/ai/{alert_id}/smart-escalation", response_model=APIResponse)
async def ai_smart_escalation(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 智能升级路径"""
    try:
        result = await alert_ai_engine.smart_escalation(alert_id, db)
        return APIResponse(
            success=True,
            message=f"智能升级完成：{len(result['escalation_chain'])} 级路径",
            data=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/ai/{alert_id}/priority", response_model=APIResponse)
async def ai_priority(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 告警优先级打分（5 维加权）"""
    try:
        result = await alert_ai_engine.priority_score(alert_id, db)
        return APIResponse(
            success=True,
            message=f"优先级：{result['priority']}（{result['priority_score']}）",
            data=result,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/ai/dedup", response_model=APIResponse)
async def ai_dedup(
    window_hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 重复告警去重"""
    try:
        result = await alert_ai_engine.dedup(window_hours, db)
        return APIResponse(
            success=True,
            message=f"去重扫描完成：{result['deduplicated_count']} 条可去重（{result['dedup_groups']} 组）",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
