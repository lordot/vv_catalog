from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings

# pool_pre_ping: the crawler keeps connections idle for hours; a Postgres
# restart must not surface as "server closed the connection unexpectedly".
engine = create_engine(settings.db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
