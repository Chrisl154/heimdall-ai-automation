"""Integration tests for /api/webhooks endpoints."""
import pytest


class TestListWebhooks:
    def test_empty_by_default(self, test_client):
        resp = test_client.get("/api/webhooks")
        assert resp.status_code == 200
        assert resp.json() == {"webhooks": []}


class TestAddWebhook:
    def test_add_returns_201(self, test_client):
        body = {"url": "https://example.com/hook", "events": ["task_completed"], "enabled": True}
        resp = test_client.post("/api/webhooks", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://example.com/hook"
        assert data["enabled"] is True

    def test_added_webhook_appears_in_list(self, test_client):
        body = {"url": "https://hooks.example.com/a", "events": ["task_failed"], "enabled": True}
        test_client.post("/api/webhooks", json=body)
        resp = test_client.get("/api/webhooks")
        hooks = resp.json()["webhooks"]
        assert any(h["url"] == "https://hooks.example.com/a" for h in hooks)

    def test_secret_is_masked_in_list(self, test_client):
        body = {
            "url": "https://example.com/secret-hook",
            "secret": "my-webhook-secret",
            "events": [],
            "enabled": True,
        }
        test_client.post("/api/webhooks", json=body)
        hooks = test_client.get("/api/webhooks").json()["webhooks"]
        match = next(h for h in hooks if h["url"] == "https://example.com/secret-hook")
        assert match["secret"] == "***"


class TestUpdateWebhook:
    def test_update_enabled_flag(self, test_client):
        body = {"url": "https://example.com/upd", "events": [], "enabled": True}
        test_client.post("/api/webhooks", json=body)
        resp = test_client.patch("/api/webhooks/0", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_update_events(self, test_client):
        body = {"url": "https://example.com/ev", "events": ["task_completed"], "enabled": True}
        test_client.post("/api/webhooks", json=body)
        resp = test_client.patch("/api/webhooks/0", json={"events": ["task_failed", "task_escalated"]})
        assert resp.status_code == 200
        assert set(resp.json()["events"]) == {"task_failed", "task_escalated"}

    def test_update_out_of_range_returns_404(self, test_client):
        resp = test_client.patch("/api/webhooks/99", json={"enabled": False})
        assert resp.status_code == 404


class TestDeleteWebhook:
    def test_delete_returns_204(self, test_client):
        body = {"url": "https://example.com/del", "events": [], "enabled": True}
        test_client.post("/api/webhooks", json=body)
        resp = test_client.delete("/api/webhooks/0")
        assert resp.status_code == 204

    def test_deleted_hook_gone_from_list(self, test_client):
        body = {"url": "https://example.com/gone", "events": [], "enabled": True}
        test_client.post("/api/webhooks", json=body)
        test_client.delete("/api/webhooks/0")
        hooks = test_client.get("/api/webhooks").json()["webhooks"]
        assert not any(h["url"] == "https://example.com/gone" for h in hooks)

    def test_delete_out_of_range_returns_404(self, test_client):
        resp = test_client.delete("/api/webhooks/99")
        assert resp.status_code == 404
