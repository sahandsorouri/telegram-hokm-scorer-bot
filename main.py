import logging

from telegram import MenuButtonWebApp, WebAppInfo
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler

import config
import handlers
import webapi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# httpx logs every request URL at INFO, and the URL holds the bot token: keep it out of the logs (12 Nov 2026)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("hokm")


async def _post_init(app: Application) -> None:
    app.bot_data["web_runner"] = await webapi.start(app)
    if config.WEBAPP_URL:
        try:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="🎴 حکم", web_app=WebAppInfo(url=config.WEBAPP_URL)))
        except TelegramError as e:
            log.warning("menu button not set: %s", e)


async def _post_shutdown(app: Application) -> None:
    runner = app.bot_data.get("web_runner")
    if runner:
        await runner.cleanup()


def build_app() -> Application:
    app = (Application.builder().token(config.BOT_TOKEN)
           .post_init(_post_init).post_shutdown(_post_shutdown).build())
    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(CommandHandler("newgame", handlers.cmd_newgame))
    app.add_handler(CommandHandler("score", handlers.cmd_score))
    app.add_handler(CommandHandler("stats", handlers.cmd_stats))
    app.add_handler(CommandHandler("undo", handlers.cmd_undo))
    app.add_handler(CommandHandler("endgame", handlers.cmd_endgame))
    app.add_handler(CommandHandler("import", handlers.cmd_import))
    app.add_handler(CommandHandler("app", handlers.cmd_app))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_error_handler(handlers.on_error)
    return app


def main():
    log.info("Hokm bot starting…")
    app = build_app()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
