from fastapi.testclient import TestClient

import app.api.health as health_module
from app.main import app, create_app


def test_health_checks_the_database_workers_and_library(database):
    with TestClient(app) as client:  # `with` runs startup: tables, then the pool
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["workers_alive"] == 0  # no worker runs in this test
    assert body["status"] == "degraded"  # the API works, but reports would wait for a worker
    assert body["version"] == "0.1.0"


def test_health_is_503_when_the_database_is_down(monkeypatch):
    async def database_down(_pool) -> bool:
        return False

    monkeypatch.setattr(health_module, "database_is_up", database_down)
    monkeypatch.setattr(health_module, "get_pool", lambda: None)
    client = TestClient(create_app())  # no `with`: startup doesn't run, no database needed
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert response.json()["checks"]["database"] == "unreachable"


def test_every_response_carries_a_request_id(database):
    with TestClient(app) as client:
        response = client.get("/health")
    assert len(response.headers["X-Request-ID"]) == 32  # a fresh uuid4, as hex
