"""Telegram message fetcher using Telethon."""
import asyncio
import re
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    AuthKeyError,
)
from telethon.tl.types import Message as TLMessage

from src.config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_SESSION_PATH,
    TELEGRAM_CHANNELS,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
)
from src.logger import get_logger
from src.state import get_last_message_id, set_last_message_id

log = get_logger("telegram")


class TelegramFetcher:
    """Async Telegram client that fetches new messages from channels."""

    def __init__(self) -> None:
        self.client = TelegramClient(
            TELEGRAM_SESSION_PATH,
            TELEGRAM_API_ID,
            TELEGRAM_API_HASH,
        )

    async def connect(self) -> None:
        await self.client.connect()
        if not await self.client.is_user_authorized():
            log.error("Telegram session not authorized. Run auth_setup.py first.")
            raise RuntimeError("Telegram not authorized")

    async def disconnect(self) -> None:
        await self.client.disconnect()

    async def fetch_new_messages(
        self, channel_username: str
    ) -> list[dict]:
        """
        Fetch messages newer than the last-seen ID.
        Returns list of dicts with keys: id, text, date, link, channel.
        """
        last_id = get_last_message_id(channel_username)
        messages: list[dict] = []

        for attempt in range(MAX_RETRIES):
            try:
                entity = await self.client.get_entity(channel_username)
                async for msg in self.client.iter_messages(
                    entity, min_id=last_id, limit=100
                ):
                    if msg.id <= last_id:
                        continue
                    text = msg.message or ""
                    if not text.strip():
                        continue
                    # Build t.me link
                    link = f"https://t.me/{channel_username}/{msg.id}"
                    messages.append(
                        {
                            "id": msg.id,
                            "text": text,
                            "date": msg.date.isoformat() if msg.date else "",
                            "link": link,
                            "channel": channel_username,
                        }
                    )
                # Update last seen
                if messages:
                    max_id = max(m["id"] for m in messages)
                    set_last_message_id(channel_username, max_id)
                    log.info(
                        f"Fetched {len(messages)} new messages from @{channel_username} (last_id now {max_id})",
                        extra={"channel": channel_username, "action": "fetch"},
                    )
                return messages

            except FloodWaitError as e:
                wait = e.seconds
                log.warning(
                    f"FloodWait for @{channel_username}: {wait}s",
                    extra={"channel": channel_username},
                )
                await asyncio.sleep(wait)

            except ChannelPrivateError:
                log.error(
                    f"Channel @{channel_username} is private or inaccessible",
                    extra={"channel": channel_username},
                )
                return []

            except AuthKeyError:
                log.error("Telegram auth key invalid. Re-run auth_setup.py.")
                raise

            except Exception as e:
                delay = RETRY_BASE_DELAY ** (attempt + 1)
                log.warning(
                    f"Error fetching @{channel_username} (attempt {attempt+1}/{MAX_RETRIES}): {e}. Retrying in {delay:.0f}s",
                    extra={"channel": channel_username},
                )
                await asyncio.sleep(delay)

        log.error(
            f"Failed to fetch @{channel_username} after {MAX_RETRIES} attempts",
            extra={"channel": channel_username},
        )
        return []

    async def fetch_all_channels(self) -> list[dict]:
        """Fetch new messages from all configured channels."""
        await self.connect()
        all_messages: list[dict] = []
        try:
            for ch in TELEGRAM_CHANNELS:
                msgs = await self.fetch_new_messages(ch)
                all_messages.extend(msgs)
        finally:
            await self.disconnect()
        return all_messages
