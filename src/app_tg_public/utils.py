import asyncio
import hashlib
import inspect
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel
from typing_extensions import ParamSpec

from src.const import CACHE_DIR

logger = logging.getLogger(__name__)

TR = TypeVar("TR")


async def run_chunked(tasks: list[Coroutine[Any, Any, TR]], *, size: int) -> list[TR]:
    results = []
    for i in range(0, len(tasks), size):
        chunk = tasks[i * size : (i + 1) * size]
        results += list(await asyncio.gather(*chunk))
    return results


def flatten(matrix: list[list[TR]]) -> list[TR]:
    flat_list = []
    for row in matrix:
        flat_list += row
    return flat_list


T = TypeVar("T", bound=BaseModel)


class Cache(Generic[T]):
    def __init__(self, struct: type[T]) -> None:
        self.struct = struct
        self.version = f"{struct.__name__}{hashlib.sha256(str(inspect.getsource(struct)).encode()).hexdigest()}"

    def get(self, **params: str) -> T | None:
        cache_file = CACHE_DIR / self.version / f'{self.struct.__name__}__{"__".join(f"{k}_{params[k]}" for k in sorted(params.keys()))}'
        if cache_file.exists():
            content = json.loads(cache_file.read_bytes())
            return self.struct(**content)
        return None

    def set(self, value: T, **params: str) -> None:
        cache_file = CACHE_DIR / self.version / f'{self.struct.__name__}__{"__".join(f"{k}_{params[k]}" for k in sorted(params.keys()))}'
        cache_file.parent.mkdir(exist_ok=True, parents=True)
        cache_file.write_text(value.model_dump_json())


def auth(headers: dict[str, str]) -> Callable[[httpx.Request], httpx.Request]:
    def headers_fn(request: httpx.Request) -> httpx.Request:
        for k, v in headers.items():
            request.headers[k] = v
        return request

    return headers_fn


TP = ParamSpec("TP")


async def ignore_error(default: TR, coro: Coroutine[Any, Any, TR]) -> TR:
    try:
        return await coro
    except Exception as e:
        logger.error(f"ERROR {type(e).__name__}: {e}", exc_info=e)
        return default


async def http_get_list(
    model: type[T], url: str, au: Callable[[httpx.Request], httpx.Request], sel: Callable[[dict[str, Any]], list[dict[str, Any]]]
) -> list[T]:
    async with httpx.AsyncClient(auth=au) as client:
        response = await client.get(url)
        response.raise_for_status()
        return [model(**r) for r in sel(response.json())]


async def http_get_one(model: type[T], url: str, au: Callable[[httpx.Request], httpx.Request], sel: Callable[[dict[str, Any]], dict[str, Any]]) -> T | None:
    async with httpx.AsyncClient(auth=au) as client:
        response = await client.get(url)
        response.raise_for_status()
        return model(**sel(response.json()))


class IdRow(BaseModel, extra="ignore"):
    id: int
