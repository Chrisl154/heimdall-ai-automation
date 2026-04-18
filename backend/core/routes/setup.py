"""
First-run setup routes — configure vault key and API token.
These endpoints are excluded from token auth (needed before auth is configured).
"""
import os
import secrets
import base64
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dotenv import dotenv_values

router = APIRouter(prefix="/api/setup", tags=["setup"])


def _env_path() -> Path:
    return Path(__file__).parent.parent.parent.parent / ".env"


class SetupStatusResponse(BaseModel):
    configured: bool
    has_vault_key: bool
    has_api_token: bool


class SetupInitRequest(BaseModel):
    vault_key: str
    api_token: str
    anthropic_key: str = ""
    ollama_url: str = "http://127.0.0.1:11434"


@router.get("/status", response_model=SetupStatusResponse)
def get_setup_status():
    env_path = _env_path()
    if not env_path.exists():
        return SetupStatusResponse(configured=False, has_vault_key=False, has_api_token=False)

    values = dotenv_values(env_path)
    vault_key = values.get("HEIMDALL_VAULT_KEY", "").strip()
    api_token = values.get("HEIMDALL_API_TOKEN", "").strip()

    return SetupStatusResponse(
        configured=bool(vault_key),
        has_vault_key=bool(vault_key),
        has_api_token=bool(api_token),
    )


@router.post("/init")
def init_setup(body: SetupInitRequest):
    env_path = _env_path()

    if env_path.exists():
        values = dotenv_values(env_path)
        vault_key = values.get("HEIMDALL_VAULT_KEY", "").strip()
        if vault_key:
            raise HTTPException(400, "Already configured")

    if not env_path.exists():
        example_path = Path(__file__).parent.parent.parent.parent / ".env.example"
        if not example_path.exists():
            raise HTTPException(500, ".env.example not found")
        content = example_path.read_text(encoding="utf-8")
    else:
        content = env_path.read_text(encoding="utf-8")

    content = content.replace(
        "HEIMDALL_VAULT_KEY=<generate-with-fernet>",
        f"HEIMDALL_VAULT_KEY={body.vault_key}"
    )
    content = content.replace(
        "HEIMDALL_API_TOKEN=",
        f"HEIMDALL_API_TOKEN={body.api_token}"
    )
    content = content.replace(
        "OLLAMA_BASE_URL=http://127.0.0.1:11434",
        f"OLLAMA_BASE_URL={body.ollama_url}"
    )
    content = content.replace(
        "HEIMDALL_SECRET_KEY=change-me-use-a-long-random-string",
        f"HEIMDALL_SECRET_KEY={secrets.token_hex(32)}"
    )

    env_path.write_text(content, encoding="utf-8")

    if body.anthropic_key.strip():
        try:
            from core.vault import get_vault
            get_vault().set("anthropic_key", body.anthropic_key)
        except Exception:
            pass

    return {"ok": True, "message": "Restart Heimdall for changes to take effect"}


@router.get("/generate-key")
def generate_key():
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    return {"key": key}
