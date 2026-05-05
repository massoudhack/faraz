import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
FARAZ_BOT_USERNAME = os.environ.get("FARAZ_BOT_USERNAME", "farazsignal_bot")
TARGET_GROUP_ID = int(os.environ["TARGET_GROUP_ID"])

TEHRAN_TZ = pytz.timezone("Asia/Tehran")

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
        print(f"📩 پیام جدید از فراز: {event.message.text[:80]}...")
        try:
            await client.forward_messages(TARGET_GROUP_ID, event.message)
            print("✅ فوروارد شد!")
        except Exception as e:
            print(f"❌ خطا در فوروارد: {e}")

async def fetch_forex_news():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json(content_type=None)

        today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
        high_events = []

        for event in data:
            try:
                event_date = event.get("date", "")[:10]
                impact = event.get("impact", "").lower()
                if event_date == today and impact == "high":
                    title = event.get("title", "نامشخص")
                    currency = event.get("country", "")
                    time_str = event.get("date", "")
                    # Parse time
                    try:
                        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        dt_tehran = dt.astimezone(TEHRAN_TZ)
                        time_fmt = dt_tehran.strftime("%H:%M")
                    except:
                        time_fmt = "نامشخص"

                    forecast = event.get("forecast", "-") or "-"
                    previous = event.get("previous", "-") or "-"
                    high_events.append((time_fmt, currency, title, forecast, previous))
            except:
                continue

        return high_events

    except Exception as e:
        print(f"❌ خطا در گرفتن اخبار: {e}")
        return []

async def send_daily_news():
    print("📰 در حال گرفتن اخبار فارکس...")
    events_list = await fetch_forex_news()

    if not events_list:
        msg = "📰 امروز خبر قرمز (High Impact) نداریم! 🟢"
    else:
        today_str = datetime.now(TEHRAN_TZ).strftime("%A %d %B %Y")
        lines = [f"🗓 اخبار مهم فارکس — {today_str}\n🔴 High Impact Events\n{'─'*30}"]
        for time_fmt, currency, title, forecast, previous in sorted(events_list):
            lines.append(
                f"🕐 {time_fmt} | 🌍 {currency.upper()}\n"
                f"📌 {title}\n"
                f"📊 پیش‌بینی: {forecast} | قبلی: {previous}\n"
            )
        lines.append("─"*30)
        lines.append("⚠️ در زمان این اخبار مراقب نوسانات باشید!")
        msg = "\n".join(lines)

    try:
        await client.send_message(TARGET_GROUP_ID, msg, parse_mode="md")
        print(f"✅ اخبار ارسال شد! ({len(events_list)} خبر قرمز)")
    except Exception as e:
        print(f"❌ خطا در ارسال اخبار: {e}")

async def news_scheduler():
    print("⏰ News scheduler شروع شد - هر روز ساعت ۸ صبح تهران")
    while True:
        now = datetime.now(TEHRAN_TZ)
        # محاسبه وقت ۸ صبح فردا
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        print(f"⏳ تا ارسال بعدی: {int(wait_seconds//3600)} ساعت و {int((wait_seconds%3600)//60)} دقیقه")
        await asyncio.sleep(wait_seconds)
        await send_daily_news()

async def main():
    await client.start()
    me = await client.get_me()
    print(f"✅ لاگین شد: {me.first_name} (@{me.username})")
    print(f"👀 منتظر پیام از: @{FARAZ_BOT_USERNAME}")
    print(f"📤 ارسال به گروه: {TARGET_GROUP_ID}")
    print("✅ ربات آماده‌ست!")

    # اجرای همزمان فوروارد و scheduler
    await asyncio.gather(
        client.run_until_disconnected(),
        news_scheduler()
    )

asyncio.run(main())
