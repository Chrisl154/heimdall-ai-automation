"""
Restrictions engine.

Loads config/restrictions.yaml and enforces rules before any agent action.
All checks raise RestrictionViolation so callers can handle them uniformly.
"""
import fnmatch
import os
from functools import lru_cache
from pathlib import Path

import yaml


class RestrictionViolation(Exception):
    pass


@lru_cache(maxsize=1)
def _load_rules() -> dict:
    config_dir = os.getenv("HEIMDALL_CONFIG_DIR", "config")
    path = Path(config_dir) / "restrictions.yaml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _rules() -> dict:
    return _load_rules()


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(value, p) for p in patterns)


# ── Path checks ───────────────────────────────────────────────────────────────

def check_path_read(path: str, agent: str = "worker") -> None:
    rules = _rules()
    protected = rules.get("global", {}).get("protected_paths", [])
    if _matches_any(path, protected):
        raise RestrictionViolation(f"Agent '{agent}' is not allowed to read protected path: {path}")

    agent_key = f"{agent}_restrictions"
    restricted = rules.get(agent_key, {}).get("read_restricted", [])
    if _matches_any(path, restricted):
        raise RestrictionViolation(f"Agent '{agent}' read access restricted for: {path}")


def check_path_write(path: str, agent: str = "worker") -> None:
    rules = _rules()
    protected = rules.get("global", {}).get("protected_paths", [])
    if _matches_any(path, protected):
        raise RestrictionViolation(f"Agent '{agent}' is not allowed to write protected path: {path}")

    agent_key = f"{agent}_restrictions"
    agent_rules = rules.get(agent_key, {})

    write_allowed = agent_rules.get("write_allowed")
    if write_allowed is not None:
        if not _matches_any(path, write_allowed) and not any(
            path.startswith(p.rstrip("*").rstrip("/")) for p in write_allowed
        ):
            raise RestrictionViolation(
                f"Agent '{agent}' write access not in allowed list for: {path}"
            )

    write_restricted = agent_rules.get("write_restricted", [])
    if _matches_any(path, write_restricted):
        raise RestrictionViolation(f"Agent '{agent}' write access restricted for: {path}")


def check_commit_path(path: str) -> None:
    rules = _rules()
    never_commit = rules.get("global", {}).get("never_commit", [])
    filename = Path(path).name
    if _matches_any(filename, never_commit) or _matches_any(path, never_commit):
        raise RestrictionViolation(f"Commit blocked — path matches never_commit rule: {path}")


# ── Content checks ────────────────────────────────────────────────────────────

def check_content(content: str, agent: str = "worker") -> None:
    rules = _rules()
    blocked = rules.get("global", {}).get("blocked_patterns", [])
    for pattern in blocked:
        if pattern.lower() in content.lower():
            raise RestrictionViolation(
                f"Agent '{agent}' content blocked — contains forbidden pattern: '{pattern}'"
            )


# ── File size check ───────────────────────────────────────────────────────────

def check_file_size(size_bytes: int, agent: str = "worker") -> None:
    rules = _rules()
    agent_key = f"{agent}_restrictions"
    max_size = rules.get(agent_key, {}).get("max_file_size", 10 * 1024 * 1024)
    if size_bytes > max_size:
        raise RestrictionViolation(
            f"Agent '{agent}' file size {size_bytes} bytes exceeds limit {max_size} bytes"
        )


# ── Git checks ────────────────────────────────────────────────────────────────

def check_git_push(force: bool = False) -> None:
    rules = _rules()
    if force and not rules.get("pm_restrictions", {}).get("git_force_push", False):
        raise RestrictionViolation("Force-push is not allowed by restrictions.")


def check_git_delete_branch() -> None:
    rules = _rules()
    if not rules.get("pm_restrictions", {}).get("git_delete_branches", False):
        raise RestrictionViolation("Branch deletion is not allowed by restrictions.")


# ── Iteration guard ───────────────────────────────────────────────────────────

def check_task_iterations(task_id: str, current: int) -> None:
    rules = _rules()
    max_iter = rules.get("pm_restrictions", {}).get("max_total_iterations_per_task", 10)
    if current >= max_iter:
        raise RestrictionViolation(
            f"Task '{task_id}' has reached the maximum iteration limit ({max_iter}). "
            "Escalating to human."
        )


def reload() -> None:
    """Force-reload restrictions from disk (clears lru_cache)."""
    _load_rules.cache_clear()
