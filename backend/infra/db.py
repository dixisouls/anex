"""
Database (async).

The async SQLAlchemy engine and session factory for Postgres, built from
DATABASE_URL. Two ways to get a session:

- session_scope(): an async context manager for scripts and background work (the
  seeder, the broker, the ledger). Commits on success, rolls back on error.
      async with session_scope() as session:
          await repo.upsert_agent(session, agent)
          
- get_session(): a FastAPI dependency for B4. Yields a session per request.

Postgres is the system of record. Redis is downstream of it.
"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import DATABASE_URL

_engine = None
_sessionmaker = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_sessionmaker():
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _sessionmaker


@asynccontextmanager
async def session_scope():
    session = get_sessionmaker()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session():
    """FastAPI dependency (B4). Use with Depends(get_session)."""
    async with get_sessionmaker()() as session:
        yield session