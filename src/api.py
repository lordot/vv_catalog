import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from datetime import datetime, timezone

from src.config import settings, PAGES
from src.crawler import run as run_crawler, _run_full_cycle, _crawl_section, _crawl_product_details
from src.db import SessionLocal, engine
from src.logger import logger
from src.models import Base, Product, Type, SubType
from src.rest.fetcher import CatalogFetcher
from src.rest.parser import ProductParser

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    from src.seed import seed_reference_data
    db = SessionLocal()
    try:
        seed_reference_data(db)
    finally:
        db.close()

    app.state.crawler_task = asyncio.create_task(run_crawler())
    app.state.scan_running = False
    logger.info("Catalog API started, crawler running in background")
    yield
    app.state.crawler_task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/products")
def get_products(db: Session = Depends(get_db)):
    products = (
        db.query(Product)
        .options(selectinload(Product.type), selectinload(Product.subtype))
        .all()
    )
    return [_product_to_dict(p) for p in products]


@app.get("/types")
def get_types(db: Session = Depends(get_db)):
    rows = (
        db.query(Type.id, Type.name, func.count(Product.id).label("product_count"))
        .outerjoin(Product, Product.type_id == Type.id)
        .group_by(Type.id)
        .all()
    )
    items = [{"id": r.id, "name": r.name, "product_count": r.product_count} for r in rows]
    return {"total": sum(r.product_count for r in rows), "items": items}


@app.get("/subtypes")
def get_subtypes(db: Session = Depends(get_db)):
    rows = (
        db.query(SubType.id, SubType.name, func.count(Product.id).label("product_count"))
        .outerjoin(Product, Product.subtype_id == SubType.id)
        .group_by(SubType.id)
        .all()
    )
    subtype_urls = {sid: path for path, sid, _ in PAGES}
    items = [
        {
            "id": r.id,
            "name": r.name,
            "product_count": r.product_count,
            "url": settings.base_url + subtype_urls[r.id] if r.id in subtype_urls else None,
        }
        for r in rows
    ]
    return {"total": sum(r.product_count for r in rows), "items": items}


def _product_to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "type_id": p.type_id,
        "type_name": p.type.name if p.type else None,
        "subtype_id": p.subtype_id,
        "subtype_name": p.subtype.name if p.subtype else None,
        "count": p.count,
        "image": p.image,
        "link": p.link,
        "ccals": p.ccals,
        "prots": p.prots,
        "fats": p.fats,
        "carbs": p.carbs,
        "rate": p.rate,
        "weight": p.weight,
        "last_updated": p.last_updated.replace(tzinfo=timezone.utc).isoformat() if p.last_updated else None,
    }


@app.post("/products/{product_id}/rescan")
async def rescan_product(product_id: int, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .options(selectinload(Product.type), selectinload(Product.subtype))
        .filter_by(id=product_id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.link:
        raise HTTPException(status_code=400, detail="Product has no link to rescan")

    async with CatalogFetcher() as fetcher:
        content = await fetcher.fetch_page_bytes(settings.base_url + product.link)

    if not content:
        raise HTTPException(status_code=502, detail="Failed to fetch product page")

    details = ProductParser.parse_product_details(content, product.subtype_id)
    for key, value in details.items():
        setattr(product, key, value)
    product.last_updated = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)

    logger.info(f"Rescanned product {product_id}: {product.name}")
    return _product_to_dict(product)


@app.post("/subtypes/{subtype_id}/scan")
async def scan_subtype(subtype_id: int):
    sections = [(p, sid, nf) for p, sid, nf in PAGES if sid == subtype_id]
    if not sections:
        raise HTTPException(status_code=404, detail="No section configured for this subtype")

    asyncio.create_task(_scan_subtype_bg(subtype_id, sections))
    return {"status": "started"}


async def _scan_subtype_bg(subtype_id: int, sections: list):
    db = SessionLocal()
    try:
        async with CatalogFetcher() as fetcher:
            total = 0
            for path, sid, name_filter in sections:
                count = await _crawl_section(fetcher, db, path, sid, name_filter)
                total += count
            products = db.query(Product).filter(
                Product.subtype_id == subtype_id,
                Product.link.isnot(None),
            ).all()
            for product in products:
                content = await fetcher.fetch_page_bytes(settings.base_url + product.link)
                if content:
                    details = ProductParser.parse_product_details(content, product.subtype_id)
                    for key, value in details.items():
                        setattr(product, key, value)
                    product.last_updated = datetime.now(timezone.utc)
                await asyncio.sleep(settings.request_delay)
            db.commit()
        logger.info(f"Section scan complete for subtype {subtype_id}: {total} catalog + {len(products)} details")
    except Exception:
        logger.exception(f"Section scan failed for subtype {subtype_id}")
    finally:
        db.close()


async def _forced_scan():
    """Run a full crawl cycle without pauses, then restart continuous crawler."""
    try:
        async with CatalogFetcher() as fetcher:
            await _run_full_cycle(fetcher, pause_between_sections=0)
        logger.info("Forced scan complete")
    finally:
        app.state.scan_running = False
        app.state.crawler_task = asyncio.create_task(run_crawler())
        logger.info("Continuous crawler restarted")


@app.post("/scan")
async def force_scan():
    if app.state.scan_running:
        return {"status": "already_running"}
    app.state.scan_running = True
    app.state.crawler_task.cancel()
    asyncio.create_task(_forced_scan())
    return {"status": "started"}
