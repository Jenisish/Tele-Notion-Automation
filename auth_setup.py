"""
One-time Telegram authentication setup.
Run this first: python3 auth_setup.py
It will ask for your phone number and the login code.
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.config import (
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_SESSION_PATH,
)
from src.logger import get_logger

log = get_logger("auth")


async def main():
    from telethon import TelegramClient

    print("=" * 50)
    print("Telegram Authentication Setup")
    print("=" * 50)

    if TELEGRAM_API_ID == 0 or not TELEGRAM_API_HASH:
        print("ERROR: Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env first")
        sys.exit(1)

    # Ensure state directory exists
    os.makedirs(os.path.dirname(TELEGRAM_SESSION_PATH), exist_ok=True)

    client = TelegramClient(
        TELEGRAM_SESSION_PATH,
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
    )

    await client.connect()

    if await client.is_user_authorized():
        print("Already authorized! Session is valid.")
        me = await client.get_me()
        print(f"Logged in as: {me.first_name} (@{me.username or 'no username'})")
        await client.disconnect()
        return

    phone = input("Enter your phone number (with country code, e.g. +91XXXXXXXXXX): ").strip()
    if not phone:
        print("Phone number required.")
        sys.exit(1)

    await client.send_code_request(phone)
    code = input("Enter the code you received: ").strip()

    try:
        await client.sign_in(phone, code)
    except Exception:
        password = input("Enter your 2FA password: ").strip()
        await client.sign_in(password=password)

    me = await client.get_me()
    print(f"\nSuccess! Logged in as: {me.first_name} (@{me.username or 'no username'})")
    print(f"Session saved to: {TELEGRAM_SESSION_PATH}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
