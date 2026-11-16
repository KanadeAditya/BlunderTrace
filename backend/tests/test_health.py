from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    with TestClient(app) as client:  # runs the app in-process, no server needed
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
