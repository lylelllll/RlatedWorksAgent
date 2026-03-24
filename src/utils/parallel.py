"""asyncio 并行工具——在事件循环中运行 CPU 密集型任务。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar
from functools import partial

T = TypeVar("T")

_executor: ThreadPoolExecutor | None = None


def get_executor(max_workers: int = 8) -> ThreadPoolExecutor:
    """获取全局线程池（惰性创建）。"""
    global _executor
    if _executor is None or _executor._shutdown:
        _executor = ThreadPoolExecutor(max_workers=max_workers)
    return _executor


async def run_in_executor(
    func: Callable[..., T], *args: Any, max_workers: int = 8, **kwargs: Any
) -> T:
    """在线程池中运行阻塞函数。"""
    loop = asyncio.get_event_loop()
    executor = get_executor(max_workers)
    return await loop.run_in_executor(executor, partial(func, *args, **kwargs))


async def parallel_map(
    func: Callable[..., T],
    items: list[Any],
    max_workers: int = 8,
) -> list[T]:
    """并行对列表中每个元素执行函数。"""
    loop = asyncio.get_event_loop()
    executor = get_executor(max_workers)
    tasks = [loop.run_in_executor(executor, func, item) for item in items]
    return await asyncio.gather(*tasks)
