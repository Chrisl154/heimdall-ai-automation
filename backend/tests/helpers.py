"""
Shared test utilities for Heimdall backend tests.

Provides:
  - make_authed_client  — context-manager that yields a TestClient with auth on
  - auth_header         — helper that returns an Authorization header dict
  - AUTH_TOKEN          — default token used across auth-aware tests
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

AUTH_TOKEN = "test-secret-token"


@contextmanager
def make_authed_client(monkeypatch, tmp_path, token: str = AUTH_TOKEN):
    """
    Context manager that yields a FastAPI TestClient with auth enforced.

    Patches are held for the full lifetime of the context so the lifespan
    mocks remain active throughout the test.  All module-level singletons are
    reset before the client is created so each test starts from a clean state.
    """
    # ── Environment ───────────────────────────────────────────────────────────
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("HEIMDALL_VAULT_KEY", key)
    monkeypatch.setenv("HEIMDALL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HEIMDALL_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))
    monkeypatch.setenv("HEIMDALL_API_TOKEN", token)

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "completed").mkdir(exist_ok=True)
    (tasks_dir / "backlog.yaml").write_text("[]", encoding="utf-8")

    # ── Singleton reset ───────────────────────────────────────────────────────
    import core.vault as vault_mod
    import core.pm_engine as pm_mod
    import core.task_manager as tm_mod
    vault_mod._vault = None
    pm_mod._pm = None
    tm_mod._task_manager = None

    # ── Client (patches held for the full block) ──────────────────────────────
    with (
        patch("core.messaging.manager.MessagingManager.start_all", new=AsyncMock()),
        patch("core.messaging.manager.MessagingManager.stop_all", new=AsyncMock()),
        patch("core.pm_engine.PMEngine.stop", new=AsyncMock()),
    ):
        from main import app
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client


def auth_header(token: str = AUTH_TOKEN) -> dict[str, str]:
    """Return a pre-built Authorization header dict for a given token."""
    return {"Authorization": f"Bearer {token}"}
