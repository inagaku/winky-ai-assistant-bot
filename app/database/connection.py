"""Database connection and management."""

import asyncio
import logging
import os
import ssl
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
from asyncpg import Pool, Connection

logger = logging.getLogger(__name__)

# Global database instance
_database: Optional["Database"] = None

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds


def _is_connection_error(e: Exception) -> bool:
    """Check if exception is a transient connection error that can be retried."""
    connection_errors = (
        asyncpg.ConnectionDoesNotExistError,
        asyncpg.InterfaceError,
        ConnectionResetError,
        ConnectionRefusedError,
        OSError,
    )
    return isinstance(e, connection_errors) or "connection" in str(e).lower()


class Database:
    """Database connection manager using asyncpg."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "winky_bot",
        user: str = "postgres",
        password: str = "",
        min_connections: int = 2,
        max_connections: int = 10,
        use_ssl: bool = True,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.use_ssl = use_ssl
        self._pool: Optional[Pool] = None
        self._connecting = False

    async def connect(self) -> None:
        """Create connection pool."""
        if self._pool is not None:
            return

        if self._connecting:
            # Wait for existing connection attempt
            while self._connecting:
                await asyncio.sleep(0.1)
            return

        self._connecting = True
        try:
            logger.info(f"Connecting to database {self.database} at {self.host}:{self.port}")

            # SSL context for Supabase/cloud databases
            ssl_context = None
            if self.use_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.min_connections,
                max_size=self.max_connections,
                ssl=ssl_context if self.use_ssl else False,
                # Connection health settings
                command_timeout=60,
                # Reset stale connections
                max_inactive_connection_lifetime=60.0,
            )
            logger.info("Database connection pool created")
        finally:
            self._connecting = False

    async def reconnect(self) -> None:
        """Force reconnection to database."""
        logger.info("Reconnecting to database...")
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception as e:
                logger.warning(f"Error closing pool during reconnect: {e}")
            self._pool = None
        await self.connect()
        logger.info("Database reconnected")

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed")

    @property
    def pool(self) -> Pool:
        """Get the connection pool."""
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Connection, None]:
        """Acquire a connection from the pool."""
        async with self.pool.acquire() as connection:
            yield connection

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[Connection, None]:
        """Acquire a connection and start a transaction."""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                yield connection

    async def execute(self, query: str, *args) -> str:
        """Execute a query with retry on connection errors."""
        return await self._execute_with_retry("execute", query, *args)

    async def fetch(self, query: str, *args) -> list:
        """Fetch multiple rows with retry on connection errors."""
        return await self._execute_with_retry("fetch", query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row with retry on connection errors."""
        return await self._execute_with_retry("fetchrow", query, *args)

    async def fetchval(self, query: str, *args):
        """Fetch a single value with retry on connection errors."""
        return await self._execute_with_retry("fetchval", query, *args)

    async def _execute_with_retry(self, method: str, query: str, *args):
        """Execute a database operation with retry logic for connection errors."""
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                async with self.acquire() as conn:
                    func = getattr(conn, method)
                    return await func(query, *args)
            except Exception as e:
                last_error = e
                if _is_connection_error(e):
                    logger.warning(
                        f"Database connection error on attempt {attempt + 1}/{MAX_RETRIES}: {e}"
                    )
                    if attempt < MAX_RETRIES - 1:
                        # Try to reconnect before next attempt
                        try:
                            await self.reconnect()
                        except Exception as reconnect_error:
                            logger.error(f"Reconnection failed: {reconnect_error}")
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                else:
                    # Non-connection error, don't retry
                    raise

        # All retries exhausted
        logger.error(f"Database operation failed after {MAX_RETRIES} attempts")
        raise last_error


def get_database() -> Database:
    """Get the global database instance."""
    global _database
    if _database is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _database


def init_database(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    use_ssl: bool = True,
) -> Database:
    """Initialize the global database instance."""
    global _database
    _database = Database(
        host=host,
        port=int(port),
        database=database,
        user=user,
        password=password,
        use_ssl=use_ssl,
    )
    return _database
