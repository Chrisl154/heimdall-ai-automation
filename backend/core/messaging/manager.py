"""
MessagingManager — starts/stops adapters and routes outbound messages.
"""
import json
import logging
import uuid
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

_VAULT_CRED_KEYS = {
    # channel_type -> list of credential field names that should go in vault
    ChannelType.TELEGRAM: ["bot_token"],
    ChannelType.DISCORD: ["bot_token"],
    ChannelType.EMAIL: ["smtp_password", "imap_password"],
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
        # Save channels with vault key references, not raw secrets
        data = [c.model_dump() for c in self._channels.values()]
        self._channels_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ── Credential vault storage ───────────────────────────────────────────────

    def _store_credentials_in_vault(self, channel: MessagingChannel) -> MessagingChannel:
        """Move sensitive credential values into the vault, replacing them with vault key refs."""
        vault = get_vault()
        secret_fields = _VAULT_CRED_KEYS.get(channel.type, [])
        new_creds = dict(channel.credentials)
        for field in secret_fields:
            raw_value = new_creds.get(field, "")
            if not raw_value:
                continue
            # Only store if it looks like an actual secret, not already a vault key ref
            vault_key = f"channel_{channel.id}_{field}"
            vault.set(vault_key, raw_value)
            new_creds[field] = vault_key  # store the key name, not the secret
        channel.credentials = new_creds
        return channel

    def _resolve_credentials(self, channel: MessagingChannel) -> MessagingChannel:
        """Resolve vault key references back to real values for use by adapters."""
        vault = get_vault()
        resolved = {}
        for k, v in channel.credentials.items():
            resolved[k] = vault.get(v, v)  # if v is a vault key → real value; else v itself
        # Return a copy so the stored channel keeps vault key refs
        import copy
        resolved_ch = copy.copy(channel)
        resolved_ch.credentials = resolved
        return resolved_ch

    # ── Adapter lifecycle ──────────────────────────────────────────────────────

    def set_pm_callback(self, cb) -> None:
        self._pm_callback = cb

    async def start_all(self) -> None:
        for channel in self._channels.values():
            if channel.enabled:
                await self.start_channel(channel)

    async def start_channel(self, channel: MessagingChannel) -> None:
        """Start (or restart) the adapter for a single channel."""
        if channel.id in self._adapters:
            await self.stop_channel(channel.id)
        await self._start_adapter(channel)

    async def _start_adapter(self, channel: MessagingChannel) -> None:
        dotpath = _ADAPTER_MAP.get(channel.type)
        if not dotpath:
            logger.warning("No adapter for channel type: %s", channel.type)
            return
        try:
            resolved = self._resolve_credentials(channel)
            AdapterCls = _import_adapter(dotpath)
            adapter = AdapterCls(resolved, self._on_inbound_message)
            await adapter.start()
            self._adapters[channel.id] = adapter
            logger.info("Started %s adapter for channel %s", channel.type, channel.id)
        except ImportError as exc:
            logger.error("Adapter import failed for %s: %s", channel.type, exc)
        except Exception as exc:
            logger.error("Failed to start adapter for channel %s: %s", channel.id, exc)

    async def stop_channel(self, channel_id: str) -> None:
        """Stop the adapter for a single channel if running."""
        adapter = self._adapters.pop(channel_id, None)
        if adapter:
            try:
                await adapter.stop()
            except Exception as exc:
                logger.warning("Adapter stop error for %s: %s", channel_id, exc)

    async def stop_all(self) -> None:
        for channel_id in list(self._adapters.keys()):
            await self.stop_channel(channel_id)

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
        # Store sensitive credentials in vault before persisting
        channel = self._store_credentials_in_vault(channel)
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
