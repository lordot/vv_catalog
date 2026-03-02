import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.config import settings, PAGES, FAMILY_PAGES
from src.db import SessionLocal
from src.logger import logger
from src.models import Product, Type, SubType
from src.rest.fetcher import CatalogFetcher
from src.rest.parser import ProductParser


def _db_is_empty() -> bool:
    """Check if the products table has any rows."""
    db = SessionLocal()
    try:
        count = db.query(Product).count()
        return count == 0
    finally:
        db.close()


def _upsert_products(db: Session, products: list[dict]) -> int:
    """Upsert products into PostgreSQL. Returns number of upserted rows."""
    if not products:
        return 0

    now = datetime.now(timezone.utc)
    for p in products:
        p["last_updated"] = now

    stmt = pg_insert(Product).values(products)
    # On conflict: only update fields present in data, preserve others (type_id, nutrition, etc.)
    present_keys = {k for p in products for k in p} - {"id"}
    update_cols = {k: stmt.excluded[k] for k in present_keys}
    stmt = stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)
    db.execute(stmt)
    db.commit()
    return len(products)


async def _crawl_section(
    fetcher: CatalogFetcher,
    db: Session,
    path: str,
    subtype_id: int,
    name_filter: str | None,
) -> int:
    """Crawl one catalog section (paginated). Returns total products found."""
    parser = ProductParser()
    total = 0

    for page_num in range(1, 100):
        url = settings.base_url + path + f"?PAGEN_1={page_num}"
        content = await fetcher.fetch_page(url)
        await asyncio.sleep(settings.request_delay)

        products = parser.parse_catalog_page(content, subtype_id, name_filter)
        if not products:
            break

        rows = [p.model_dump(exclude_none=True) for p in products]
        _upsert_products(db, rows)
        total += len(products)
        logger.info(f"Section {path} page {page_num}: {len(products)} products")

    return total


async def _crawl_family_section(
    fetcher: CatalogFetcher,
    db: Session,
    path: str,
) -> int:
    """Crawl family-format section. Only updates count=2 for existing products."""
    parser = ProductParser()
    total = 0

    for page_num in range(1, 100):
        url = settings.base_url + path + f"?PAGEN_1={page_num}"
        content = await fetcher.fetch_page(url)
        await asyncio.sleep(settings.request_delay)

        products = parser.parse_family_page(content)
        if not products:
            break

        # Only update existing products (set count=2)
        for p in products:
            existing = db.query(Product).filter_by(id=p.id).first()
            if existing:
                existing.count = 2
        db.commit()
        total += len(products)

    return total


async def _crawl_product_details(
    fetcher: CatalogFetcher,
    db: Session,
) -> int:
    """Fetch details for all products that have a link. Sequential, one at a time."""
    products = db.query(Product).filter(Product.link.isnot(None)).all()
    updated = 0

    for product in products:
        content = await fetcher.fetch_page_bytes(settings.base_url + product.link)
        await asyncio.sleep(settings.request_delay)

        if not content:
            continue

        details = ProductParser.parse_product_details(content, product.subtype_id)
        for key, value in details.items():
            setattr(product, key, value)
        updated += 1

        if updated % 50 == 0:
            db.commit()
            logger.info(f"Product details: {updated}/{len(products)}")

    db.commit()
    logger.info(f"Product details complete: {updated}/{len(products)}")
    return updated


async def _run_full_cycle(fetcher: CatalogFetcher, pause_between_sections: float):
    """Run one full cycle through all catalog sections + product details."""
    db = SessionLocal()
    try:
        total = 0

        for path, subtype_id, name_filter in PAGES:
            count = await _crawl_section(fetcher, db, path, subtype_id, name_filter)
            total += count
            logger.info(f"Section {path}: {count} products")
            if pause_between_sections > 0:
                await asyncio.sleep(pause_between_sections)

        for path in FAMILY_PAGES:
            count = await _crawl_family_section(fetcher, db, path)
            logger.info(f"Family section {path}: {count} products")
            if pause_between_sections > 0:
                await asyncio.sleep(pause_between_sections)

        await _crawl_product_details(fetcher, db)
        logger.info(f"Full cycle complete: {total} catalog products")
    finally:
        db.close()


async def run():
    """Main entry point: INIT if empty, then CONTINUOUS forever."""
    async with CatalogFetcher() as fetcher:
        if _db_is_empty():
            logger.info("DB is empty — running INIT mode (no inter-section pauses)")
            await _run_full_cycle(fetcher, pause_between_sections=0)
            logger.info("INIT complete")

        logger.info("Entering CONTINUOUS mode")
        while True:
            await _run_full_cycle(fetcher, pause_between_sections=settings.section_pause)
            logger.info("CONTINUOUS cycle done, restarting...")
