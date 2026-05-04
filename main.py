import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User, Channel, Chat

# --- Config from environment variables ---
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
FARAZ_BOT_USERNAME = os.environ.get("FARAZ_BOT_USERNAME", "farazsignal_bot").lower().strip("@")
TARGET_GROUP_ID = int(os.environ["TARGET_GROUP_ID"])

print("🚀 Faraz Forwarder starting...")

# ✅ FIX: use StringSession properly
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


def is_from_faraz(sender, chat) -> bool:
    """Check if message is from Faraz bot — works for both user-bots and channels."""
    if sender:
        username = (getattr(sender, "username", "") or "").lower()
        is_bot = getattr(sender, "bot", False)
        if username == FARAZ_BOT_USERNAME:
            return True
        if is_bot and FARAZ_BOT_USERNAME in username:
            return True

    # ✅ FIX: also handle channel/chat as sender (common for signal bots)
    if chat:
        username = (getattr(chat, "username", "") or "").lower()
        title = (getattr(chat, "title", "") or "").lower()
        if username == FARAZ_BOT_USERNAME:
            return True
        if FARAZ_BOT_USERNAME in username or FARAZ_BOT_USERNAME in title:
            return True

    return False


@client.on(events.NewMessage())
async def handler(event):
    try:
        sender = await event.get_sender()
        chat = await event.get_chat()

        if not is_from_faraz(sender, chat):
            return

        text_preview = (event.message.text or "")[:80]
        print(f"📩 New alert from Faraz: {text_preview}...")

        await client.forward_messages(TARGET_GROUP_ID, event.message)
        print("✅ Forwarded to group successfully.")

    except Exception as e:
        print(f"❌ Error in handler: {e}")


async def main():
    await client.start()
    me = await client.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")
    print(f"👀 Watching for messages from: @{FARAZ_BOT_USERNAME}")
    print(f"📤 Forwarding to group ID: {TARGET_GROUP_ID}")

    # ✅ FIX: keep alive with reconnect loop
    while True:
        try:
            await client.run_until_disconnected()
        except Exception as e:
            print(f"⚠️ Disconnected: {e} — reconnecting in 5s...")
            await asyncio.sleep(5)
            await client.connect()


if __name__ == "__main__":
    asyncio.run(main())
