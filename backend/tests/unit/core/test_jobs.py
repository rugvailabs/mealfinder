import pytest

from app.core import jobs


async def test_registered_job_runs_by_name() -> None:
    calls: list[str] = []

    @jobs.job("test.ping")
    async def ping() -> None:
        calls.append("ping")

    try:
        assert "outbox.dispatch" in jobs.registered_jobs()
        await jobs.run_job("test.ping")
        assert calls == ["ping"]
        with pytest.raises(ValueError, match="already registered"):
            jobs.job("test.ping")(ping)
    finally:
        jobs._jobs.pop("test.ping")


async def test_unknown_job_names_the_known_ones() -> None:
    with pytest.raises(KeyError, match=r"outbox.dispatch"):
        await jobs.run_job("nope")
