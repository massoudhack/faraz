import os
import asyncio
import aiohttp
import json
import pickle
from datetime import datetime, timedelta
from pathlib import Path
import pytz
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BotCommand
from aiohttp import web

# ========== CONFIG ==========
API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
FARAZ_BOT_USERNAME = os.environ.get("FARAZ_BOT_USERNAME", "farazsignal_bot")
TARGET_GROUP_ID = int(os.environ["TARGET_GROUP_ID"])
PORT = int(os.environ.get("PORT", 8080))
FETCH_HOUR = 7
NEWS_HOUR = 9
DATA_FILE = "/tmp/bot_data.pkl"
# ============================

TEHRAN_TZ = pytz.timezone("Asia/Tehran")
UTC_TZ = pytz.utc

SESSIONS = {
    "لندن 🇬🇧":   (6, 0),
    "نیویورک 🇺🇸": (13, 0),
}

forwarded_today = 0
userbot = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== DATA STORE ==========
def load_data():
    try:
        if Path(DATA_FILE).exists():
            with open(DATA_FILE, "rb") as f:
                return pickle.load(f)
    except:
        pass
    return {"sent_reminders": set(), "today_news": [], "today_date": ""}

def save_data(d):
    try:
        with open(DATA_FILE, "wb") as f:
            pickle.dump(d, f)
    except Exception as e:
        print(f"❌ save: {e}")

data = load_data()
print(f"✅ دیتا لود | اخبار: {len(data['today_news'])} | date: {data['today_date']}")

# ========== FETCH ==========
async def fetch_news_from_api():
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    async with aiohttp.ClientSession(headers=headers) as session:
        for url in ["https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                    "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json"]:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    text = await resp.text()
                    if text.strip().startswith("["):
                        print("✅ API جواب داد")
                        return json.loads(text)
            except Exception as e:
                print(f"⚠️ {url}: {e}")
    return None

def parse_today_events(raw):
    today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
    events_today = []
    for ev in raw:
        try:
            if ev.get("impact", "").lower() != "high": continue
            if ev.get("date", "")[:10] != today: continue
            dt = datetime.fromisoformat(ev["date"].replace("Z", "+00:00")).astimezone(TEHRAN_TZ)
            events_today.append({
                "time": dt,
                "time_fmt": dt.strftime("%H:%M"),
                "currency": ev.get("country", "").upper(),
                "title": ev.get("title", "؟"),
                "forecast": ev.get("forecast", "-") or "-",
                "previous": ev.get("previous", "-") or "-",
                "actual": ev.get("actual", "") or "",
            })
        except: continue
    return sorted(events_today, key=lambda x: x["time"])

async def fetch_with_retry():
    today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
    if data["today_date"] == today and data["today_news"]:
        print(f"📦 cache امروز ({len(data['today_news'])} خبر)")
        return data["today_news"]
    attempt = 0
    while True:
        attempt += 1
        now = datetime.now(TEHRAN_TZ)
        print(f"🌐 تلاش {attempt}...")
        raw = await fetch_news_from_api()
        if raw:
            events_list = parse_today_events(raw)
            data["today_news"] = events_list
            data["today_date"] = today
            data["sent_reminders"] = set()
            save_data(data)
            print(f"✅ {len(events_list)} خبر ذخیره شد")
            return events_list
        if now.hour >= 8 and now.minute >= 55:
            return []
        await asyncio.sleep(5 * 60)

async def fetch_result_for_event(ev):
    raw = await fetch_news_from_api()
    if not raw: return ""
    today = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d")
    for e in raw:
        if (e.get("date","")[:10] == today and
            e.get("title","") == ev["title"] and
            e.get("country","").upper() == ev["currency"]):
            return e.get("actual","") or ""
    return ""

# ========== MESSAGE BUILDERS ==========
def build_news_message(events_list):
    today_str = datetime.now(TEHRAN_TZ).strftime("%d %B %Y")
    if not events_list:
        return f"📰 اخبار فارکس | {today_str}\n✅ امروز خبر High Impact نداریم!\n🟢 بازار آروم"
    lines = [f"🗓 اخبار مهم فارکس | {today_str}", f"🔴 {len(events_list)} خبر High Impact", "─"*30]
    for ev in events_list:
        lines.append(f"\n🕐 {ev['time_fmt']} | 🌍 {ev['currency']}\n📌 {ev['title']}\n📊 پیش‌بینی: {ev['forecast']} | قبلی: {ev['previous']}")
    lines += ["\n"+"─"*30, "⚠️ در زمان این اخبار مراقب نوسانات باشید!"]
    return "\n".join(lines)

def build_sessions_message():
    now_utc = datetime.now(UTC_TZ)
    now_teh = datetime.now(TEHRAN_TZ)
    lines = [f"🕐 ساعت الان تهران: {now_teh.strftime('%H:%M')}", "─"*30]
    for name, (h, m) in SESSIONS.items():
        open_utc = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)
        close_h = (h + 9) % 24
        close_utc = now_utc.replace(hour=close_h, minute=0, second=0, microsecond=0)
        open_teh = open_utc.astimezone(TEHRAN_TZ).strftime("%H:%M")
        close_teh = close_utc.astimezone(TEHRAN_TZ).strftime("%H:%M")
        is_open = open_utc.hour <= now_utc.hour < close_utc.hour
        status = "🟢 باز" if is_open else "🔴 بسته"
        lines.append(f"{status} {name}\n🕐 {open_teh} - {close_teh}")
    return "\n".join(lines)

def build_next_message():
    now = datetime.now(TEHRAN_TZ)
    upcoming = [ev for ev in data["today_news"] if (ev["time"] - now).total_seconds() > 0]
    if not upcoming:
        return "✅ امروز خبر مهم دیگه‌ای نداریم!"
    ev = upcoming[0]
    diff = (ev["time"] - now).total_seconds()
    mins = int(diff // 60)
    return (f"⏰ نزدیک‌ترین خبر:\n{'─'*30}\n"
            f"📌 {ev['title']}\n🌍 {ev['currency']}\n"
            f"🕐 {ev['time_fmt']} (تا {mins} دقیقه دیگه)\n"
            f"📊 پیش‌بینی: {ev['forecast']} | قبلی: {ev['previous']}")

def build_status_message():
    now = datetime.now(TEHRAN_TZ)
    target = now.replace(hour=NEWS_HOUR, minute=0, second=0, microsecond=0)
    if now >= target: target += timedelta(days=1)
    diff = target - now
    cached = "✅" if data["today_date"] == now.strftime("%Y-%m-%d") else "❌"
    return (f"✅ ربات آنلاین\n"
            f"⏰ اخبار: {NEWS_HOUR}:00 تهران\n"
            f"⏳ تا ارسال بعدی: {int(diff.total_seconds()//3600)}h {int((diff.total_seconds()%3600)//60)}m\n"
            f"📦 Cache: {cached} ({len(data['today_news'])} خبر)\n"
            f"📨 فوروارد امروز: {forwarded_today}")

# ========== BOT COMMANDS ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 سلام!\nمن ربات هشدار فارکس هستم.\n\n"
        "دستورات:\n"
        "/news — اخبار امروز\n"
        "/next — نزدیک‌ترین خبر\n"
        "/sessions — وضعیت سشن‌ها\n"
        "/status — وضعیت ربات\n"
        "/help — راهنما"
    )

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    await message.answer(build_news_message(data["today_news"]))

@dp.message(Command("next"))
async def cmd_next(message: types.Message):
    await message.answer(build_next_message())

@dp.message(Command("sessions"))
async def cmd_sessions(message: types.Message):
    await message.answer(build_sessions_message())

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    await message.answer(build_status_message())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 راهنما:\n\n"
        "/news — اخبار High Impact امروز\n"
        "/next — نزدیک‌ترین خبر مهم\n"
        "/sessions — ساعت سشن لندن و نیویورک\n"
        "/status — وضعیت ربات و cache\n\n"
        "🔔 هشدارهای خودکار:\n"
        "• آلارم‌های فراز در گروه\n"
        "• اخبار روزانه ساعت ۹\n"
        "• Reminder USD 15 دقیقه قبل خبر\n"
        "• نتیجه خبر بعد از انتشار\n"
        "• Reminder سشن لندن و نیویورک"
    )

# ========== SEND TO GROUP ==========
async def send_to_group(msg):
    try:
        await bot.send_message(TARGET_GROUP_ID, msg)
    except Exception as e:
        print(f"❌ send_to_group: {e}")

# ========== USERBOT (فوروارد فراز) ==========
@userbot.on(events.NewMessage(incoming=True))
async def userbot_handler(event):
    global forwarded_today
    sender = await event.get_sender()
    if not sender: return
    username = getattr(sender, "username", "") or ""
    is_bot = getattr(sender, "bot", False)
    if username.lower() == FARAZ_BOT_USERNAME.lower() or (is_bot and FARAZ_BOT_USERNAME.lower() in username.lower()):
        print(f"📩 فراز: {event.message.text[:60]}...")
        try:
            await userbot.forward_messages(TARGET_GROUP_ID, event.message)
            forwarded_today += 1
            asyncio.create_task(check_faraz_correlation(event.message.text or ""))
        except Exception as e:
            print(f"❌ forward: {e}")

# ========== SCHEDULED TASKS ==========
async def schedule_all_tasks(events_list):
    now = datetime.now(TEHRAN_TZ)
    now_utc = datetime.now(UTC_TZ)
    tasks = []

    for name, (h, m) in SESSIONS.items():
        open_utc = now_utc.replace(hour=h, minute=m, second=0, microsecond=0)
        if open_utc <= now_utc: open_utc += timedelta(days=1)
        wait = (open_utc - timedelta(minutes=15) - now_utc).total_seconds()
        if wait > 0:
            open_teh = open_utc.astimezone(TEHRAN_TZ).strftime("%H:%M")
            tasks.append(asyncio.create_task(scheduled_session_reminder(wait, name, open_teh)))
            print(f"📌 Session '{name}' در {int(wait//3600)}h {int((wait%3600)//60)}m")

    for ev in events_list:
        diff = (ev["time"] - now).total_seconds()
        if ev["currency"] == "USD" and diff > 15*60:
            key = f"pre_{ev['title']}_{ev['time_fmt']}"
            if key not in data["sent_reminders"]:
                tasks.append(asyncio.create_task(scheduled_news_reminder(diff - 15*60, ev, key)))
                print(f"📌 USD reminder '{ev['title']}' در {int((diff-15*60)//60)}m")
        if diff > -60:
            result_key = f"result_{ev['title']}_{ev['time_fmt']}"
            if result_key not in data["sent_reminders"]:
                tasks.append(asyncio.create_task(scheduled_result(max(diff + 60, 5), ev, result_key)))
    return tasks

async def scheduled_session_reminder(wait, name, open_teh):
    await asyncio.sleep(wait)
    key = f"session_{name}_{datetime.now(TEHRAN_TZ).strftime('%Y-%m-%d')}"
    if key in data["sent_reminders"]: return
    data["sent_reminders"].add(key); save_data(data)
    await send_to_group(f"🔔 ۱۵ دقیقه دیگه سشن باز میشه!\n{'─'*30}\n📍 {name}\n🕐 باز شدن (تهران): {open_teh}\n{'─'*30}\n⚡ آماده باشید!")
    print(f"✅ Session reminder: {name}")

async def scheduled_news_reminder(wait, ev, key):
    await asyncio.sleep(wait)
    if key in data["sent_reminders"]: return
    data["sent_reminders"].add(key); save_data(data)
    await send_to_group(f"🇺🇸 ۱۵ دقیقه دیگه خبر USD!\n{'─'*30}\n📌 {ev['title']}\n🕐 {ev['time_fmt']}\n📊 پیش‌بینی: {ev['forecast']} | قبلی: {ev['previous']}\n{'─'*30}\n⚠️ آماده باشید!")
    print(f"✅ News reminder: {ev['title']}")

async def scheduled_result(wait, ev, key):
    await asyncio.sleep(wait)
    if key in data["sent_reminders"]: return
    actual = ""
    for _ in range(5):
        actual = await fetch_result_for_event(ev)
        if actual: break
        await asyncio.sleep(60)
    if not actual: return
    data["sent_reminders"].add(key); save_data(data)
    try:
        def parse_num(s):
            return float(s.replace("K","e3").replace("M","e6").replace("B","e9").replace("%","").strip())
        a, f_ = parse_num(actual), parse_num(ev["forecast"])
        verdict = "🟢 بهتر از پیش‌بینی" if a > f_ else ("🔴 بدتر از پیش‌بینی" if a < f_ else "🟡 مطابق پیش‌بینی")
    except:
        verdict = "📊 نتیجه منتشر شد"
    await send_to_group(f"📢 نتیجه خبر!\n{'─'*30}\n📌 {ev['title']}\n🌍 {ev['currency']}\n📊 پیش‌بینی: {ev['forecast']} | قبلی: {ev['previous']}\n✅ واقعی: {actual}\n{'─'*30}\n{verdict}")
    print(f"✅ Result: {ev['title']}")

async def check_faraz_correlation(msg_text):
    now = datetime.now(TEHRAN_TZ)
    for ev in data["today_news"]:
        if not ev["time"]: continue
        if ev["currency"] != "USD": continue
        diff = (ev["time"] - now).total_seconds()
        if 0 <= diff <= 30*60:
            key = f"corr_{ev['title']}_{now.strftime('%Y-%m-%d')}"
            if key in data["sent_reminders"]: continue
            data["sent_reminders"].add(key); save_data(data)
            mins = int(diff // 60)
            await send_to_group(f"⚡ هشدار همبستگی!\n{'─'*30}\n🚨 آلارم فراز فعال شد\n⏰ {mins} دقیقه دیگه خبر USD\n📌 {ev['title']}\n🕐 {ev['time_fmt']}\n📊 پیش‌بینی: {ev['forecast']} | قبلی: {ev['previous']}\n{'─'*30}\n⚠️ احتمال نوسان بالا!")
            print("⚡ Correlation alert")

# ========== MAIN LOOP ==========
scheduled_tasks = []

async def daily_loop():
    global scheduled_tasks
    while True:
        now = datetime.now(TEHRAN_TZ)
        fetch_target = now.replace(hour=FETCH_HOUR, minute=0, second=0, microsecond=0)
        if now >= fetch_target: fetch_target += timedelta(days=1)
        await asyncio.sleep((fetch_target - now).total_seconds())

        events_list = await fetch_with_retry()

        send_target = datetime.now(TEHRAN_TZ).replace(hour=NEWS_HOUR, minute=0, second=0, microsecond=0)
        if datetime.now(TEHRAN_TZ) >= send_target: send_target += timedelta(days=1)
        wait2 = (send_target - datetime.now(TEHRAN_TZ)).total_seconds()
        if wait2 > 0: await asyncio.sleep(wait2)

        await send_to_group(build_news_message(data["today_news"]))

        for t in scheduled_tasks: t.cancel()
        scheduled_tasks = await schedule_all_tasks(data["today_news"])

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    print(f"🌐 Web server پورت {PORT}")

async def main():
    global scheduled_tasks
    await userbot.start()
    me = await userbot.get_me()
    print(f"✅ Userbot: {me.first_name} (@{me.username})")

    await bot.set_my_commands([
        BotCommand(command="news", description="اخبار امروز"),
        BotCommand(command="next", description="نزدیک‌ترین خبر"),
        BotCommand(command="sessions", description="وضعیت سشن‌ها"),
        BotCommand(command="status", description="وضعیت ربات"),
        BotCommand(command="help", description="راهنما"),
    ])
    print("✅ Bot commands ست شد")

    events_list = await fetch_with_retry()
    if events_list:
        scheduled_tasks = await schedule_all_tasks(events_list)

    print("✅ آماده!")
    await asyncio.gather(
        start_web_server(),
        userbot.run_until_disconnected(),
        dp.start_polling(bot),
        daily_loop(),
    )

asyncio.run(main())
