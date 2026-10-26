"""The continuous crawler must survive a failed cycle (DB connection dropped,
parser error, ...) instead of dying silently — that is how the catalog went
stale from 2026-05-29 to 2026-10-26 without a line in the logs."""
import asyncio

import pytest

from src import crawler


class _Fetcher:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_a_failed_cycle_is_logged_and_the_loop_goes_on(monkeypatch):
    calls = []

    async def cycle(fetcher, pause_between_sections):
        calls.append(pause_between_sections)
        if len(calls) == 1:
            raise RuntimeError("server closed the connection unexpectedly")
        if len(calls) == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(crawler, "CatalogFetcher", _Fetcher)
    monkeypatch.setattr(crawler, "_db_is_empty", lambda: False)
    monkeypatch.setattr(crawler, "_run_full_cycle", cycle)
    monkeypatch.setattr(crawler.settings, "cycle_retry_delay", 0)

    with pytest.raises(asyncio.CancelledError):
        await crawler.run()
    assert len(calls) == 3
    assert calls == [crawler.settings.section_pause] * 3


@pytest.mark.asyncio
async def test_each_section_gets_its_own_db_session(monkeypatch):
    """One session for a six-hour cycle dies with the first dropped connection;
    a fresh one per section recovers by itself."""
    sessions = []

    class _Session:
        def __init__(self):
            self.closed = False
            sessions.append(self)

        def close(self):
            self.closed = True

    async def section(fetcher, db, path, subtype_id, name_filter):
        assert not db.closed
        return 0

    async def family(fetcher, db, path):
        return 0

    async def details(fetcher, db):
        return 0

    monkeypatch.setattr(crawler, "SessionLocal", _Session)
    monkeypatch.setattr(crawler, "_crawl_section", section)
    monkeypatch.setattr(crawler, "_crawl_family_section", family)
    monkeypatch.setattr(crawler, "_crawl_product_details", details)
    await crawler._run_full_cycle(_Fetcher(), pause_between_sections=0)
    assert len(sessions) == len(crawler.PAGES) + len(crawler.FAMILY_PAGES) + 1
    assert all(s.closed for s in sessions)
