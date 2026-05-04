import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- Config ---
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]

# SESSION_STRING رو اینجا مستقیم بذار
SESSION_STRING = "1BJWap1wBu47GkqAUHhnfTTny6USARgztwGS8OvPSihvRU6bXfbNy74qn8qdkdwxN74cTJAv1toTi5YxbOlSbYm37PY3d2teigsViAG5mU1UzfOPPgBuhA-3PCvk-zBgP-pCoPkhWQYQNsKI_aepkgfKsyT3cVNawKeE-bpDGVCcEEENIpWlW0MU-L7PX1kts2DM0sw1AlNQSWZSFBVZWmYzBK0yMGARa9heeQ5ee3QZU8AG0egHaspW95cicK5EfYE9CjDpYfPe75ykbdXXRduNXltgHvQcEPxP-4LBj5hM8o6F0deRoJnXnMrje6SOiaK7rTX2C9v5Wa06WbN--TUO5STanV74="

FARAZ_BOT_USERNAME = os.environ.get("FARAZ_BOT_USERNAME", "farazsignal_bot")
TARGET_GROUP_ID = int(os.environ["TARGET_GROUP_ID"])

print("🚀 Faraz Forwarder starting...")
print(f"SESSION length: {len(SESSION_STRING)}")

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
