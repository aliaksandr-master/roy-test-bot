import asyncio
import logging

import langchain.globals

from src.app_tg_public.bot import telegram
from src.app_tg_public.llm import make_faq_llm_chat
from src.app_tg_public.src_notion import load_faq_from_notion
from src.app_tg_public.src_roy import load_faq_from_roy
from src.env import app_settings


async def main() -> None:
    records = []
    if app_settings.SRC_ROY_ORG_ID:
        records += await load_faq_from_roy(app_settings.SRC_ROY_ORG_ID, sections_filter=app_settings.roy_sections)
    if app_settings.SRC_NOTION_WIKI_ID:
        records += await load_faq_from_notion(app_settings.SRC_NOTION_WIKI_ID)

    chat = make_faq_llm_chat(records)
    await telegram(chat)


if __name__ == "__main__":
    if app_settings.DEBUG:
        logging.basicConfig(level=logging.DEBUG)
        langchain.globals.set_debug(True)
    else:
        logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
