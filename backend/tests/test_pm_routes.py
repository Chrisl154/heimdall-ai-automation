"""
Tests for GET/POST /api/pm/* — PM control, chat, approvals, and utility endpoints.
"""
from unittest.mock import AsyncMock, patch

import pytest


# ── GET /api/pm/status ────────────────────────────────────────────────────────

class TestStatusEndpoint:
    def test_returns_200(self, test_client):
        assert test_client.get("/api/pm/status").status_code == 200

    def test_response_has_required_fields(self, test_client):
        body = test_client.get("/api/pm/status").json()
        for field in ("running", "current_task_id", "tasks_pending",
                      "tasks_completed", "tasks_failed", "uptime_seconds"):
            assert field in body, f"missing field: {field}"

    def test_running_is_bool(self, test_client):
        body = test_client.get("/api/pm/status").json()
        assert isinstance(body["running"], bool)

    def test_task_counts_are_ints(self, test_client):
        body = test_client.get("/api/pm/status").json()
        assert isinstance(body["tasks_pending"], int)
        assert isinstance(body["tasks_completed"], int)
        assert isinstance(body["tasks_failed"], int)


# ── POST /api/pm/start and /stop ──────────────────────────────────────────────

class TestStartStop:
    def test_start_returns_200_and_status(self, test_client):
        with patch("core.pm_engine.PMEngine.start", new=AsyncMock()):
            resp = test_client.post("/api/pm/start")
        assert resp.status_code == 200
        assert "running" in resp.json()

    def test_stop_returns_200_and_status(self, test_client):
        with patch("core.pm_engine.PMEngine.stop", new=AsyncMock()):
            resp = test_client.post("/api/pm/stop")
        assert resp.status_code == 200
        assert "running" in resp.json()

    def test_start_sets_running_true(self, test_client):
        from core.pm_engine import get_pm
        with patch("core.pm_engine.PMEngine.start", new=AsyncMock()) as mock_start:
            resp = test_client.post("/api/pm/start")
        # start() was called exactly once
        mock_start.assert_called_once()

    def test_stop_calls_stop_once(self, test_client):
        with patch("core.pm_engine.PMEngine.stop", new=AsyncMock()) as mock_stop:
            test_client.post("/api/pm/stop")
        mock_stop.assert_called_once()


# ── POST /api/pm/chat ─────────────────────────────────────────────────────────

class TestChatEndpoint:
    def test_returns_200_with_reply(self, test_client):
        with patch("core.pm_engine.PMEngine.chat", new=AsyncMock(return_value="Hello from PM")):
            resp = test_client.post("/api/pm/chat", json={"message": "Hi", "session_id": "s1"})
        assert resp.status_code == 200
        assert resp.json()["reply"] == "Hello from PM"

    def test_reply_contains_session_id(self, test_client):
        with patch("core.pm_engine.PMEngine.chat", new=AsyncMock(return_value="ok")):
            resp = test_client.post("/api/pm/chat", json={"message": "test", "session_id": "abc"})
        assert resp.json()["session_id"] == "abc"

    def test_missing_message_returns_422(self, test_client):
        resp = test_client.post("/api/pm/chat", json={"session_id": "s1"})
        assert resp.status_code == 422


# ── POST /api/pm/chat/direct ──────────────────────────────────────────────────

class TestDirectChat:
    def test_unknown_provider_returns_400(self, test_client):
        resp = test_client.post("/api/pm/chat/direct", json={
            "message": "hi", "model": "x", "provider": "bogus", "session_id": "s1"
        })
        assert resp.status_code == 400

    def test_cloud_provider_without_api_key_returns_400(self, test_client):
        # No anthropic_key in vault → 400
        resp = test_client.post("/api/pm/chat/direct", json={
            "message": "hi", "model": "claude-sonnet-4-6",
            "provider": "anthropic", "session_id": "s1"
        })
        assert resp.status_code == 400

    def test_ollama_provider_calls_llm(self, test_client):
        async def fake_call_llm(*args, **kwargs):
            return ("mocked reply", {"input_tokens": 1, "output_tokens": 1})

        with patch("core.routes.pm.call_llm", side_effect=fake_call_llm):
            resp = test_client.post("/api/pm/chat/direct", json={
                "message": "hello", "model": "qwen2.5:7b",
                "provider": "ollama", "session_id": "s1"
            })
        assert resp.status_code == 200
        assert resp.json()["reply"] == "mocked reply"

    def test_llm_error_surfaces_as_502(self, test_client):
        from core.llm_providers import LLMError

        async def fail(*args, **kwargs):
            raise LLMError("connection refused")

        with patch("core.routes.pm.call_llm", side_effect=fail):
            resp = test_client.post("/api/pm/chat/direct", json={
                "message": "hi", "model": "qwen2.5:7b",
                "provider": "ollama", "session_id": "s1"
            })
        assert resp.status_code == 502


# ── POST /api/pm/tasks/{id}/approve-commit and /decline-commit ───────────────

class TestApproveDeclineCommit:
    def test_approve_unknown_task_returns_404(self, test_client):
        resp = test_client.post("/api/pm/tasks/nonexistent/approve-commit")
        assert resp.status_code == 404

    def test_decline_unknown_task_returns_404(self, test_client):
        resp = test_client.post("/api/pm/tasks/nonexistent/decline-commit")
        assert resp.status_code == 404

    def test_approve_pending_task_returns_200(self, test_client):
        from core.pm_engine import get_pm
        from core.models import Task, TaskStatus

        pm = get_pm()
        fake_task = Task(
            id="task-approve-test",
            title="Approve test",
            description="d",
            priority="medium",
            status=TaskStatus.COMPLETED,
            created_at="2026-01-01",
        )
        pm._pending_approvals["task-approve-test"] = (fake_task, "output content")

        with patch("core.pm_engine.PMEngine._maybe_commit", new=AsyncMock()):
            resp = test_client.post("/api/pm/tasks/task-approve-test/approve-commit")
        assert resp.status_code == 200
        assert resp.json()["status"] == "committed"


# ── Utility endpoints ─────────────────────────────────────────────────────────

class TestUtilityEndpoints:
    def test_pending_approvals_returns_list(self, test_client):
        body = test_client.get("/api/pm/pending-approvals").json()
        assert "approvals" in body
        assert isinstance(body["approvals"], list)

    def test_claude_usage_returns_dict(self, test_client):
        resp = test_client.get("/api/pm/claude-usage")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_chat_history_returns_list(self, test_client):
        body = test_client.get("/api/pm/chat/history").json()
        assert "messages" in body
        assert isinstance(body["messages"], list)

    def test_conversation_returns_list(self, test_client):
        body = test_client.get("/api/pm/conversation").json()
        assert "entries" in body
        assert isinstance(body["entries"], list)

    def test_conversation_respects_limit_param(self, test_client):
        resp = test_client.get("/api/pm/conversation?limit=5")
        assert resp.status_code == 200
