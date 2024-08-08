import asyncio
from datetime import datetime

import httpx

from src.app_tg_public.llm import PageDoc
from src.app_tg_public.utils import Cache
from src.env import app_settings

notion_page_cache = Cache(PageDoc)


class BearerAuth(httpx.Auth):
    def __init__(self, token):
        self.token = token

    def auth_flow(self, request):
        # Send the request, with a custom `X-Authentication` header.
        request.headers['Authorization'] = f'Bearer {self.token}'
        request.headers['Notion-Version'] = f'2022-06-28'
        yield request


async def notion_get_page(client: httpx.AsyncClient, page_id: str, updated_at: datetime) -> PageDoc | None:
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
    notion_page = PageDoc(page_id, updated_at.isoformat(), page_title, page_url, content_blocks)
    notion_page_cache.set(notion_page, **cache_id)
    return notion_page


async def load_faq_from_notion(db_id: str) -> list[PageDoc]:
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
