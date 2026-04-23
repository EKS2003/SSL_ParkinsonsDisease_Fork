from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from repo.sql_models import Base

engine = create_engine(settings.db_url, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)
