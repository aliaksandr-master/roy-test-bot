import asyncio
import functools
import logging
from datetime import datetime
from typing import NamedTuple

import httpx
import langchain.globals
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.embeddings.cache import CacheBackedEmbeddings
from langchain.schema.document import Document
from langchain.storage.file_system import LocalFileStore
from langchain.text_splitter import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ChatMemberHandler, MessageReactionHandler, ChatJoinRequestHandler, MessageHandler, \
    filters

from src.cache import Cache
from src.const import CACHE_DIR
from src.env import app_settings

logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE, *, faq_chat: Runnable) -> None:
    question = update.message.text
    response = await faq_chat.ainvoke({'input': question})
    answer = response['answer']
    logger.info(f'cmd_faq {update.effective_user.id} Q: "{question}"')
    logger.info(f'cmd_faq {update.effective_user.id} A: "{answer}"', )
    await update.message.reply_text(answer)


async def chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"chat_member_handler {update.effective_user.id}")
    await update.message.reply_text(f'chat_member_handler {update.effective_user.first_name}')


async def message_reaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"message_reaction_handler {update.effective_user.id}")
    # await update.message.reply_text(f'message_reaction_handler {update.effective_user.first_name}')


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"message_handler {update.effective_user.id}")
    await update.message.reply_text(f'message_handler {update.effective_user.first_name}')


async def chat_join_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"chat_join_request_handler {update.effective_user.id}")
    await update.message.reply_text(f'chat_join_request_handler {update.effective_user.first_name}')


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"echo {update.effective_user.id}")
    await update.message.reply_text(update.message.text)


async def telegram(faq_chat: Runnable) -> None:
    app = ApplicationBuilder().token(app_settings.TELEGRAM_API_KEY.get_secret_value()).build()

    app.add_handler(CommandHandler("faq", functools.partial(cmd_faq, faq_chat=faq_chat)))
    app.add_handler(ChatMemberHandler(chat_member_handler))
    app.add_handler(MessageReactionHandler(message_reaction_handler))
    app.add_handler(ChatJoinRequestHandler(message_reaction_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    async with app:
        try:
            await app.start()
            await app.updater.start_polling(poll_interval=1, allowed_updates=Update.ALL_TYPES)

            while True:
                await asyncio.sleep(1)
        finally:
            await app.updater.stop()
            await app.stop()


class BearerAuth(httpx.Auth):
    def __init__(self, token):
        self.token = token

    def auth_flow(self, request):
        # Send the request, with a custom `X-Authentication` header.
        request.headers['Authorization'] = f'Bearer {self.token}'
        request.headers['Notion-Version'] = f'2022-06-28'
        yield request


class NotionPage(NamedTuple):
    id: str
    updated_at: str
    title: str
    url: str
    blocks: list[str]


notion_page_cache = Cache(NotionPage)


async def notion_get_page(client: httpx.AsyncClient, page_id: str, updated_at: datetime) -> NotionPage | None:
    cache_id = dict(page_id=page_id, updated_at=updated_at.isoformat())
    if cached := notion_page_cache.get(**cache_id):
        return cached
    res = await client.get(f'https://api.notion.com/v1/pages/{page_id}')
    page = res.json()
    page_title = page['properties']['Name']['title'][0]['plain_text']
    page_url = page['url']
    next_cursor = ''
    content_blocks = []
    while True:
        res = await client.get(f'https://api.notion.com/v1/blocks/{page_id}/children?page_size=30{f"&start_cursor={next_cursor}" if next_cursor else ""}')
        if res.status_code >= 400:
            print(res.status_code, res.json())
            return None
        blocks = res.json()
        next_cursor = blocks['next_cursor'] or ''

        for block in blocks['results']:
            match block['type']:
                case "bulleted_list_item" | "paragraph" | "heading_1" | "heading_2" | "heading_3":
                    for rt in block[block['type']].get('rich_text', []):
                        if rt['type'] == 'text':
                            content_blocks.append(rt['plain_text'])
        if not next_cursor:
            break
    notion_page = NotionPage(page_id, updated_at.isoformat(), page_title, page_url, content_blocks)
    notion_page_cache.set(notion_page, **cache_id)
    return notion_page


async def load_faq_from_notion(db_id: str) -> list[NotionPage]:
    async with httpx.AsyncClient(auth=BearerAuth(app_settings.NOTION_API_KEY.get_secret_value())) as client:
        next_cursor = None
        page_tasks = []
        while True:
            res = await client.post(f'https://api.notion.com/v1/databases/{db_id}/query', data={
                'filter_properties': [],
                'page_size': 50,
                'start_cursor': next_cursor
            })
            if res.status_code >= 400:
                print(res.text)
                return []
            res_data = res.json()
            for page in filter(lambda page: page['object'] == 'page' and len(page['properties']['Name']['title']) == 1, res_data['results']):
                page_tasks.append(asyncio.create_task(notion_get_page(client, page['id'], datetime.fromisoformat(page['last_edited_time']))))
            next_cursor = res_data['next_cursor'] or ''
            if not next_cursor:
                break
        return list(await asyncio.gather(*page_tasks))


def mk_faq_ai_model(pages: list[NotionPage]) -> VectorStoreRetriever:
    store = LocalFileStore(CACHE_DIR / 'langchain_storage')
    underlying_embeddings = OpenAIEmbeddings(openai_api_key=app_settings.OPENAI_API_KEY.get_secret_value())
    embedder = CacheBackedEmbeddings.from_bytes_store(underlying_embeddings, store, namespace=underlying_embeddings.model)
    text_splitter = CharacterTextSplitter(separator='\n', chunk_size=1000, chunk_overlap=100, length_function=len)
    docs = [Document(page_content='this is faq')]

    print('>>> pages count', len(pages))
    for page in pages:
        metadata = dict(page_id=page.id, page_title=page.title, page_url=page.url)
        for block in page.blocks:
            for txt in text_splitter.split_text(block):
                docs.append(Document(page_content=txt, metadata=metadata))

    print('>>> documents count', len(docs))
    vector_store = Chroma.from_documents(documents=docs, embedding=embedder)

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 3},
    )
    return retriever

PROMPT_SYSTEM = """
You are an assistant for question-answering tasks. 
Use {lang} language for answering questions.
Use the following pieces of retrieved context to answer the question. 
If you don't know the answer, say that you don't know. 
Use three sentences maximum and keep the answer concise.

{context}
"""

PROMPT_QUESTION = """
{input}
"""


def load_llm(retriever: VectorStoreRetriever, lang: str = 'english') -> Runnable:
    llm = ChatOpenAI(model="gpt-3.5-turbo-0125", api_key=app_settings.OPENAI_API_KEY.get_secret_value())
    prompt = ChatPromptTemplate.from_messages([
        ("system", PROMPT_SYSTEM.replace('{lang}', lang.upper())),
        ("human", PROMPT_QUESTION.replace('{lang}', lang.upper())),
    ])
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    return rag_chain


async def main() -> None:
    pages = await load_faq_from_notion('fc16af447ed54d04b2a3fc28105bfec4')
    retriever = mk_faq_ai_model(pages)
    chat = load_llm(retriever, lang='Russian')
    await telegram(chat)


if __name__ == "__main__":
    if app_settings.DEBUG:
        langchain.globals.set_debug(True)
    asyncio.run(main())
