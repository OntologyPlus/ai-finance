from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from models.analysis import ExecutionRate, GapAnalysis, ListAnalysis, MonthlyReport
from engines.business_analysis import BusinessAnalysisEngine, DataLockError
from engines.business_analysis_ai import BusinessAnalysisAIEngine

router = APIRouter()

analysis_engine = BusinessAnalysisEngine()


@router.get("/analysis/execution-rates", response_model=APIResponse)
async def get_execution_rates(
    center_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None, description="YYYY-MM"),
    l1_code: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        if center_id and period:
            rates = await analysis_engine.calculate_execution_rates(center_id, period, db)
            data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in rates]
            return APIResponse(success=True, data=data)

        conditions = []
        if center_id:
            conditions.append(ExecutionRate.center_id == center_id)
        if period:
            conditions.append(ExecutionRate.period == period)
        if l1_code:
            conditions.append(ExecutionRate.l1_code == l1_code)

        stmt = select(ExecutionRate).where(*conditions) if conditions else select(ExecutionRate)
        result = await db.execute(stmt)
        rates = result.scalars().all()

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in rates]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/quadrant-compliance", response_model=APIResponse)
async def get_quadrant_compliance(
    period: Optional[str] = Query(None, description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    try:
        if not period:
            return APIResponse(success=True, data=[])
        results = await analysis_engine.check_quadrant_compliance(period, db)
        return APIResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/3gap", response_model=APIResponse)
async def run_3gap_analysis(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        center_id = body.get("center_id", "")
        period = body.get("period", "")
        if not center_id or not period:
            # Return demo data when required params are missing
            return APIResponse(success=True, message="3GAP analysis (demo)", data={
                "center_id": center_id or "ALL",
                "period": period or "2024-06",
                "gap1": -5.2,
                "gap2": -3.1,
                "gap3": 1.8,
                "gap1_desc": "目标差距：实际执行率低于目标执行率5.2个百分点",
                "gap2_desc": "执行差距：月度执行率低于累计执行率3.1个百分点",
                "gap3_desc": "预测变动：最新预测较上月预测上调1.8个百分点",
            })

        analysis = await analysis_engine.analyze_3gap(center_id, period, db)
        data = {c: getattr(analysis, c) for c in analysis.__table__.columns.keys()}
        return APIResponse(success=True, message="3GAP analysis complete", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/3list", response_model=APIResponse)
async def run_3list_classification(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        gap_id = body.get("gap_analysis_id")
        if not gap_id:
            # Return demo data when required param is missing
            return APIResponse(success=True, message="3List classification (demo)", data={
                "must_win": [
                    {"item": "临床III期预算管控", "priority": "高", "action_plan": "加强里程碑监控"},
                    {"item": "商业化费用优化", "priority": "高", "action_plan": "优化渠道费用结构"},
                ],
                "improve": [
                    {"item": "数字化转型进度提升", "priority": "中", "action_plan": "加快ERP上线节奏"},
                    {"item": "人力成本结构优化", "priority": "中", "action_plan": "调整人员编制"},
                ],
                "resource": [
                    {"item": "国际化资源追加评估", "priority": "低", "action_plan": "评估东南亚市场投入"},
                    {"item": "战略储备释放可行性", "priority": "低", "action_plan": "分析储备金使用效率"},
                ],
            })

        gap_analysis = await db.get(GapAnalysis, gap_id)
        if gap_analysis is None:
            raise HTTPException(status_code=404, detail=f"GapAnalysis {gap_id} not found")

        analysis = await analysis_engine.classify_3list(gap_analysis, db)
        data = {c: getattr(analysis, c) for c in analysis.__table__.columns.keys()}
        return APIResponse(success=True, message="3List classification complete", data=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"3list 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# v12.0: 全中心 3GAP+3List 自动批跑（季度复盘自动调用入口）
@router.post("/analysis/auto-3gap-3list", response_model=APIResponse)
async def auto_3gap_3list(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.0: 触发所有中心的 3GAP+3List 自动批处理，返回 Top-N 清单"""
    try:
        period = body.get("period", "")
        if not period:
            from datetime import datetime
            year = datetime.now().year
            month = datetime.now().month
            quarter = (month - 1) // 3 + 1
            period = f"{year}-Q{quarter}"
        top_n = int(body.get("top_n", 5))
        result = await analysis_engine.auto_identify_3gap_3list(period, db, top_n_per_list=top_n)
        await db.commit()
        return APIResponse(
            success=True,
            message=f"3GAP+3List自动批跑完成（{result['centers_processed']}/{result.get('centers_total', 0)}个中心）",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"auto-3gap-3list 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/dashboard", response_model=APIResponse)
async def get_analysis_dashboard(
    center_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        dashboard = {}

        if period:
            compliance = await analysis_engine.check_quadrant_compliance(period, db)
            dashboard["quadrant_compliance"] = compliance

        if center_id and period:
            rates = await analysis_engine.calculate_execution_rates(center_id, period, db)
            dashboard["execution_rates"] = [
                {
                    "l1_code": r.l1_code,
                    "monthly_rate": float(r.monthly_rate or 0),
                    "cumulative_rate": float(r.cumulative_rate or 0),
                    "annual_rate": float(r.annual_rate or 0),
                }
                for r in rates
            ]

        stmt_gap = select(GapAnalysis)
        if center_id:
            stmt_gap = stmt_gap.where(GapAnalysis.center_id == center_id)
        if period:
            stmt_gap = stmt_gap.where(GapAnalysis.period == period)
        result_gap = await db.execute(stmt_gap)
        gaps = result_gap.scalars().all()
        dashboard["gap_analyses"] = [
            {
                "id": g.id,
                "center_id": g.center_id,
                "gap1": float(g.gap1 or 0),
                "gap2": float(g.gap2 or 0),
                "gap3": float(g.gap3 or 0),
            }
            for g in gaps
        ]

        stmt_list = select(ListAnalysis)
        if center_id:
            stmt_list = stmt_list.where(ListAnalysis.center_id == center_id)
        if period:
            stmt_list = stmt_list.where(ListAnalysis.period == period)
        result_list = await db.execute(stmt_list)
        lists = result_list.scalars().all()
        dashboard["list_analyses"] = [
            {
                "id": l.id,
                "center_id": l.center_id,
                "list_type": l.list_type,
                "item_name": l.item_name,
                "action_plan": l.action_plan,
            }
            for l in lists
        ]

        return APIResponse(success=True, data=dashboard)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/center-responsibilities", response_model=APIResponse)
async def get_center_responsibilities(
    db: AsyncSession = Depends(get_db),
):
    try:
        data = analysis_engine.get_center_responsibilities()
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/collect-center-data", response_model=APIResponse)
async def collect_center_data(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    center = body.get("center")
    period = body.get("period")
    if not center or not period:
        raise HTTPException(status_code=400, detail="center and period are required")
    try:
        data = await analysis_engine.collect_center_data(center, period, db)
        return APIResponse(success=True, message="Center data collected", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/lock-period", response_model=APIResponse)
async def lock_period(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period")
        locked_by = body.get("locked_by")
        if not period or not locked_by:
            raise HTTPException(status_code=400, detail="period and locked_by are required")

        result = await analysis_engine.lock_period_data(period, locked_by, db)
        return APIResponse(success=True, message="Period locked", data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/lock-status/{period}", response_model=APIResponse)
async def get_lock_status(
    period: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(ExecutionRate).where(ExecutionRate.period == period)
        result = await db.execute(stmt)
        rates = result.scalars().all()

        if not rates:
            return APIResponse(success=True, data={"period": period, "is_locked": False, "locked_by": "", "locked_at": None})

        is_locked = any(r.is_locked for r in rates)
        locked_by = next((r.locked_by for r in rates if r.locked_by), "")
        locked_at = next((r.locked_at.isoformat() if r.locked_at else None for r in rates if r.locked_at), None)

        return APIResponse(success=True, data={"period": period, "is_locked": is_locked, "locked_by": locked_by, "locked_at": locked_at})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/predict-trend", response_model=APIResponse)
async def predict_execution_trend(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        l1_code = body.get("l1_code")
        if not l1_code:
            raise HTTPException(status_code=400, detail="l1_code is required")
        months_ahead = body.get("months_ahead", 6)
        data = await analysis_engine.predict_execution_trend(l1_code, db, months_ahead)
        return APIResponse(success=True, message="Trend prediction complete", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/detect-anomalies", response_model=APIResponse)
async def detect_anomalies(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period")
        if not period:
            raise HTTPException(status_code=400, detail="period is required (YYYY-MM)")
        z_threshold = body.get("z_threshold", 2.0)
        iqr_multiplier = body.get("iqr_multiplier", 1.5)
        data = await analysis_engine.detect_anomalies(period, db, z_threshold, iqr_multiplier)
        return APIResponse(success=True, message="Anomaly detection complete", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/root-cause", response_model=APIResponse)
async def root_cause_analysis(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        issue_type = body.get("issue_type")
        period = body.get("period")
        if not issue_type or not period:
            raise HTTPException(status_code=400, detail="issue_type and period are required")
        if issue_type not in ("超支", "低执行率"):
            raise HTTPException(status_code=400, detail="issue_type must be '超支' or '低执行率'")
        l1_code = body.get("l1_code")
        data = await analysis_engine.root_cause_analysis(issue_type, l1_code, period, db)
        return APIResponse(success=True, message="Root cause analysis complete", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/compare-periods", response_model=APIResponse)
async def compare_periods(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period1 = body.get("period1")
        period2 = body.get("period2")
        if not period1 or not period2:
            raise HTTPException(status_code=400, detail="period1 and period2 are required")
        l1_code = body.get("l1_code")
        data = await analysis_engine.compare_periods(period1, period2, l1_code, db)
        return APIResponse(success=True, message="Period comparison complete", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════
#  9 张经营诊断卡 + 4 个分析框架 + 信号灯规则（v3.0 新增）
#  保留旧 4-Tab 端点不破坏
# ════════════════════════════════════════════════════════════════

from engines.business_diagnosis import (
    DiagnosisEngine,
    NINE_CARDS,
    load_signal_light_rules,
    save_signal_light_rules,
    get_signal_light_thresholds,
)

diagnosis_engine = DiagnosisEngine()


async def _run_diagnosis_with_ai(card_type: str, period: str, db: AsyncSession) -> Dict[str, Any]:
    """工厂函数：跑单张诊断卡并生成 AI 文字（带 try/except 兜底）"""
    method = getattr(diagnosis_engine, f"diagnose_{card_type}", None)
    if not method:
        raise HTTPException(status_code=404, detail=f"Unknown card type: {card_type}")
    try:
        card = await method(period, db)
        # AI 文字生成（带超时回退）
        try:
            card_with_ai = await diagnosis_engine.ai_generate_card_text(card, db)
            return card_with_ai
        except Exception as ai_err:
            logger.warning(f"[api] ai_generate failed for {card_type}, fallback to template: {ai_err}")
            return diagnosis_engine._fallback_template(card)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"诊断卡 {card_type} 失败: {e}")


# === 9 张诊断卡端点 ===
DIAGNOSIS_CARD_ROUTES = {
    "revenue-health": "revenue_health",
    "gross-margin": "gross_margin",
    "expense-pacing": "expense_pacing",
    "product-mix": "product_mix",
    "channel-split": "channel_split",
    "profit-authenticity": "profit_authenticity",
    "commercialization-efficiency": "commercialization_efficiency",
    "policy-risk": "policy_risk",
    "cashflow-quality": "cashflow_quality",
}


for _route_suffix, _card_type in DIAGNOSIS_CARD_ROUTES.items():

    async def _diagnose_handler(
        body: dict, _ct: str = _card_type, db: AsyncSession = Depends(get_db)
    ):
        period = body.get("period", "")
        if not period:
            raise HTTPException(status_code=400, detail="period is required (YYYY-MM)")
        return APIResponse(success=True, data=await _run_diagnosis_with_ai(_ct, period, db))

    _diagnose_handler.__name__ = f"diagnose_{_card_type}"
    _diagnose_handler.__doc__ = f"诊断卡 {_card_type}"
    router.add_api_route(
        f"/analysis/diagnose/{_route_suffix}",
        _diagnose_handler,
        methods=["POST"],
        response_model=APIResponse,
    )


# === 4 个分析框架端点 ===
async def _framework_handler(
    framework: str, period: str, db: AsyncSession
) -> Dict[str, Any]:
    method = getattr(diagnosis_engine, f"calc_{framework}", None)
    if not method:
        raise HTTPException(status_code=404, detail=f"Unknown framework: {framework}")
    try:
        return await method(period, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"框架 {framework} 计算失败: {e}")


@router.get("/analysis/framework/dupont", response_model=APIResponse)
async def get_framework_dupont(
    period: str = Query(..., description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    return APIResponse(success=True, data=await _framework_handler("dupont_waterfall", period, db))


@router.get("/analysis/framework/bridge", response_model=APIResponse)
async def get_framework_bridge(
    period: str = Query(..., description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    return APIResponse(success=True, data=await _framework_handler("bridge_analysis", period, db))


@router.get("/analysis/framework/bcg", response_model=APIResponse)
async def get_framework_bcg(
    period: str = Query(..., description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    return APIResponse(success=True, data=await _framework_handler("bcg_matrix", period, db))


@router.get("/analysis/framework/sar", response_model=APIResponse)
async def get_framework_sar(
    period: str = Query(..., description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    # SAR 需要先跑 9 张卡
    try:
        card_results: List[Dict[str, Any]] = []
        for _card in NINE_CARDS:
            _method = getattr(diagnosis_engine, f"diagnose_{_card['type']}", None)
            if _method:
                try:
                    card_results.append(await _method(period, db))
                except Exception as e:
                    logger.warning(f"[sar] card {_card['type']} failed: {e}")
        sar = await diagnosis_engine.calc_sar_recommendations(period, db, card_results)
        return APIResponse(success=True, data=sar)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SAR 框架失败: {e}")


# === 信号灯规则（可配置）===
@router.get("/analysis/signal-light-rules", response_model=APIResponse)
async def get_signal_light_rules(
    card_type: Optional[str] = Query(None, description="诊断卡类型（不传则返回全部）"),
):
    try:
        rules = load_signal_light_rules(force_reload=True)
        if card_type:
            thresholds = get_signal_light_thresholds(card_type)
            return APIResponse(
                success=True,
                data={"card_type": card_type, "thresholds": thresholds, "rules": rules.get(card_type, {})},
            )
        return APIResponse(success=True, data=rules)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载信号灯规则失败: {e}")


@router.put("/analysis/signal-light-rules", response_model=APIResponse)
async def update_signal_light_rules(payload: Dict[str, Any]):
    try:
        ok = save_signal_light_rules(payload)
        if not ok:
            raise HTTPException(status_code=500, detail="写入信号灯规则失败")
        return APIResponse(success=True, message="信号灯规则已更新", data={"card_count": len(payload)})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === 报告组装（一键生成 4 部分 + 9 卡）===
@router.post("/analysis/diagnosis-report", response_model=APIResponse)
async def generate_diagnosis_report(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    period = body.get("period", "")
    if not period:
        raise HTTPException(status_code=400, detail="period is required (YYYY-MM)")
    try:
        report = await diagnosis_engine.generate_diagnosis_report(period, db)
        return APIResponse(success=True, message="诊断报告已生成", data=report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"诊断报告生成失败: {e}")


@router.get("/analysis/diagnosis-report", response_model=APIResponse)
async def get_diagnosis_report(
    period: str = Query(..., description="YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    """获取已生成的诊断报告（无 DB 缓存时现场生成）"""
    try:
        from models.analysis import DiagnosisReport as _DR
        stmt = select(_DR).where(_DR.period == period)
        result = await db.execute(stmt)
        cached = result.scalar_one_or_none()
        if cached and cached.card_results:
            return APIResponse(
                success=True,
                data={
                    "id": cached.id,
                    "period": cached.period,
                    "part1_overview": {
                        "dupont": cached.dupont_data,
                        "top_judgments": cached.top_judgments,
                    },
                    "part2_cards": cached.card_results,
                    "part3_bcg": cached.bcg_data,
                    "part4_sar": cached.sar_data,
                    "status": cached.status,
                },
            )
        # 现场生成
        report = await diagnosis_engine.generate_diagnosis_report(period, db)
        return APIResponse(success=True, data=report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === 诊断卡元信息（9 张卡定义）===
@router.get("/analysis/diagnosis-cards", response_model=APIResponse)
async def list_diagnosis_cards():
    """列出 9 张诊断卡的元信息（前端用于渲染"九宫格"标题）"""
    return APIResponse(success=True, data={"cards": NINE_CARDS, "total": len(NINE_CARDS)})


# ══════════════════════════════════════════════════════════════════════════
# v12.1: 阶段 4 — 经营分析 AI 智能引擎（5 大能力）
# ══════════════════════════════════════════════════════════════════════════

@router.post("/analysis/ai/root-cause-drilldown", response_model=APIResponse)
async def ai_root_cause_drilldown(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 根因下钻（v12.0 升级版）

    请求体：{"issue_type": "超支/低执行率/执行偏差", "period": "2025-06", "l1_code": "01"(可选)}
    """
    try:
        issue_type = body.get("issue_type", "执行偏差")
        period = body.get("period", "")
        l1_code = body.get("l1_code")
        if not period:
            raise HTTPException(status_code=400, detail="period 必填")
        result = await analysis_ai_engine.root_cause_drilldown(issue_type, period, l1_code, db)
        return APIResponse(
            success=True,
            message=f"AI 根因下钻完成：发现 {result.get('problematic_count', 0)} 个问题项，{len(result.get('root_causes', []))} 个根因",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/ai/smart-attribution", response_model=APIResponse)
async def ai_smart_attribution(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 智能归因（偏差 → 责任主体）"""
    try:
        center_id = body.get("center_id", "")
        period = body.get("period", "")
        if not center_id or not period:
            raise HTTPException(status_code=400, detail="center_id 和 period 必填")
        result = await analysis_ai_engine.smart_attribution(center_id, period, db)
        return APIResponse(
            success=True,
            message=f"AI 归因完成：{result.get('attribution_count', 0)} 个偏差项已归因到 {len(result.get('role_summary', []))} 类责任主体",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/ai/generate-narrative", response_model=APIResponse)
async def ai_generate_narrative(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 叙事生成（4 段式经营分析报告）"""
    try:
        center_id = body.get("center_id", "")
        period = body.get("period", "")
        if not center_id or not period:
            raise HTTPException(status_code=400, detail="center_id 和 period 必填")
        result = await analysis_ai_engine.generate_narrative(center_id, period, db)
        return APIResponse(
            success=True,
            message=f"AI 叙事生成完成：风险等级【{result.get('risk_level', '未知')}】",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/ai/predict-health", response_model=APIResponse)
async def ai_predict_health(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 健康度预测（5 维加权健康分）"""
    try:
        center_id = body.get("center_id", "")
        period = body.get("period", "")
        if not center_id or not period:
            raise HTTPException(status_code=400, detail="center_id 和 period 必填")
        result = await analysis_ai_engine.predict_health_score(center_id, period, db)
        return APIResponse(
            success=True,
            message=f"健康度预测完成：{result.get('health_level', '未知')}（{result.get('health_score', 0)}）",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analysis/ai/smart-recommendations", response_model=APIResponse)
async def ai_smart_recommendations(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 智能建议（综合根因+归因+健康度 Top N 行动清单）"""
    try:
        center_id = body.get("center_id", "")
        period = body.get("period", "")
        top_n = int(body.get("top_n", 5))
        if not center_id or not period:
            raise HTTPException(status_code=400, detail="center_id 和 period 必填")
        result = await analysis_ai_engine.smart_recommendations(center_id, period, db, top_n=top_n)
        return APIResponse(
            success=True,
            message=f"AI 建议生成完成：{result.get('summary', {}).get('total_recommendations', 0)} 条建议",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
