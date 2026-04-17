"""Shared pytest fixtures for the Heimdall backend test suite."""
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient


@pytest.fixture
def vault_key():
    return Fernet.generate_key().decode()


@pytest.fixture
def vault_env(monkeypatch, tmp_path, vault_key):
    """Set HEIMDALL_VAULT_KEY and HEIMDALL_DATA_DIR to isolated temp paths."""
    monkeypatch.setenv("HEIMDALL_VAULT_KEY", vault_key)
    monkeypatch.setenv("HEIMDALL_DATA_DIR", str(tmp_path))
    return {"vault_key": vault_key, "data_dir": tmp_path}


@pytest.fixture
def tmp_tasks_dir(tmp_path):
    """Minimal backlog.yaml with 3 test tasks in a temp directory."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "completed").mkdir(exist_ok=True)
    (tasks_dir / "backlog.yaml").write_text(
        """\
- id: task-001
  title: "Test Task 1"
  description: "A pending test task"
  priority: medium
  status: pending
  created_at: "2026-04-16"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 0
  output_path: ""

- id: task-002
  title: "Test Task 2"
  description: "An in_progress test task"
  priority: high
  status: in_progress
  created_at: "2026-04-16"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 1
  output_path: ""

- id: task-003
  title: "Test Task 3"
  description: "A completed test task"
  priority: low
  status: completed
  created_at: "2026-04-16"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 0
  output_path: ""
""",
        encoding="utf-8",
    )
    return tasks_dir


@pytest.fixture
def test_client(monkeypatch, tmp_path):
    """
    FastAPI TestClient with env vars isolated to tmp_path.
    Lifespan messaging/PM startup is mocked so tests don't need
    real Ollama, LM Studio, or Telegram connections.
    """
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HEIMDALL_VAULT_KEY", key)
    monkeypatch.setenv("HEIMDALL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HEIMDALL_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "completed").mkdir(exist_ok=True)
    (tasks_dir / "backlog.yaml").write_text(
        """\
- id: task-001
  title: "Test Task 1"
  description: "A pending test task"
  priority: medium
  status: pending
  created_at: "2026-04-16"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 0
  output_path: ""
""",
        encoding="utf-8",
    )

    # Reset module-level singletons so each test gets a clean state
    import core.vault as vault_mod
    import core.pm_engine as pm_mod
    vault_mod._vault = None
    pm_mod._pm = None

    with (
        patch("core.messaging.manager.MessagingManager.start_all", new=AsyncMock()),
        patch("core.messaging.manager.MessagingManager.stop_all", new=AsyncMock()),
        patch("core.pm_engine.PMEngine.stop", new=AsyncMock()),
    ):
        from main import app
        with TestClient(app) as client:
            yield client
