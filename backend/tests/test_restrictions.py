"""Tests for core.restrictions."""
import pytest

from core.restrictions import (
    RestrictionViolation,
    check_path_read,
    check_path_write,
    check_content,
    check_file_size,
    check_git_push,
    check_task_iterations,
    reload,
)


@pytest.fixture(autouse=True)
def reset_restrictions_cache():
    """Clear the lru_cache before each test so HEIMDALL_CONFIG_DIR changes take effect."""
    reload()
    yield
    reload()


@pytest.fixture
def restrictions_env(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "restrictions.yaml").write_text(
        """\
global:
  protected_paths:
    - "config/secrets.yaml"
    - ".env"
  blocked_patterns:
    - "DO_NOT_INCLUDE_THIS_PHRASE"

worker_restrictions:
  read_restricted:
    - "vendor/*"
  write_allowed:
    - "workspace/current/*"
    - "logs/*.log"
  write_restricted:
    - "config/*"
  max_file_size: 1048576

pm_restrictions:
  git_force_push: false
  git_delete_branches: false
  max_total_iterations_per_task: 5
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("HEIMDALL_CONFIG_DIR", str(config_dir))
    return config_dir


class TestCheckPathRead:
    def test_blocked_by_protected_paths(self, restrictions_env):
        with pytest.raises(RestrictionViolation, match="protected path"):
            check_path_read("config/secrets.yaml", agent="worker")

    def test_blocked_by_read_restricted(self, restrictions_env):
        with pytest.raises(RestrictionViolation, match="read access restricted"):
            check_path_read("vendor/package.py", agent="worker")

    def test_allowed_path_passes(self, restrictions_env):
        check_path_read("workspace/current/task.md", agent="worker")


class TestCheckPathWrite:
    def test_blocked_by_protected_paths(self, restrictions_env):
        with pytest.raises(RestrictionViolation, match="protected path"):
            check_path_write("config/secrets.yaml", agent="worker")

    def test_blocked_not_in_write_allowed(self, restrictions_env):
        with pytest.raises(RestrictionViolation, match="write access not in allowed list"):
            check_path_write("src/other.py", agent="worker")

    def test_allowed_path_passes(self, restrictions_env):
        check_path_write("workspace/current/task.md", agent="worker")


class TestCheckContent:
    def test_blocked_pattern(self, restrictions_env):
        with pytest.raises(RestrictionViolation, match="forbidden pattern"):
            check_content("This contains DO_NOT_INCLUDE_THIS_PHRASE here", agent="worker")

    def test_allowed_content_passes(self, restrictions_env):
        check_content("This is perfectly fine content", agent="worker")


class TestCheckFileSize:
    def test_exceeds_limit(self, restrictions_env):
        with pytest.raises(RestrictionViolation, match="exceeds limit"):
            check_file_size(2_000_000, agent="worker")

    def test_within_limit_passes(self, restrictions_env):
        check_file_size(500_000, agent="worker")


class TestCheckGitPush:
    def test_force_push_blocked(self, restrictions_env):
        with pytest.raises(RestrictionViolation, match="Force-push is not allowed"):
            check_git_push(force=True)

    def test_non_force_push_passes(self, restrictions_env):
        check_git_push(force=False)

    def test_force_push_allowed_after_reload(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "restrictions.yaml").write_text(
            """\
global:
  protected_paths: []
  blocked_patterns: []
pm_restrictions:
  git_force_push: true
  max_total_iterations_per_task: 10
""",
            encoding="utf-8",
        )
        monkeypatch.setenv("HEIMDALL_CONFIG_DIR", str(config_dir))
        reload()
        check_git_push(force=True)  # should not raise


class TestCheckTaskIterations:
    def test_at_limit_raises(self, restrictions_env):
        with pytest.raises(RestrictionViolation, match="maximum iteration limit"):
            check_task_iterations("task-001", 5)

    def test_below_limit_passes(self, restrictions_env):
        check_task_iterations("task-001", 4)


class TestReload:
    def test_reload_picks_up_new_rules(self, monkeypatch, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        restrictions_file = config_dir / "restrictions.yaml"
        restrictions_file.write_text(
            """\
global:
  protected_paths: []
  blocked_patterns: []
pm_restrictions:
  git_force_push: false
  max_total_iterations_per_task: 10
""",
            encoding="utf-8",
        )
        monkeypatch.setenv("HEIMDALL_CONFIG_DIR", str(config_dir))
        reload()
        # No rules blocking this — should pass
        check_path_read("anything.txt", agent="worker")
