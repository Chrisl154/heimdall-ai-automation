"""
MessagingManager — starts/stops adapters and routes outbound messages.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from core.models import ChannelType, MessagingChannel
from core.vault import get_vault

logger = logging.getLogger(__name__)

_ADAPTER_MAP = {
    ChannelType.TELEGRAM: "core.messaging.adapters.telegram.TelegramAdapter",
    ChannelType.DISCORD: "core.messaging.adapters.discord.DiscordAdapter",
    ChannelType.EMAIL: "core.messaging.adapters.email_adapter.EmailAdapter",
}


def _import_adapter(dotpath: str):
    module_path, cls_name = dotpath.rsplit(".", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, cls_name)


class MessagingManager:
    def __init__(self, data_dir: str = "data"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._channels_path = self._data_dir / "channels.json"
        self._adapters: dict[str, object] = {}
        self._channels: dict[str, MessagingChannel] = {}
        self._pm_callback = None
        self._load_channels()

    # ── Channel persistence ────────────────────────────────────────────────────

    def _load_channels(self) -> None:
        if not self._channels_path.exists():
            return
        try:
            raw = json.loads(self._channels_path.read_text(encoding="utf-8"))
            for item in raw:
                ch = MessagingChannel(**item)
                self._channels[ch.id] = ch
        except Exception as exc:
            logger.warning("Failed to load channels: %s", exc)

    def _save_channels(self) -> None:
        data = [c.model_dump() for c in self._channels.values()]
        self._channels_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ── Adapter lifecycle ──────────────────────────────────────────────────────

    def set_pm_callback(self, cb) -> None:
        self._pm_callback = cb

    async def start_all(self) -> None:
        vault = get_vault()
        for channel in self._channels.values():
            if not channel.enabled:
                continue
            # Inject credentials from vault
            resolved_creds = {}
            for k, v in channel.credentials.items():
                resolved_creds[k] = vault.get(v, v)  # treat value as vault key name
            channel.credentials = resolved_creds
            await self._start_adapter(channel)

    async def _start_adapter(self, channel: MessagingChannel) -> None:
        dotpath = _ADAPTER_MAP.get(channel.type)
        if not dotpath:
            logger.warning("No adapter for channel type: %s", channel.type)
            return
        try:
            AdapterCls = _import_adapter(dotpath)
            adapter = AdapterCls(channel, self._on_inbound_message)
            await adapter.start()
            self._adapters[channel.id] = adapter
            logger.info("Started %s adapter for channel %s", channel.type, channel.id)
        except ImportError as exc:
            logger.error("Adapter import failed for %s: %s", channel.type, exc)
        except Exception as exc:
            logger.error("Failed to start adapter for channel %s: %s", channel.id, exc)

    async def stop_all(self) -> None:
        for adapter in self._adapters.values():
            try:
                await adapter.stop()
            except Exception as exc:
                logger.warning("Adapter stop error: %s", exc)
        self._adapters.clear()

    # ── Broadcast ──────────────────────────────────────────────────────────────

    async def broadcast(self, text: str, urgent: bool = False) -> None:
        """Send text to all enabled channels."""
        prefix = "URGENT: " if urgent else ""
        for channel_id, adapter in self._adapters.items():
            channel = self._channels.get(channel_id)
            if not channel:
                continue
            for target in channel.targets:
                try:
                    await adapter.send_message(target, prefix + text)
                except Exception as exc:
                    logger.warning("Failed to send to %s/%s: %s", channel_id, target, exc)

    # ── Channel CRUD ───────────────────────────────────────────────────────────

    def add_channel(self, channel: MessagingChannel) -> None:
        self._channels[channel.id] = channel
        self._save_channels()

    def remove_channel(self, channel_id: str) -> bool:
        existed = channel_id in self._channels
        self._channels.pop(channel_id, None)
        if existed:
            self._save_channels()
        return existed

    def list_channels(self) -> list[MessagingChannel]:
        return list(self._channels.values())

    def get_channel(self, channel_id: str) -> Optional[MessagingChannel]:
        return self._channels.get(channel_id)

    def update_channel(self, channel_id: str, **kwargs) -> Optional[MessagingChannel]:
        ch = self._channels.get(channel_id)
        if not ch:
            return None
        for k, v in kwargs.items():
            setattr(ch, k, v)
        self._save_channels()
        return ch

    # ── Inbound routing ────────────────────────────────────────────────────────

    async def _on_inbound_message(self, sender_id: str, text: str, user_id: str) -> str:
        if self._pm_callback:
            return await self._pm_callback(text, session_id=f"msg_{sender_id}")
        return "PM not available."
