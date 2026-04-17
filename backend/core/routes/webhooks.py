"""
Webhook management routes — list configured hooks and send test payloads.
"""
from fastapi import APIRouter, HTTPException

from core import config
from core.models import EventType, PipelineEvent

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


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
