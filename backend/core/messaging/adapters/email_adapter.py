"""
Email adapter — stub pending qwen-005 implementation.
"""
import logging
from core.messaging.base import MessagingAdapter
from core.models import MessagingChannel

logger = logging.getLogger(__name__)


class EmailAdapter(MessagingAdapter):
    """Stub — replace with qwen-005 output after review."""

    async def start(self) -> None:
        logger.warning("[Email] Adapter not yet implemented (qwen-005 pending).")

    async def stop(self) -> None:
        pass

    async def send_message(self, target: str, text: str) -> None:
        logger.warning("[Email] send_message called but adapter not implemented.")
