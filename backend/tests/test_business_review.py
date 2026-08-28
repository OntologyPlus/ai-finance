import pytest
from engines.business_review_engine import BusinessReviewEngine

class TestBusinessReviewEngine:
    def test_init(self):
        engine = BusinessReviewEngine()
        assert engine is not None
        assert engine.engine_name == "business_review"
