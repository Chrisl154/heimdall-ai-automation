"""Discord messaging adapter for Heimdall."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

import discord
from discord.ext import commands
from discord import Message

from core.models import MessagingChannel
from core.messaging.base import MessagingAdapter

logger = logging.getLogger(__name__)


class DiscordAdapter(MessagingAdapter):
    """Discord adapter using discord.py v2."""

    def __init__(
        self,
        channel: MessagingChannel,
        on_message_cb: Callable[[str, str, str], Awaitable[str]],
    ) -> None:
        super().__init__(channel, on_message_cb)
        self.bot_token: str = channel.credentials.get("bot_token", "")
        if not self.bot_token:
            raise ValueError("Discord channel credentials must include 'bot_token'")
        self.allowed_channel_ids: set[str] = set(channel.targets)
        self._bot: commands.Bot | None = None
        self._task: asyncio.Task | None = None
        self._running: bool = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True

        intents = discord.Intents.default()
        intents.message_content = True
        self._bot = commands.Bot(command_prefix="!", intents=intents)

        adapter = self  # capture for closures

        @self._bot.event
        async def on_ready() -> None:
            logger.info("[Discord] Bot ready as %s", adapter._bot.user)

        @self._bot.event
        async def on_message(message: Message) -> None:
            if message.author.bot:
                return
            channel_id = str(message.channel.id)
            if adapter.allowed_channel_ids and channel_id not in adapter.allowed_channel_ids:
                return
            content = message.content.strip()
            if not content:
                return
            user_id = str(message.author.id)
            if content.startswith("!"):
                await adapter._handle_command(channel_id, content.split()[0], " ".join(content.split()[1:]), "discord")
            else:
                await adapter._dispatch(channel_id, content, user_id, "discord")

        @self._bot.event
        async def on_command_error(ctx: commands.Context, error: Exception) -> None:
            pass

        # bot.start() blocks until the bot is closed — run it as a background task
        self._task = asyncio.create_task(self._bot.start(self.bot_token))
        logger.info("[Discord] Adapter started for channel %s", self.channel_id)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._bot:
            try:
                await self._bot.close()
            except Exception as exc:
                logger.warning("[Discord] Error during shutdown: %s", exc)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        logger.info("[Discord] Adapter stopped.")

    async def send_message(self, target: str, text: str) -> None:
        if not self._bot:
            raise RuntimeError("Discord adapter not started")
        channel = self._bot.get_channel(int(target))
        if not channel:
            logger.warning("[Discord] Channel %s not found in cache", target)
            return
        for chunk in _split_message(text):
            await channel.send(chunk)


def _split_message(text: str, max_length: int = 2000) -> list[str]:
    chunks: list[str] = []
    while len(text) > max_length:
        split_pos = text.rfind("\n", 0, max_length)
        if split_pos == -1:
            split_pos = text.rfind(" ", 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        chunks.append(text[:split_pos].strip())
        text = text[split_pos:].strip()
    if text:
        chunks.append(text)
    return chunks
