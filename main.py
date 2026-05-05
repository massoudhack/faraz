import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
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
# برای تست: هر ۳۰ دقیقه - برای production روی False بذار
TEST_MODE = os.environ.get("TEST_MODE", "true").lower() == "true"

TEHRAN_TZ = pytz.timezone("Asia/Tehran")
forwarded_today = 0

print("🚀 Faraz Forwarder starting...")
print(f"🧪 TEST_MODE: {TEST_MODE}")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def fetch_forex_news():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json(content_type=None)
        today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
        high_events = []
        for ev in data:
            try:
                event_date = ev.get("date", "")[:10]
                impact = ev.get("impact", "").lower()
                if event_date == today and impact == "high":
                    title = ev.get("title", "نامشخص")
                    currency = ev.get("country", "")
                    time_str = ev.get("date", "")
                    try:
                        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        dt_tehran = dt.astimezone(TEHRAN_TZ)
                        time_fmt = dt_tehran.strftime("%H:%M")
                    except:
                        time_fmt = "نامشخص"
                    forecast = ev.get("forecast", "-") or "-"
                    previous = ev.get("previous", "-") or "-"
                    high_events.append((time_fmt, currency, title, forecast, previous))
            except:
                continue
        return high_events
    except Exception as e:
        print(f"❌ خطا در گرفتن اخبار: {e}")
        return None

async def send_daily_news():
    print("📰 در حال گرفتن اخبار فارکس...")
    events_list = await fetch_forex_news()
    if events_list is None:
        msg = "❌ خطا در دریافت اخبار!"
    elif len(events_list) == 0:
        msg = "📰 امروز خبر قرمز نداریم! 🟢"
    else:
        today_str = datetime.now(TEHRAN_TZ).strftime("%d %B %Y")
        lines = [f"🗓 اخبار مهم فارکس — {today_str}\n🔴 High Impact Events\n{'─'*30}"]
        for time_fmt, currency, title, forecast, previous in sorted(events_list):
            lines.append(
                f"🕐 {time_fmt} | 🌍 {currency.upper()}\n"
                f"📌 {title}\n"
                f"📊 پیش‌بینی: {forecast} | قبلی: {previous}\n"
            )
        lines.append("─"*30)
        lines.append("⚠️ در زمان این اخبار مراقب نوسانات باشید!")
    if TEST_MODE:
        msg = "🧪 [TEST MODE]\n\n" + "\n".join(lines) if isinstance(lines, list) else "🧪 [TEST MODE]\n\n" + msg
    else:
        msg = "\n".join(lines) if isinstance(lines, list) else msg
    try:
        await client.send_message(TARGET_GROUP_ID, msg)
        print(f"✅ اخبار ارسال شد!")
    except Exception as e:
        print(f"❌ خطا در ارسال: {e}")

async def status_message():
    now = datetime.now(TEHRAN_TZ)
    if TEST_MODE:
        next_send = now + timedelta(minutes=30 - now.minute % 30)
        diff = next_send - now
    else:
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        diff = target - now
    hours = int(diff.total_seconds() // 3600)
    minutes = int((diff.total_seconds() % 3600) // 60)
    mode = "🧪 تست (هر ۳۰ دقیقه)" if TEST_MODE else "📅 روزانه ساعت ۹ صبح"
    return (
        f"✅ ربات آنلاین است\n"
        f"⏰ حالت: {mode}\n"
        f"⏳ تا ارسال بعدی: {hours} ساعت و {minutes} دقیقه\n"
        f"📨 فوروارد امروز: {forwarded_today}"
    )

@client.on(events.NewMessage(incoming=True))
async def incoming_handler(event):
    global forwarded_today
    text = (event.message.text or "").strip().lower()

    if text == "/news":
        print("📰 /news دریافت شد")
        await send_daily_news()
        return

    if text == "/status":
        await client.send_message(TARGET_GROUP_ID, await status_message())
        return

    sender = await event.get_sender()
    if not sender:
        return
    sender_username = getattr(sender, "username", "") or ""
    is_bot = getattr(sender, "bot", False)
    if sender_username.lower() == FARAZ_BOT_USERNAME.lower() or (
        is_bot and FARAZ_BOT_USERNAME.lower() in sender_username.lower()
    ):
        print(f"📩 پیام فراز: {event.message.text[:80]}...")
        try:
            await client.forward_messages(TARGET_GROUP_ID, event.message)
            forwarded_today += 1
            print(f"✅ فوروارد شد! (امروز: {forwarded_today})")
        except Exception as e:
            print(f"❌ خطا: {e}")

@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    text = (event.message.text or "").strip().lower()
    if text == "/news":
        print("📰 /news از خودت")
        await send_daily_news()
    elif text == "/status":
        await client.send_message(TARGET_GROUP_ID, await status_message())

async def news_scheduler():
    if TEST_MODE:
        print("🧪 Test mode: هر ۳۰ دقیقه اخبار میفرسته")
        while True:
            await asyncio.sleep(1800)
            await send_daily_news()
    else:
        print("⏰ Scheduler: هر روز ساعت ۹ صبح تهران")
        while True:
            now = datetime.now(TEHRAN_TZ)
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            print(f"⏳ تا اخبار بعدی: {int(wait_seconds//3600)}h {int((wait_seconds%3600)//60)}m")
            await asyncio.sleep(wait_seconds)
            await send_daily_news()

async def health_check(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Web server روی پورت {PORT} شروع شد")

async def main():
    await client.start()
    me = await client.get_me()
    print(f"✅ لاگین شد: {me.first_name} (@{me.username})")
    print(f"👀 منتظر پیام از: @{FARAZ_BOT_USERNAME}")
    print(f"📤 گروه: {TARGET_GROUP_ID}")
    print("✅ آماده! دستورات: /news /status")

    await asyncio.gather(
        start_web_server(),
        client.run_until_disconnected(),
        news_scheduler()
    )

asyncio.run(main())
