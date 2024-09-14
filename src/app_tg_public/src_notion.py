import logging
from collections.abc import Coroutine
from datetime import datetime
from typing import Any, Callable

import httpx

from src.app_tg_public.llm import QARecord
from src.app_tg_public.utils import Cache, auth, ignore_error, run_chunked
from src.env import app_settings

logger = logging.getLogger(__name__)

notion_page_cache = Cache(QARecord)


NOTION_API = "https://api.notion.com/v1"


async def notion_get_page_blocks(page_id: str, next_cursor: str) -> dict[str, Any]:
    res = await client.get(f'{NOTION_API}/blocks/{page_id}/children?page_size=30{f"&start_cursor={next_cursor}" if next_cursor else ""}')
    if res.status_code >= 400:
        return None


async def notion_get_page(client: httpx.AsyncClient, page_id: str, updated_at: datetime) -> QARecord | None:
    if cached := notion_page_cache.get(page_id=page_id, updated_at=updated_at.isoformat()):
        return cached
    res = await client.get(f"{NOTION_API}/pages/{page_id}")
    page = res.json()
    page_url = page["url"]
    next_cursor = ""
    content_blocks = []
    while True:
        res = await client.get(f'{NOTION_API}/blocks/{page_id}/children?page_size=30{f"&start_cursor={next_cursor}" if next_cursor else ""}')
        if res.status_code >= 400:
            return None
        blocks = res.json()
        next_cursor = blocks["next_cursor"] or ""

        for block in blocks["results"]:
            match block["type"]:
                case "bulleted_list_item" | "paragraph" | "heading_1" | "heading_2" | "heading_3":
                    for rt in block[block["type"]].get("rich_text", []):
                        if rt["type"] == "text":
                            content_blocks.append(rt["plain_text"])
        if not next_cursor:
            break
    notion_page = QARecord(
        id=page_id, updated_at=updated_at.isoformat(), title=page["properties"]["Name"]["title"][0]["plain_text"], url=page_url, blocks=content_blocks
    )
    notion_page_cache.set(notion_page, page_id=page_id, updated_at=updated_at.isoformat())
    return notion_page


async def make_auth() -> Callable[[httpx.Request], httpx.Request]:
    return auth({"Authorization": f"Bearer {app_settings.SRC_NOTION_API_KEY.get_secret_value()}", "Notion-Version": "2022-06-28"})


async def get_list_of_records(wiki_id: str) -> list[QARecord]:
    async with httpx.AsyncClient(auth=await make_auth()) as client:
        next_cursor = None
        page_tasks: list[Coroutine[Any, Any, QARecord | None]] = []
        while True:
            res = await client.post(f"{NOTION_API}/databases/{wiki_id}/query", data={"page_size": 50, "start_cursor": next_cursor})
            if res.status_code >= 400:
                return []
            res_data = res.json()
            for page in filter(lambda p: p["object"] == "page" and len(p["properties"]["Name"]["title"]) == 1, res_data["results"]):
                page_tasks.append(ignore_error(None, notion_get_page(client, page["id"], datetime.fromisoformat(page["last_edited_time"]))))
            next_cursor = res_data["next_cursor"] or ""
            if not next_cursor:
                break
        return [p for p in await run_chunked(page_tasks, size=15) if p is not None]


async def load_faq_from_notion(wiki_id: str) -> list[QARecord]:
    assert app_settings.SRC_NOTION_API_KEY
    return await ignore_error([], get_list_of_records(wiki_id))
