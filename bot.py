"""Unhook Telegram bot.   Run:  python bot.py"""
import asyncio
import logging
import sys

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app import db, settings
from app.formatting import (ERROR_TEXT, NO_INPUT_TEXT, REPLY_TO_CHECK_TEXT, START_TEXT, THINKING_TEXT,
                           format_group_warning, format_verdict)
from app.linkcheck import extract_urls
from app.service import check

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx logs URLs that contain the bot token
log = logging.getLogger("unhook.bot")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_TEXT, parse_mode=ParseMode.HTML)


async def _reply_with_check(update: Update, text: str | None, image: bytes | None) -> None:
    message = update.message
    if not text and not image:
        await message.reply_text(NO_INPUT_TEXT)
        return
    await message.chat.send_action(ChatAction.TYPING)
    waiting = await message.reply_text(THINKING_TEXT)
    try:
        verdict, _ = await asyncio.to_thread(check, text, image, "telegram")  # analyzer is blocking
        answer = format_verdict(verdict)
    except Exception:
        log.exception("check failed")
        answer = ERROR_TEXT
    try:
        await waiting.edit_text(answer, parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("could not edit reply, sending a new message")
        await message.reply_text(answer, parse_mode=ParseMode.HTML)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply_with_check(update, update.message.text, None)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    photo = message.photo[-1] if message.photo else message.document  # largest size / image sent as a file
    file = await photo.get_file()
    image = bytes(await file.download_as_bytearray())
    await _reply_with_check(update, message.caption, image)


async def on_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Family-group guard: only messages with a link are checked (saves the free quota), and the bot stays silent
    unless it finds a scam or something suspicious."""
    message = update.message
    text = message.text or message.caption
    if not text or not extract_urls(text):
        return
    try:
        verdict, _ = await asyncio.to_thread(check, text, None, "telegram")
        if verdict.verdict == "safe" or verdict.degraded:
            return
        await message.reply_text(format_group_warning(verdict), parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("group check failed")  # never spam a group with errors


async def yoxla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/yoxla as a reply to any message (works in groups and private chats)."""
    message = update.message
    target = message.reply_to_message
    if target is None:
        await message.reply_text(REPLY_TO_CHECK_TEXT, parse_mode=ParseMode.HTML)
        return
    image = None
    if target.photo:
        file = await target.photo[-1].get_file()
        image = bytes(await file.download_as_bytearray())
    text = target.text or target.caption
    if not text and not image:
        await message.reply_text(REPLY_TO_CHECK_TEXT, parse_mode=ParseMode.HTML)
        return
    await _reply_with_check(update, text, image)


def build_app() -> Application:
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("yoxla", yoxla))
    private = filters.ChatType.PRIVATE
    app.add_handler(MessageHandler(private & (filters.PHOTO | filters.Document.IMAGE), on_photo))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & (filters.TEXT | filters.CAPTION) & ~filters.COMMAND, on_group_text))
    return app


def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        sys.exit("TELEGRAM_BOT_TOKEN is empty. Create a bot with @BotFather and put the token in .env")
    db.init_db()
    log.info("Unhook bot is running (analyzer=%s). Press Ctrl+C to stop.", settings.ANALYZER_PROVIDER)
    build_app().run_polling()


if __name__ == "__main__":
    main()
