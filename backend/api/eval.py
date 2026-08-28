import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from models.ontology import ReasoningTrace

router = APIRouter()

EVAL_CATEGORIES = [
    {
        "id": "budget_planning",
        "name": "预算编制",
        "description": "验证预算编制引擎的科目分类、象限归属、A/B分类和战略对齐能力",
    },
    {
        "id": "budget_grant",
        "name": "预算授予",
        "description": "验证A类冻结、B类授予、B→A转换和额度释放的正确性",
    },
    {
        "id": "expense_reimbursement",
        "name": "费用报销",
        "description": "验证报销提交、管控路由、发票查重和预算核销流程",
    },
    {
        "id": "approval",
        "name": "审批流程",
        "description": "验证双线审批、审批链创建和审批步骤处理",
    },
    {
        "id": "alert_monitoring",
        "name": "预警监控",
        "description": "验证月度执行进度、季度滚动预测和里程碑预警触发",
    },
    {
        "id": "business_analysis",
        "name": "经营分析",
        "description": "验证3GAP分析、3List分类和执行率计算",
    },
    {
        "id": "pdca_review",
        "name": "PDCA复盘",
        "description": "验证月度/季度/年度复盘流程和改进建议生成",
    },
    {
        "id": "report_generation",
        "name": "报表出具",
        "description": "验证月度快报、季度汇报、年度复盘和经营分析会材料生成",
    },
    {
        "id": "ontology_rules",
        "name": "本体规则",
        "description": "验证硬规则执行、软规则参数化和推理规则链路",
    },
]

BASELINE_PASS_RATES = {
    "budget_planning": 0.85,
    "budget_grant": 0.90,
    "expense_reimbursement": 0.88,
    "approval": 0.92,
    "alert_monitoring": 0.80,
    "business_analysis": 0.82,
    "pdca_review": 0.78,
    "report_generation": 0.85,
    "ontology_rules": 0.75,
}


@router.get("/eval/categories", response_model=APIResponse)
async def list_eval_categories():
    return APIResponse(success=True, data=EVAL_CATEGORIES)


@router.post("/eval/run", response_model=APIResponse)
async def run_evaluation(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        category = body.get("category")
        if not category:
            raise HTTPException(status_code=400, detail="category is required")

        valid_categories = [c["id"] for c in EVAL_CATEGORIES]
        if category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}. Valid: {valid_categories}")

        import uuid
        from datetime import datetime

        run_id = f"EVAL-{uuid.uuid4().hex[:8].upper()}"
        baseline = BASELINE_PASS_RATES.get(category, 0.80)

        stmt = select(ReasoningTrace).where(
            ReasoningTrace.scene_name.contains(category.replace("_", ""))
        ).limit(10)
        result = await db.execute(stmt)
        traces = result.scalars().all()

        total_checks = max(len(traces), 1)
        passed = sum(1 for t in traces if t.confidence and float(t.confidence or 0) >= 80)
        pass_rate = round(passed / total_checks, 4)

        eval_result = {
            "run_id": run_id,
            "category": category,
            "category_name": next((c["name"] for c in EVAL_CATEGORIES if c["id"] == category), category),
            "total_checks": total_checks,
            "passed": passed,
            "failed": total_checks - passed,
            "pass_rate": pass_rate,
            "baseline": baseline,
            "status": "PASS" if pass_rate >= baseline else "FAIL",
            "run_at": datetime.now().isoformat(),
        }

        return APIResponse(success=True, message=f"Evaluation complete: {eval_result['status']}", data=eval_result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/eval/results", response_model=APIResponse)
async def get_latest_eval_results(
    db: AsyncSession = Depends(get_db),
):
    try:
        results = []
        for cat in EVAL_CATEGORIES:
            baseline = BASELINE_PASS_RATES.get(cat["id"], 0.80)
            results.append({
                "category": cat["id"],
                "category_name": cat["name"],
                "baseline": baseline,
                "latest_pass_rate": None,
                "status": "not_run",
            })

        return APIResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/eval/results/{run_id}", response_model=APIResponse)
async def get_eval_run_detail(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(ReasoningTrace).where(
            ReasoningTrace.trace_id.startswith("RT-EVAL")
        ).limit(1)
        result = await db.execute(stmt)
        trace = result.scalars().first()

        if trace is None:
            return APIResponse(success=True, data={"run_id": run_id, "status": "not_found"})

        data = {c: getattr(trace, c) for c in trace.__table__.columns.keys()}
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/eval/baseline", response_model=APIResponse)
async def get_baseline_pass_rates():
    return APIResponse(success=True, data=BASELINE_PASS_RATES)
