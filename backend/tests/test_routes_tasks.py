"""Integration tests for /api/tasks REST endpoints."""
import pytest


class TestListTasks:
    def test_returns_list(self, test_client):
        response = test_client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(t["id"] == "task-001" for t in data)


class TestCreateTask:
    def test_create_valid_task_returns_201(self, test_client):
        response = test_client.post(
            "/api/tasks",
            json={"title": "New Task", "description": "A test task", "priority": "high"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Task"
        assert data["status"] == "pending"
        assert "id" in data

    def test_missing_title_returns_422(self, test_client):
        response = test_client.post(
            "/api/tasks",
            json={"description": "No title here", "priority": "medium"},
        )
        assert response.status_code == 422


class TestGetTask:
    def test_get_existing_task(self, test_client):
        response = test_client.get("/api/tasks/task-001")
        assert response.status_code == 200
        assert response.json()["id"] == "task-001"

    def test_get_nonexistent_returns_404(self, test_client):
        response = test_client.get("/api/tasks/does-not-exist")
        assert response.status_code == 404


class TestUpdateTask:
    def test_update_status(self, test_client):
        response = test_client.patch("/api/tasks/task-001", json={"status": "completed"})
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

    def test_update_nonexistent_returns_404(self, test_client):
        response = test_client.patch("/api/tasks/does-not-exist", json={"status": "completed"})
        assert response.status_code == 404


class TestDeleteTask:
    def test_delete_returns_204(self, test_client):
        response = test_client.delete("/api/tasks/task-001")
        assert response.status_code == 204

    def test_delete_nonexistent_returns_404(self, test_client):
        response = test_client.delete("/api/tasks/does-not-exist")
        assert response.status_code == 404

    def test_deleted_task_not_found_on_get(self, test_client):
        test_client.delete("/api/tasks/task-001")
        assert test_client.get("/api/tasks/task-001").status_code == 404
