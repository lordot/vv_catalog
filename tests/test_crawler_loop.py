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


@pytest.mark.asyncio
async def test_a_section_stops_when_a_page_brings_no_new_products(monkeypatch):
    """vkusvill.ru answers PAGEN_1 beyond the last page with the last page again
    (seen 2026-10-26: 30+ identical pages of 8), so an empty page never comes."""
    from src import schemas

    pages = []

    class _F:
        async def fetch_page(self, url):
            pages.append(url)
            return url

    def parse(content, subtype_id, name_filter):
        n = int(content.rsplit("=", 1)[1])
        ids = [1, 2, 3] if n == 1 else [4, 5]           # page 3, 4, ... repeat page 2
        return [schemas.Product(id=i, name=f"p{i}", subtype_id=subtype_id, count=1) for i in ids]

    class _DB:
        def query(self, *a):
            raise AssertionError("no stale cleanup in this test")

    monkeypatch.setattr(crawler.ProductParser, "parse_catalog_page", staticmethod(parse))
    monkeypatch.setattr(crawler, "_upsert_products", lambda db, rows: len(rows))
    monkeypatch.setattr(crawler.settings, "request_delay", 0)

    async def no_cleanup(*a, **k):
        return 0
    monkeypatch.setattr(crawler, "_remove_stale", no_cleanup)

    total = await crawler._crawl_section(_F(), _DB(), "/x/", 1, None)
    assert total == 5
    assert len(pages) == 3      # page 1, page 2, page 3 (repeat → stop)
