import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.crawler import run as run_crawler, _run_full_cycle
from src.db import SessionLocal, engine
from src.logger import logger
from src.models import Base, Product, Type, SubType
from src.rest.fetcher import CatalogFetcher


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


@app.get("/products")
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "type_id": p.type_id,
            "subtype_id": p.subtype_id,
            "count": p.count,
            "exist": p.exist,
            "image": p.image,
            "link": p.link,
            "ccals": p.ccals,
            "prots": p.prots,
            "fats": p.fats,
            "carbs": p.carbs,
            "rate": p.rate,
            "weight": p.weight,
            "last_updated": p.last_updated,
        }
        for p in products
    ]


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
    items = [{"id": r.id, "name": r.name, "product_count": r.product_count} for r in rows]
    return {"total": sum(r.product_count for r in rows), "items": items}


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
