"""
LLM provider stub.

The full implementation is assigned to Qwen via task qwen-001 in tasks/backlog.yaml.
This stub lets the rest of the codebase import and call call_llm without errors
while Qwen's implementation is pending review.

Once qwen-001 is completed and approved, replace this file with the reviewed output.
"""
import asyncio
from typing import Optional


class LLMError(Exception):
    """Raised when an LLM call fails after all retries."""


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

    This stub raises LLMError until replaced by the qwen-001 implementation.
    After qwen-001 is reviewed and approved, this file will be replaced.
    """
    raise LLMError(
        f"LLM provider '{provider}' not yet implemented. "
        "Waiting for task qwen-001 to be completed and reviewed."
    )
