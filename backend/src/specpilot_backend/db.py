from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

from specpilot_backend.config import Settings, get_settings


def create_sqlite_engine(settings: Settings | None = None) -> Engine:
    resolved = settings or get_settings()
    return create_engine(resolved.database_url, connect_args={"check_same_thread": False})


engine = create_sqlite_engine()


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
