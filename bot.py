import json
import logging
import os
from pathlib import Path
from typing import Set

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SUBSCRIBERS_FILE = Path("subscribers.json")
HELP_TEXT = (
    "Привет. Это базовый Telegram-бот каркас для твоего проекта.\n\n"
    "Команды:\n"
    "/start\n"
    "/help\n"
    "/subscribe\n"
    "/unsubscribe\n"
    "/notify_now\n"
    "/broadcast <текст> (только админ)\n\n"
    "Я убрал выдуманную логику скачивания. Дальше встраиваем только твой реальный код."
)


def _admin_ids() -> Set[int]:
    raw = os.getenv("ADMIN_CHAT_IDS", "").strip()
    if not raw:
        return set()
    result: Set[int] = set()
    for item in raw.split(","):
        value = item.strip()
        if value and (value.isdigit() or (value.startswith("-") and value[1:].isdigit())):
            result.add(int(value))
    return result


def _load_subscribers() -> Set[int]:
    if not SUBSCRIBERS_FILE.exists():
        return set()
    try:
        data = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
        return {int(chat_id) for chat_id in data}
    except (json.JSONDecodeError, OSError, ValueError):
        logger.warning("subscribers.json invalid, recreating")
        return set()


def _save_subscribers(subscribers: Set[int]) -> None:
    SUBSCRIBERS_FILE.write_text(
        json.dumps(sorted(subscribers), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat:
        subscribers = _load_subscribers()
        subscribers.add(update.effective_chat.id)
        _save_subscribers(subscribers)
    if update.message:
        await update.message.reply_text(HELP_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(HELP_TEXT)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return
    subscribers = _load_subscribers()
    subscribers.add(update.effective_chat.id)
    _save_subscribers(subscribers)
    await update.message.reply_text("Подписка включена ✅")


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return
    subscribers = _load_subscribers()
    subscribers.discard(update.effective_chat.id)
    _save_subscribers(subscribers)
    await update.message.reply_text("Подписка отключена ❌")


async def notify_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Тест уведомления: бот запущен и может отправлять сообщения.",
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return

    if update.effective_chat.id not in _admin_ids():
        await update.message.reply_text("Недостаточно прав для рассылки.")
        return

    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Использование: /broadcast <текст>")
        return

    subscribers = _load_subscribers()
    sent = 0
    for chat_id in subscribers:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("broadcast error for %s: %s", chat_id, exc)

    await update.message.reply_text(f"Рассылка отправлена: {sent} пользователям")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception. update=%s", update, exc_info=context.error)


def main() -> None:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("notify_now", notify_now))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_error_handler(error_handler)

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
