"""
Pydantic data models for Heimdall.
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Task status state machine ─────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    FIXING = "fixing"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Task(BaseModel):
    id: str
    title: str
    description: str
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    max_review_iterations: int = 3
    current_iteration: int = 0
    output_path: str = ""
    error: Optional[str] = None
    # Latest worker output (populated during workflow)
    latest_output: Optional[str] = None
    # Latest review result
    latest_review: Optional["ReviewResult"] = None


class ReviewIssue(BaseModel):
    severity: str       # "critical" | "major" | "minor"
    description: str
    location: str = ""


class ReviewResult(BaseModel):
    approved: bool
    summary: str = ""
    issues: list[ReviewIssue] = Field(default_factory=list)
    feedback: str = ""
    iteration: int = 0


class TaskResult(BaseModel):
    task_id: str
    status: str         # "completed" | "escalated" | "failed"
    output: str = ""
    review: Optional[ReviewResult] = None
    iterations: int = 0
    reason: str = ""
    duration_seconds: float = 0.0


# ── PM / Workflow events (streamed via SSE) ───────────────────────────────────

class EventType(str, Enum):
    PM_STARTED = "pm_started"
    PM_STOPPED = "pm_stopped"
    TASK_STARTED = "task_started"
    TASK_SENT_TO_WORKER = "task_sent_to_worker"
    WORKER_OUTPUT_RECEIVED = "worker_output_received"
    REVIEW_STARTED = "review_started"
    REVIEW_APPROVED = "review_approved"
    REVIEW_REJECTED = "review_rejected"
    FIX_REQUESTED = "fix_requested"
    TASK_COMPLETED = "task_completed"
    TASK_ESCALATED = "task_escalated"
    TASK_FAILED = "task_failed"
    PM_CHAT_RESPONSE = "pm_chat_response"
    ERROR = "error"


class PipelineEvent(BaseModel):
    type: EventType
    task_id: Optional[str] = None
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


# ── Messaging ─────────────────────────────────────────────────────────────────

class ChannelType(str, Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"


class MessagingChannel(BaseModel):
    id: str
    type: ChannelType
    name: str
    enabled: bool = True
    credentials: dict[str, str] = Field(default_factory=dict)
    # For Discord: channel IDs; for Telegram: chat IDs; for Email: addresses
    targets: list[str] = Field(default_factory=list)


# ── API request/response schemas ─────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str           # "user" | "assistant"
    content: str
    timestamp: float = Field(default_factory=time.time)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    session_id: str


class VaultSetRequest(BaseModel):
    value: str


class TaskCreateRequest(BaseModel):
    title: str
    description: str
    priority: TaskPriority = TaskPriority.MEDIUM
    tags: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    max_review_iterations: int = 3
    output_path: str = ""


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    tags: Optional[list[str]] = None


class PMStatusResponse(BaseModel):
    running: bool
    current_task_id: Optional[str] = None
    tasks_pending: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_escalated: int = 0
    uptime_seconds: float = 0.0


class DirectChatRequest(BaseModel):
    message: str
    provider: str
    model: str
    session_id: str = "default"
