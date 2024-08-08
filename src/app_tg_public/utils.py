import asyncio
import hashlib
import inspect
import json
from typing import Coroutine
from typing import NamedTuple, Generic, TypeVar

from src.const import CACHE_DIR

TR = TypeVar('TR')


async def run_list(tasks: list[Coroutine[None, None, TR]], size: int) -> list[TR]:
    results = []
    for i in range(0, len(tasks), size):
        chunk = tasks[i * size:(i + 1) * size]
        res = await asyncio.gather(*chunk)
        for r in res:
            results.append(r)
    return results


def flatten(matrix):
    flat_list = []
    for row in matrix:
        flat_list += row
    return flat_list


T = TypeVar('T', bound=NamedTuple)


class Cache(Generic[T]):

    def __init__(self, struct: type[T]) -> None:
        self.struct = struct
        self.version = f'{struct.__name__}{hashlib.sha256(str(inspect.getsource(struct)).encode()).hexdigest()}'

    def get(self, **params: str) -> T | None:
        cache_file = CACHE_DIR / self.version / f'{self.struct.__name__}__{"__".join(f"{k}_{params[k]}" for k in sorted(params.keys()))}'
        if cache_file.exists():
            content = json.loads(cache_file.read_bytes())
            return self.struct(**content)
        return None

    def set(self, value: T, **params: str) -> None:
        cache_file = CACHE_DIR / self.version / f'{self.struct.__name__}__{"__".join(f"{k}_{params[k]}" for k in sorted(params.keys()))}'
        cache_file.parent.mkdir(exist_ok=True, parents=True)
        cache_file.write_text(json.dumps(value._asdict()))
