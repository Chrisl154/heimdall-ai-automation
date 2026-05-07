"""Tests for the Bearer-token authentication middleware."""
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient


@pytest.fixture
def authed_client(monkeypatch, tmp_path):
    """TestClient with HEIMDALL_API_TOKEN set — auth enforced."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HEIMDALL_VAULT_KEY", key)
    monkeypatch.setenv("HEIMDALL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HEIMDALL_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))
    monkeypatch.setenv("HEIMDALL_API_TOKEN", "super-secret-token")

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
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client


class TestMissingToken:
    def test_missing_header_returns_401(self, authed_client):
        resp = authed_client.get("/api/tasks")
        assert resp.status_code == 401

    def test_wrong_token_returns_401(self, authed_client):
        resp = authed_client.get("/api/tasks", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401

    def test_malformed_bearer_returns_401(self, authed_client):
        resp = authed_client.get("/api/tasks", headers={"Authorization": "Token super-secret-token"})
        assert resp.status_code == 401


class TestValidToken:
    def test_correct_token_accepted(self, authed_client):
        resp = authed_client.get("/api/tasks", headers={"Authorization": "Bearer super-secret-token"})
        assert resp.status_code == 200

    def test_pm_status_requires_token(self, authed_client):
        assert authed_client.get("/api/pm/status").status_code == 401
        resp = authed_client.get("/api/pm/status", headers={"Authorization": "Bearer super-secret-token"})
        assert resp.status_code == 200


class TestDevMode:
    def test_no_token_env_allows_all_requests(self, test_client):
        """When HEIMDALL_API_TOKEN is unset, every request is permitted."""
        resp = test_client.get("/api/tasks")
        assert resp.status_code == 200

    def test_setup_routes_always_public(self, authed_client):
        """Setup endpoints must be reachable without a token at all times."""
        resp = authed_client.get("/api/setup/status")
        assert resp.status_code == 200

    def test_generate_key_always_public(self, authed_client):
        resp = authed_client.get("/api/setup/generate-key")
        assert resp.status_code == 200
