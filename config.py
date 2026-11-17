import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN env var is required (put it in .env)")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

TZ = ZoneInfo("Asia/Tehran")
DAY_CUTOFF_HOUR = 6
UNDO_WINDOW_SECONDS = 300
WIN_TARGET = 7
EPHEMERAL_DELETE_SECONDS = 5

# Duration averages / percentiles only consider games started on/after this moment.
# Earlier games predate the bot's reliable timestamping. 2026-05-07 22:00 Dubai (UTC+4)
# == 2026-05-07 21:30 Tehran (UTC+3:30).
STATS_DURATION_CUTOFF = datetime.fromisoformat("2026-05-07T21:30:00+03:30")

# Live scoreboard auto-refresh interval (used in step 5).
LIVE_REFRESH_SECONDS = 60

# A paused game that is resumed on another game day counts for the day it is
# resumed (and won) on, but only if the pause was at least this long. A short
# break that happens to cross the 6am cutoff keeps its original day.
PAUSE_NEW_DAY_SECONDS = 6 * 3600

# Legacy kots (logged before normal/hakem split tracking) are estimated: this
# fraction is assumed to have been hakem-kots (+3), the rest normal kots (+2).
LEGACY_HAKEM_KOT_RATIO = 0.3

# Mini App (webapi.py). The web server runs inside the bot process.
WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("WEB_PORT", "8050"))
# Public https URL of the Mini App page (set as the private-chat menu button).
WEBAPP_URL = os.environ.get("WEBAPP_URL", "").strip()
# t.me link that opens the Mini App inside a group, e.g. https://t.me/Hokmnightsbot?startapp
# (needs the Main Mini App switched on in BotFather). Empty = no app button on the boards.
WEBAPP_LINK = os.environ.get("WEBAPP_LINK", "").strip()
