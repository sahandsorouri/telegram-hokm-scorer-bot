"""Mini App (Telegram Web App) for the Hokm bot.

Runs inside the bot process (same event loop, same per-chat locks), so a tap in the
app and a tap on the group's buttons go through exactly the same code: the group
scoreboard message is edited, the end-of-game message is posted, events are logged.

Auth: every request carries Telegram's initData, checked with the bot token
(https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).
Access to a chat's data needs the user to be a member of that chat (checked with
getChatMember and cached).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web
from telegram.error import TelegramError

import config
import events
import game
import handlers
import storage

log = logging.getLogger("hokm.web")

STATIC_DIR = Path(__file__).resolve().parent / "webapp"
INIT_DATA_MAX_AGE = 24 * 3600
MEMBER_CACHE_SECONDS = 600
_member_cache: dict[tuple[int, int], float] = {}


class _Ctx:
    """Stand-in for the PTB callback context: the handler helpers only use .bot
    and .application."""

    def __init__(self, application):
        self.application = application
        self.bot = application.bot


# ── auth ───────────────────────────────────────────────────────────────────────

def verify_init_data(init_data: str) -> dict | None:
    """Return the parsed initData (with 'user' decoded) if the signature is valid."""
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received = pairs.pop("hash", None)
    if not received:
        return None
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        return None
    try:
        if time.time() - int(pairs.get("auth_date", "0")) > INIT_DATA_MAX_AGE:
            return None
        pairs["user"] = json.loads(pairs.get("user", "{}"))
    except (ValueError, TypeError):
        return None
    if not pairs["user"].get("id"):
        return None
    return pairs


def parse_start_param(sp: str | None) -> int | None:
    """startapp payload: 'g<digits>' = group -<digits>, 'u<digits>' = private chat."""
    if not sp or len(sp) < 2 or not sp[1:].isdigit():
        return None
    if sp[0] == "g":
        return -int(sp[1:])
    if sp[0] == "u":
        return int(sp[1:])
    return None


async def _is_member(bot, chat_id: int, user_id: int) -> bool:
    if chat_id == user_id:
        return True
    key = (chat_id, user_id)
    if _member_cache.get(key, 0) > time.time():
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
    except TelegramError:
        return False
    if m.status in ("creator", "administrator", "member", "restricted"):
        _member_cache[key] = time.time() + MEMBER_CACHE_SECONDS
        return True
    return False


def _known_chats() -> list[int]:
    out = []
    for p in sorted(config.DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            out.append(int(p.stem))
        except ValueError:
            continue
    return out


async def _resolve_chat(request: web.Request, body: dict) -> tuple[int, dict]:
    auth = verify_init_data(body.get("initData", ""))
    if not auth:
        raise web.HTTPUnauthorized(text="bad initData")
    user_id = int(auth["user"]["id"])
    bot = request.app["ptb"].bot
    wanted = body.get("chat")
    candidates: list[int] = []
    if isinstance(wanted, int):
        candidates.append(wanted)
    sp = parse_start_param(auth.get("start_param"))
    if sp is not None:
        candidates.append(sp)
    # Opened from the private chat / menu button: use the busiest group he is in.
    candidates += [c for c in _known_chats() if c < 0]
    for c in candidates:
        if await _is_member(bot, c, user_id):
            return c, auth
    raise web.HTTPForbidden(text="no chat")


# ── view model ─────────────────────────────────────────────────────────────────

def _secs_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return (game.now_tz() - datetime.fromisoformat(iso)).total_seconds()
    except (TypeError, ValueError):
        return None


def _live_game_view(g: dict) -> dict:
    played = _secs_since(g.get("started_at")) or 0.0
    played -= game.paused_seconds(g.get("pauses"))
    if g.get("paused_at"):
        played -= _secs_since(g["paused_at"]) or 0.0
    return {
        "score": g["score"],
        "hakem": g["hakem"],
        "initial_hakem": g.get("initial_hakem"),
        "hands": [
            {"w": h["winner"], "p": h["points"], "k": bool(h.get("kot")),
             "x": bool(h.get("wrapped")), "hk": h.get("hakem_at_hand")}
            for h in g["hands"]
        ],
        "paused": bool(g.get("paused_at")),
        "started_at": g.get("started_at"),
        "played_seconds": max(0.0, played),
        "game_day": g.get("game_day"),
    }


def _rec_view(rec: dict, with_hands: bool) -> dict:
    out = {
        "day": rec.get("game_day"),
        "imported": bool(rec.get("imported")),
    }
    if rec.get("imported"):
        out["wins"] = rec.get("wins")
        out["kots"] = rec.get("kots")
        return out
    out.update({
        "winner": rec.get("winner"),
        "score": rec.get("final_score"),
        "started_at": rec.get("started_at"),
        "ended_at": rec.get("ended_at"),
        "seconds": game.record_duration_sec(rec),
        "hands_count": game._reconstruct_hands_count(rec),
        "kots_normal": rec.get("kots_normal"),
        "kots_hakem": rec.get("kots_hakem"),
        "kots": rec.get("kots"),
        "wraps": rec.get("wraps"),
        "paused_seconds": rec.get("paused_seconds"),
    })
    if with_hands and rec.get("hands"):
        out["hands"] = [
            {"w": h["winner"], "p": h["points"], "k": bool(h.get("kot")), "x": bool(h.get("wrapped"))}
            for h in rec["hands"]
        ]
    return out


def _fun_stats(state: dict) -> dict:
    """Records and streaks over the logged games (imported day tallies have no order)."""
    live = [r for r in state["history"] if not r.get("imported") and r.get("winner")]
    best = {"red": 0, "blue": 0}
    cur_team, cur_len = None, 0
    for r in live:
        if r["winner"] == cur_team:
            cur_len += 1
        else:
            cur_team, cur_len = r["winner"], 1
        best[cur_team] = max(best[cur_team], cur_len)
    shutouts = {"red": 0, "blue": 0}
    comeback = None  # biggest deficit a winner climbed back from
    fastest = None
    longest = None
    most_hands = None
    for r in live:
        fs = r.get("final_score") or {}
        loser = game.opposite(r["winner"])
        if fs.get(loser) == 0:
            shutouts[r["winner"]] += 1
        sec = game.record_duration_sec(r)
        if sec and sec >= 60:
            if fastest is None or sec < fastest["seconds"]:
                fastest = {"seconds": sec, "day": r.get("game_day"), "winner": r["winner"], "score": fs}
            if longest is None or sec > longest["seconds"]:
                longest = {"seconds": sec, "day": r.get("game_day"), "winner": r["winner"], "score": fs}
        hc = game._reconstruct_hands_count(r)
        if hc and (most_hands is None or hc > most_hands["hands"]):
            most_hands = {"hands": hc, "day": r.get("game_day"), "winner": r["winner"], "score": fs}
        if r.get("hands"):
            sc = {"red": 0, "blue": 0}
            worst = 0
            for h in r["hands"]:
                sc[h["winner"]] += h["points"]
                if sc[h["winner"]] > config.WIN_TARGET:
                    sc[h["winner"]] -= config.WIN_TARGET
                worst = max(worst, sc[loser] - sc[r["winner"]])
            if worst > 0 and (comeback is None or worst > comeback["deficit"]):
                comeback = {"deficit": worst, "day": r.get("game_day"), "winner": r["winner"], "score": fs}
    # best single night for a team (most wins)
    best_night = None
    for day, slot in game.daily_breakdown(state).items():
        for t in ("red", "blue"):
            if best_night is None or slot[t] > best_night["wins"]:
                best_night = {"wins": slot[t], "team": t, "day": day, "other": slot[game.opposite(t)]}
    form = [r["winner"] for r in live[-20:]]
    return {
        "best_streak": best,
        "current_streak": {"team": cur_team, "len": cur_len},
        "shutouts": shutouts,
        "comeback": comeback,
        "fastest": fastest,
        "longest": longest,
        "most_hands": most_hands,
        "best_night": best_night,
        "form": form,
    }


def build_view(chat_id: int, state: dict) -> dict:
    g = state.get("active_game")
    today = game.today_summary(state)
    life = game.lifetime_stats(state)
    life.pop("durations_after_cutoff", None)
    hist = state["history"]
    recent = [_rec_view(r, with_hands=i >= len(hist) - 80) for i, r in enumerate(hist)]
    tonight = [v for v in recent if not v["imported"] and v["day"] == today["today_date"]]
    return {
        "chat": chat_id,
        "now": game.now_tz().isoformat(),
        "target": config.WIN_TARGET,
        "game": _live_game_view(g) if g else None,
        "can_undo_ended": game.can_undo_ended(state),
        "last_game": recent[-1] if recent and not g else None,
        "today": today,
        "tonight": tonight,
        "lifetime": life,
        "fun": _fun_stats(state),
        "history": recent,
    }


# ── actions (same code paths as the group buttons) ─────────────────────────────

async def _act(ctx: _Ctx, chat_id: int, state: dict, body: dict, who: str) -> str:
    action = body.get("action")
    g = state.get("active_game")
    team = body.get("team")

    if action in ("win", "kot", "kot1"):
        if not g or game.game_ended(g):
            raise web.HTTPConflict(text="no game")
        if game.is_paused(g):
            raise web.HTTPConflict(text="paused")
        if team not in ("red", "blue"):
            raise web.HTTPBadRequest(text="team")
        if action == "kot1":
            hakem = body.get("hakem")
            if hakem not in ("red", "blue") or g["hands"]:
                raise web.HTTPConflict(text="stale")
            g["initial_hakem"] = hakem
            g["hakem"] = hakem
            events.append(chat_id, {"type": "hakem_confirmed", "initial_hakem": hakem,
                                    "reason": "first_hand_kot", "via": "webapp"})
        pts = game.add_hand(g, team, kot=action != "win")
        handlers._log_hand_event(chat_id, g)
        if game.game_ended(g):
            await handlers._finish_game(ctx, chat_id, state)
            return "ended"
        storage.save(chat_id, state)
        await handlers._edit_scoreboard(ctx, chat_id, state)
        return f"+{pts}"

    if action == "undo":
        if g and game.can_undo(g):
            popped = game.undo_last(g)
            events.append(chat_id, {"type": "undo_hand", "popped": popped,
                                    "score_after": dict(g["score"]), "via": "webapp"})
            storage.save(chat_id, state)
            await handlers._edit_scoreboard(ctx, chat_id, state)
            return "undone"
        raise web.HTTPConflict(text="nothing to undo")

    if action == "undo_ended":
        if not game.can_undo_ended(state):
            raise web.HTTPConflict(text="too late")
        end_id = (state.get("last_ended_game") or {}).get("end_message_id")
        game.restore_last_game(state)
        events.append(chat_id, {"type": "undo_ended_game", "via": "webapp"})
        storage.save(chat_id, state)
        if end_id:
            await handlers._safe_delete(ctx.bot, chat_id, end_id)
        await handlers._send_scoreboard_fresh(ctx, chat_id, state)
        return "restored"

    if action in ("pause", "resume"):
        if not g:
            raise web.HTTPConflict(text="no game")
        if action == "pause":
            if not game.pause_game(g):
                return "already"
            handlers._cancel_refresh(chat_id)
            events.append(chat_id, {"type": "game_pause", "score_at_pause": dict(g["score"]),
                                    "hands_at_pause": len(g["hands"]), "via": "webapp"})
        else:
            p = game.resume_game(g)
            if p is None:
                return "already"
            events.append(chat_id, {"type": "game_resume", "paused_from": p["from"],
                                    "paused_seconds": game.paused_seconds([p]),
                                    "game_day": g["game_day"], "via": "webapp"})
        storage.save(chat_id, state)
        await handlers._edit_scoreboard(ctx, chat_id, state)
        return action

    if action == "newgame":
        if g:
            if not body.get("confirm"):
                raise web.HTTPConflict(text="active")
            handlers._cancel_refresh(chat_id)
            old_id = g.get("score_board_message_id")
            if old_id:
                await handlers._safe_delete(ctx.bot, chat_id, old_id)
            state["active_game"] = None
        end_id = (state.get("last_ended_game") or {}).get("end_message_id")
        if end_id:
            # the end message's buttons would now be stale
            try:
                await ctx.bot.edit_message_reply_markup(chat_id=chat_id, message_id=end_id, reply_markup=None)
            except TelegramError:
                pass
        await handlers._start_new_game(ctx, chat_id, state)
        return "started"

    if action == "abort":
        if not g:
            raise web.HTTPConflict(text="no game")
        handlers._cancel_refresh(chat_id)
        old_id = g.get("score_board_message_id")
        if old_id:
            await handlers._safe_delete(ctx.bot, chat_id, old_id)
        events.append(chat_id, {"type": "game_aborted", "score_at_abort": dict(g["score"]),
                                "hands_at_abort": len(g["hands"]), "via": "webapp"})
        state["active_game"] = None
        state["last_ended_game"] = None
        storage.save(chat_id, state)
        await handlers._ephemeral(ctx, chat_id, "بازی فعلی بدون ثبت تموم شد.")
        return "aborted"

    raise web.HTTPBadRequest(text="action")


# ── http ───────────────────────────────────────────────────────────────────────

async def _json_body(request: web.Request) -> dict:
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        raise web.HTTPBadRequest(text="json")
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="json")
    return body


async def api_state(request: web.Request) -> web.Response:
    body = await _json_body(request)
    chat_id, _ = await _resolve_chat(request, body)
    state = storage.load(chat_id)
    return web.json_response(build_view(chat_id, state), dumps=lambda o: json.dumps(o, ensure_ascii=False))


async def api_act(request: web.Request) -> web.Response:
    body = await _json_body(request)
    chat_id, auth = await _resolve_chat(request, body)
    ctx = _Ctx(request.app["ptb"])
    who = auth["user"].get("first_name") or str(auth["user"]["id"])
    async with storage.lock_for(chat_id):
        state = storage.load(chat_id)
        result = await _act(ctx, chat_id, state, body, who)
        state = storage.load(chat_id)
    log.info("webapp action %s by user %s in chat %s: %s", body.get("action"), auth["user"]["id"], chat_id, result)
    return web.json_response({"result": result, "view": build_view(chat_id, state)},
                             dumps=lambda o: json.dumps(o, ensure_ascii=False))


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


def make_app(ptb_application) -> web.Application:
    app = web.Application(client_max_size=64 * 1024)
    app["ptb"] = ptb_application
    app.router.add_get("/", index)
    app.router.add_post("/api/state", api_state)
    app.router.add_post("/api/act", api_act)
    app.router.add_static("/static/", STATIC_DIR, show_index=False)
    return app


async def start(ptb_application) -> web.AppRunner:
    runner = web.AppRunner(make_app(ptb_application), access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host=config.WEB_HOST, port=config.WEB_PORT)
    await site.start()
    log.info("webapp listening on %s:%s", config.WEB_HOST, config.WEB_PORT)
    return runner
