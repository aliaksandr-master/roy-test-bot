import asyncio
import functools
import logging
from typing import cast

from langchain_core.documents import Document
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from src.app_tg_public.llm import Tfaq
from src.env import app_settings

logger = logging.getLogger(__name__)


def format_log(update: Update, text: str) -> str:
    return f'[user_id={getattr(update.effective_user, "id", "unknown")}] {text}'


async def telegram_faq_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, *, language: str, faq_chat: Tfaq) -> None:
    if update.message is None or update.message.text is None:
        return
    logger.info(format_log(update, f'telegram_faq_command_handler Q: "{update.message.text}"'))
    response = await faq_chat.ainvoke({"input": update.message.text.removeprefix("/faq ")})
    links = "\n".join(sorted({f"- {doc.metadata.get('url')}" for doc in cast(list[Document], response["context"]) if doc.metadata.get("url")}))
    answer_with_urls = f'{response["answer"]}\n\n{("read more" if language.lower() != "russian" else "Подробней") if links else ""}\n{links}'.strip()
    logger.info(format_log(update, f'telegram_faq_command_handler A: "{answer_with_urls}"'))
    await update.message.reply_text(answer_with_urls)


async def telegram(faq_chat: Tfaq) -> None:
    if app_settings.BOT_API_KEY is None:
        return
    app = ApplicationBuilder().token(app_settings.BOT_API_KEY.get_secret_value()).build()
    app.add_handler(CommandHandler("faq", functools.partial(telegram_faq_command_handler, language=app_settings.LANG, faq_chat=faq_chat)))
    async with app:
        if app.updater is None:
            return
        try:
            await app.start()
            await app.updater.start_polling(poll_interval=1, allowed_updates=Update.ALL_TYPES)
            while True:  # noqa: ASYNC110
                await asyncio.sleep(1)
        finally:
            await app.updater.stop()
            await app.stop()
