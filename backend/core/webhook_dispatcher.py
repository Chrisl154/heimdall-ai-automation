"""
Outbound webhook dispatcher.

Fires POST requests to configured URLs on pipeline events.
Config lives under `webhooks:` in settings.yaml.

Each webhook entry:
  url: "https://example.com/hook"
  secret: "optional_hmac_secret"   # adds X-Heimdall-Signature: sha256=<hex>
  events: ["task_completed", ...]  # empty list = all events
  enabled: true
"""
import hashlib
import hmac
import json
import logging
from typing import TYPE_CHECKING

import httpx

from core.models import PipelineEvent

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    def __init__(self, settings: dict) -> None:
        self._hooks: list[dict] = settings.get("webhooks", [])

    async def handle_event(self, event: PipelineEvent) -> None:
        if not self._hooks:
            return
        payload = {
            "event": event.type.value,
            "task_id": event.task_id,
            "message": event.message,
            "timestamp": event.timestamp,
            "data": event.data,
        }
        body = json.dumps(payload, separators=(",", ":")).encode()

        for hook in self._hooks:
            if not hook.get("enabled", True):
                continue
            allowed = hook.get("events", [])
            if allowed and event.type.value not in allowed:
                continue
            url = hook.get("url", "")
            if not url:
                continue
            secret = hook.get("secret", "")
            # fire-and-forget — don't await, don't block pipeline
            import asyncio
            asyncio.create_task(_fire(url, body, secret))


async def _fire(url: str, body: bytes, secret: str) -> None:
    headers = {"Content-Type": "application/json"}
    if secret:
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Heimdall-Signature"] = f"sha256={sig}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(2):
            try:
                resp = await client.post(url, content=body, headers=headers)
                if resp.status_code < 500:
                    return
                logger.warning("Webhook %s returned %s (attempt %d)", url, resp.status_code, attempt + 1)
            except Exception as exc:
                logger.warning("Webhook %s error (attempt %d): %s", url, attempt + 1, exc)
                return  # network error — don't retry
