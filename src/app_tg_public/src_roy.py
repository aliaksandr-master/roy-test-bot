import logging
import operator
from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from src.app_tg_public.llm import QARecord
from src.app_tg_public.utils import IdRow, auth, flatten, http_get_list, http_get_one, ignore_error, run_chunked
from src.env import app_settings

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class RoyPage(BaseModel, extra="ignore"):
    id: int
    organization: IdRow
    title: str
    content: str | None = None
    published_at: datetime

    def to_page_doc(self) -> QARecord:
        return QARecord(
            id=str(self.id),
            title=self.title,
            updated_at=self.published_at.isoformat(),
            url=f"https://roy.team/{self.organization.id}/materials/{self.id}",
            blocks=[BeautifulSoup(self.content or "", "html.parser").text],
        )


ROY_API = "https://api.roy.team/api"


async def make_auth() -> Callable[[httpx.Request], httpx.Request]:
    if not app_settings.SRC_ROY_LOGIN:
        return auth({})
    assert app_settings.SRC_ROY_PASSWORD is not None
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{ROY_API}/auth/login",
            json={
                "email": app_settings.SRC_ROY_LOGIN.get_secret_value(),
                "password": app_settings.SRC_ROY_PASSWORD.get_secret_value(),
                "device_name": "Custom device",
            },
        )
        res.raise_for_status()
        res_json = res.json()
        logger.info("roy authorized")
        return auth({"Authorization": f"Bearer {res_json['token']}"})


async def load_faq_from_roy(organization_id: int, sections_filter: set[int] | None) -> list[QARecord]:
    au = await make_auth()
    sel = operator.itemgetter("data")

    sections: list[IdRow] = await ignore_error([], http_get_list(IdRow, f"{ROY_API}/kbase/sections?organization_id={organization_id}", au, sel))
    logger.info(f"roy ALL sections count = {len(sections)}")
    sections = [s for s in sections if sections_filter is None or s.id in sections_filter]
    logger.info(f"roy FILTERED sections count = {len(sections)}")

    short_sect_materials_c = [http_get_list(RoyPage, f"{ROY_API}/kbase/materials?organization_id={organization_id}&section={s.id}", au, sel) for s in sections]
    short_sect_materials: list[RoyPage] = flatten(await run_chunked([ignore_error([], coro) for coro in short_sect_materials_c], size=15))
    logger.info(f"roy short materials count = {len(short_sect_materials)}")

    full_material_coros = [http_get_one(RoyPage, f"{ROY_API}/kbase/materials/{m.id}", au, sel) for m in short_sect_materials]
    full_materials: list[RoyPage | None] = await run_chunked([ignore_error(None, coro) for coro in full_material_coros], size=15)
    logger.info(f"roy full materials count = {len(full_materials)}")

    return [m.to_page_doc() for m in full_materials if m is not None]
