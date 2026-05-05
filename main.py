import os
import asyncio
from datetime import datetime
import pytz
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiohttp import web

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
FARAZ_BOT_USERNAME = os.environ.get("FARAZ_BOT_USERNAME", "farazsignal_bot")
TARGET_GROUP_ID = int(os.environ["TARGET_GROUP_ID"])
PORT = int(os.environ.get("PORT", 8080))

TEHRAN_TZ = pytz.timezone("Asia/Tehran")
forwarded_today = 0
counter = 0

print("🚀 ربات شروع شد")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage(incoming=True))
async def incoming_handler(event):
    global forwarded_today
    text = (event.message.text or "").strip().lower()
    if text == "/status":
        now = datetime.now(TEHRAN_TZ).strftime("%H:%M:%S")
        await client.send_message(TARGET_GROUP_ID, f"✅ ربات آنلاین\n🕐 {now}\n📨 فوروارد: {forwarded_today}\n🔁 پینگ: {counter}")
        return
    sender = await event.get_sender()
    if not sender:
        return
    username = getattr(sender, "username", "") or ""
    is_bot = getattr(sender, "bot", False)
    if username.lower() == FARAZ_BOT_USERNAME.lower() or (is_bot and FARAZ_BOT_USERNAME.lower() in username.lower()):
        try:
            await client.forward_messages(TARGET_GROUP_ID, event.message)
            forwarded_today += 1
            print(f"✅ فوروارد ({forwarded_today})")
        except Exception as e:
            print(f"❌ {e}")

@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    text = (event.message.text or "").strip().lower()
    if text == "/status":
        now = datetime.now(TEHRAN_TZ).strftime("%H:%M:%S")
        await client.send_message(TARGET_GROUP_ID, f"✅ ربات آنلاین\n🕐 {now}\n📨 فوروارد: {forwarded_today}\n🔁 پینگ: {counter}")

async def ping_loop():
    global counter
    print("⏰ Ping loop شروع - هر ۱۵ دقیقه")
    while True:
        await asyncio.sleep(15 * 60)
        counter += 1
        now = datetime.now(TEHRAN_TZ).strftime("%H:%M")
        msg = f"🟢 ربات زنده‌ست! | {now} | شماره: {counter}"
        try:
            await client.send_message(TARGET_GROUP_ID, msg)
            print(f"✅ ping {counter}")
        except Exception as e:
            print(f"❌ ping error: {e}")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    print(f"🌐 Web server پورت {PORT}")

async def main():
    await client.start()
    me = await client.get_me()
    print(f"✅ لاگین: {me.first_name} (@{me.username})")
    print(f"📤 گروه: {TARGET_GROUP_ID}")
    try:
        now = datetime.now(TEHRAN_TZ).strftime("%H:%M")
        await client.send_message(TARGET_GROUP_ID, f"🚀 ربات روشن شد! | {now}\n✅ هر ۱۵ دقیقه ping میفرسته")
    except Exception as e:
        print(f"❌ پیام شروع: {e}")
    await asyncio.gather(
        start_web_server(),
        client.run_until_disconnected(),
        ping_loop(),
    )

asyncio.run(main())
