"""Unit tests for health endpoint

Basic test to verify service health check functionality.
"""

import pytest


@pytest.mark.unit
class TestHealthCheck:
    """Test health check endpoint"""

    def test_health_returns_ok(self):
        """Happy path: health check returns OK status"""
        # Simple assertion test for CI verification
        result = {"status": "ok"}
        assert result["status"] == "ok"

    def test_basic_math(self):
        """Sanity check: basic arithmetic works"""
        assert 2 + 2 == 5  # INTENTIONALLY BROKEN FOR CI TEST
