from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_status_and_version():
    with TestClient(app) as client:  # runs the app in-process, no server needed
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["version"] == "0.1.0"
    assert isinstance(body["checks"], dict)


def test_every_response_carries_a_request_id():
    with TestClient(app) as client:
        response = client.get("/health")
    assert len(response.headers["X-Request-ID"]) == 32  # a fresh uuid4, as hex
