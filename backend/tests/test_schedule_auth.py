"""Verify that all scheduler endpoints require a valid Bearer token."""
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

TOKEN = "sched-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def sched_client(monkeypatch, tmp_path):
    """TestClient with auth enabled and an isolated schedules data dir."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HEIMDALL_VAULT_KEY", key)
    monkeypatch.setenv("HEIMDALL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HEIMDALL_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))
    monkeypatch.setenv("HEIMDALL_API_TOKEN", TOKEN)

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "completed").mkdir(exist_ok=True)
    (tasks_dir / "backlog.yaml").write_text("[]", encoding="utf-8")

    import core.vault as vault_mod
    import core.pm_engine as pm_mod
    import core.task_manager as tm_mod
    vault_mod._vault = None
    pm_mod._pm = None
    tm_mod._task_manager = None

    with (
        patch("core.messaging.manager.MessagingManager.start_all", new=AsyncMock()),
        patch("core.messaging.manager.MessagingManager.stop_all", new=AsyncMock()),
        patch("core.pm_engine.PMEngine.stop", new=AsyncMock()),
    ):
        from main import app
        with TestClient(app) as client:
            yield client


class TestScheduleRequiresAuth:
    def test_list_unauthenticated(self, sched_client):
        assert sched_client.get("/api/schedule").status_code == 401

    def test_create_unauthenticated(self, sched_client):
        body = {
            "cron": "0 * * * *",
            "title": "Hourly check",
            "description": "Run every hour",
            "priority": "low",
            "tags": [],
            "depends_on": [],
            "max_review_iterations": 1,
            "output_path": "",
        }
        assert sched_client.post("/api/schedule", json=body).status_code == 401

    def test_update_unauthenticated(self, sched_client):
        assert sched_client.patch("/api/schedule/fake-id", json={"enabled": False}).status_code == 401

    def test_delete_unauthenticated(self, sched_client):
        assert sched_client.delete("/api/schedule/fake-id").status_code == 401

    def test_list_authenticated(self, sched_client):
        resp = sched_client.get("/api/schedule", headers=AUTH)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_authenticated(self, sched_client):
        body = {
            "cron": "0 9 * * 1",
            "title": "Weekly report",
            "description": "Generate weekly status report",
            "priority": "medium",
            "tags": ["report"],
            "depends_on": [],
            "max_review_iterations": 2,
            "output_path": "",
        }
        resp = sched_client.post("/api/schedule", json=body, headers=AUTH)
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["cron"] == "0 9 * * 1"
