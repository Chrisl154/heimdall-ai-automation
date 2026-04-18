"""
Webhook management routes — list configured hooks and send test payloads.
"""
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import yaml

from core import config
from core.config import load_config
from core.models import EventType, PipelineEvent

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _path() -> Path:
    return Path(os.getenv("HEIMDALL_CONFIG_DIR", "config")) / "settings.yaml"


class WebhookConfig(BaseModel):
    url: str
    secret: str = ""
    events: list[str] = []
    enabled: bool = True


class WebhookCreateRequest(BaseModel):
    url: str
    secret: str = ""
    events: list[str] = []
    enabled: bool = True


class WebhookUpdateRequest(BaseModel):
    url: Optional[str] = None
    secret: Optional[str] = None
    events: Optional[list[str]] = None
    enabled: Optional[bool] = None


def _masked_hooks() -> list[dict]:
    hooks = config.get("webhooks", [])
    result = []
    for h in hooks:
        entry = dict(h)
        if entry.get("secret"):
            entry["secret"] = "***"
        result.append(entry)
    return result


@router.get("")
def list_webhooks():
    return {"webhooks": _masked_hooks()}


@router.post("", status_code=201)
def add_webhook(body: WebhookCreateRequest):
    p = _path()
    if not p.exists():
        cfg: dict = {"webhooks": []}
    else:
        with open(p, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    webhooks = cfg.get("webhooks", [])
    webhooks.append(body.model_dump())
    cfg["webhooks"] = webhooks

    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

    load_config.cache_clear()
    return body.model_copy()


@router.patch("/{index}", status_code=200)
def update_webhook(index: int, body: WebhookUpdateRequest):
    p = _path()
    if not p.exists():
        raise HTTPException(404, "No settings file")

    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    webhooks = cfg.get("webhooks", [])
    if index < 0 or index >= len(webhooks):
        raise HTTPException(404, f"Webhook at index {index} not found")

    webhook = webhooks[index]
    if body.url is not None:
        webhook["url"] = body.url
    if body.secret is not None:
        webhook["secret"] = body.secret
    if body.events is not None:
        webhook["events"] = body.events
    if body.enabled is not None:
        webhook["enabled"] = body.enabled
    webhooks[index] = webhook

    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

    load_config.cache_clear()
    return webhook


@router.delete("/{index}", status_code=204)
def delete_webhook(index: int):
    p = _path()
    if not p.exists():
        raise HTTPException(404, "No settings file")

    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    webhooks = cfg.get("webhooks", [])
    if index < 0 or index >= len(webhooks):
        raise HTTPException(404, f"Webhook at index {index} not found")

    del webhooks[index]
    cfg["webhooks"] = webhooks

    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

    load_config.cache_clear()


@router.post("/test/{index}", status_code=200)
async def test_webhook(index: int):
    hooks = config.get("webhooks", [])
    if index < 0 or index >= len(hooks):
        raise HTTPException(status_code=404, detail=f"No webhook at index {index}")

    from core.webhook_dispatcher import WebhookDispatcher
    dispatcher = WebhookDispatcher({"webhooks": [hooks[index]]})

    test_event = PipelineEvent(
        type=EventType.PM_STARTED,
        task_id=None,
        message="Heimdall webhook test payload",
        data={"test": True},
    )
    await dispatcher.handle_event(test_event)
    return {"sent": True, "url": hooks[index].get("url")}
