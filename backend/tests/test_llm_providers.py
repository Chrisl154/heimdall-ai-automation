"""
Tests for core/llm_providers.py.

Network calls are fully mocked — no real Ollama or Anthropic connection needed.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm_providers import (
    LLMError,
    call_llm,
    get_claude_rate_info,
    stream_llm,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _collect(gen) -> list[tuple[str, str]]:
    """Drain an async generator into a list."""
    return [item async for item in gen]


def _make_ollama_mock(ndjson_lines: list[str]):
    """
    Build a mock httpx.AsyncClient whose .stream() context manager yields
    the given NDJSON lines via aiter_lines().
    """
    async def _aiter_lines():
        for line in ndjson_lines:
            yield line

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.aread = AsyncMock(return_value=b"")
    mock_resp.aiter_lines = _aiter_lines
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    return mock_client


# ── Ollama thinking extraction ────────────────────────────────────────────────

class TestOllamaThinkingExtraction:
    """_stream_ollama() should emit (thinking/text/__stats__) tuples correctly."""

    def _run(self, lines):
        from core.llm_providers import _stream_ollama
        client = _make_ollama_mock(lines)
        with patch("httpx.AsyncClient", return_value=client):
            return asyncio.get_event_loop().run_until_complete(
                _collect(_stream_ollama("prompt", "", "model", "http://localhost:11434", 0.7, 512, None))
            )

    def test_dedicated_thinking_field_yields_thinking_chunk(self):
        lines = [
            json.dumps({"message": {"thinking": "step 1", "content": ""}}),
            json.dumps({"message": {"thinking": "", "content": "answer"}, "done": True,
                        "prompt_eval_count": 5, "eval_count": 10}),
        ]
        chunks = self._run(lines)
        thinking = [t for t in chunks if t[0] == "thinking"]
        assert any("step 1" in t[1] for t in thinking)

    def test_inline_think_tags_extracted_and_stripped(self):
        lines = [
            json.dumps({"message": {"thinking": "", "content": "<think>reason</think>answer"},
                        "done": True, "prompt_eval_count": 1, "eval_count": 2}),
        ]
        chunks = self._run(lines)
        assert ("thinking", "reason") in chunks
        text_chunks = [t[1] for t in chunks if t[0] == "text"]
        assert any("answer" in t for t in text_chunks)
        # The <think> block must not bleed into the text output
        assert not any("<think>" in t for t in text_chunks)

    def test_plain_content_yields_text_only(self):
        lines = [
            json.dumps({"message": {"thinking": "", "content": "hello"},
                        "done": True, "prompt_eval_count": 1, "eval_count": 1}),
        ]
        chunks = self._run(lines)
        assert ("text", "hello") in chunks
        assert not any(t[0] == "thinking" for t in chunks)

    def test_empty_think_block_is_skipped(self):
        lines = [
            json.dumps({"message": {"thinking": "", "content": "<think>   </think>answer"},
                        "done": True, "prompt_eval_count": 1, "eval_count": 1}),
        ]
        chunks = self._run(lines)
        thinking_chunks = [t for t in chunks if t[0] == "thinking"]
        # Whitespace-only block should be skipped
        assert not any(t[1].strip() == "" or t[1].strip() == "   " for t in thinking_chunks if t[1])

    def test_stats_tuple_emitted_at_end(self):
        lines = [
            json.dumps({"message": {"thinking": "", "content": "hi"},
                        "done": True, "prompt_eval_count": 10, "eval_count": 20}),
        ]
        chunks = self._run(lines)
        last = chunks[-1]
        assert last[0] == "__stats__"
        stats = json.loads(last[1])
        assert stats["input_tokens"] == 10
        assert stats["output_tokens"] == 20

    def test_http_error_raises_llm_error(self):
        async def _aiter_lines():
            return
            yield  # make it a generator

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.aread = AsyncMock(return_value=b"Internal Server Error")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        from core.llm_providers import _stream_ollama
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(LLMError, match="500"):
                asyncio.get_event_loop().run_until_complete(
                    _collect(_stream_ollama("p", "", "m", "http://localhost:11434", 0.5, 256, None))
                )


# ── stream_llm dispatch ───────────────────────────────────────────────────────

class TestStreamLlmDispatch:
    """stream_llm() must route providers correctly and reject unknown ones."""

    def test_unknown_provider_raises_llm_error(self):
        with pytest.raises(LLMError, match="Unknown provider"):
            asyncio.get_event_loop().run_until_complete(
                _collect(stream_llm("p", "", "m", "bogus", None, None, 0.5, 256))
            )

    def test_ollama_provider_dispatches_to_stream_ollama(self):
        called_with: list = []

        async def fake_stream_ollama(prompt, system, model, base_url, temp, max_tok, hist):
            called_with.extend([prompt, model, base_url])
            yield ("text", "ok")
            yield ("__stats__", '{"input_tokens": 0, "output_tokens": 0}')

        with patch("core.llm_providers._stream_ollama", side_effect=fake_stream_ollama):
            asyncio.get_event_loop().run_until_complete(
                _collect(stream_llm("prompt", "", "mymodel", "ollama",
                                    "http://localhost:11434", None, 0.7, 512))
            )
        assert called_with[0] == "prompt"
        assert called_with[1] == "mymodel"


# ── call_llm ─────────────────────────────────────────────────────────────────

class TestCallLlm:
    """call_llm() concatenates text chunks and surfaces stats."""

    def test_unknown_provider_raises_llm_error(self):
        with pytest.raises(LLMError):
            asyncio.get_event_loop().run_until_complete(
                call_llm("p", "", "m", "bogus", None, None, 0.5, 256)
            )

    def test_call_llm_returns_text_and_stats(self):
        # call_llm delegates to _call_ollama; mock that directly
        async def fake_call_ollama(*args, **kwargs):
            return ("hello world", {"input_tokens": 5, "output_tokens": 2})

        with patch("core.llm_providers._call_ollama", side_effect=fake_call_ollama):
            text, stats = asyncio.get_event_loop().run_until_complete(
                call_llm("p", "", "m", "ollama", None, None, 0.5, 256)
            )
        assert text == "hello world"
        assert stats["input_tokens"] == 5
        assert stats["output_tokens"] == 2

    def test_call_llm_returns_value_from_provider(self):
        async def fake_call_ollama(*args, **kwargs):
            return ("answer", {"input_tokens": 3, "output_tokens": 1})

        with patch("core.llm_providers._call_ollama", side_effect=fake_call_ollama):
            text, stats = asyncio.get_event_loop().run_until_complete(
                call_llm("p", "", "m", "ollama", None, None, 0.5, 256)
            )
        assert text == "answer"
        assert stats["output_tokens"] == 1


# ── Misc public API ───────────────────────────────────────────────────────────

class TestMiscPublicApi:
    def test_get_claude_rate_info_returns_dict(self):
        info = get_claude_rate_info()
        assert isinstance(info, dict)
