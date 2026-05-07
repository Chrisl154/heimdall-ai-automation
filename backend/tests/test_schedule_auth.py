"""Verify that all scheduler endpoints require a valid Bearer token."""
import pytest

from tests.helpers import AUTH_TOKEN, auth_header, make_authed_client

_CREATE_BODY = {
    "cron": "0 9 * * 1",
    "title": "Weekly report",
    "description": "Generate weekly status report",
    "priority": "medium",
    "tags": ["report"],
    "depends_on": [],
    "max_review_iterations": 2,
    "output_path": "",
}


@pytest.fixture
def sched_client(monkeypatch, tmp_path):
    with make_authed_client(monkeypatch, tmp_path) as client:
        yield client


# ── Unauthenticated requests must be rejected ─────────────────────────────────

class TestScheduleRequiresAuth:
    def test_list_unauthenticated(self, sched_client):
        assert sched_client.get("/api/schedule").status_code == 401

    def test_create_unauthenticated(self, sched_client):
        assert sched_client.post("/api/schedule", json=_CREATE_BODY).status_code == 401

    def test_update_unauthenticated(self, sched_client):
        assert sched_client.patch("/api/schedule/fake-id", json={"enabled": False}).status_code == 401

    def test_delete_unauthenticated(self, sched_client):
        assert sched_client.delete("/api/schedule/fake-id").status_code == 401


# ── Authenticated requests must succeed ───────────────────────────────────────

class TestScheduleAuthenticatedAccess:
    def test_list_returns_empty_array(self, sched_client):
        resp = sched_client.get("/api/schedule", headers=auth_header())
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_persists_schedule(self, sched_client):
        resp = sched_client.post("/api/schedule", json=_CREATE_BODY, headers=auth_header())
        assert resp.status_code in (200, 201)
        assert resp.json()["cron"] == _CREATE_BODY["cron"]

    def test_created_schedule_appears_in_list(self, sched_client):
        sched_client.post("/api/schedule", json=_CREATE_BODY, headers=auth_header())
        items = sched_client.get("/api/schedule", headers=auth_header()).json()
        assert any(s["cron"] == _CREATE_BODY["cron"] for s in items)
