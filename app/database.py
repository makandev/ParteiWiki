"""SQLAlchemy-Engine, Session-Factory und Declarative Base."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Basisklasse aller ORM-Modelle."""


def get_db() -> Iterator[Session]:
    """FastAPI-Dependency: liefert eine Session pro Request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
