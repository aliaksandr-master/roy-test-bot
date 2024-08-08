from datetime import datetime
from typing import TypeVar

import httpx
from bs4 import BeautifulSoup  # type: ignore
from openai import BaseModel

from src.app_tg_public.llm import PageDoc
from src.app_tg_public.utils import flatten, run_list

T = TypeVar("T", bound=BaseModel)


class RoyBackendSection(BaseModel):
    id: int
    organization_id: int
    name: str
    description: str | None
    cover: str
    materials_count: int
    created_at: datetime
    updated_at: datetime


class RoyBackendSectionMaterialOrg(BaseModel):
    id: int


class RoyBackendSectionMaterialSection(BaseModel):
    id: int


class RoyBackendSectionMaterial(BaseModel):
    id: int
    organization: RoyBackendSectionMaterialOrg
    section: RoyBackendSectionMaterialSection
    # user: str
    type: str
    image: str | None
    title: str
    excerpt: str
    content: str | None = None
    # link: str | None
    tags: list[str]
    comments_count: int
    published_at: datetime

    def to_page_doc(self) -> PageDoc:
        return PageDoc(
            id=str(self.id),
            title=self.title,
            updated_at=self.published_at.isoformat(),
            url=f"https://roy.team/{self.organization.id}/materials/{self.id}",
            blocks=[BeautifulSoup(self.content or "", "html.parser").text],
        )


def roy_backend_auth(request: httpx.Request) -> httpx.Request:
    request.headers["Authorization"] = "Bearer 2019|Eml3qUTp5rHB6Th0xmCzHIzqIelDMujytpV0DRll"
    return request


async def roy_backend_get_list(model: type[T], url: str, default: list[T] | None = None) -> list[T]:
    try:
        async with httpx.AsyncClient(auth=roy_backend_auth) as client:
            response = await client.get(url)
            # print('>>>', response.status_code, url, json.dumps(response.json(), indent=4))
            response.raise_for_status()
            data = response.json()
            return [model(**r) for r in data["data"]]
    except Exception:
        if default is not None:
            return default
        raise


async def roy_backend_get_one(model: type[T], url: str) -> T:
    async with httpx.AsyncClient(auth=roy_backend_auth) as client:
        response = await client.get(url)
        # print('>>>', response.status_code, url, json.dumps(response.json(), indent=4))
        response.raise_for_status()
        data = response.json()
        return model(**data["data"])


async def load_faq_from_roy(organization_id: int, sections: set[int] | None) -> list[PageDoc]:
    all_sections = await roy_backend_get_list(
        RoyBackendSection, f"https://api.roy.team/api/kbase/sections?organization_id={organization_id}&sortDirection=asc", []
    )
    short_materials_chunks: list[RoyBackendSectionMaterial] = flatten(
        await run_list(
            [
                roy_backend_get_list(
                    RoyBackendSectionMaterial, f"https://api.roy.team/api/kbase/materials?organization_id={organization_id}&section={s.id}", []
                )
                for s in filter(lambda s: sections is None or s.id in sections, all_sections)
            ],
            15,
        )
    )
    materials = await run_list(
        [roy_backend_get_one(RoyBackendSectionMaterial, f"https://api.roy.team/api/kbase/materials/{sm.id}") for sm in short_materials_chunks], 15
    )
    return [m.to_page_doc() for m in materials]
