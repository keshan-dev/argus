import pytest
from fastapi.testclient import TestClient
from app.main import app  # Adjust import based on your FastAPI app instance location

client = TestClient(app)

def test_get_member_insight_success():
    response = client.get("/api/members/member_123/insight?question=progress")
    assert response.status_code == 200
    data = response.json()
    assert data["member_id"] == "member_123"
    assert data["question"] == "progress"
    assert "sources" in data

def test_get_member_insight_invalid_question_422():
    response = client.get("/api/members/member_123/insight?question=invalid_type")
    assert response.status_code == 422

def test_get_member_insight_unauthorized_403():
    response = client.get("/api/members/unauthorized_member/insight?question=risks")
    assert response.status_code == 403

def test_get_team_overview_success():
    response = client.get("/api/teams/team_alpha/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["team_id"] == "team_alpha"
    assert data["overall_status"] in ["On Track", "Needs Attention", "Blocked", "Unknown"]