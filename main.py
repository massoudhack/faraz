import os
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
import pytz
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiohttp import web

# ========== CONFIG ==========
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
FARAZ_BOT_USERNAME = os.environ.get("FARAZ_BOT_USERNAME", "farazsignal_bot")
TARGET_GROUP_ID = int(os.environ["TARGET_GROUP_ID"])
PORT = int(os.environ.get("PORT", 8080))
TEST_MODE = True   # هر ۳۰ دقیقه - برای production بذار False
NEWS_HOUR = 9      # ساعت ارسال روزانه (فقط production)
# ============================

TEHRAN_TZ = pytz.timezone("Asia/Tehran")
forwarded_today = 0
sent_reminders = set()

print("🚀 Faraz Forwarder starting...")
print("🧪 TEST MODE - هر ۳۰ دقیقه اخبار")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def fetch_forex_news():
    urls = [
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
        "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.forexfactory.com/",
    }
    data = None
    async with aiohttp.ClientSession(headers=headers) as session:
        for url in urls:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    text = await resp.text()
                    if text and text.strip().startswith("["):
                        data = json.loads(text)
                        print(f"✅ اخبار دریافت شد از: {url}")
                        break
            except Exception as e:
                print(f"⚠️ {url} خطا: {e}")

    if data is None:
        print("❌ هیچ API جواب نداد")
        return None

    today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
    high_events = []
    for ev in data:
        try:
            if ev.get("date", "")[:10] != today:
                continue
            if ev.get("impact", "").lower() != "high":
                continue
            time_str = ev.get("date", "")
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                dt_tehran = dt.astimezone(TEHRAN_TZ)
            except:
                dt_tehran = None
            high_events.append({
                "time": dt_tehran,
                "time_fmt": dt_tehran.strftime("%H:%M") if dt_tehran else "؟",
                "currency": ev.get("country", "").upper(),
                "title": ev.get("title", "نامشخص"),
                "forecast": ev.get("forecast", "-") or "-",
                "previous": ev.get("previous", "-") or "-",
                "actual": ev.get("actual", "") or "",
            })
        except:
            continue
    return sorted(high_events, key=lambda x: x["time"] or datetime.min.replace(tzinfo=pytz.utc))

async def send_daily_news():
    print("📰 ارسال اخبار...")
    events_list = await fetch_forex_news()
    now_str = datetime.now(TEHRAN_TZ).strftime("%H:%M")
    today_str = datetime.now(TEHRAN_TZ).strftime("%d %B %Y")
    label = "🧪 [تست] " if TEST_MODE else ""

    if events_list is None:
        msg = "❌ خطا در دریافت اخبار! سرویس در دسترس نیست."
    elif len(events_list) == 0:
        msg = f"📰 {label}اخبار فارکس | {today_str}\n{'─'*30}\n✅ امروز خبر High Impact نداریم!\n🟢 بازار آروم پیش میره"
    else:
        lines = [
            f"🗓 {label}اخبار مهم فارکس",
            f"📅 {today_str} | ارسال: {now_str}",
            f"🔴 {len(events_list)} خبر High Impact",
            f"{'─'*30}",
        ]
        for ev in events_list:
            lines.append(
                f"\n🕐 {ev['time_fmt']} | 🌍 {ev['currency']}\n"
                f"📌 {ev['title']}\n"
                f"📊 پیش‌بینی: {ev['forecast']}  |  قبلی: {ev['previous']}"
            )
        lines += [f"\n{'─'*30}", "⚠️ در زمان این اخبار مراقب نوسانات باشید!"]
        msg = "\n".join(lines)

    try:
        await client.send_message(TARGET_GROUP_ID, msg)
        print(f"✅ اخبار ارسال شد!")
    except Exception as e:
        print(f"❌ خطا ارسال: {e}")

async def check_reminders():
    events_list = await fetch_forex_news()
    if not events_list:
        return
    now = datetime.now(TEHRAN_TZ)
    for ev in events_list:
        if not ev["time"]:
            continue
        diff = (ev["time"] - now).total_seconds()
        key = f"{ev['title']}_{ev['time_fmt']}"

        # ۱۵ دقیقه قبل
        if 14*60 <= diff <= 15*60 and f"pre_{key}" not in sent_reminders:
            sent_reminders.add(f"pre_{key}")
            msg = (
                f"⏰ ۱۵ دقیقه دیگه خبر مهم!\n{'─'*30}\n"
                f"📌 {ev['title']}\n"
                f"🌍 {ev['currency']} | 🕐 {ev['time_fmt']}\n"
                f"📊 پیش‌بینی: {ev['forecast']} | قبلی: {ev['previous']}\n"
                f"{'─'*30}\n⚠️ آماده باشید!"
            )
            try:
                await client.send_message(TARGET_GROUP_ID, msg)
                print(f"⏰ Reminder: {ev['title']}")
            except Exception as e:
                print(f"❌ reminder error: {e}")

        # نتیجه خبر
        result_key = f"result_{key}"
        if -180 <= diff <= 0 and result_key not in sent_reminders and ev["actual"]:
            sent_reminders.add(result_key)
            actual = ev["actual"]
            forecast = ev["forecast"]
            try:
                def parse_num(s):
                    return float(s.replace("K","e3").replace("M","e6").replace("B","e9").replace("%","").strip())
                a, f_ = parse_num(actual), parse_num(forecast)
                verdict = "🟢 بهتر از پیش‌بینی (Bullish)" if a > f_ else ("🔴 بدتر از پیش‌بینی (Bearish)" if a < f_ else "🟡 مطابق پیش‌بینی")
            except:
                verdict = "📊 نتیجه منتشر شد"
            msg = (
                f"📢 نتیجه خبر!\n{'─'*30}\n"
                f"📌 {ev['title']}\n"
                f"🌍 {ev['currency']}\n"
                f"📊 پیش‌بینی: {forecast} | قبلی: {ev['previous']}\n"
                f"✅ واقعی: {actual}\n"
                f"{'─'*30}\n{verdict}"
            )
            try:
                await client.send_message(TARGET_GROUP_ID, msg)
                print(f"📢 نتیجه: {ev['title']}")
            except Exception as e:
                print(f"❌ result error: {e}")

async def status_message():
    now = datetime.now(TEHRAN_TZ)
    if TEST_MODE:
        return (f"✅ ربات آنلاین\n🧪 حالت تست (هر ۳۰ دقیقه)\n"
                f"🔔 Reminder 15min قبل خبر\n📢 نتیجه بعد از خبر\n"
                f"📨 فوروارد امروز: {forwarded_today}")
    target = now.replace(hour=NEWS_HOUR, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    diff = target - now
    return (f"✅ ربات آنلاین\n⏰ اخبار ساعت {NEWS_HOUR}:00 تهران\n"
            f"⏳ تا ارسال بعدی: {int(diff.total_seconds()//3600)}h {int((diff.total_seconds()%3600)//60)}m\n"
            f"📨 فوروارد امروز: {forwarded_today}")

@client.on(events.NewMessage(incoming=True))
async def incoming_handler(event):
    global forwarded_today
    text = (event.message.text or "").strip().lower()
    if text == "/news":
        await send_daily_news(); return
    if text == "/status":
        await client.send_message(TARGET_GROUP_ID, await status_message()); return
    sender = await event.get_sender()
    if not sender:
        return
    username = getattr(sender, "username", "") or ""
    is_bot = getattr(sender, "bot", False)
    if username.lower() == FARAZ_BOT_USERNAME.lower() or (is_bot and FARAZ_BOT_USERNAME.lower() in username.lower()):
        print(f"📩 فراز: {event.message.text[:60]}...")
        try:
            await client.forward_messages(TARGET_GROUP_ID, event.message)
            forwarded_today += 1
            print(f"✅ فوروارد ({forwarded_today} امروز)")
        except Exception as e:
            print(f"❌ فوروارد خطا: {e}")

@client.on(events.NewMessage(outgoing=True))
async def outgoing_handler(event):
    text = (event.message.text or "").strip().lower()
    if text == "/news":
        await send_daily_news()
    elif text == "/status":
        await client.send_message(TARGET_GROUP_ID, await status_message())

async def news_scheduler():
    if TEST_MODE:
        await send_daily_news()
        while True:
            await asyncio.sleep(1800)
            await send_daily_news()
    else:
        while True:
            now = datetime.now(TEHRAN_TZ)
            target = now.replace(hour=NEWS_HOUR, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            print(f"⏳ تا اخبار: {int(wait//3600)}h {int((wait%3600)//60)}m")
            await asyncio.sleep(wait)
            await send_daily_news()
            sent_reminders.clear()

async def reminder_loop():
    print("🔔 Reminder loop فعال")
    while True:
        try:
            await check_reminders()
        except Exception as e:
            print(f"❌ reminder: {e}")
        await asyncio.sleep(30)

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
    print(f"👀 @{FARAZ_BOT_USERNAME} → گروه {TARGET_GROUP_ID}")
    print("✅ آماده! /news /status")
    await asyncio.gather(
        start_web_server(),
        client.run_until_disconnected(),
        news_scheduler(),
        reminder_loop(),
    )

asyncio.run(main())
