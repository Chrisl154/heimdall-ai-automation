"""
LLM Provider Config routes — manage agent configurations.
"""
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import yaml

from core.config import load_config

router = APIRouter(prefix="/api/config", tags=["config"])


def _path() -> Path:
    return Path(os.getenv("HEIMDALL_CONFIG_DIR", "config")) / "settings.yaml"


class AgentConfig(BaseModel):
    model: str
    provider: str
    base_url: Optional[str] = None
    temperature: float
    max_tokens: int


class AgentsConfig(BaseModel):
    worker: AgentConfig
    reviewer: AgentConfig
    orchestrator: AgentConfig


class AgentConfigPatch(BaseModel):
    model: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@router.get("/agents", response_model=AgentsConfig)
def get_agents():
    p = _path()
    if not p.exists():
        raise HTTPException(404, "No settings file")

    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    agents = cfg.get("agents", {})
    result = {
        "worker": {
            "model": agents.get("worker", {}).get("model", ""),
            "provider": agents.get("worker", {}).get("provider", ""),
            "base_url": agents.get("worker", {}).get("base_url"),
            "temperature": agents.get("worker", {}).get("temperature", 0.0),
            "max_tokens": agents.get("worker", {}).get("max_tokens", 0),
        },
        "reviewer": {
            "model": agents.get("reviewer", {}).get("model", ""),
            "provider": agents.get("reviewer", {}).get("provider", ""),
            "base_url": agents.get("reviewer", {}).get("base_url"),
            "temperature": agents.get("reviewer", {}).get("temperature", 0.0),
            "max_tokens": agents.get("reviewer", {}).get("max_tokens", 0),
        },
        "orchestrator": {
            "model": agents.get("orchestrator", {}).get("model", ""),
            "provider": agents.get("orchestrator", {}).get("provider", ""),
            "base_url": agents.get("orchestrator", {}).get("base_url"),
            "temperature": agents.get("orchestrator", {}).get("temperature", 0.0),
            "max_tokens": agents.get("orchestrator", {}).get("max_tokens", 0),
        },
    }
    return AgentsConfig(**result)


@router.patch("/agents/{agent_name}", response_model=AgentConfig)
def update_agent(agent_name: str, body: AgentConfigPatch):
    if agent_name not in ("worker", "reviewer", "orchestrator"):
        raise HTTPException(400, "Invalid agent name")

    p = _path()
    if not p.exists():
        raise HTTPException(404, "No settings file")

    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    agents = cfg.get("agents", {})
    agent = agents.get(agent_name, {})

    if body.model is not None:
        agent["model"] = body.model
    if body.provider is not None:
        agent["provider"] = body.provider
    if body.base_url is not None:
        agent["base_url"] = body.base_url
    if body.temperature is not None:
        agent["temperature"] = body.temperature
    if body.max_tokens is not None:
        agent["max_tokens"] = body.max_tokens

    agents[agent_name] = agent
    cfg["agents"] = agents

    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

    load_config.cache_clear()

    return AgentConfig(**agent)
