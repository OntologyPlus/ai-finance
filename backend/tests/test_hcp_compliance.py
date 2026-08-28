import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from engines.hcp_compliance_engine import HCPComplianceEngine
from models.hcp_compliance import HCP, HCPInteraction, HCPPayment


class TestHCPComplianceEngine:
    def test_init(self):
        engine = HCPComplianceEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_verify_hcp_no_db(self):
        engine = HCPComplianceEngine()
        result = await engine.verify_hcp("HCP-001", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_check_payment_limit_no_db(self):
        engine = HCPComplianceEngine()
        result = await engine.check_payment_limit("HCP-001", 10000, db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_analyze_aggregate_risk_no_db(self):
        engine = HCPComplianceEngine()
        result = await engine.analyze_aggregate_risk("HCP-001", "2026", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_check_interaction_compliance_no_db(self):
        engine = HCPComplianceEngine()
        result = await engine.check_interaction_compliance(1, db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_verify_hcp_not_found(self):
        engine = HCPComplianceEngine()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        result = await engine.verify_hcp("HCP-999", db=mock_db)
        assert result["verified"] is False
        assert "不存在" in result["error"]

    @pytest.mark.asyncio
    async def test_verify_hcp_success(self):
        engine = HCPComplianceEngine()
        mock_db = AsyncMock()
        hcp = HCP(
            hcp_id="HCP-001",
            name="测试医生",
            institution="测试医院",
            department="内科",
            specialty="心血管",
            verification_status="待验证",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = hcp
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        result = await engine.verify_hcp("HCP-001", db=mock_db)
        assert result["verified"] is True
        assert result["verification_status"] == "已验证"
        assert all(c["passed"] for c in result["checks"])

    @pytest.mark.asyncio
    async def test_verify_hcp_incomplete_info(self):
        engine = HCPComplianceEngine()
        mock_db = AsyncMock()
        hcp = HCP(
            hcp_id="HCP-002",
            name="测试医生",
            institution="",
            department="",
            specialty="",
            verification_status="待验证",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = hcp
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()

        result = await engine.verify_hcp("HCP-002", db=mock_db)
        assert result["verified"] is False
        assert result["verification_status"] == "验证失败"

    @pytest.mark.asyncio
    async def test_check_payment_limit_unverified(self):
        engine = HCPComplianceEngine()
        mock_db = AsyncMock()
        hcp = HCP(
            hcp_id="HCP-003",
            name="未验证医生",
            verification_status="待验证",
            annual_payment_total=10000,
            payment_limit=50000,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = hcp
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await engine.check_payment_limit("HCP-003", 5000, db=mock_db)
        assert result["can_pay"] is False
        assert "HR-026" in result["reason"]

    @pytest.mark.asyncio
    async def test_check_payment_limit_within(self):
        engine = HCPComplianceEngine()
        mock_db = AsyncMock()
        hcp = HCP(
            hcp_id="HCP-001",
            name="已验证医生",
            verification_status="已验证",
            annual_payment_total=30000,
            payment_limit=50000,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = hcp
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await engine.check_payment_limit("HCP-001", 10000, db=mock_db)
        assert result["can_pay"] is True
        assert result["projected_total"] == 40000
        assert result["remaining_limit"] == 20000

    @pytest.mark.asyncio
    async def test_check_payment_limit_exceed(self):
        engine = HCPComplianceEngine()
        mock_db = AsyncMock()
        hcp = HCP(
            hcp_id="HCP-001",
            name="已验证医生",
            verification_status="已验证",
            annual_payment_total=48000,
            payment_limit=50000,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = hcp
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await engine.check_payment_limit("HCP-001", 5000, db=mock_db)
        assert result["can_pay"] is False
        assert result["exceed_amount"] == 3000
        assert "HR-027" in result["reason"]

    def test_assess_frequency_risk(self):
        engine = HCPComplianceEngine()
        assert engine._assess_frequency_risk(3)["level"] == "低"
        assert engine._assess_frequency_risk(8)["level"] == "中"
        assert engine._assess_frequency_risk(15)["level"] == "高"
        assert engine._assess_frequency_risk(30)["level"] == "极高"

    def test_assess_amount_risk(self):
        engine = HCPComplianceEngine()
        assert engine._assess_amount_risk(20000, 50000)["level"] == "低"
        assert engine._assess_amount_risk(35000, 50000)["level"] == "中"
        assert engine._assess_amount_risk(45000, 50000)["level"] == "高"
        assert engine._assess_amount_risk(55000, 50000)["level"] == "极高"

    def test_calculate_risk_score(self):
        engine = HCPComplianceEngine()
        # 无违规
        score = engine._calculate_risk_score(0, 0, False)
        assert score == 0
        # 有HR-029违规
        score = engine._calculate_risk_score(30, 30, True)
        assert score == 50  # (30+30)/2 + 20

    def test_risk_level(self):
        engine = HCPComplianceEngine()
        assert engine._risk_level(10) == "低风险"
        assert engine._risk_level(30) == "中风险"
        assert engine._risk_level(60) == "高风险"
        assert engine._risk_level(85) == "极高风险"
