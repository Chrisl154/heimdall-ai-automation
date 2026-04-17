"""
Discord adapter — stub pending qwen-004 implementation.
"""
import logging
from core.messaging.base import MessagingAdapter
from core.models import MessagingChannel

logger = logging.getLogger(__name__)


class DiscordAdapter(MessagingAdapter):
    """Stub — replace with qwen-004 output after review."""

    async def start(self) -> None:
        logger.warning("[Discord] Adapter not yet implemented (qwen-004 pending).")

    async def stop(self) -> None:
        pass

    async def send_message(self, target: str, text: str) -> None:
        logger.warning("[Discord] send_message called but adapter not implemented.")
