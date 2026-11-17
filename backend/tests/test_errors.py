from typing import Literal

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api import AppError
from app.main import create_app


class Body(BaseModel):
    games: Literal[10, 20, 30, 50]


@pytest.fixture
def client() -> TestClient:
    app = create_app()

    @app.post("/echo")
    async def echo(body: Body) -> dict:
        return {"games": body.games}

    @app.get("/missing-report")
    async def missing() -> dict:
        raise AppError(404, "report_not_found", "No report with that id.")

    @app.get("/crash")
    async def crash() -> dict:
        raise RuntimeError("database password is hunter2")  # must never reach the visitor

    return TestClient(app)


def test_invalid_input_uses_our_shape(client):
    response = client.post("/echo", json={"games": 7})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_input"
    assert body["detail"].startswith("games:")


def test_app_error_uses_our_shape(client):
    response = client.get("/missing-report")
    assert response.status_code == 404
    assert response.json() == {"error": "report_not_found", "detail": "No report with that id."}


def test_unknown_url_uses_our_shape(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_crash_is_a_short_500_without_internals(client):
    response = client.get("/crash")
    assert response.status_code == 500
    assert response.json()["error"] == "internal_error"
    assert "hunter2" not in response.text
    assert "X-Request-ID" in response.headers


def test_a_safe_incoming_request_id_is_kept(client):
    response = client.get("/missing-report", headers={"X-Request-ID": "trace-abc_123"})
    assert response.headers["X-Request-ID"] == "trace-abc_123"


def test_an_unsafe_incoming_request_id_is_replaced(client):
    response = client.get("/missing-report", headers={"X-Request-ID": 'x"} {"level":"fake'})
    assert response.headers["X-Request-ID"] != 'x"} {"level":"fake'
    assert len(response.headers["X-Request-ID"]) == 32
