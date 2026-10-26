"""Registry of named background jobs, so a worker or cron can run them by name:

python -m app.core.jobs outbox.dispatch
"""

import asyncio
import sys
from collections.abc import Awaitable, Callable

from app.core.db import get_sessionmaker
from app.core.outbox import dispatch_pending

Job = Callable[[], Awaitable[None]]
_jobs: dict[str, Job] = {}


def job(name: str) -> Callable[[Job], Job]:
    def decorator(fn: Job) -> Job:
        if name in _jobs:
            raise ValueError(f"job {name!r} is already registered")
        _jobs[name] = fn
        return fn

    return decorator


def registered_jobs() -> list[str]:
    return sorted(_jobs)


async def run_job(name: str) -> None:
    try:
        fn = _jobs[name]
    except KeyError:
        raise KeyError(f"unknown job {name!r}; known: {registered_jobs()}") from None
    await fn()


@job("outbox.dispatch")
async def _dispatch_outbox() -> None:
    async with get_sessionmaker()() as session:
        await dispatch_pending(session)


if __name__ == "__main__":
    import app.modules  # noqa: F401  registers module jobs and outbox subscribers

    asyncio.run(run_job(sys.argv[1]))
