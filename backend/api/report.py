from typing import Optional, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse, APIPageResponse
from models.analysis import MonthlyReport
from models.caliber import CaliberMapping, CaliberDifference
from engines.report_engine import ReportEngine
from engines.report_ai import ReportAIEngine
from engines.caliber_engine import CaliberEngine
from services.report_llm_drafter import ReportLLMDrafter
from services.scheduler import (
    get_cutoff_status,
    auto_generate_at_cutoff,
    CUTOFF_TYPES,
)


router = APIRouter()

report_engine = ReportEngine()
report_ai_engine = ReportAIEngine()
caliber_engine = CaliberEngine()
report_drafter = ReportLLMDrafter()

_CHALLENGES_STORE: list[Dict] = []
_challenge_counter = 0


# v12.0: 5/8/10/12 截点状态查询 + 手动触发
@router.get("/reports/cutoff-status", response_model=APIResponse)
async def get_reports_cutoff_status(period: Optional[str] = Query(None)):
    """获取当月 5/8/10/12 截点的出具状态（D2 决策：Asia/Shanghai 02:00 自动触发）"""
    try:
        result = get_cutoff_status(period)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/trigger-cutoff", response_model=APIResponse)
async def trigger_cutoff_now(
    day: int = Query(..., ge=1, le=31),
    period: Optional[str] = Query(None),
):
    """手动触发某个截点的报告出具（用于测试和补出）"""
    if day not in CUTOFF_TYPES:
        raise HTTPException(status_code=400, detail=f"未定义截点 {day}（仅支持 5/8/10/12）")
    result = await auto_generate_at_cutoff(day, period)
    return APIResponse(success=result.get("success", False), data=result)


@router.get("/reports", response_model=APIPageResponse)
async def list_reports(
    type: Optional[str] = Query(None, description="报告类型"),
    period: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if type:
            conditions.append(MonthlyReport.report_type == type)
        if period:
            conditions.append(MonthlyReport.period == period)

        stmt = select(MonthlyReport).where(*conditions) if conditions else select(MonthlyReport)
        result = await db.execute(stmt)
        items = result.scalars().all()

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in page_items]

        return APIPageResponse(
            success=True,
            total=total,
            page=page,
            page_size=page_size,
            data=data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/caliber-comparison", response_model=APIResponse)
async def caliber_comparison(
    period: str = Query(..., description="期间 YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    """双口径对比视图：返回管理口径和财务口径并排对比"""
    try:
        from models.budget import BudgetItem
        stmt = select(BudgetItem).where(
            BudgetItem.status.in_(["已授予", "执行中", "已核销"]),
        )
        result = await db.execute(stmt)
        budget_items = result.scalars().all()

        by_l1 = {}
        for item in budget_items:
            l1 = item.l1_code
            if l1 not in by_l1:
                by_l1[l1] = 0
            by_l1[l1] += float(item.annual_amount or 0)

        financial_data = {"by_l1": by_l1, "budget_items": budget_items}
        management_view = await caliber_engine.convert_to_management_view(financial_data, period, db)
        financial_view = await caliber_engine.convert_to_financial_view(financial_data, period, db)
        reconciliation = await caliber_engine.reconcile_calibers(period, db)

        return APIResponse(success=True, data={
            "period": period,
            "financial_view": financial_view,
            "management_view": management_view,
            "differences": reconciliation.get("differences", []),
            "total_financial": reconciliation.get("total_financial", 0),
            "total_management": reconciliation.get("total_management", 0),
            "total_difference": reconciliation.get("total_difference", 0),
            "reconciliation_note": reconciliation.get("reconciliation_note", ""),
            "caliber_note": caliber_engine.generate_caliber_note("comparison"),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/caliber-mappings", response_model=APIResponse)
async def get_caliber_mappings(
    db: AsyncSession = Depends(get_db),
):
    """获取所有口径映射配置"""
    try:
        mappings = await caliber_engine._get_mappings(db)
        data = [
            {
                "mapping_id": m.mapping_id,
                "financial_code": m.financial_code,
                "financial_name": m.financial_name,
                "management_code": m.management_code,
                "management_name": m.management_name,
                "conversion_rule": m.conversion_rule,
                "adjustment_formula": m.adjustment_formula,
                "difference_note": m.difference_note,
                "sort_order": m.sort_order,
            }
            for m in mappings.values()
        ]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}", response_model=APIResponse)
async def get_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        report = await db.get(MonthlyReport, report_id)
        if report is None:
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

        data = {c: getattr(report, c) for c in report.__table__.columns.keys()}
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/monthly-flash", response_model=APIResponse)
async def generate_monthly_flash(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period")
        if not period:
            raise HTTPException(status_code=400, detail="period is required (YYYY-MM)")

        content = await report_engine.generate_monthly_flash(period, db)
        return APIResponse(success=True, message="Monthly flash report generated", data=content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/quarterly", response_model=APIResponse)
async def generate_quarterly_report(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period")
        if not period:
            raise HTTPException(status_code=400, detail="period is required (YYYY-QN)")

        content = await report_engine.generate_quarterly_report(period, db)
        return APIResponse(success=True, message="Quarterly report generated", data=content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/annual-review", response_model=APIResponse)
async def generate_annual_review(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period")
        if not period:
            raise HTTPException(status_code=400, detail="period is required (YYYY)")

        content = await report_engine.generate_annual_review(period, db)
        return APIResponse(success=True, message="Annual review report generated", data=content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/meeting-materials", response_model=APIResponse)
async def generate_meeting_materials(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period")
        if not period:
            raise HTTPException(status_code=400, detail="period is required (YYYY-MM)")

        content = await report_engine.generate_meeting_materials(period, db)
        return APIResponse(success=True, message="Meeting materials generated", data=content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/consistency", response_model=APIResponse)
async def check_data_consistency(
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await report_engine.validate_data_consistency(db)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/challenge", response_model=APIResponse)
async def create_challenge(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    global _challenge_counter
    report_id = body.get("report_id")
    question = body.get("question")
    challenged_by = body.get("challenged_by", "管委会委员")
    if not report_id or not question:
        raise HTTPException(status_code=400, detail="report_id and question are required")
    _challenge_counter += 1
    challenge_id = f"CH-{_challenge_counter:06d}"
    challenge = {
        "challenge_id": challenge_id,
        "report_id": report_id,
        "question": question,
        "challenged_by": challenged_by,
        "status": "待响应",
        "response": None,
        "responded_by": None,
        "created_at": __import__("datetime").datetime.now().isoformat(),
    }
    _CHALLENGES_STORE.append(challenge)
    return APIResponse(success=True, message="Challenge created", data=challenge)


@router.post("/reports/challenge/{challenge_id}/respond", response_model=APIResponse)
async def respond_challenge(
    challenge_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    response_text = body.get("response")
    responded_by = body.get("responded_by", "财经中心")
    if not response_text:
        raise HTTPException(status_code=400, detail="response is required")
    challenge = next((c for c in _CHALLENGES_STORE if c["challenge_id"] == challenge_id), None)
    if challenge is None:
        raise HTTPException(status_code=404, detail=f"Challenge {challenge_id} not found")
    challenge["response"] = response_text
    challenge["responded_by"] = responded_by
    challenge["status"] = "已响应"
    challenge["responded_at"] = __import__("datetime").datetime.now().isoformat()
    return APIResponse(success=True, message="Challenge responded", data=challenge)


@router.get("/reports/challenges", response_model=APIResponse)
async def list_challenges(
    db: AsyncSession = Depends(get_db),
):
    return APIResponse(success=True, data=_CHALLENGES_STORE)


@router.post("/reports/trend-analysis", response_model=APIResponse)
async def generate_trend_analysis(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """生成趋势分析报告：分析过去N个月的执行率趋势"""
    try:
        months = body.get("months", 6)
        l1_code = body.get("l1_code")
        data = await report_engine.generate_trend_analysis(l1_code, months, db)
        return APIResponse(success=True, message="Trend analysis report generated", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/risk-assessment", response_model=APIResponse)
async def generate_risk_assessment(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """生成风险评估报告：包含风险矩阵和风险评估"""
    try:
        period = body.get("period")
        if not period:
            raise HTTPException(status_code=400, detail="period is required (YYYY-MM)")
        data = await report_engine.generate_risk_assessment(period, db)
        return APIResponse(success=True, message="Risk assessment report generated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/special", response_model=APIResponse)
async def generate_special_report(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """生成专项报告：针对特定L1科目或战略意图的深度分析"""
    try:
        report_type = body.get("report_type")
        target_code = body.get("target_code")
        period = body.get("period")
        if not report_type or not target_code or not period:
            raise HTTPException(status_code=400, detail="report_type, target_code, and period are required")
        if report_type not in ("L1科目专项", "战略意图专项"):
            raise HTTPException(status_code=400, detail="report_type must be 'L1科目专项' or '战略意图专项'")
        data = await report_engine.generate_special_report(report_type, target_code, period, db)
        return APIResponse(success=True, message="Special report generated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────── v7.0 新增：LLM 智能起草 + 9 卡联动 ──────


@router.post("/reports/draft", response_model=APIResponse)
async def draft_report_with_diagnosis(
    body: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
):
    """LLM 智能起草报告（联动 9 诊断卡 + 主动建议）"""
    try:
        period = body.get("period", "2024-06")
        report_type = body.get("report_type", "monthly")
        diagnosis_cards = body.get("diagnosis_cards", [])
        proactive_insights = body.get("proactive_insights", [])
        budget_summary = body.get("budget_summary")
        alert_summary = body.get("alert_summary")

        draft = await report_drafter.draft_report(
            period=period,
            report_type=report_type,
            diagnosis_cards=diagnosis_cards,
            proactive_insights=proactive_insights,
            budget_summary=budget_summary,
            alert_summary=alert_summary,
        )
        return APIResponse(success=True, message="报告草稿生成成功", data=draft.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/diff", response_model=APIResponse)
async def diff_reports(
    body: dict = Body(default_factory=dict),
):
    """报告版本 diff（对比 v1 vs v2 关键发现）"""
    try:
        v1_findings = body.get("v1_findings", [])
        v2_findings = body.get("v2_findings", [])
        added = [f for f in v2_findings if f not in v1_findings]
        removed = [f for f in v1_findings if f not in v2_findings]
        kept = [f for f in v2_findings if f in v1_findings]
        return APIResponse(
            success=True,
            message=f"v1: {len(v1_findings)} 项 → v2: {len(v2_findings)} 项",
            data={
                "added": added,
                "removed": removed,
                "kept": kept,
                "v1_count": len(v1_findings),
                "v2_count": len(v2_findings),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/link-diagnosis/{period}", response_model=APIResponse)
async def link_diagnosis(
    period: str,
    db: AsyncSession = Depends(get_db),
):
    """联动 9 诊断卡数据（获取当期诊断卡的 judgment/root_cause/action_plan）"""
    try:
        from engines.business_diagnosis import DiagnosisEngine
        engine = DiagnosisEngine()
        report = await engine.generate_diagnosis_report(period, db)
        cards_data = []
        for card in report.get("part2_cards", []):
            cards_data.append({
                "card_type": card.get("card_type"),
                "card_name": card.get("card_name"),
                "signal_light": card.get("signal_light"),
                "light_reason": card.get("light_reason"),
                "action_plan": card.get("action_plan", ""),
                "judgment": card.get("judgment", ""),
            })
        return APIResponse(
            success=True,
            message=f"已联动 {len(cards_data)} 张诊断卡",
            data={"period": period, "cards": cards_data},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# v12.1: 阶段 7 — 报表出具 AI 智能引擎（5 大能力）
# ══════════════════════════════════════════════════════════════════════════

@router.post("/reports/ai/detect-anomalies", response_model=APIResponse)
async def ai_report_anomalies(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 报表异常检测"""
    try:
        period = body.get("period", "")
        if not period:
            raise HTTPException(status_code=400, detail="period 必填")
        result = await report_ai_engine.detect_anomalies(period, db)
        return APIResponse(
            success=True,
            message=f"报表异常检测完成：{result['anomaly_count']} 个异常（{result['anomaly_rate']}%）",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/ai/interpret", response_model=APIResponse)
async def ai_interpret(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 自然语言解读"""
    try:
        center_id = body.get("center_id", "")
        period = body.get("period", "")
        if not center_id or not period:
            raise HTTPException(status_code=400, detail="center_id 和 period 必填")
        result = await report_ai_engine.interpret(center_id, period, db)
        return APIResponse(
            success=True,
            message=f"自然语言解读完成：{period}",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/ai/cross-period-compare", response_model=APIResponse)
async def ai_cross_period_compare(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 跨期对比"""
    try:
        center_id = body.get("center_id", "")
        current_period = body.get("current_period", "")
        previous_period = body.get("previous_period", "")
        if not center_id or not current_period or not previous_period:
            raise HTTPException(status_code=400, detail="center_id/current_period/previous_period 必填")
        result = await report_ai_engine.cross_period_compare(center_id, current_period, previous_period, db)
        return APIResponse(
            success=True,
            message=f"跨期对比完成：{result['trend']}（{result['change_pp']}pp）",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/ai/generate-template", response_model=APIResponse)
async def ai_generate_template(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 报表模板生成"""
    try:
        report_type = body.get("report_type", "月报")
        center_id = body.get("center_id")
        result = await report_ai_engine.generate_template(report_type, center_id, db)
        return APIResponse(
            success=True,
            message=f"模板生成完成：{report_type}",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/ai/health-summary", response_model=APIResponse)
async def ai_health_summary(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 综合健康摘要"""
    try:
        center_id = body.get("center_id")
        result = await report_ai_engine.health_summary(center_id, db)
        return APIResponse(
            success=True,
            message=f"健康摘要完成：{result['overall_health']}（{result['total_score']}）",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
