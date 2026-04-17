"""Base class for all messaging adapters."""
from abc import ABC, abstractmethod
from typing import Callable, Awaitable

from core.models import MessagingChannel


class MessagingAdapter(ABC):
    def __init__(self, channel: MessagingChannel, on_message_cb: Callable[..., Awaitable[str]]):
        self.channel = channel
        self.channel_id = channel.id
        self._on_message_cb = on_message_cb

    @abstractmethod
    async def start(self) -> None:
        """Start the adapter (polling, webhooks, etc.)."""

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully shut down the adapter."""

    @abstractmethod
    async def send_message(self, target: str, text: str) -> None:
        """Send a message to the given target (chat_id, channel_id, email address)."""

    async def _dispatch(self, sender_id: str, text: str, user_id: str, session_id: str) -> None:
        """Forward an inbound message to the PM and reply with the result."""
        try:
            reply = await self._on_message_cb(sender_id, text, user_id)
            if reply:
                await self.send_message(sender_id, reply)
        except Exception as exc:
            try:
                await self.send_message(sender_id, f"Error: {exc}")
            except Exception:
                pass

    async def _handle_command(self, sender_id: str, command: str, args: str, session_id: str) -> None:
        """Map slash/prefix commands to PM chat messages."""
        cmd_map = {
            "/start": "Hello! I am Heimdall. How can I help?",
            "/help": "help",
            "/status": "status",
            "/tasks": "list tasks",
            "/stop": "stop pm",
            "!status": "status",
            "!tasks": "list tasks",
            "!stop": "stop pm",
            "!help": "help",
        }
        text = cmd_map.get(command, f"{command} {args}".strip())
        await self._dispatch(sender_id, text, sender_id, session_id)
