"""Tests for the Bearer-token authentication middleware."""
import pytest
from fastapi.testclient import TestClient

from tests.helpers import AUTH_TOKEN, auth_header, make_authed_client


@pytest.fixture
def authed_client(monkeypatch, tmp_path):
    with make_authed_client(monkeypatch, tmp_path) as client:
        yield client


# ── Missing / wrong token ─────────────────────────────────────────────────────

class TestInvalidToken:
    def test_missing_header_returns_401(self, authed_client):
        assert authed_client.get("/api/tasks").status_code == 401

    def test_wrong_token_returns_401(self, authed_client):
        assert authed_client.get(
            "/api/tasks", headers={"Authorization": "Bearer wrong-token"}
        ).status_code == 401

    def test_malformed_bearer_prefix_returns_401(self, authed_client):
        # "Token …" instead of "Bearer …"
        assert authed_client.get(
            "/api/tasks", headers={"Authorization": f"Token {AUTH_TOKEN}"}
        ).status_code == 401


# ── Valid token ───────────────────────────────────────────────────────────────

class TestValidToken:
    def test_correct_token_accepted_on_tasks(self, authed_client):
        assert authed_client.get(
            "/api/tasks", headers=auth_header()
        ).status_code == 200

    def test_correct_token_accepted_on_pm_status(self, authed_client):
        assert authed_client.get(
            "/api/pm/status", headers=auth_header()
        ).status_code == 200

    def test_missing_token_on_pm_status_returns_401(self, authed_client):
        assert authed_client.get("/api/pm/status").status_code == 401


# ── Dev mode (no HEIMDALL_API_TOKEN set) ─────────────────────────────────────

class TestDevMode:
    def test_no_token_env_allows_all_requests(self, test_client):
        """test_client fixture blanks HEIMDALL_API_TOKEN → dev mode."""
        assert test_client.get("/api/tasks").status_code == 200

    def test_setup_routes_always_public(self, authed_client):
        assert authed_client.get("/api/setup/status").status_code == 200

    def test_generate_key_always_public(self, authed_client):
        assert authed_client.get("/api/setup/generate-key").status_code == 200
