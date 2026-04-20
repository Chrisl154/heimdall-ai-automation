"""
PM control routes — start/stop/status + chat + SSE event stream.
"""
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

import os

from core.models import ChatRequest, ChatResponse, DirectChatRequest, PMStatusResponse
from core.pm_engine import get_pm
from core.vault import Vault
from core.llm_providers import call_llm, LLMError

router = APIRouter(prefix="/api/pm", tags=["pm"])


@router.post("/start", response_model=PMStatusResponse)
async def start_pm():
    pm = get_pm()
    await pm.start()
    return pm.get_status()


@router.post("/stop", response_model=PMStatusResponse)
async def stop_pm():
    pm = get_pm()
    await pm.stop()
    return pm.get_status()


@router.get("/status", response_model=PMStatusResponse)
async def get_status():
    return get_pm().get_status()


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    pm = get_pm()
    reply = await pm.chat(body.message, session_id=body.session_id)
    return ChatResponse(reply=reply, session_id=body.session_id)


_CLOUD_KEY_MAP = {
    "anthropic": "anthropic_key",
    "openai": "openai_key",
    "grok": "grok_key",
    "deepseek": "deepseek_key",
}

_CLOUD_BASE_URLS = {
    "grok": "https://api.x.ai",
    "deepseek": "https://api.deepseek.com",
}


@router.post("/chat/direct")
async def direct_chat(body: DirectChatRequest):
    """Call any LLM directly, bypassing the PM pipeline."""
    provider = body.provider
    vault = Vault()

    api_key: str | None = None
    base_url: str | None = None

    if provider in _CLOUD_KEY_MAP:
        api_key = vault.get(_CLOUD_KEY_MAP[provider])
        if not api_key:
            raise HTTPException(status_code=400, detail=f"No API key configured for {provider}. Add it in Models → Connect.")
        if provider in _CLOUD_BASE_URLS:
            base_url = _CLOUD_BASE_URLS[provider]
            provider_call = "openai_compat"
        else:
            provider_call = provider
    elif provider == "ollama":
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        provider_call = "ollama"
    elif provider == "lmstudio":
        base_url = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234")
        provider_call = "lmstudio"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        reply = await call_llm(
            prompt=body.message,
            system="You are a helpful AI assistant.",
            model=body.model,
            provider=provider_call,
            base_url=base_url,
            api_key=api_key,
            temperature=0.7,
            max_tokens=2048,
        )
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {"reply": reply, "provider": body.provider, "model": body.model, "session_id": body.session_id}


@router.get("/conversation")
def get_conversation(limit: int = 100):
    """Return the agent-to-agent conversation log."""
    return {"entries": get_pm().get_conversation(limit)}


@router.get("/events")
async def event_stream():
    """Server-Sent Events stream for real-time pipeline updates."""
    pm = get_pm()
    queue = pm.subscribe()

    async def generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = event.model_dump_json()
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield "data: {\"type\":\"ping\"}\n\n"
        finally:
            pm.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
