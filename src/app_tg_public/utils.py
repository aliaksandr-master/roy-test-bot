import asyncio
from typing import TypeVar, Coroutine

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
