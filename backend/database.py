import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/api_pulse",
)


def _connect_args() -> dict:
    """Supabase (and most cloud Postgres) require SSL.
    
    Supabase uses PgBouncer in transaction pooling mode which does not support
    prepared statements. Setting statement_cache_size=0 disables them.
    """
    args: dict = {}
    ssl = os.getenv("DATABASE_SSL", "").strip()
    if ssl:
        args["ssl"] = ssl
    elif "supabase.co" in DATABASE_URL:
        args["ssl"] = "require"

    # PgBouncer (used by Supabase pooler) does not support prepared statements.
    # Disable the asyncpg statement cache to prevent DuplicatePreparedStatementError.
    if "supabase.co" in DATABASE_URL or "pooler" in DATABASE_URL:
        args["statement_cache_size"] = 0

    return args


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_connect_args(),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
