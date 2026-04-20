"""
NotificationRouter — consumes PipelineEvents and broadcasts human-readable
notifications to all enabled messaging channels.
"""
import asyncio
import logging
from typing import TYPE_CHECKING

from core.models import EventType, PipelineEvent

if TYPE_CHECKING:
    from core.messaging.manager import MessagingManager

logger = logging.getLogger(__name__)

_NOTIFICATION_EVENTS = {
    EventType.PM_STARTED,
    EventType.PM_STOPPED,
    EventType.TASK_STARTED,
    EventType.TASK_COMPLETED,
    EventType.TASK_ESCALATED,
    EventType.TASK_FAILED,
    EventType.REVIEW_APPROVED,
    EventType.REVIEW_REJECTED,
    EventType.ERROR,
}

_EVENT_TEMPLATES = {
    EventType.PM_STARTED:         "Heimdall PM started.",
    EventType.PM_STOPPED:         "Heimdall PM stopped.",
    EventType.TASK_STARTED:       "Task [{task_id}] started.",
    EventType.TASK_COMPLETED:     "Task [{task_id}] completed successfully.",
    EventType.TASK_ESCALATED:     "ESCALATION — Task [{task_id}] needs human input: {message}",
    EventType.TASK_FAILED:        "FAILURE — Task [{task_id}] failed: {message}",
    EventType.REVIEW_APPROVED:    "Task [{task_id}] review approved: {message}",
    EventType.REVIEW_REJECTED:    "Task [{task_id}] review rejected: {message}",
    EventType.ERROR:              "Error in task [{task_id}]: {message}",
}

_URGENT_EVENTS = {EventType.TASK_ESCALATED, EventType.TASK_FAILED, EventType.ERROR}


class NotificationRouter:
    def __init__(self, messaging_manager: "MessagingManager"):
        self._mgr = messaging_manager
        self._settings: dict = {}

    def configure(self, settings: dict) -> None:
        self._settings = settings.get("notifications", {})

    async def broadcast(self, text: str, urgent: bool = False) -> None:
        """Send a plain-text notification to all enabled channels."""
        try:
            await self._mgr.broadcast(text, urgent=urgent)
        except Exception as exc:
            logger.warning("Notification broadcast failed: %s", exc)

    async def handle_event(self, event: PipelineEvent) -> None:
        if event.type not in _NOTIFICATION_EVENTS:
            return

        # Check per-event type toggle in settings
        setting_key = f"on_{event.type.value}"
        if not self._settings.get(setting_key, True):
            return

        template = _EVENT_TEMPLATES.get(event.type, "{message}")
        text = template.format(
            task_id=event.task_id or "—",
            message=event.message,
        )
        urgent = event.type in _URGENT_EVENTS

        try:
            await self._mgr.broadcast(text, urgent=urgent)
        except Exception as exc:
            logger.warning("Notification broadcast failed: %s", exc)
