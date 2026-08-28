from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from engines.cash_flow_engine import CashFlowEngine
from engines.cashflow_advisor import CashflowAdvisorEngine
from engines.cashflow_aging import CashflowAgingEngine
from engines.cashflow_forecast import CashflowForecastEngine

router = APIRouter()

engine = CashFlowEngine()
aging_engine = CashflowAgingEngine()
forecast_engine = CashflowForecastEngine()
advisor_engine = CashflowAdvisorEngine()


@router.get("/cashflow/forecast", response_model=APIResponse)
async def forecast_cash_flow(
    period: str = Query(..., description="预测起始期间, 如 2024-06"),
    horizon_months: int = Query(3, ge=1, le=12, description="预测月数"),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.forecast_cash_flow(period, horizon_months, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cashflow/liquidity-gap", response_model=APIResponse)
async def check_liquidity_gap(
    period: str = Query(..., description="期间, 如 2024-06"),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.check_liquidity_gap(period, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cashflow/profit-cash-gap", response_model=APIResponse)
async def analyze_profit_cash_gap(
    period: str = Query(..., description="期间, 如 2024-06"),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.analyze_profit_cash_gap(period, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cashflow/receipt-payment-match", response_model=APIResponse)
async def match_receipt_payment(
    period: str = Query(..., description="期间, 如 2024-06"),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.match_receipt_payment(period, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────── v7.0 新增：账龄分析（AR/AP Aging） ──────


@router.get("/cashflow/aging", response_model=APIResponse)
async def analyze_aging(
    kind: str = Query("AR", description="AR=应收账款 / AP=应付账款"),
    db: AsyncSession = Depends(get_db),
):
    """账龄分析（4 段：0-30/31-60/61-90/90+）"""
    try:
        if kind.upper() == "AR":
            report = await aging_engine.analyze_receivable_aging(db)
        elif kind.upper() == "AP":
            report = await aging_engine.analyze_payable_aging(db)
        else:
            raise HTTPException(status_code=400, detail="kind 必须是 AR 或 AP")
        return APIResponse(success=True, data=report.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────── v7.0 新增：12 周滚动预测 ──────


@router.get("/cashflow/rolling-forecast", response_model=APIResponse)
async def rolling_forecast(
    horizon_weeks: int = Query(12, ge=1, le=52, description="预测周数（默认 12）"),
    initial_balance: float = Query(None, description="初始现金池余额（None 则从 DB 读取）"),
    db: AsyncSession = Depends(get_db),
):
    """12 周滚动现金流预测 + 流动性健康度评分"""
    try:
        report = await forecast_engine.rolling_forecast(
            db, horizon_weeks=horizon_weeks, initial_balance=initial_balance
        )
        return APIResponse(success=True, data=report.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────── v7.0 新增：智能调拨建议 ──────


@router.post("/cashflow/transfer-recommend", response_model=APIResponse)
async def recommend_transfer(
    body: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
):
    """智能调拨建议（指定目标资金池 + 缺口金额）"""
    try:
        target_pool_id = int(body.get("target_pool_id", 1))
        gap_amount = float(body.get("gap_amount", 0))
        horizon_days = int(body.get("horizon_days", 7))
        plan = await advisor_engine.recommend_transfer(
            db, target_pool_id, gap_amount, horizon_days
        )
        return APIResponse(success=True, data=plan.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
