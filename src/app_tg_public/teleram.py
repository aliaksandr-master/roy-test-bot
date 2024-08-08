import asyncio
import functools
import logging

from langchain_core.documents import Document
from langchain_core.runnables import Runnable
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from src.env import app_settings

logger = logging.getLogger(__name__)


LN = '\n'


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE, *, params: tuple[str, Runnable]) -> None:
    language, faq_chat = params
    question = update.message.text
    logger.info(f'[user_id={update.effective_user.id if update.effective_user else "unknown"}] cmd_faq Q: "{question}"')
    response = await faq_chat.ainvoke({'input': question.removeprefix('/faq ')})
    answer = response['answer']
    context: list[Document] = response['context']
    more_txt = 'read more' if language.lower() != 'russian' else 'Подробней'
    links = "\n".join(sorted(set(f"- {doc.metadata.get('url')}" for doc in context if doc.metadata.get('url'))))
    answer_with_urls = f'{answer}{LN}{LN}{f"{more_txt}:{LN}" if links else ""}{links}'
    logger.info(f'[user_id={update.effective_user.id if update.effective_user else "unknown"}] cmd_faq A: "{answer}"', )
    await update.message.reply_text(answer_with_urls.strip())


async def telegram(language: str, faq_chat: Runnable) -> None:
    app = ApplicationBuilder().token(app_settings.TELEGRAM_API_KEY.get_secret_value()).build()
    app.add_handler(CommandHandler("faq", functools.partial(cmd_faq, params=(language, faq_chat))))
    async with app:
        try:
            await app.start()
            await app.updater.start_polling(poll_interval=1, allowed_updates=Update.ALL_TYPES)
            while True:
                await asyncio.sleep(1)
        finally:
            await app.updater.stop()
            await app.stop()
