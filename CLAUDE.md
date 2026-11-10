# Hokm Bot

ربات تلگرام برای ثبت نتایج بازی حکم.

## Stack
- Python 3.10+ (تست‌شده روی 3.11)
- python-telegram-bot v21 (async)
- python-dotenv
- ذخیره‌سازی: فایل JSON به ازای هر `chat_id` در `data/`

## Conventions
- همه پیام‌های ربات فارسی، با اعداد فارسی
- Timezone: `Asia/Tehran`
- روز بازی: قبل از ۶ صبح = روز قبل (cutoff در `config.DAY_CUTOFF_HOUR`)
- Undo window پس از پایان بازی: ۵ دقیقه (`config.UNDO_WINDOW_SECONDS`)
- سقف امتیاز بازی: ۷ (`config.WIN_TARGET`)
- پیام‌های موقت ربات بعد از ۵ ثانیه حذف میشن
- Lock کانکارنسی: `asyncio.Lock` per chat_id

## Scoring
- برد عادی: +۱
- کت تیم حاکم: +۲
- کت تیم غیر حاکم (حاکم کت شد): +۳
- حاکم اولیه‌ی هر بازی: random
- حاکم بعدی: برنده‌ی هر دست
- کت چرخشی: اگه امتیاز با کت از ۷ رد بشه (مثلا ۶+۳=۹)، به جای پایان بازی، ۷ کم میشه و بازی ادامه پیدا میکنه (۹ → ۲). فقط کت میتونه باعثش بشه، چون برد عادی (+۱) حداکثر دقیقا روی ۷ می‌شینه.

## Pause
- دکمه‌ی «⏸ توقف» روی اسکوربورد ساعت بازی رو نگه میداره؛ «▶️ ادامه بازی» دوباره راهش میندازه. تا وقتی متوقفه هیچ دستی ثبت نمیشه.
- هر توقف توی `pauses` بازی ذخیره میشه (`from`, `to`). رکورد بازیِ متوقف‌شده `pauses` و `paused_seconds` داره؛ بازی عادی این فیلدها رو نداره.
- مدت بازی همه‌جا = `ended_at - started_at - paused_seconds` (تابع `game.record_duration_sec`).
- اگه توقف ۶ ساعت یا بیشتر باشه و بازی توی یه روزِ بازیِ دیگه ادامه پیدا کنه، `game_day` میشه همون روز و روز اول توی `game_day_started` میمونه (`config.PAUSE_NEW_DAY_SECONDS`).
- بازی ۷ تا ۱۰ نوامبر ۲۰۲۶ (قبل از این دکمه ۶۷ ساعت باز مونده بود) با `scripts/fix_unpaused_game.py` یه توقف retro گرفت.

## Tests
`BOT_TOKEN=test python tests/test_pause.py` (بدون تلگرام، با دیتای موقت).

## Files
- `main.py` — entry point، register handler ها
- `handlers.py` — همه command و callback handler ها
- `game.py` — منطق pure (امتیاز، حاکم، کت، undo)
- `storage.py` — load/save JSON با backup و lock
- `keyboards.py` — تمام inline keyboard ها
- `messages.py` — متن‌های فارسی + helper اعداد فارسی
- `config.py` — env و constant ها
- `data/` — JSON state per chat (gitignored)
  - هر دست یه فلگ `wrapped` داره، هر رکورد بازی یه `wraps` (از ۲۰۲۶-۰۵-۲۳ به بعد). رکوردهای قدیمی‌تر و ایمپورت‌ها دیتای دست ندارن، پس ۰ حساب میشن — تخمین نمیزنیم.
- `deploy/` — systemd unit و deploy script

## Commands
`/start /help /newgame /score /stats /endgame /undo /import`

## Import format
```
/import YYYY-MM-DD red-blue [redKots-blueKots]
/import 2026-04-15 3-1 1-0
/import 2026-04-15 3-1
```

## Deploy
روی سرور با systemd. فایل `deploy/hokm-bot.service` و `deploy/deploy.sh`.
