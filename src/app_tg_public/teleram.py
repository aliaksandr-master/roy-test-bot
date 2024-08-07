import asyncio
import functools
import logging

from langchain_core.runnables import Runnable
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from src.env import app_settings

logger = logging.getLogger(__name__)


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE, *, faq_chat: Runnable) -> None:
    question = update.message.text
    response = await faq_chat.ainvoke({'input': question})
    answer = response['answer']
    logger.info(f'cmd_faq {update.effective_user.id} Q: "{question}"')
    logger.info(f'cmd_faq {update.effective_user.id} A: "{answer}"', )
    await update.message.reply_text(answer)


async def telegram(faq_chat: Runnable) -> None:
    app = ApplicationBuilder().token(app_settings.TELEGRAM_API_KEY.get_secret_value()).build()
    app.add_handler(CommandHandler("faq", functools.partial(cmd_faq, faq_chat=faq_chat)))
    async with app:
        try:
            await app.start()
            await app.updater.start_polling(poll_interval=1, allowed_updates=Update.ALL_TYPES)
            while True:
                await asyncio.sleep(1)
        finally:
            await app.updater.stop()
            await app.stop()
