"""
Tests for GET /api/config/agents and PATCH /api/config/agents/{name}.
"""
import yaml
import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

_DEFAULT_SETTINGS = {
    "agents": {
        "worker": {
            "model": "qwen2.5-coder:7b",
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "temperature": 0.2,
            "max_tokens": 4096,
        },
        "reviewer": {
            "model": "claude-sonnet-4-6",
            "provider": "anthropic",
            "base_url": None,
            "temperature": 0.1,
            "max_tokens": 2048,
        },
        "orchestrator": {
            "model": "gemma3:12b",
            "provider": "lmstudio",
            "base_url": "http://localhost:1234",
            "temperature": 0.3,
            "max_tokens": 2048,
        },
    }
}


@pytest.fixture
def client_with_config(test_client, tmp_path):
    """
    test_client fixture with a valid settings.yaml pre-written into the
    HEIMDALL_CONFIG_DIR (tmp_path).  Returns the TestClient.
    """
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(
        yaml.dump(_DEFAULT_SETTINGS, allow_unicode=True),
        encoding="utf-8",
    )
    from core.config import load_config
    load_config.cache_clear()
    return test_client


# ── GET /api/config/agents ────────────────────────────────────────────────────

class TestGetAgents:
    def test_returns_200_when_settings_exist(self, client_with_config):
        resp = client_with_config.get("/api/config/agents")
        assert resp.status_code == 200

    def test_response_has_all_three_agents(self, client_with_config):
        body = client_with_config.get("/api/config/agents").json()
        assert set(body.keys()) == {"worker", "reviewer", "orchestrator"}

    def test_each_agent_has_required_fields(self, client_with_config):
        body = client_with_config.get("/api/config/agents").json()
        for role in ("worker", "reviewer", "orchestrator"):
            agent = body[role]
            assert "model" in agent
            assert "provider" in agent
            assert "temperature" in agent
            assert "max_tokens" in agent

    def test_returns_correct_values(self, client_with_config):
        body = client_with_config.get("/api/config/agents").json()
        assert body["worker"]["model"] == "qwen2.5-coder:7b"
        assert body["reviewer"]["provider"] == "anthropic"

    def test_returns_404_when_no_settings_file(self, test_client):
        # test_client has no settings.yaml in its tmp_path
        resp = test_client.get("/api/config/agents")
        assert resp.status_code == 404


# ── PATCH /api/config/agents/{name} ──────────────────────────────────────────

class TestPatchAgent:
    def test_patch_model_returns_200(self, client_with_config):
        resp = client_with_config.patch(
            "/api/config/agents/worker",
            json={"model": "qwen3:8b"},
        )
        assert resp.status_code == 200

    def test_patch_model_persists_to_get(self, client_with_config):
        client_with_config.patch("/api/config/agents/worker", json={"model": "qwen3:8b"})
        body = client_with_config.get("/api/config/agents").json()
        assert body["worker"]["model"] == "qwen3:8b"

    def test_patch_temperature_persists(self, client_with_config):
        client_with_config.patch("/api/config/agents/reviewer", json={"temperature": 0.9})
        body = client_with_config.get("/api/config/agents").json()
        assert body["reviewer"]["temperature"] == pytest.approx(0.9)

    def test_patch_invalid_agent_name_returns_400(self, client_with_config):
        resp = client_with_config.patch(
            "/api/config/agents/nonexistent",
            json={"model": "x"},
        )
        assert resp.status_code == 400

    def test_patch_returns_updated_agent(self, client_with_config):
        resp = client_with_config.patch(
            "/api/config/agents/orchestrator",
            json={"max_tokens": 8192},
        )
        body = resp.json()
        assert body["max_tokens"] == 8192
