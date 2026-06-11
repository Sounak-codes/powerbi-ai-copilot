"""
Unit tests for the main application.
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestChatEndpoints:
    """Test chat endpoints."""

    def test_create_session(self):
        """Test session creation."""
        response = client.post("/api/chat/session?user_id=test_user")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["user_id"] == "test_user"

    def test_get_session(self):
        """Test getting session."""
        # Create session first
        create_resp = client.post("/api/chat/session?user_id=test_user")
        session_id = create_resp.json()["session_id"]

        # Get session
        response = client.get(f"/api/chat/session/{session_id}")
        assert response.status_code == 200
        assert response.json()["session_id"] == session_id


class TestIntentClassification:
    """Test intent classification."""

    @pytest.mark.asyncio
    async def test_intent_classifier(self):
        """Test intent classifier."""
        from intent_engine.classifier import IntentClassifier

        classifier = IntentClassifier()
        intent = await classifier.classify("What is the average sales?")

        assert intent is not None
        assert intent.confidence > 0


class TestAnalyticsEngine:
    """Test analytics engine."""

    @pytest.mark.asyncio
    async def test_insight_generator(self):
        """Test insight generator."""
        from analytics_engine.insight_generator import InsightGenerator

        generator = InsightGenerator()
        insights = await generator.generate_insights(data={"test": "data"})

        assert isinstance(insights, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
