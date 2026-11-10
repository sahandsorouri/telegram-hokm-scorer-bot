"""Tests for the pause button. No test framework needed:

    BOT_TOKEN=test python tests/test_pause.py

Time is faked, Telegram is faked, and the data folder is a temp folder, so this
never touches real state and never talks to Telegram.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("BOT_TOKEN", "test")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

config.DATA_DIR = Path(tempfile.mkdtemp(prefix="hokm-test-"))

import game  # noqa: E402
import handlers  # noqa: E402
import keyboards as kb  # noqa: E402
import messages as msg  # noqa: E402
import storage  # noqa: E402


class Clock:
    def __init__(self, iso: str):
        self.t = datetime.fromisoformat(iso)

    def now(self) -> datetime:
        return self.t

    def tick(self, **kw) -> None:
        self.t += timedelta(**kw)


def use_clock(iso: str) -> Clock:
    c = Clock(iso)
    game.now_tz = c.now
    return c


def play_to_end(g: dict, clock: Clock, team: str = "red") -> None:
    while not game.game_ended(g):
        clock.tick(minutes=5)
        game.add_hand(g, team, kot=False)


# ── pure logic ────────────────────────────────────────────────────────────────

def test_pause_time_is_left_out_of_duration():
    c = use_clock("2026-11-08T01:18:00+03:30")
    state = storage.empty_state(1)
    g = state["active_game"] = game.new_game()
    for _ in range(3):
        c.tick(minutes=5)
        game.add_hand(g, "red", kot=False)
    assert game.pause_game(g) is True
    assert game.is_paused(g)
    assert game.pause_game(g) is False  # second tap changes nothing
    c.tick(hours=67)
    p = game.resume_game(g)
    assert p and not game.is_paused(g)
    assert game.resume_game(g) is None
    play_to_end(g, c)  # 4 more hands, 20 minutes
    rec = game.archive_game(state)
    assert rec["paused_seconds"] == 67 * 3600
    assert game.record_duration_sec(rec) == 35 * 60
    text = msg.end_game_text(rec, game.today_summary(state), state)
    assert "⏱ مدت بازی: ۳۵ دقیقه" in text
    assert "⏸ توقف وسط بازی: ۶۷ ساعت" in text


def test_normal_game_record_and_message_are_unchanged():
    c = use_clock("2026-11-10T21:00:00+03:30")
    state = storage.empty_state(1)
    g = state["active_game"] = game.new_game()
    play_to_end(g, c)
    rec = game.archive_game(state)
    for key in ("pauses", "paused_seconds", "game_day_started"):
        assert key not in rec
    assert game.record_duration_sec(rec) == 35 * 60
    text = msg.end_game_text(rec, game.today_summary(state), state)
    assert "⏱ مدت بازی: ۳۵ دقیقه" in text
    assert "توقف" not in text


def test_long_pause_moves_game_to_the_day_it_is_resumed():
    c = use_clock("2026-11-08T01:18:00+03:30")  # before 6am: game day is 7 Nov
    state = storage.empty_state(1)
    g = state["active_game"] = game.new_game()
    assert g["game_day"] == "2026-11-07"
    game.pause_game(g)
    c.tick(days=2, hours=19)
    game.resume_game(g)
    assert g["game_day"] == "2026-11-10"
    assert g["game_day_started"] == "2026-11-07"
    play_to_end(g, c)
    rec = game.archive_game(state)
    assert rec["game_day"] == "2026-11-10" and rec["game_day_started"] == "2026-11-07"
    assert game.today_summary(state)["today_wins"] == {"red": 1, "blue": 0}


def test_short_pause_across_the_6am_cutoff_keeps_the_day():
    c = use_clock("2026-11-08T05:50:00+03:30")
    g = game.new_game()
    game.pause_game(g)
    c.tick(minutes=30)  # now 06:20, a new game day
    game.resume_game(g)
    assert g["game_day"] == "2026-11-07"
    assert "game_day_started" not in g


def test_old_records_without_pause_fields_still_work():
    rec = {
        "game_day": "2026-08-27",
        "started_at": "2026-08-27T22:00:00+03:30",
        "ended_at": "2026-08-27T22:49:00+03:30",
        "winner": "blue", "final_score": {"red": 3, "blue": 7},
    }
    assert game.record_duration_sec(rec) == 49 * 60
    assert msg._record_duration_text(rec) == "۴۹ دقیقه"
    assert msg._pause_line(rec) == ""


# ── handlers, with a fake Telegram ────────────────────────────────────────────

class FakeBot:
    def __init__(self):
        self.sent, self.edited, self.deleted = [], [], []
        self._id = 100

    async def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        self._id += 1
        self.sent.append((self._id, text, reply_markup))
        return SimpleNamespace(message_id=self._id)

    async def edit_message_text(self, chat_id, message_id, text, reply_markup=None, parse_mode=None):
        self.edited.append((message_id, text, reply_markup))

    async def delete_message(self, chat_id, message_id):
        self.deleted.append(message_id)


class FakeQuery:
    def __init__(self, chat_id: int, data: str):
        self.data = data
        self.answers = []

        async def _noop(*a, **k):
            return None

        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=chat_id), delete=_noop, edit_reply_markup=_noop)

    async def answer(self, text=None, **kw):
        self.answers.append(text)


def buttons(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row]


async def _tap(context, chat_id: int, data: str) -> FakeQuery:
    q = FakeQuery(chat_id, data)
    await handlers.on_callback(SimpleNamespace(callback_query=q), context)
    return q


async def _handler_flow():
    chat_id = 4242
    c = use_clock("2026-11-08T01:18:00+03:30")
    bot = FakeBot()
    context = SimpleNamespace(bot=bot, application=SimpleNamespace(bot=bot), chat_data={})

    await _tap(context, chat_id, "newgame")
    assert "pause" in buttons(bot.sent[-1][2])  # the pause button is on the scoreboard

    for _ in range(3):
        c.tick(minutes=5)
        await _tap(context, chat_id, "win:red")
    assert storage.load(chat_id)["active_game"]["score"] == {"red": 3, "blue": 0}

    q = await _tap(context, chat_id, "pause")
    assert q.answers == ["⏸ بازی متوقف شد"]
    _, text, markup = bot.edited[-1]
    assert "بازی متوقف شده" in text and buttons(markup) == ["resume", "stats"]
    assert storage.load(chat_id)["active_game"]["paused_at"]

    # While paused, nothing can be scored (also from an old scoreboard message).
    c.tick(hours=67)
    for data in ("win:red", "win:blue", "kot", "kotwin:red", "kot1:red:red"):
        q = await _tap(context, chat_id, data)
        assert q.answers == [msg.paused_notice()], data
    assert storage.load(chat_id)["active_game"]["score"] == {"red": 3, "blue": 0}

    q = await _tap(context, chat_id, "resume")
    assert q.answers == ["▶️ بازی ادامه پیدا کرد"]
    _, text, markup = bot.edited[-1]
    assert "بازی در جریان" in text and "win:red" in buttons(markup)
    g = storage.load(chat_id)["active_game"]
    assert g["paused_at"] is None and len(g["pauses"]) == 1
    assert g["game_day"] == "2026-11-10"

    for _ in range(4):
        c.tick(minutes=5)
        await _tap(context, chat_id, "win:red")
    state = storage.load(chat_id)
    assert state["active_game"] is None
    rec = state["history"][-1]
    assert rec["final_score"] == {"red": 7, "blue": 0}
    assert game.record_duration_sec(rec) == 35 * 60
    end_text = bot.sent[-1][1]
    assert "⏱ مدت بازی: ۳۵ دقیقه" in end_text
    assert "⏸ توقف وسط بازی: ۶۷ ساعت" in end_text
    assert "📅 <b>امروز (2026-11-10):</b>\n🔴 ۱ — ۰ 🔵" in end_text

    # A second game with no pause looks exactly like before.
    await _tap(context, chat_id, "newgame")
    for _ in range(7):
        c.tick(minutes=4)
        await _tap(context, chat_id, "win:blue")
    end_text = bot.sent[-1][1]
    assert "⏱ مدت بازی: ۲۸ دقیقه" in end_text and "توقف" not in end_text

    # Stale pause/resume taps after the game ended do nothing harmful.
    for data in ("pause", "resume"):
        q = await _tap(context, chat_id, data)
        assert q.answers == [msg.stale_button()]

    for t in list(handlers._refresh_tasks.values()):
        t.cancel()


def test_handler_flow():
    asyncio.run(_handler_flow())


def test_keyboards():
    assert buttons(kb.main_kb()) == ["win:red", "win:blue", "kot", "undo", "pause", "stats"]
    assert buttons(kb.board_kb({"paused_at": None})) == buttons(kb.main_kb())
    assert buttons(kb.board_kb({"paused_at": "x"})) == ["resume", "stats"]


if __name__ == "__main__":
    real_now = game.now_tz
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"ok    {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {t.__name__}: {type(e).__name__}: {e}")
        finally:
            game.now_tz = real_now
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
