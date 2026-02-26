import asyncio

from src.db import engine, SessionLocal
from src.models import Base
from src.seed import seed_reference_data
from src.crawler import run
from src.logger import logger


def main():
    logger.info("Starting vv_catalog service")

    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    # Seed reference data
    db = SessionLocal()
    try:
        seed_reference_data(db)
    finally:
        db.close()

    # Run crawler
    asyncio.run(run())


if __name__ == "__main__":
    main()
