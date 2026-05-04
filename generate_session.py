"""
Run this script ONCE locally to generate your SESSION_STRING.
Then copy the output string into your Railway environment variables.

Install first:  pip install telethon
Run with:       python generate_session.py
"""

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = input("Enter your API_ID: ").strip()
API_HASH = input("Enter your API_HASH: ").strip()

async def main():
    async with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
        session_string = client.session.save()
        print("\n" + "="*60)
        print("✅ Your SESSION_STRING (copy this into Railway):")
        print("="*60)
        print(session_string)
        print("="*60 + "\n")

asyncio.run(main())
