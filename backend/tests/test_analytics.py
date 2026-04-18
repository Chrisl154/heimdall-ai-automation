"""Tests for GET /api/analytics."""
import pytest


def test_analytics_empty(test_client, tmp_path):
    # Overwrite the backlog with an empty list so there are no tasks
    (tmp_path / "tasks" / "backlog.yaml").write_text("[]", encoding="utf-8")

    response = test_client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tasks"] == 0
    assert data["completed"] == 0
    assert data["failed"] == 0
    assert data["escalated"] == 0
    assert data["pending"] == 0
    assert data["success_rate"] == 0.0


def test_analytics_with_tasks(test_client, tmp_path):
    # Write a backlog with known statuses
    (tmp_path / "tasks" / "backlog.yaml").write_text(
        """\
- id: t-pending
  title: "Pending"
  description: ""
  priority: low
  status: pending
  created_at: "2026-04-18"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 0
  output_path: ""

- id: t-completed-1
  title: "Done 1"
  description: ""
  priority: high
  status: completed
  created_at: "2026-04-18"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 2
  output_path: ""

- id: t-completed-2
  title: "Done 2"
  description: ""
  priority: critical
  status: completed
  created_at: "2026-04-18"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 1
  output_path: ""

- id: t-failed
  title: "Failed"
  description: ""
  priority: medium
  status: failed
  created_at: "2026-04-18"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 3
  output_path: ""

- id: t-escalated
  title: "Escalated"
  description: ""
  priority: medium
  status: escalated
  created_at: "2026-04-18"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 3
  output_path: ""
""",
        encoding="utf-8",
    )

    response = test_client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()

    assert data["total_tasks"] == 5
    assert data["completed"] == 2
    assert data["failed"] == 1
    assert data["escalated"] == 1
    assert data["pending"] == 1

    # success_rate = completed / total_tasks * 100
    assert data["success_rate"] == pytest.approx(40.0, abs=0.1)

    assert data["tasks_by_priority"]["low"] == 1
    assert data["tasks_by_priority"]["medium"] == 2
    assert data["tasks_by_priority"]["high"] == 1
    assert data["tasks_by_priority"]["critical"] == 1


def test_analytics_tags(test_client, tmp_path):
    (tmp_path / "tasks" / "backlog.yaml").write_text(
        """\
- id: tag-1
  title: "Tagged A"
  description: ""
  priority: medium
  status: pending
  created_at: "2026-04-18"
  tags: ["backend", "python"]
  depends_on: []
  max_review_iterations: 3
  current_iteration: 0
  output_path: ""

- id: tag-2
  title: "Tagged B"
  description: ""
  priority: medium
  status: pending
  created_at: "2026-04-18"
  tags: ["backend", "fastapi"]
  depends_on: []
  max_review_iterations: 3
  current_iteration: 0
  output_path: ""
""",
        encoding="utf-8",
    )

    response = test_client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()

    tags = data["tasks_by_tag"]
    assert tags.get("backend") == 2
    assert tags.get("python") == 1
    assert tags.get("fastapi") == 1


def test_analytics_recent_completions(test_client, tmp_path):
    tasks_yaml = ""
    for i in range(5):
        tasks_yaml += f"""\
- id: done-{i}
  title: "Completed Task {i}"
  description: ""
  priority: medium
  status: completed
  created_at: "2026-04-18"
  completed_at: "2026-04-18T1{i}:00:00Z"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 1
  output_path: ""

"""
    (tmp_path / "tasks" / "backlog.yaml").write_text(tasks_yaml, encoding="utf-8")

    response = test_client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()

    completions = data["recent_completions"]
    assert len(completions) <= 10
    assert len(completions) == 5
    ids = {c["id"] for c in completions}
    for i in range(5):
        assert f"done-{i}" in ids
