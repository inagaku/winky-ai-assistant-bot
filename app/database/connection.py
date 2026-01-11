"""Database connection and management."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
from asyncpg import Pool, Connection

logger = logging.getLogger(__name__)

# Global database instance
_database: Optional["Database"] = None


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
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_connections = min_connections
        self.max_connections = max_connections
        self._pool: Optional[Pool] = None

    async def connect(self) -> None:
        """Create connection pool."""
        if self._pool is not None:
            return

        logger.info(f"Connecting to database {self.database} at {self.host}:{self.port}")
        self._pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            min_size=self.min_connections,
            max_size=self.max_connections,
        )
        logger.info("Database connection pool created")

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
        """Execute a query."""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list:
        """Fetch multiple rows."""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Fetch a single row."""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        """Fetch a single value."""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def initialize_schema(self) -> None:
        """Initialize database schema."""
        schema_sql = """
        -- Users table
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            timezone VARCHAR(50) DEFAULT 'UTC',
            language VARCHAR(10) DEFAULT 'en',
            notification_enabled BOOLEAN DEFAULT TRUE,
            daily_summary_time VARCHAR(5),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Reminders table
        CREATE TABLE IF NOT EXISTS reminders (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            remind_at TIMESTAMP WITH TIME ZONE NOT NULL,
            repeat_rule VARCHAR(255),
            status VARCHAR(20) DEFAULT 'pending',
            snooze_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Tasks table
        CREATE TABLE IF NOT EXISTS tasks (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            due_date TIMESTAMP WITH TIME ZONE,
            priority VARCHAR(20) DEFAULT 'medium',
            status VARCHAR(20) DEFAULT 'pending',
            tags TEXT[] DEFAULT '{}',
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Meetings table
        CREATE TABLE IF NOT EXISTS meetings (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            participants TEXT[] DEFAULT '{}',
            start_time TIMESTAMP WITH TIME ZONE NOT NULL,
            end_time TIMESTAMP WITH TIME ZONE NOT NULL,
            location VARCHAR(500),
            meeting_link VARCHAR(500),
            status VARCHAR(20) DEFAULT 'scheduled',
            reminder_minutes_before INTEGER DEFAULT 15,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
        CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
        CREATE INDEX IF NOT EXISTS idx_reminders_remind_at ON reminders(remind_at) WHERE status = 'pending';
        CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date) WHERE status IN ('pending', 'in_progress');
        CREATE INDEX IF NOT EXISTS idx_meetings_user_id ON meetings(user_id);
        CREATE INDEX IF NOT EXISTS idx_meetings_start_time ON meetings(start_time) WHERE status = 'scheduled';
        """
        await self.execute(schema_sql)
        logger.info("Database schema initialized")


def get_database() -> Database:
    """Get the global database instance."""
    global _database
    if _database is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _database


def init_database(
    host: str = "localhost",
    port: int = 5432,
    database: str = "winky_bot",
    user: str = "postgres",
    password: str = "",
) -> Database:
    """Initialize the global database instance."""
    global _database
    _database = Database(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
    )
    return _database
