"""Base repository with common CRUD operations."""

import logging
from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.database import Database

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseRepository(ABC, Generic[T]):
    """Abstract base repository for common CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Get the table name for this repository."""
        pass

    @abstractmethod
    def _row_to_model(self, row) -> T:
        """Convert a database row to a model instance."""
        pass

    @abstractmethod
    def _model_to_dict(self, model: T) -> dict:
        """Convert a model instance to a dictionary for database operations."""
        pass

    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get an entity by ID."""
        query = f"SELECT * FROM {self.table_name} WHERE id = $1"
        row = await self.db.fetchrow(query, id)
        if row:
            return self._row_to_model(row)
        return None

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all entities with pagination."""
        query = f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT $1 OFFSET $2"
        rows = await self.db.fetch(query, limit, offset)
        return [self._row_to_model(row) for row in rows]

    async def delete(self, id: UUID) -> bool:
        """Delete an entity by ID."""
        query = f"DELETE FROM {self.table_name} WHERE id = $1"
        result = await self.db.execute(query, id)
        return result == "DELETE 1"

    async def exists(self, id: UUID) -> bool:
        """Check if an entity exists."""
        query = f"SELECT EXISTS(SELECT 1 FROM {self.table_name} WHERE id = $1)"
        return await self.db.fetchval(query, id)

    async def count(self) -> int:
        """Count all entities."""
        query = f"SELECT COUNT(*) FROM {self.table_name}"
        return await self.db.fetchval(query)
