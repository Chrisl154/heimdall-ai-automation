"""
Restrictions routes — read/update restrictions.yaml.
"""
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import yaml

from core.restrictions import reload as reload_restrictions

router = APIRouter(prefix="/api/restrictions", tags=["restrictions"])


def _path() -> Path:
    return Path(os.getenv("HEIMDALL_CONFIG_DIR", "config")) / "restrictions.yaml"


@router.get("")
def get_restrictions():
    p = _path()
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class RestrictionsPatchRequest(BaseModel):
    yaml_content: str


@router.patch("", status_code=204)
def update_restrictions(body: RestrictionsPatchRequest):
    """Replace restrictions.yaml with the supplied YAML string."""
    try:
        parsed = yaml.safe_load(body.yaml_content)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}")
    p = _path()
    p.write_text(body.yaml_content, encoding="utf-8")
    reload_restrictions()
