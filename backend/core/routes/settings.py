"""
Settings routes — read/update the running configuration.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import config

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings():
    """Return the full resolved config (no secrets)."""
    cfg = config.load_config()
    # Strip any api_key / token fields that may have leaked into config
    def _scrub(obj):
        if isinstance(obj, dict):
            return {
                k: _scrub(v)
                for k, v in obj.items()
                if "key" not in k.lower() and "token" not in k.lower() and "password" not in k.lower()
            }
        return obj
    return _scrub(cfg)


class SettingsPatchRequest(BaseModel):
    path: str   # dot-separated e.g. "pm.auto_commit"
    value: object


@router.patch("", status_code=204)
def patch_setting(body: SettingsPatchRequest):
    """
    Patch a single setting at runtime (non-persistent — survives until restart).
    For persistent changes, edit config/settings.yaml directly.
    """
    cfg = config.load_config()
    parts = body.path.split(".")
    node = cfg
    for part in parts[:-1]:
        if part not in node:
            raise HTTPException(status_code=404, detail=f"Setting path not found: {body.path}")
        node = node[part]
    node[parts[-1]] = body.value
