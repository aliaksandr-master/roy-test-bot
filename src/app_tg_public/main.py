import asyncio
import logging
import langchain.globals

from src.app_tg_public.llm import mk_faq_ai_model, load_llm
from src.app_tg_public.src_notion import load_faq_from_notion
from src.app_tg_public.src_roy import load_faq_from_roy
from src.app_tg_public.teleram import telegram
from src.env import app_settings

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    # pages = await load_faq_from_roy(13490, sections=None)
    pages = await load_faq_from_notion('fc16af447ed54d04b2a3fc28105bfec4')

    retriever = mk_faq_ai_model(pages)
    chat = load_llm(retriever, lang='Russian')
    await telegram(chat)


if __name__ == "__main__":
    if app_settings.DEBUG:
        langchain.globals.set_debug(True)
    asyncio.run(main())
