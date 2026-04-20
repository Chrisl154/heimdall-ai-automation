"""
Model discovery — scans all configured providers concurrently and returns
available models grouped by provider.
"""
import asyncio
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter

from core.config import load_config
from core.vault import Vault

router = APIRouter(prefix="/api/models", tags=["models"])
logger = logging.getLogger(__name__)

TIMEOUT = 5.0

_ANTHROPIC_FALLBACK = [
    "claude-opus-4-7-20251101",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
]
_OPENAI_FALLBACK = [
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
    "o1", "o1-mini", "o3-mini",
]
_GROK_FALLBACK = [
    "grok-3", "grok-3-mini", "grok-2-1212", "grok-beta",
]
_DEEPSEEK_FALLBACK = [
    "deepseek-chat", "deepseek-reasoner",
]


async def _scan_ollama(base_url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{base_url.rstrip('/')}/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                return {"available": True, "models": sorted(models)}
    except Exception as exc:
        logger.debug("Ollama scan failed: %s", exc)
    return {"available": False, "models": []}


async def _scan_lmstudio(base_url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{base_url.rstrip('/')}/v1/models")
            if r.status_code == 200:
                models = [m["id"] for m in r.json().get("data", [])]
                return {"available": True, "models": sorted(models)}
    except Exception as exc:
        logger.debug("LM Studio scan failed: %s", exc)
    return {"available": False, "models": []}


async def _scan_anthropic(api_key: Optional[str]) -> dict:
    if not api_key:
        return {"available": False, "models": _ANTHROPIC_FALLBACK, "no_key": True}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            )
            if r.status_code == 200:
                models = [m["id"] for m in r.json().get("data", [])]
                return {"available": True, "models": models or _ANTHROPIC_FALLBACK, "no_key": False}
    except Exception as exc:
        logger.debug("Anthropic scan failed: %s", exc)
    return {"available": True, "models": _ANTHROPIC_FALLBACK, "no_key": False}


async def _scan_openai(api_key: Optional[str]) -> dict:
    if not api_key:
        return {"available": False, "models": _OPENAI_FALLBACK, "no_key": True}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if r.status_code == 200:
                data = r.json().get("data", [])
                models = sorted([
                    m["id"] for m in data
                    if any(p in m["id"] for p in ("gpt-4", "gpt-3.5", "o1", "o3"))
                ])
                return {"available": True, "models": models or _OPENAI_FALLBACK, "no_key": False}
    except Exception as exc:
        logger.debug("OpenAI scan failed: %s", exc)
    return {"available": True, "models": _OPENAI_FALLBACK, "no_key": False}


async def _scan_grok(api_key: Optional[str]) -> dict:
    if not api_key:
        return {"available": False, "models": _GROK_FALLBACK, "no_key": True}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://api.x.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if r.status_code == 200:
                models = sorted([m["id"] for m in r.json().get("data", [])])
                return {"available": True, "models": models or _GROK_FALLBACK, "no_key": False}
    except Exception as exc:
        logger.debug("Grok scan failed: %s", exc)
    return {"available": True, "models": _GROK_FALLBACK, "no_key": False}


async def _scan_deepseek(api_key: Optional[str]) -> dict:
    if not api_key:
        return {"available": False, "models": _DEEPSEEK_FALLBACK, "no_key": True}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://api.deepseek.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if r.status_code == 200:
                models = sorted([m["id"] for m in r.json().get("data", [])])
                return {"available": True, "models": models or _DEEPSEEK_FALLBACK, "no_key": False}
    except Exception as exc:
        logger.debug("DeepSeek scan failed: %s", exc)
    return {"available": True, "models": _DEEPSEEK_FALLBACK, "no_key": False}


def _safe(result, fallback: dict) -> dict:
    return result if isinstance(result, dict) else fallback


@router.get("")
async def scan_models():
    """Scan all providers concurrently and return available models."""
    cfg = load_config()
    vault = Vault()

    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    lmstudio_url = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234")

    # Pick up URL overrides from agent config
    for agent in cfg.get("agents", {}).values():
        if agent.get("provider") == "ollama" and agent.get("base_url"):
            ollama_url = agent["base_url"]
        if agent.get("provider") == "lmstudio" and agent.get("base_url"):
            lmstudio_url = agent["base_url"]

    anthropic_key = vault.get("anthropic_key")
    openai_key = vault.get("openai_key")
    grok_key = vault.get("grok_key")
    deepseek_key = vault.get("deepseek_key")

    raw = await asyncio.gather(
        _scan_ollama(ollama_url),
        _scan_lmstudio(lmstudio_url),
        _scan_anthropic(anthropic_key),
        _scan_openai(openai_key),
        _scan_grok(grok_key),
        _scan_deepseek(deepseek_key),
        return_exceptions=True,
    )

    providers = {
        "ollama": {
            **_safe(raw[0], {"available": False, "models": []}),
            "base_url": ollama_url,
            "type": "local",
            "label": "Ollama",
            "description": "Local open-source models",
        },
        "lmstudio": {
            **_safe(raw[1], {"available": False, "models": []}),
            "base_url": lmstudio_url,
            "type": "local",
            "label": "LM Studio",
            "description": "Local models with GUI",
        },
        "anthropic": {
            **_safe(raw[2], {"available": False, "models": _ANTHROPIC_FALLBACK, "no_key": not anthropic_key}),
            "type": "cloud",
            "label": "Anthropic (Claude)",
            "description": "Claude Opus, Sonnet, Haiku",
            "key_name": "anthropic_key",
            "key_url": "https://console.anthropic.com/settings/keys",
        },
        "openai": {
            **_safe(raw[3], {"available": False, "models": _OPENAI_FALLBACK, "no_key": not openai_key}),
            "type": "cloud",
            "label": "OpenAI",
            "description": "GPT-4o, o1, o3",
            "key_name": "openai_key",
            "key_url": "https://platform.openai.com/api-keys",
        },
        "grok": {
            **_safe(raw[4], {"available": False, "models": _GROK_FALLBACK, "no_key": not grok_key}),
            "type": "cloud",
            "label": "Grok (xAI)",
            "description": "Grok-3, Grok-3 Mini",
            "key_name": "grok_key",
            "key_url": "https://console.x.ai",
        },
        "deepseek": {
            **_safe(raw[5], {"available": False, "models": _DEEPSEEK_FALLBACK, "no_key": not deepseek_key}),
            "type": "cloud",
            "label": "DeepSeek",
            "description": "DeepSeek Chat, Reasoner",
            "key_name": "deepseek_key",
            "key_url": "https://platform.deepseek.com/api_keys",
        },
    }

    all_models = [
        {"provider": name, "model": m, "label": f"{p['label']} / {m}"}
        for name, p in providers.items()
        if p.get("available")
        for m in p["models"]
    ]

    return {"providers": providers, "all_models": all_models}
