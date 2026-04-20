"""
LLM provider implementations.

Supported providers: anthropic | ollama | lmstudio | openai | openai_compat

Exponential backoff: 5, 10, 20, 40, 80 s on 429/5xx.
"""
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_BACKOFF = [5, 10, 20, 40, 80]


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


async def _call_anthropic(
    prompt: str,
    system: str,
    model: str,
    api_key: str,
    temperature: float,
    max_tokens: int,
    history: Optional[list[dict]],
) -> str:
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
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]
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
) -> str:
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
                if resp.status_code in (429,) or resp.status_code >= 500:
                    last_exc = LLMError(f"Ollama {resp.status_code}: {resp.text[:200]}")
                    logger.warning("Ollama %s, retry %d/%d", resp.status_code, i, len(_BACKOFF))
                    continue
                resp.raise_for_status()
                return resp.json()["message"]["content"]
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
) -> str:
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
                if resp.status_code in (429,) or resp.status_code >= 500:
                    last_exc = LLMError(f"OpenAI-compat {resp.status_code}: {resp.text[:200]}")
                    logger.warning("OpenAI-compat %s, retry %d/%d", resp.status_code, i, len(_BACKOFF))
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
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
) -> str:
    """
    Route an LLM call to the correct provider.

    Supported providers: anthropic | ollama | lmstudio | openai | openai_compat
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
