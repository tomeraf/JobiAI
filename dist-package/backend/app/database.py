from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event

from app.config import settings


class Base(DeclarativeBase):
    pass


def _create_engine():
    """Create database engine with appropriate settings for SQLite or PostgreSQL."""
    if settings.is_sqlite:
        # SQLite-specific configuration
        engine = create_async_engine(
            settings.database_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )

        # Enable foreign keys for SQLite (must be done on each connection)
        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
            cursor.close()

        return engine
    else:
        # PostgreSQL configuration
        return create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
        )


engine = _create_engine()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_session():
    """
    Async context manager for getting database session.
    Use this for startup/background tasks (not FastAPI endpoints).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
