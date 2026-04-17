"""
Telegram adapter — stub pending qwen-003 implementation.
Implements the interface so imports don't fail.
"""
import logging
from core.messaging.base import MessagingAdapter
from core.models import MessagingChannel

logger = logging.getLogger(__name__)


class TelegramAdapter(MessagingAdapter):
    """Stub — replace with qwen-003 output after review."""

    def __init__(self, channel: MessagingChannel, on_message_cb):
        super().__init__(channel, on_message_cb)
        self._task = None

    async def start(self) -> None:
        logger.warning("[Telegram] Adapter not yet implemented (qwen-003 pending).")

    async def stop(self) -> None:
        pass

    async def send_message(self, target: str, text: str) -> None:
        logger.warning("[Telegram] send_message called but adapter not implemented.")
