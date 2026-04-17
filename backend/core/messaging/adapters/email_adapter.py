"""Email messaging adapter for Heimdall (SMTP outbound + IMAP inbound)."""
from __future__ import annotations

import asyncio
import logging
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as email_policy
from typing import Callable, Awaitable

import aiosmtplib
import aioimaplib

from core.models import MessagingChannel
from core.messaging.base import MessagingAdapter

logger = logging.getLogger(__name__)


class EmailAdapter(MessagingAdapter):
    """Email adapter using aiosmtplib (SMTP) and aioimaplib (IMAP)."""

    def __init__(
        self,
        channel: MessagingChannel,
        on_message_cb: Callable[[str, str, str], Awaitable[str]],
    ) -> None:
        super().__init__(channel, on_message_cb)
        c = channel.credentials
        self._smtp_host: str = c.get("smtp_host", "")
        self._smtp_port: int = int(c.get("smtp_port", 587))
        self._smtp_user: str = c.get("smtp_user", "")
        self._smtp_password: str = c.get("smtp_password", "")
        self._from_address: str = c.get("from_address", "")
        self._imap_host: str = c.get("imap_host", "")
        self._imap_port: int = int(c.get("imap_port", 993))
        self._imap_user: str = c.get("imap_user", "")
        self._imap_password: str = c.get("imap_password", "")
        self._command_prefix: str = c.get("command_subject_prefix", "[Heimdall]")
        self._recipients: list[str] = channel.targets
        self._running: bool = False
        self._imap_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._imap_task = asyncio.create_task(self._imap_poller())
        logger.info("[Email] Adapter started for channel %s", self.channel_id)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._imap_task:
            self._imap_task.cancel()
            try:
                await self._imap_task
            except asyncio.CancelledError:
                pass
        logger.info("[Email] Adapter stopped.")

    async def send_message(self, target: str, text: str) -> None:
        msg = EmailMessage()
        msg["From"] = self._from_address
        msg["To"] = target
        msg["Subject"] = "[Heimdall] Status Update"
        msg.set_content(text)
        msg.add_alternative(_html_wrap(text), subtype="html")
        await aiosmtplib.send(
            msg,
            hostname=self._smtp_host,
            port=self._smtp_port,
            username=self._smtp_user,
            password=self._smtp_password,
            start_tls=self._smtp_port == 587,
            use_tls=self._smtp_port == 465,
        )

    # ── IMAP polling ──────────────────────────────────────────────────────────

    async def _imap_poller(self) -> None:
        while self._running:
            try:
                await self._check_imap()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("[Email] IMAP check failed: %s", exc)
            await asyncio.sleep(30)

    async def _check_imap(self) -> None:
        imap = aioimaplib.IMAP4_SSL(host=self._imap_host, port=self._imap_port)
        await imap.wait_hello_from_server()
        await imap.login(self._imap_user, self._imap_password)
        await imap.select("INBOX")

        # Only fetch unseen messages matching command prefix
        status, data = await imap.search("UNSEEN")
        if status != "OK" or not data or not data[0]:
            await imap.logout()
            return

        uid_list = data[0].split()
        for uid in uid_list[-20:]:  # cap at 20 to avoid flooding
            try:
                status, msg_data = await imap.fetch(uid, "(RFC822)")
                if status != "OK" or len(msg_data) < 2:
                    continue

                raw_bytes = msg_data[1] if isinstance(msg_data[1], bytes) else msg_data[1].encode()
                msg = BytesParser(policy=email_policy).parsebytes(raw_bytes)

                subject = str(msg.get("Subject", ""))
                if not subject.startswith(self._command_prefix):
                    continue

                sender = str(msg.get("From", ""))
                body_part = msg.get_body(preferencelist=("plain",))
                body = body_part.get_content().strip() if body_part else ""

                # Mark as seen
                await imap.store(uid, "+FLAGS", "\\Seen")

                # Dispatch to PM
                try:
                    reply = await self._on_message_cb(sender, f"{subject}\n\n{body}", sender)
                    if reply and sender:
                        await self.send_message(sender, reply)
                except Exception as exc:
                    logger.warning("[Email] Dispatch error: %s", exc)

            except Exception as exc:
                logger.warning("[Email] Failed to process message %s: %s", uid, exc)

        await imap.logout()


def _html_wrap(text: str) -> str:
    import html as html_lib
    escaped = html_lib.escape(text)
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        "<body style='font-family:sans-serif;padding:20px;'>"
        f"<pre style='white-space:pre-wrap;word-wrap:break-word;'>{escaped}</pre>"
        "</body></html>"
    )
