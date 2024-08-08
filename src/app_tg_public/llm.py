from typing import NamedTuple

from src.const import CACHE_DIR
from src.env import app_settings
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain.embeddings.cache import CacheBackedEmbeddings
from langchain.schema.document import Document
from langchain.storage.file_system import LocalFileStore
from langchain.text_splitter import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.runnables import Runnable


class PageDoc(NamedTuple):
    id: str
    updated_at: str
    title: str
    url: str
    blocks: list[str]


def mk_faq_ai_model(pages: list[PageDoc]) -> VectorStoreRetriever:
    store = LocalFileStore(CACHE_DIR / 'langchain_storage')
    underlying_embeddings = OpenAIEmbeddings(openai_api_key=app_settings.OPENAI_API_KEY.get_secret_value())
    embedder = CacheBackedEmbeddings.from_bytes_store(underlying_embeddings, store, namespace=underlying_embeddings.model)
    text_splitter = CharacterTextSplitter(separator='\n', chunk_size=1000, chunk_overlap=100, length_function=len)
    docs = [Document(page_content='this is faq')]

    print('>>> pages count', len(pages))
    for page in pages:
        for block in page.blocks:
            for txt in text_splitter.split_text(block):
                docs.append(Document(page_content=txt, metadata=dict(id=page.id, title=page.title, url=page.url, updated_at=page.updated_at)))

    print('>>> documents count', len(docs))
    vector_store = Chroma.from_documents(documents=docs, embedding=embedder)
    return vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})


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


def mk_chat(pages: list[PageDoc], lang: str = 'english') -> Runnable:
    retriever = mk_faq_ai_model(pages)
    llm = ChatOpenAI(model="gpt-3.5-turbo-0125", api_key=app_settings.OPENAI_API_KEY.get_secret_value())
    prompt = ChatPromptTemplate.from_messages([
        ("system", PROMPT_SYSTEM.replace('{lang}', lang.upper())),
        ("human", PROMPT_QUESTION.replace('{lang}', lang.upper())),
    ])
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    return rag_chain
