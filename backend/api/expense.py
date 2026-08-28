from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse, APIPageResponse
from models.expense import ExpenseReport, InvoiceRecord
from models.expense_effect import ExpenseEffectTracking
from models.approval import ApprovalRecord
from models.budget import BudgetItem
from engines.expense_reimbursement import ExpenseReimbursementEngine
from engines.expense_anomaly import ExpenseAnomalyEngine
from engines.expense_risk_score import ExpenseRiskScoreEngine
from engines.budget_burn_predictor import BudgetBurnPredictor
from engines.approval_engine import ApprovalEngine
from engines.expense_ai import ExpenseAIEngine

from api.deps import get_current_user, get_center_filter_for_user
from models.user import User

router = APIRouter()

expense_engine = ExpenseReimbursementEngine()
approval_engine = ApprovalEngine()
anomaly_engine = ExpenseAnomalyEngine()
risk_score_engine = ExpenseRiskScoreEngine()
burn_predictor = BudgetBurnPredictor()


# v11.0: 报销状态 → 本体规则 ID 映射
# 让前端能展示"依据 HR-xxx"标签
EXPENSE_STATUS_RULE_MAP = {
    "submitted": ["HR-001"],
    "org_approved": ["HR-001", "HR-015"],
    "legal_approved": ["HR-001", "HR-015", "HR-AP-001"],
    "rejected": ["HR-002"],
    "written_off": ["HR-WO-001"],
}


def _attach_expense_rule_ids(rows: list[dict]) -> list[dict]:
    """v11.0: 给 expense 响应附加 rule_ids 字段"""
    for row in rows:
        # 优先按状态映射
        status = row.get("status")
        if status and status in EXPENSE_STATUS_RULE_MAP:
            row["rule_ids"] = EXPENSE_STATUS_RULE_MAP[status]
        else:
            row["rule_ids"] = ["HR-001"]
    return rows


# ─── v8.0 费用异常检测 / 风险评分 / 预算消耗预测 ──────────────────────


@router.get("/expenses/anomalies", response_model=APIResponse)
async def scan_expense_anomalies(
    period: str = Query(..., description="YYYY-MM"),
    center_id: Optional[str] = Query(None, description="中心 ID（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """扫描期间内所有异常（单笔 + 群体 + 趋势）"""
    try:
        result = await anomaly_engine.scan_period(db, period, center_id)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/risk-scores", response_model=APIResponse)
async def get_expense_risk_scores(
    period: str = Query(..., description="YYYY-MM"),
    center_id: Optional[str] = Query(None, description="中心 ID（可选）"),
    top_n: int = Query(20, ge=1, le=100, description="返回 TopN 风险"),
    db: AsyncSession = Depends(get_db),
):
    """批量评分本期所有报销（5 维风险）"""
    try:
        result = await risk_score_engine.score_batch(db, period, center_id, top_n)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/budget-burn-prediction", response_model=APIResponse)
async def predict_budget_burn(
    period: str = Query(..., description="YYYY-MM"),
    center_id: Optional[str] = Query(None, description="中心 ID（可选）"),
    db: AsyncSession = Depends(get_db),
):
    """批量预测所有预算项的全年消耗 + 跑道"""
    try:
        result = await burn_predictor.batch_predict(db, period, center_id)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/{expense_id}/risk-score", response_model=APIResponse)
async def get_single_expense_risk(
    expense_id: str,
    db: AsyncSession = Depends(get_db),
):
    """对单笔报销实时评分"""
    try:
        expense = await db.get(ExpenseReport, expense_id)
        if expense is None:
            raise HTTPException(status_code=404, detail=f"Expense {expense_id} not found")

        from datetime import datetime, timedelta
        from models.budget import BudgetItem
        hist_start = datetime.now() - timedelta(days=180)
        from sqlalchemy import and_ as _and
        stmt = select(ExpenseReport).where(_and_(
            ExpenseReport.applicant_id == expense.applicant_id,
            ExpenseReport.created_at >= hist_start,
            ExpenseReport.expense_id != expense_id,
        ))
        result = await db.execute(stmt)
        hist = result.scalars().all()

        # 历史驳回数
        rejected = [e for e in hist if e.status == "已驳回"]

        score = await risk_score_engine.score_expense(expense, hist, len(rejected))
        return APIResponse(success=True, data=score)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses", response_model=APIPageResponse)
async def list_expenses(
    status: Optional[str] = Query(None),
    budget_id: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
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
            conditions.append(ExpenseReport.center_id == user_center_filter)
        if status:
            conditions.append(ExpenseReport.status == status)
        if budget_id:
            conditions.append(ExpenseReport.budget_id == budget_id)
        if department:
            conditions.append(ExpenseReport.department_id == department)

        stmt = select(ExpenseReport).where(and_(*conditions)) if conditions else select(ExpenseReport)
        result = await db.execute(stmt)
        items = result.scalars().all()

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in page_items]
        _attach_expense_rule_ids(data)

        return APIPageResponse(
            success=True,
            total=total,
            page=page,
            page_size=page_size,
            data=data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/effect-summary", response_model=APIResponse)
async def get_effect_summary(
    l1_code: Optional[str] = Query(None, description="L1科目代码"),
    budget_id: Optional[str] = Query(None, description="预算ID"),
    db: AsyncSession = Depends(get_db),
):
    """获取报销效果跟踪汇总"""
    try:
        conditions = []
        if budget_id:
            conditions.append(ExpenseEffectTracking.budget_id == budget_id)

        stmt = select(ExpenseEffectTracking).where(and_(*conditions)) if conditions else select(ExpenseEffectTracking)
        result = await db.execute(stmt)
        trackings = result.scalars().all()

        total = len(trackings)
        avg_score = 0
        follow_up_count = 0
        by_l1: Dict[str, Any] = {}

        if total > 0:
            scores = [t.effect_score for t in trackings if t.effect_score is not None]
            avg_score = sum(scores) / len(scores) if scores else 0
            follow_up_count = sum(1 for t in trackings if t.follow_up_required)

            for t in trackings:
                budget_item = await db.get(BudgetItem, t.budget_id)
                l1 = budget_item.l1_code if budget_item else "unknown"
                if l1 not in by_l1:
                    by_l1[l1] = {"count": 0, "avg_score": 0, "scores": []}
                by_l1[l1]["count"] += 1
                if t.effect_score is not None:
                    by_l1[l1]["scores"].append(t.effect_score)

            for l1, data in by_l1.items():
                data["avg_score"] = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
                del data["scores"]

        return APIResponse(success=True, data={
            "total_evaluations": total,
            "avg_effect_score": round(avg_score, 2),
            "follow_up_required_count": follow_up_count,
            "by_l1": by_l1,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/{expense_id}", response_model=APIResponse)
async def get_expense(
    expense_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        expense = await db.get(ExpenseReport, expense_id)
        if expense is None:
            raise HTTPException(status_code=404, detail=f"Expense report {expense_id} not found")

        data = {c: getattr(expense, c) for c in expense.__table__.columns.keys()}
        _attach_expense_rule_ids([data])
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses", response_model=APIResponse)
async def submit_expense(
    expense_data: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        expense = await expense_engine.submit_expense(expense_data, db)
        data = {c: getattr(expense, c) for c in expense.__table__.columns.keys()}
        return APIResponse(success=True, message="Expense report submitted", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


_INVOICES_STORE: list[Dict] = []


@router.post("/expenses/check-invoice", response_model=APIResponse)
async def check_invoice_duplicate(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    invoice_number = body.get("invoice_number")
    if not invoice_number:
        raise HTTPException(status_code=400, detail="invoice_number is required")
    try:
        stmt = select(InvoiceRecord).where(InvoiceRecord.invoice_number == invoice_number)
        result = await db.execute(stmt)
        records = result.scalars().all()
        is_duplicate = len(records) > 0
        duplicate_records = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in records]
        return APIResponse(success=True, data={
            "invoice_number": invoice_number,
            "is_duplicate": is_duplicate,
            "duplicate_count": len(duplicate_records),
            "duplicate_records": duplicate_records,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses/invoices/upload", response_model=APIResponse)
async def upload_invoice(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    invoice_number = body.get("invoice_number")
    invoice_type = body.get("invoice_type")
    amount = body.get("amount")
    invoice_date = body.get("invoice_date")
    vendor_name = body.get("vendor_name")
    if not invoice_number:
        raise HTTPException(status_code=400, detail="invoice_number is required")
    try:
        is_duplicate = await expense_engine.check_invoice_duplicate(invoice_number, db)
        invoice_record = {
            "invoice_number": invoice_number,
            "invoice_type": invoice_type,
            "amount": amount,
            "invoice_date": invoice_date,
            "vendor_name": vendor_name,
            "is_duplicate": is_duplicate,
            "upload_status": "重复" if is_duplicate else "正常",
        }
        if not is_duplicate:
            import uuid
            record = InvoiceRecord(
                invoice_id=f"INV-{uuid.uuid4().hex[:8].upper()}",
                expense_id="",
                invoice_number=invoice_number,
                invoice_type=invoice_type,
                invoice_amount=amount,
                invoice_date=invoice_date,
                seller_name=vendor_name,
                is_duplicate=False,
            )
            db.add(record)
            await db.flush()
            invoice_record["invoice_id"] = record.invoice_id
        return APIResponse(success=True, message="Invoice uploaded", data=invoice_record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/invoices", response_model=APIResponse)
async def list_invoices(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(InvoiceRecord)
        result = await db.execute(stmt)
        invoices = result.scalars().all()
        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in invoices]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/invoices/duplicates", response_model=APIResponse)
async def list_duplicate_invoices(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(InvoiceRecord).where(InvoiceRecord.is_duplicate.is_(True))
        result = await db.execute(stmt)
        invoices = result.scalars().all()
        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in invoices]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses/{expense_id}/approve", response_model=APIResponse)
async def approve_expense(
    expense_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        approver_id = body.get("approver_id")
        comment = body.get("comment")
        if not approver_id:
            raise HTTPException(status_code=400, detail="approver_id is required")

        stmt = select(ApprovalRecord).where(
            and_(
                ApprovalRecord.expense_id == expense_id,
                ApprovalRecord.approver_id == approver_id,
                ApprovalRecord.approval_action == "待审批",
            )
        )
        result = await db.execute(stmt)
        record = result.scalars().first()

        if record is None:
            raise HTTPException(status_code=404, detail=f"No pending approval found for expense {expense_id} and approver {approver_id}")

        record = await approval_engine.approve_step(record.approval_id, "通过", comment, db)
        data = {c: getattr(record, c) for c in record.__table__.columns.keys()}
        return APIResponse(success=True, message="Expense approved", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses/{expense_id}/reject", response_model=APIResponse)
async def reject_expense(
    expense_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        approver_id = body.get("approver_id")
        comment = body.get("comment")
        if not approver_id:
            raise HTTPException(status_code=400, detail="approver_id is required")

        stmt = select(ApprovalRecord).where(
            and_(
                ApprovalRecord.expense_id == expense_id,
                ApprovalRecord.approver_id == approver_id,
                ApprovalRecord.approval_action == "待审批",
            )
        )
        result = await db.execute(stmt)
        record = result.scalars().first()

        if record is None:
            raise HTTPException(status_code=404, detail=f"No pending approval found for expense {expense_id} and approver {approver_id}")

        record = await approval_engine.approve_step(record.approval_id, "驳回", comment, db)
        data = {c: getattr(record, c) for c in record.__table__.columns.keys()}
        return APIResponse(success=True, message="Expense rejected", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses/{expense_id}/cancel", response_model=APIResponse)
async def cancel_expense(
    expense_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        expense = await db.get(ExpenseReport, expense_id)
        if expense is None:
            raise HTTPException(status_code=404, detail=f"Expense report {expense_id} not found")

        if expense.status not in ("草稿", "待审批"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel expense in status: {expense.status}",
            )

        expense.status = "已取消"
        await db.flush()

        data = {c: getattr(expense, c) for c in expense.__table__.columns.keys()}
        return APIResponse(success=True, message="Expense cancelled", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/{expense_id}/control-route", response_model=APIResponse)
async def get_control_route(
    expense_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        expense = await db.get(ExpenseReport, expense_id)
        if expense is None:
            raise HTTPException(status_code=404, detail=f"Expense report {expense_id} not found")

        routing = await expense_engine.route_control_level(expense.l3_code, db)
        return APIResponse(success=True, data=routing)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses/{expense_id}/write-off", response_model=APIResponse)
async def write_off_expense(
    expense_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        write_off = await expense_engine.write_off_budget(expense_id, db)
        data = {c: getattr(write_off, c) for c in write_off.__table__.columns.keys()}
        return APIResponse(success=True, message="Budget written off", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/{expense_id}/effect-tracking", response_model=APIResponse)
async def get_expense_effect_tracking(
    expense_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取单个报销的效果追踪记录"""
    try:
        stmt = select(ExpenseEffectTracking).where(
            ExpenseEffectTracking.expense_id == expense_id,
        )
        result = await db.execute(stmt)
        trackings = result.scalars().all()
        data = [{c: getattr(t, c) for c in t.__table__.columns.keys()} for t in trackings]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses/{expense_id}/evaluate-effect", response_model=APIResponse)
async def evaluate_expense_effect(
    expense_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """提交报销效果评估"""
    try:
        expense = await db.get(ExpenseReport, expense_id)
        if expense is None:
            raise HTTPException(status_code=404, detail=f"Expense report {expense_id} not found")

        import uuid
        from datetime import datetime

        tracking = ExpenseEffectTracking(
            tracking_id=f"ET-{uuid.uuid4().hex[:8].upper()}",
            expense_id=expense_id,
            budget_id=expense.budget_id,
            expected_outcome=body.get("expected_outcome"),
            actual_outcome=body.get("actual_outcome"),
            effect_score=body.get("effect_score"),
            evaluation_date=datetime.now(),
            evaluator_id=body.get("evaluator_id", ""),
            follow_up_required=body.get("follow_up_required", False),
        )
        db.add(tracking)
        await db.flush()

        data = {c: getattr(tracking, c) for c in tracking.__table__.columns.keys()}
        return APIResponse(success=True, message="Effect evaluation submitted", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
# v12.1: 阶段 3 — 费用报销 AI 智能路由（4 大能力）
# ══════════════════════════════════════════════════════════════════════════

@router.post("/expenses/ai/recognize-l3", response_model=APIResponse)
async def ai_recognize_l3(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 智能识别 L3 科目

    请求体：{"description": "...", "amount": 1234}
    返回：推荐 L3 + 置信度 + 候选项 + 命中关键词
    """
    try:
        description = body.get("description", "")
        amount = float(body.get("amount", 0) or 0)
        result = await expense_ai_engine.recognize_l3(description, amount, db)
        return APIResponse(
            success=True,
            message=f"识别结果：{result['l3_name']}（置信度 {result['confidence']}%）",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses/ai/detect-anomalies", response_model=APIResponse)
async def ai_detect_anomalies(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 5 维异常检测

    请求体：{"applicant_id":"...","amount":...,"l3_code":"...","invoice_number":"...","expense_date":"..."}
    返回：风险分 + 风险等级 + 异常列表 + 是否拦截
    """
    try:
        result = await expense_ai_engine.detect_anomalies(body, db)
        return APIResponse(
            success=True,
            message=f"异常检测完成：风险分 {result['risk_score']}，{result['risk_level']}风险",
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses/ai/smart-route", response_model=APIResponse)
async def ai_smart_route(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 智能路由

    一站式返回：4 级管控 + 异常加成 + 金额加成 → 审批链 + SLA 估算
    """
    try:
        amount = float(body.get("amount", 0) or 0)
        description = body.get("description", "")

        # 必须先有 L3 识别 + 异常检测结果
        l3 = await expense_ai_engine.recognize_l3(description, amount, db)
        anomaly = await expense_ai_engine.detect_anomalies(body, db)
        routing = await expense_ai_engine.smart_route(body, anomaly, l3)

        return APIResponse(
            success=True,
            message=f"智能路由完成：{len(routing['approval_chain'])} 级审批（{routing['control_tag']}）",
            data={
                "l3_recognition": l3,
                "anomaly_detection": anomaly,
                "smart_routing": routing,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expenses/ai/pre-submit-review", response_model=APIResponse)
async def ai_pre_submit_review(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v12.1: AI 提交前预审（4 步一站式）

    流程：L3 识别 → 异常检测 → 智能路由 → 拒付预警
    """
    try:
        result = await expense_ai_engine.pre_submit_review(body, db)
        s = result["smart_routing"]
        return APIResponse(
            success=True,
            message=(
                f"预审完成：L3={result['l3_recognition']['l3_name']}，"
                f"异常分={result['anomaly_detection']['risk_score']}，"
                f"拒付概率={result['rejection_prediction']['reject_probability']}%"
            ),
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expenses/ai/batch-anomaly-scan", response_model=APIResponse)
async def ai_batch_anomaly_scan(
    days: int = Query(7, ge=1, le=90, description="扫描最近 N 天"),
    top_n: int = Query(20, ge=1, le=100, description="Top N 风险"),
    db: AsyncSession = Depends(get_db),
):
    """v12.1: 批量异常扫描（管理员视角）

    返回：拆单嫌疑聚类 + 高频申请人 + 扫描统计
    """
    try:
        result = await expense_ai_engine.batch_anomaly_scan(db, days=days, top_n=top_n)
        return APIResponse(
            success=True,
            message=(
                f"扫描完成：{result['scanned_count']} 笔，"
                f"{result['high_risk_count']} 个高风险聚类"
            ),
            data=result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

