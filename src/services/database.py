"""
Database management using SQLAlchemy async driver.
Handles connection pooling and schema initialization.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import text

from src.models.subtitle import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(
        self,
        database_url: str,
        db_schema: str = "youtube_subtitles",
        pool_size: int = 10,
        pool_min_size: int = 2,
        pool_timeout: int = 30,
        echo: bool = False,
    ):
        """Initialize database manager."""
        self.database_url = database_url
        self.db_schema = db_schema
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None

        # Store config for lazy initialization
        self.pool_size = pool_size
        self.pool_min_size = pool_min_size
        self.pool_timeout = pool_timeout
        self.echo = echo

    async def connect(self):
        """Create database engine and connection pool."""
        try:
            import re

            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", self.db_schema):
                raise ValueError("Invalid DB_SCHEMA name")

            self.engine = create_async_engine(
                self.database_url,
                echo=self.echo,
                connect_args={"server_settings": {"search_path": self.db_schema}},
                pool_size=self.pool_size,
                max_overflow=10,
                pool_timeout=self.pool_timeout,
                pool_recycle=3600,  # Recycle connections after 1 hour
                pool_pre_ping=True,  # Verify connection before using
            )

            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            # Test connection
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection established")

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def disconnect(self):
        """Dispose of database engine."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")

    async def init_schema(self, *, create_tables: bool) -> None:
        """Ensure schema exists and optionally create tables (dev/local)."""
        try:
            async with self.engine.begin() as conn:
                await conn.execute(
                    text(f"CREATE SCHEMA IF NOT EXISTS {self.db_schema}")
                )
                if create_tables:
                    await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            raise

    def get_session(self):
        """Get async database session."""
        if not self.session_factory:
            raise RuntimeError("Database not connected")
        return self.session_factory()

    async def execute_query(self, query: str):
        """Execute raw SQL query."""
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(text(query))
                return result.fetchall()
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
