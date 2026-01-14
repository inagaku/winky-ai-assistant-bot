"""Task repository for data access."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.database import Database
from app.models import Task, TaskStatus, TaskPriority
from app.utils import utc_now

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class TaskRepository(BaseRepository[Task]):
    """Repository for Task entities."""

    def __init__(self, db: Database):
        super().__init__(db)

    @property
    def table_name(self) -> str:
        return "tasks"

    def _row_to_model(self, row) -> Task:
        """Convert a database row to a Task model."""
        return Task(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            description=row["description"],
            due_date=row["due_date"],
            priority=TaskPriority(row["priority"]),
            status=TaskStatus(row["status"]),
            tags=row["tags"] or [],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _model_to_dict(self, model: Task) -> dict:
        """Convert a Task model to a dictionary."""
        return {
            "id": model.id,
            "user_id": model.user_id,
            "title": model.title,
            "description": model.description,
            "due_date": model.due_date,
            "priority": model.priority.value,
            "status": model.status.value,
            "tags": model.tags,
            "completed_at": model.completed_at,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
        }

    async def create(self, task: Task) -> Task:
        """Create a new task."""
        query = """
            INSERT INTO tasks (id, user_id, title, description, due_date,
                             priority, status, tags, completed_at, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
        """
        data = self._model_to_dict(task)
        row = await self.db.fetchrow(
            query,
            data["id"],
            data["user_id"],
            data["title"],
            data["description"],
            data["due_date"],
            data["priority"],
            data["status"],
            data["tags"],
            data["completed_at"],
            data["created_at"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def update(self, task: Task) -> Task:
        """Update an existing task."""
        task.updated_at = utc_now()
        query = """
            UPDATE tasks
            SET title = $2, description = $3, due_date = $4, priority = $5,
                status = $6, tags = $7, completed_at = $8, updated_at = $9
            WHERE id = $1
            RETURNING *
        """
        data = self._model_to_dict(task)
        row = await self.db.fetchrow(
            query,
            data["id"],
            data["title"],
            data["description"],
            data["due_date"],
            data["priority"],
            data["status"],
            data["tags"],
            data["completed_at"],
            data["updated_at"],
        )
        return self._row_to_model(row)

    async def get_by_user(
        self,
        user_id: UUID,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        limit: int = 50,
    ) -> List[Task]:
        """Get tasks for a user with optional filters."""
        conditions = ["user_id = $1"]
        params = [user_id]
        param_count = 1

        if status:
            param_count += 1
            conditions.append(f"status = ${param_count}")
            params.append(status.value)

        if priority:
            param_count += 1
            conditions.append(f"priority = ${param_count}")
            params.append(priority.value)

        param_count += 1
        params.append(limit)

        query = f"""
            SELECT * FROM tasks
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE priority
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                due_date ASC NULLS LAST,
                created_at DESC
            LIMIT ${param_count}
        """
        rows = await self.db.fetch(query, *params)
        return [self._row_to_model(row) for row in rows]

    async def get_active_tasks(self, user_id: UUID, limit: int = 50) -> List[Task]:
        """Get active (pending or in_progress) tasks for a user."""
        query = """
            SELECT * FROM tasks
            WHERE user_id = $1 AND status IN ('pending', 'in_progress')
            ORDER BY
                CASE priority
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                due_date ASC NULLS LAST
            LIMIT $2
        """
        rows = await self.db.fetch(query, user_id, limit)
        return [self._row_to_model(row) for row in rows]

    async def get_overdue_tasks(self, user_id: UUID) -> List[Task]:
        """Get overdue tasks for a user."""
        query = """
            SELECT * FROM tasks
            WHERE user_id = $1
                AND status IN ('pending', 'in_progress')
                AND due_date < $2
            ORDER BY due_date ASC
        """
        rows = await self.db.fetch(query, user_id, utc_now())
        return [self._row_to_model(row) for row in rows]

    async def complete(self, task_id: UUID) -> Optional[Task]:
        """Mark a task as completed."""
        now = utc_now()
        query = """
            UPDATE tasks
            SET status = 'completed', completed_at = $2, updated_at = $2
            WHERE id = $1
            RETURNING *
        """
        row = await self.db.fetchrow(query, task_id, now)
        if row:
            return self._row_to_model(row)
        return None

    async def cancel(self, task_id: UUID) -> Optional[Task]:
        """Cancel a task."""
        query = """
            UPDATE tasks
            SET status = 'cancelled', updated_at = $2
            WHERE id = $1
            RETURNING *
        """
        row = await self.db.fetchrow(query, task_id, utc_now())
        if row:
            return self._row_to_model(row)
        return None

    async def get_by_tag(self, user_id: UUID, tag: str, limit: int = 50) -> List[Task]:
        """Get tasks with a specific tag."""
        query = """
            SELECT * FROM tasks
            WHERE user_id = $1 AND $2 = ANY(tags)
            ORDER BY created_at DESC
            LIMIT $3
        """
        rows = await self.db.fetch(query, user_id, tag, limit)
        return [self._row_to_model(row) for row in rows]

    async def get_active_count(self, user_id: UUID) -> int:
        """Get count of active tasks for a user."""
        query = """
            SELECT COUNT(*) FROM tasks
            WHERE user_id = $1 AND status IN ('pending', 'in_progress')
        """
        return await self.db.fetchval(query, user_id)
