from fastapi.testclient import TestClient

from app.main import app


def test_workflow_start_preflight_accepts_loopback_frontend() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v1/workflows/start",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_workflow_start_preflight_accepts_dynamic_local_port() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v1/workflows/start",
        headers={
            "Origin": "http://localhost:3017",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization,x-request-id",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3017"
