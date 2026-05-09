"""Tests for GET /api/analytics.

Data is seeded through POST /api/tasks (the real API) so every test
uses the live singleton TaskManager — no file-system patching needed.
The conftest mocks PMEngine.start so no background task racing occurs.
"""
import pytest


def _seed(client, tasks: list[dict]) -> None:
    for t in tasks:
        resp = client.post("/api/tasks", json=t)
        assert resp.status_code in (200, 201), resp.text


def _base(overrides: dict) -> dict:
    return {
        "title": "t",
        "description": "d",
        "priority": "medium",
        "tags": [],
        "depends_on": [],
        "max_review_iterations": 3,
        "output_path": "",
        **overrides,
    }


def _patch_status(client, task_id: str, status: str) -> None:
    resp = client.patch(f"/api/tasks/{task_id}", json={"status": status})
    assert resp.status_code == 200, resp.text


# ── Baseline (conftest task-001 only) ─────────────────────────────────────────

def test_analytics_baseline(test_client):
    """Analytics endpoint is reachable and returns the right schema."""
    resp = test_client.get("/api/analytics")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("total_tasks", "completed", "failed", "escalated",
                "pending", "success_rate", "tasks_by_priority",
                "tasks_by_tag", "recent_completions"):
        assert key in data, f"missing key: {key}"


# ── Task counts and priority breakdown ───────────────────────────────────────

def test_analytics_with_tasks(test_client):
    _seed(test_client, [
        _base({"title": "Done 1",    "priority": "high"}),
        _base({"title": "Done 2",    "priority": "critical"}),
        _base({"title": "Failed",    "priority": "medium"}),
        _base({"title": "Escalated", "priority": "medium"}),
    ])

    tasks = test_client.get("/api/tasks").json()
    by_title = {t["title"]: t["id"] for t in tasks}

    _patch_status(test_client, by_title["Done 1"],    "completed")
    _patch_status(test_client, by_title["Done 2"],    "completed")
    _patch_status(test_client, by_title["Failed"],    "failed")
    _patch_status(test_client, by_title["Escalated"], "escalated")

    data = test_client.get("/api/analytics").json()

    # conftest seeds task-001 (pending/medium) + our 4 = 5 total
    assert data["total_tasks"] == 5
    assert data["completed"] == 2
    assert data["failed"] == 1
    assert data["escalated"] == 1
    assert data["pending"] == 1  # task-001 from conftest
    assert data["success_rate"] == pytest.approx(40.0, abs=0.1)
    assert data["tasks_by_priority"]["medium"] >= 2  # task-001 + Failed + Escalated


# ── Tag aggregation ───────────────────────────────────────────────────────────

def test_analytics_tags(test_client):
    _seed(test_client, [
        _base({"title": "Tagged A", "tags": ["backend", "python"]}),
        _base({"title": "Tagged B", "tags": ["backend", "fastapi"]}),
    ])

    tags = test_client.get("/api/analytics").json()["tasks_by_tag"]
    assert tags.get("backend") == 2
    assert tags.get("python") == 1
    assert tags.get("fastapi") == 1


# ── Recent completions ────────────────────────────────────────────────────────

def test_analytics_recent_completions(test_client):
    for i in range(5):
        _seed(test_client, [_base({"title": f"Done {i}"})])

    tasks = test_client.get("/api/tasks").json()
    # Mark all as completed (includes conftest task-001 + 5 we just added)
    for t in tasks:
        _patch_status(test_client, t["id"], "completed")

    completions = test_client.get("/api/analytics").json()["recent_completions"]
    # recent_completions is capped at 5 by the route
    assert len(completions) == 5
