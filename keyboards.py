from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config


def app_url(chat_id: int | None) -> str | None:
    """t.me link that opens the Mini App on this chat, or None if the app is off."""
    if not config.WEBAPP_LINK or chat_id is None:
        return None
    param = f"g{-chat_id}" if chat_id < 0 else f"u{chat_id}"
    return f"{config.WEBAPP_LINK}={param}"


def _with_app_row(markup: InlineKeyboardMarkup, chat_id: int | None) -> InlineKeyboardMarkup:
    url = app_url(chat_id)
    if not url:
        return markup
    rows = [list(r) for r in markup.inline_keyboard]
    rows.append([InlineKeyboardButton("🎴 باز کردن برنامه حکم", url=url)])
    return InlineKeyboardMarkup(rows)


def app_kb(chat_id: int) -> InlineKeyboardMarkup | None:
    url = app_url(chat_id)
    if not url:
        return None
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎴 باز کردن برنامه حکم", url=url)]])


def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 قرمز برد", callback_data="win:red"),
            InlineKeyboardButton("🔵 آبی برد", callback_data="win:blue"),
        ],
        [InlineKeyboardButton("⚡ کت!", callback_data="kot")],
        [
            InlineKeyboardButton("↩️ Undo", callback_data="undo"),
            InlineKeyboardButton("⏸ توقف", callback_data="pause"),
            InlineKeyboardButton("📊 آمار", callback_data="stats"),
        ],
    ])


def paused_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ ادامه بازی", callback_data="resume")],
        [InlineKeyboardButton("📊 آمار", callback_data="stats")],
    ])


def board_kb(g: dict, chat_id: int | None = None) -> InlineKeyboardMarkup:
    """Keyboard for the scoreboard: resume-only while the game is paused.
    With the Mini App on, one extra row opens it."""
    return _with_app_row(paused_kb() if g.get("paused_at") else main_kb(), chat_id)


def kot_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 قرمز کت کرد", callback_data="kotwin:red"),
            InlineKeyboardButton("🔵 آبی کت کرد", callback_data="kotwin:blue"),
        ],
        [InlineKeyboardButton("← برگشت", callback_data="kotwin:cancel")],
    ])


def kot_first_hand_kb() -> InlineKeyboardMarkup:
    # callback data: kot1:<hakem>:<winner>
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑🔴 → 🔴 کت (+۲)", callback_data="kot1:red:red"),
            InlineKeyboardButton("👑🔴 → 🔵 کت (+۳)", callback_data="kot1:red:blue"),
        ],
        [
            InlineKeyboardButton("👑🔵 → 🔵 کت (+۲)", callback_data="kot1:blue:blue"),
            InlineKeyboardButton("👑🔵 → 🔴 کت (+۳)", callback_data="kot1:blue:red"),
        ],
        [InlineKeyboardButton("← برگشت", callback_data="kot1:cancel")],
    ])


def end_kb(chat_id: int | None = None) -> InlineKeyboardMarkup:
    return _with_app_row(InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 بازی جدید", callback_data="newgame")],
        [
            InlineKeyboardButton("↩️ Undo بازی", callback_data="undo_ended"),
            InlineKeyboardButton("📊 تاریخچه", callback_data="stats"),
        ],
    ]), chat_id)


def confirm_kb(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ آره", callback_data=f"confirm:{action}"),
            InlineKeyboardButton("❌ نه", callback_data="confirm:cancel"),
        ],
    ])


def import_conflict_kb(day: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ اضافه کن", callback_data=f"imp:add:{day}"),
            InlineKeyboardButton("♻️ جایگزین", callback_data=f"imp:rep:{day}"),
        ],
        [InlineKeyboardButton("❌ لغو", callback_data="imp:cancel")],
    ])
