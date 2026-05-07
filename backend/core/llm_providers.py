"""
LLM provider implementations.

Supported providers: anthropic | ollama | lmstudio | openai | openai_compat

Exponential backoff: 5, 10, 20, 40, 80 s on 429/5xx.
All calls return (text, stats_dict) where stats_dict has input_tokens, output_tokens.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

import httpx

logger = logging.getLogger(__name__)

_BACKOFF = [5, 10, 20, 40, 80]

# Updated on every successful or rate-limited Anthropic response
_claude_rate_info: dict = {}


def get_claude_rate_info() -> dict:
    """Return the most recent Claude API rate-limit headers."""
    return dict(_claude_rate_info)


class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""


class ClaudeRateLimitError(LLMError):
    """Raised when Anthropic rate-limits us after all retries (all failures were 429)."""


def _build_openai_messages(
    system: str, prompt: str, history: Optional[list[dict]]
) -> list[dict]:
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    return messages


def _extract_rate_headers(headers: httpx.Headers) -> None:
    """Store Anthropic rate-limit headers globally so the UI can display them."""
    global _claude_rate_info
    info: dict = {}
    for key in (
        "anthropic-ratelimit-tokens-limit",
        "anthropic-ratelimit-tokens-remaining",
        "anthropic-ratelimit-tokens-reset",
        "anthropic-ratelimit-requests-limit",
        "anthropic-ratelimit-requests-remaining",
        "anthropic-ratelimit-requests-reset",
    ):
        val = headers.get(key)
        if val:
            info[key.replace("anthropic-ratelimit-", "")] = val
    if info:
        _claude_rate_info = info


async def _call_anthropic(
    prompt: str,
    system: str,
    model: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
    history: Optional[list[dict]],
) -> tuple[str, dict]:
    messages: list[dict] = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        payload["system"] = system

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    last_exc: Exception = LLMError("No attempts made")
    all_rate_limited = True
    async with httpx.AsyncClient(timeout=120.0) as client:
        for i, delay in enumerate([0] + _BACKOFF):
            if delay:
                await asyncio.sleep(delay)
            try:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers=headers,
                )
                _extract_rate_headers(resp.headers)
                if resp.status_code == 429:
                    last_exc = LLMError(
                        f"Anthropic returned 429: {resp.text[:200]}"
                    )
                    logger.warning("Anthropic 429 rate-limit, retry %d/%d", i, len(_BACKOFF))
                    continue
                if resp.status_code >= 500:
                    all_rate_limited = False
                    last_exc = LLMError(
                        f"Anthropic returned {resp.status_code}: {resp.text[:200]}"
                    )
                    logger.warning("Anthropic %s, retry %d/%d", resp.status_code, i, len(_BACKOFF))
                    continue
                if resp.status_code >= 400:
                    # 4xx (except 429) — don't retry, include full body for diagnosis
                    all_rate_limited = False
                    body = resp.text[:800]
                    logger.error("Anthropic %s (no retry): %s", resp.status_code, body)
                    raise LLMError(f"Anthropic {resp.status_code}: {body}")
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                stats = {
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                }
                return data["content"][0]["text"], stats
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                all_rate_limited = False
                last_exc = LLMError(f"Anthropic network error: {exc}")
                logger.warning("Anthropic network error, retry %d/%d: %s", i, len(_BACKOFF), exc)
    if all_rate_limited:
        raise ClaudeRateLimitError(str(last_exc))
    raise last_exc


async def _call_ollama(
    prompt: str,
    system: str,
    model: str,
    base_url: str,
    temperature: float,
    max_tokens: int,
    history: Optional[list[dict]],
) -> tuple[str, dict]:
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }

    url = base_url.rstrip("/") + "/api/chat"
    last_exc: Exception = LLMError("No attempts made")
    async with httpx.AsyncClient(timeout=300.0) as client:
        for i, delay in enumerate([0] + _BACKOFF):
            if delay:
                await asyncio.sleep(delay)
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_exc = LLMError(f"Ollama {resp.status_code}: {resp.text[:200]}")
                    logger.warning("Ollama %s, retry %d/%d", resp.status_code, i, len(_BACKOFF))
                    continue
                if resp.status_code >= 400:
                    body = resp.text[:800]
                    logger.error("Ollama %s (no retry): %s", resp.status_code, body)
                    raise LLMError(f"Ollama {resp.status_code}: {body}")
                resp.raise_for_status()
                data = resp.json()
                stats = {
                    "input_tokens": data.get("prompt_eval_count", 0),
                    "output_tokens": data.get("eval_count", 0),
                }
                return data["message"]["content"], stats
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = LLMError(f"Ollama network error: {exc}")
                logger.warning("Ollama network error, retry %d/%d: %s", i, len(_BACKOFF), exc)
    raise last_exc


async def _call_openai_compat(
    prompt: str,
    system: str,
    model: str,
    base_url: str,
    api_key: Optional[str],
    temperature: float,
    max_tokens: int,
    history: Optional[list[dict]],
) -> tuple[str, dict]:
    messages = _build_openai_messages(system, prompt, history)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"content-type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = base_url.rstrip("/") + "/v1/chat/completions"
    last_exc: Exception = LLMError("No attempts made")
    async with httpx.AsyncClient(timeout=180.0) as client:
        for i, delay in enumerate([0] + _BACKOFF):
            if delay:
                await asyncio.sleep(delay)
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_exc = LLMError(f"OpenAI-compat {resp.status_code}: {resp.text[:200]}")
                    logger.warning("OpenAI-compat %s, retry %d/%d", resp.status_code, i, len(_BACKOFF))
                    continue
                if resp.status_code >= 400:
                    body = resp.text[:800]
                    logger.error("OpenAI-compat %s (no retry): %s", resp.status_code, body)
                    raise LLMError(f"OpenAI-compat {resp.status_code}: {body}")
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                stats = {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                }
                return data["choices"][0]["message"]["content"], stats
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = LLMError(f"OpenAI-compat network error: {exc}")
                logger.warning("OpenAI-compat network error, retry %d/%d: %s", i, len(_BACKOFF), exc)
    raise last_exc


async def call_llm(
    prompt: str,
    system: str,
    model: str,
    provider: str,
    base_url: Optional[str],
    api_key: Optional[str],
    temperature: float,
    max_tokens: int,
    history: Optional[list[dict]] = None,
) -> tuple[str, dict]:
    """
    Route an LLM call to the correct provider.
    Returns (text, stats) where stats = {input_tokens, output_tokens}.
    Raises LLMError on final failure.
    """
    logger.info("call_llm provider=%s model=%s", provider, model)

    if provider == "anthropic":
        if not api_key:
            raise LLMError("anthropic_key not set in vault")
        return await _call_anthropic(
            prompt, system, model, api_key, temperature, max_tokens, history
        )

    elif provider == "ollama":
        _base = base_url or "http://127.0.0.1:11434"
        return await _call_ollama(
            prompt, system, model, _base, temperature, max_tokens, history
        )

    elif provider == "lmstudio":
        _base = base_url or "http://127.0.0.1:1234"
        return await _call_openai_compat(
            prompt, system, model, _base, api_key, temperature, max_tokens, history
        )

    elif provider == "openai":
        if not api_key:
            raise LLMError("openai_key not set in vault")
        return await _call_openai_compat(
            prompt, system, model, "https://api.openai.com", api_key, temperature, max_tokens, history
        )

    elif provider == "openai_compat":
        if not base_url:
            raise LLMError("base_url required for openai_compat provider")
        return await _call_openai_compat(
            prompt, system, model, base_url, api_key, temperature, max_tokens, history
        )

    else:
        raise LLMError(f"Unknown provider '{provider}'. Supported: anthropic, ollama, lmstudio, openai, openai_compat")


# ── Streaming implementations ─────────────────────────────────────────────────
#
# stream_llm() yields (chunk_type, text) tuples where chunk_type is:
#   "thinking" — Claude extended-thinking block content
#   "text"     — regular output tokens
#   "__stats__" — final JSON blob with {input_tokens, output_tokens}
#
# Callers should collect all "text" chunks to form the complete response and
# all "thinking" chunks to show the reasoning trace.

async def _stream_anthropic(
    prompt: str,
    system: str,
    model: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
    history: Optional[list[dict]],
    enable_thinking: bool,
    thinking_budget: int,
) -> AsyncGenerator[tuple[str, str], None]:
    messages: list[dict] = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    # Thinking requires higher max_tokens to leave room for text after reasoning
    effective_max_tokens = max_tokens
    if enable_thinking:
        effective_max_tokens = max(max_tokens, thinking_budget + 1024)

    payload: dict = {
        "model": model,
        "max_tokens": effective_max_tokens,
        "messages": messages,
        "stream": True,
    }
    if system:
        payload["system"] = system
    if enable_thinking:
        payload["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    if enable_thinking:
        headers["anthropic-beta"] = "interleaved-thinking-2025-05-14"

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST", "https://api.anthropic.com/v1/messages",
            json=payload, headers=headers,
        ) as resp:
            _extract_rate_headers(resp.headers)
            if resp.status_code == 429:
                raise ClaudeRateLimitError(f"Anthropic 429 during stream")
            if resp.status_code >= 400:
                body = await resp.aread()
                raise LLMError(f"Anthropic {resp.status_code}: {body[:500].decode(errors='replace')}")

            input_tokens = output_tokens = 0
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    ev = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                ev_type = ev.get("type", "")
                if ev_type == "content_block_delta":
                    delta = ev.get("delta", {})
                    dt = delta.get("type", "")
                    if dt == "thinking_delta":
                        yield ("thinking", delta.get("thinking", ""))
                    elif dt == "text_delta":
                        yield ("text", delta.get("text", ""))
                elif ev_type == "message_delta":
                    usage = ev.get("usage", {})
                    output_tokens = usage.get("output_tokens", output_tokens)
                elif ev_type == "message_start":
                    usage = ev.get("message", {}).get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)

    yield ("__stats__", json.dumps({"input_tokens": input_tokens, "output_tokens": output_tokens}))


async def _stream_ollama(
    prompt: str,
    system: str,
    model: str,
    base_url: str,
    temperature: float,
    max_tokens: int,
    history: Optional[list[dict]],
) -> AsyncGenerator[tuple[str, str], None]:
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    url = base_url.rstrip("/") + "/api/chat"
    input_tokens = output_tokens = 0

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("POST", url, json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise LLMError(f"Ollama {resp.status_code}: {body[:500].decode(errors='replace')}")
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = data.get("message", {}).get("content", "")
                if content:
                    yield ("text", content)
                if data.get("done"):
                    input_tokens = data.get("prompt_eval_count", 0)
                    output_tokens = data.get("eval_count", 0)
                    break

    yield ("__stats__", json.dumps({"input_tokens": input_tokens, "output_tokens": output_tokens}))


async def _stream_openai_compat(
    prompt: str,
    system: str,
    model: str,
    base_url: str,
    api_key: Optional[str],
    temperature: float,
    max_tokens: int,
    history: Optional[list[dict]],
) -> AsyncGenerator[tuple[str, str], None]:
    messages = _build_openai_messages(system, prompt, history)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {"content-type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = base_url.rstrip("/") + "/v1/chat/completions"
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise LLMError(f"OpenAI-compat {resp.status_code}: {body[:500].decode(errors='replace')}")
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                content = data.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                if content:
                    yield ("text", content)

    yield ("__stats__", json.dumps({"input_tokens": 0, "output_tokens": 0}))


async def stream_llm(
    prompt: str,
    system: str,
    model: str,
    provider: str,
    base_url: Optional[str],
    api_key: Optional[str],
    temperature: float,
    max_tokens: int,
    history: Optional[list[dict]] = None,
    enable_thinking: bool = False,
    thinking_budget: int = 8000,
) -> AsyncGenerator[tuple[str, str], None]:
    """
    Stream LLM output. Yields (chunk_type, text) tuples.
    chunk_type: "thinking" | "text" | "__stats__"
    "__stats__" is always the last tuple; its text is a JSON blob.
    """
    logger.info("stream_llm provider=%s model=%s thinking=%s", provider, model, enable_thinking)

    if provider == "anthropic":
        if not api_key:
            raise LLMError("anthropic_key not set in vault")
        async for chunk in _stream_anthropic(
            prompt, system, model, api_key, temperature, max_tokens, history,
            enable_thinking, thinking_budget,
        ):
            yield chunk

    elif provider == "ollama":
        _base = base_url or "http://127.0.0.1:11434"
        async for chunk in _stream_ollama(prompt, system, model, _base, temperature, max_tokens, history):
            yield chunk

    elif provider in ("lmstudio", "openai", "openai_compat"):
        if provider == "lmstudio":
            _base = base_url or "http://127.0.0.1:1234"
        elif provider == "openai":
            _base = "https://api.openai.com"
        else:
            if not base_url:
                raise LLMError("base_url required for openai_compat provider")
            _base = base_url
        async for chunk in _stream_openai_compat(
            prompt, system, model, _base, api_key, temperature, max_tokens, history
        ):
            yield chunk

    else:
        raise LLMError(f"Unknown provider '{provider}' for streaming")
