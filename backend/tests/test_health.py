from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_provider_configuration_without_exposing_credentials() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["model_provider"] == "gemini"
    assert "model_configured" in response.json()
    assert "gemini_api_key" not in response.json()
