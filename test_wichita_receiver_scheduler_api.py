import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from wichita_receiver_scheduler_routes import router as receiver_scheduler_router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(receiver_scheduler_router)
    return TestClient(app)


def test_scheduler_health_always_visible():
    client = _client()
    r = client.get("/api/receiver-scheduler/health")
    assert r.status_code == 200
    body = r.json()
    assert body["receive_only"] is True
    assert "enabled" in body


def test_scheduler_plan_disabled_by_default():
    os.environ.pop("WICHITA_RECEIVER_SCHEDULER_ENABLED", None)
    client = _client()
    r = client.get("/api/receiver-scheduler/plan")
    assert r.status_code == 404
