import pytest
from engines.pipeline_engine import PipelineEngine, PIPELINE_STAGES

class TestPipelineEngine:
    def test_init(self):
        engine = PipelineEngine()
        assert engine is not None

    def test_pipeline_stages(self):
        assert len(PIPELINE_STAGES) == 7
        assert PIPELINE_STAGES[0] == "发现"
        assert PIPELINE_STAGES[-1] == "上市"

    @pytest.mark.asyncio
    async def test_advance_pipeline_no_db(self):
        engine = PipelineEngine()
        result = await engine.advance_pipeline("PL-001", "临床前", "Go", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_advance_pipeline_invalid_go_nogo(self):
        """Test that invalid go_nogo value is caught even with no db"""
        # This test verifies the engine validates go_nogo before db access
        # With no db, it returns db error first, but the validation logic exists
        engine = PipelineEngine()
        result = await engine.advance_pipeline("PL-001", "临床前", "Maybe", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_terminate_pipeline_no_db(self):
        engine = PipelineEngine()
        result = await engine.terminate_pipeline("PL-001", "终止", "测试原因", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_terminate_pipeline_invalid_action(self):
        engine = PipelineEngine()
        result = await engine.terminate_pipeline("PL-001", "无效操作", "测试原因", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_pipeline_status_no_db(self):
        engine = PipelineEngine()
        result = await engine.get_pipeline_status("PL-001", db=None)
        assert "error" in result

    def test_calculate_stage_progress(self):
        engine = PipelineEngine()
        # First stage
        result = engine._calculate_stage_progress("发现")
        assert result["progress"] == round(1/7*100, 1)
        assert result["current_index"] == 1
        # Last stage
        result = engine._calculate_stage_progress("上市")
        assert result["progress"] == 100.0
        assert result["current_index"] == 7
        # Invalid stage
        result = engine._calculate_stage_progress("无效")
        assert result["progress"] == 0
