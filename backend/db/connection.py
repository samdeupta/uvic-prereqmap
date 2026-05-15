from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from db.schema import Base


# ----- Database --------------------
class Database:
    def __init__(self):
        """
        Builds the async engine and session factory from the `DATABASE_URL`environment variable on 
        instantiation.

        Expected format:
            postgresql+asyncpg://`user`:`password`@`host`:`port`/`dbname`
        """

        db_url = os.environ.get("DATABASE_URL")

        if not db_url:
            raise RuntimeError("DATABASE_URL environment variable is not set.")

        self.engine : AsyncEngine = create_async_engine(
            db_url,
            echo           = False,  # Set True for SQL query logging during development
            pool_pre_ping  = True,   # Verify connections before use
        )

        self.async_session = async_sessionmaker(
            self.engine,
            expire_on_commit = False,
        )


    async def init(self):
        """
        Verifies the DB connection on API startup.
        Raises if the database is unreachable.
        """

        async with self.engine.begin() as conn:
            await conn.execute(text("SELECT 1"))  # Test connection and table existence
    

    async def create_tables(self) -> None:
        """
        Creates all tables defined in `Base` if they do not already exist.
        Called once at the start of a scraper run before any data is written.
        """
 
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        FastAPI dependency that yields an async DB session per request.

        Usage:
            ```
            @router.get("/")
            async def route(session: AsyncSession = Depends(db.get_session)):
                ...
            ```
        """

        async with self.async_session() as session:
            yield session


db = Database()