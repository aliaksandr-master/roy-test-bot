import asyncio
import logging

import langchain.globals

from src.app_tg_public.llm import mk_chat
from src.app_tg_public.src_roy import load_faq_from_roy
from src.app_tg_public.teleram import telegram
from src.env import app_settings

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    pages = await load_faq_from_roy(13490, sections=None)
    # pages = await load_faq_from_notion('fc16af447ed54d04b2a3fc28105bfec4')

    chat = mk_chat(pages, lang="Russian")
    await telegram("Russian", chat)


if __name__ == "__main__":
    if app_settings.DEBUG:
        langchain.globals.set_debug(True)
    asyncio.run(main())
