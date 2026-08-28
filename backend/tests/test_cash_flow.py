import pytest
from engines.cash_flow_engine import CashFlowEngine


class TestCashFlowEngine:
    def test_init(self):
        engine = CashFlowEngine()
        assert engine is not None

    def test_parse_period(self):
        engine = CashFlowEngine()
        year, month = engine._parse_period("2024-06")
        assert year == 2024
        assert month == 6

    @pytest.mark.asyncio
    async def test_forecast_no_db(self):
        engine = CashFlowEngine()
        result = await engine.forecast_cash_flow("2024-06", horizon_months=3, db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_liquidity_check_no_db(self):
        engine = CashFlowEngine()
        result = await engine.check_liquidity_gap("2024-06", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_profit_cash_gap_no_db(self):
        engine = CashFlowEngine()
        result = await engine.analyze_profit_cash_gap("2024-06", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_match_receipt_payment_no_db(self):
        engine = CashFlowEngine()
        result = await engine.match_receipt_payment("2024-06", db=None)
        assert "error" in result
