"""Telegram messaging adapter for Heimdall."""
from __future__ import annotations

from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from core.models import MessagingChannel
from core.messaging.base import MessagingAdapter

import logging

logger = logging.getLogger(__name__)


class TelegramAdapter(MessagingAdapter):
    """Telegram adapter using python-telegram-bot long-polling."""

    def __init__(
        self,
        channel: MessagingChannel,
        on_message_cb: Callable[[str, str, str], Awaitable[str]],
    ) -> None:
        super().__init__(channel, on_message_cb)
        self.bot_token: str = channel.credentials.get("bot_token", "")
        if not self.bot_token:
            raise ValueError("Telegram channel credentials must include 'bot_token'")
        self.allowed_chat_ids: set[str] = set(channel.targets)
        self._application: Application | None = None
        self._running: bool = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True

        async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.message or not update.effective_chat or not update.effective_user:
                return
            chat_id = str(update.effective_chat.id)
            if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
                return
            text = update.message.text or ""
            user_id = str(update.effective_user.id)
            await self._dispatch(chat_id, text, user_id, "telegram")

        async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.message or not update.effective_chat or not update.effective_user:
                return
            chat_id = str(update.effective_chat.id)
            if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
                return
            # Extract command name from message text (e.g. "/status" → "status")
            raw = update.message.text or ""
            command = raw.split()[0].lstrip("/").split("@")[0]
            args = " ".join(context.args or [])
            user_id = str(update.effective_user.id)
            await self._handle_command(chat_id, f"/{command}", args, "telegram")

        self._application = Application.builder().token(self.bot_token).build()
        self._application.add_handler(
            CommandHandler(["start", "help", "status", "tasks", "stop"], on_command)
        )
        self._application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, on_message)
        )

        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling(drop_pending_updates=True)
        logger.info("[Telegram] Adapter started for channel %s", self.channel_id)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._application:
            try:
                await self._application.updater.stop()
                await self._application.stop()
                await self._application.shutdown()
            except Exception as exc:
                logger.warning("[Telegram] Error during shutdown: %s", exc)
        logger.info("[Telegram] Adapter stopped.")

    async def send_message(self, target: str, text: str) -> None:
        if not self._application:
            raise RuntimeError("Telegram adapter not started")
        escaped = _escape_markdown_v2(text)
        await self._application.bot.send_message(
            chat_id=target,
            text=escaped,
            parse_mode="MarkdownV2",
        )


def _escape_markdown_v2(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    result = ""
    for ch in text:
        if ch in special:
            result += "\\" + ch
        else:
            result += ch
    return result
