"""
Configuration loader.

Reads config/settings.yaml, then overlays environment variables prefixed
with HEIMDALL_ (e.g. HEIMDALL_PM_AUTO_PUSH=true overrides pm.auto_push).
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()


def _deep_merge(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _apply_env_overrides(cfg: dict, prefix: str = "HEIMDALL") -> dict:
    """Walk env vars like HEIMDALL_PM_AUTO_PUSH and patch the nested dict."""
    for key, val in os.environ.items():
        if not key.startswith(prefix + "_"):
            continue
        parts = key[len(prefix) + 1 :].lower().split("_")
        node = cfg
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        # Coerce booleans/ints
        if val.lower() in ("true", "1", "yes"):
            val = True
        elif val.lower() in ("false", "0", "no"):
            val = False
        else:
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except ValueError:
                    pass
        node[parts[-1]] = val
    return cfg


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    config_dir = Path(os.getenv("HEIMDALL_CONFIG_DIR", "config"))
    settings_path = config_dir / "settings.yaml"

    if settings_path.exists():
        with open(settings_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    return _apply_env_overrides(cfg)


def get(path: str, default: Any = None) -> Any:
    """Dot-separated config key access. e.g. get('pm.auto_commit', True)"""
    cfg = load_config()
    parts = path.split(".")
    node: Any = cfg
    for part in parts:
        if not isinstance(node, dict):
            return default
        node = node.get(part)
        if node is None:
            return default
    return node
