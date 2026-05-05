import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
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
        print(f"📩 پیام جدید از فراز: {event.message.text[:80]}...")
        try:
            await client.forward_messages(TARGET_GROUP_ID, event.message)
            print("✅ فوروارد شد!")
        except Exception as e:
            print(f"❌ خطا: {e}")

async def main():
    await client.start()
    me = await client.get_me()
    print(f"✅ لاگین شد: {me.first_name} (@{me.username})")
    print(f"👀 منتظر پیام از: @{FARAZ_BOT_USERNAME}")
    print(f"📤 ارسال به گروه: {TARGET_GROUP_ID}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
