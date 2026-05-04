import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- Config from environment variables ---
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
FARAZ_BOT_USERNAME = os.environ.get("FARAZ_BOT_USERNAME", "farazsignal_bot")
TARGET_GROUP_ID = int(os.environ["TARGET_GROUP_ID"])

print("🚀 Faraz Forwarder starting...")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage())
async def handler(event):
    sender = await event.get_sender()

    if not sender:
        return

    sender_username = getattr(sender, "username", "") or ""
    is_bot = getattr(sender, "bot", False)

    if sender_username.lower() == FARAZ_BOT_USERNAME.lower() or (
        is_bot and FARAZ_BOT_USERNAME.lower() in sender_username.lower()
    ):
        print(f"📩 New alert from Faraz: {event.message.text[:80]}...")
        try:
            await client.forward_messages(TARGET_GROUP_ID, event.message)
            print("✅ Forwarded to group successfully.")
        except Exception as e:
            print(f"❌ Failed to forward: {e}")

async def main():
    await client.start()
    me = await client.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")
    print(f"👀 Watching for messages from: @{FARAZ_BOT_USERNAME}")
    print(f"📤 Forwarding to group ID: {TARGET_GROUP_ID}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
