"""Task service for task management."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models import Task, TaskStatus, TaskPriority
from app.repositories import TaskRepository

from .base_service import BaseService

logger = logging.getLogger(__name__)


class TaskService(BaseService):
    """Service for task management operations."""

    def __init__(self, task_repository: TaskRepository):
        super().__init__()
        self.task_repository = task_repository

    async def create_task(
        self,
        user_id: UUID,
        title: str,
        description: Optional[str] = None,
        due_date: Optional[datetime] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        tags: Optional[List[str]] = None,
    ) -> Task:
        """Create a new task."""
        task = Task(
            user_id=user_id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            tags=tags or [],
        )
        created = await self.task_repository.create(task)
        self.logger.info(f"Created task {created.id} for user {user_id}")
        return created

    async def create_from_params(
        self,
        user_id: UUID,
        params: Dict[str, Any],
    ) -> Task:
        """Create a task from extracted parameters."""
        title = params.get("task_name") or params.get("task") or params.get("title", "Task")
        due_date_str = params.get("datetime") or params.get("due_date") or params.get("when")

        # Parse due date
        due_date = None
        if due_date_str:
            due_date = self._parse_datetime(due_date_str)

        # Parse priority
        priority_str = params.get("priority", "medium").lower()
        priority_map = {
            "low": TaskPriority.LOW,
            "medium": TaskPriority.MEDIUM,
            "high": TaskPriority.HIGH,
            "urgent": TaskPriority.URGENT,
        }
        priority = priority_map.get(priority_str, TaskPriority.MEDIUM)

        # Parse tags
        tags = params.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        return await self.create_task(
            user_id=user_id,
            title=title,
            description=params.get("description"),
            due_date=due_date,
            priority=priority,
            tags=tags,
        )

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string. Simple implementation."""
        now = datetime.utcnow()

        if isinstance(dt_str, datetime):
            return dt_str

        dt_lower = dt_str.lower()
        if "tomorrow" in dt_lower:
            base = now + timedelta(days=1)
        elif "today" in dt_lower:
            base = now
        elif "next week" in dt_lower:
            base = now + timedelta(weeks=1)
        else:
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                return now + timedelta(days=1)

        return base.replace(hour=18, minute=0, second=0, microsecond=0)

    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """Get a task by ID."""
        return await self.task_repository.get_by_id(task_id)

    async def get_user_tasks(
        self,
        user_id: UUID,
        active_only: bool = True,
        priority: Optional[TaskPriority] = None,
        limit: int = 50,
    ) -> List[Task]:
        """Get tasks for a user."""
        if active_only:
            return await self.task_repository.get_active_tasks(user_id, limit=limit)
        return await self.task_repository.get_by_user(
            user_id, priority=priority, limit=limit
        )

    async def get_overdue_tasks(self, user_id: UUID) -> List[Task]:
        """Get overdue tasks for a user."""
        return await self.task_repository.get_overdue_tasks(user_id)

    async def complete_task(self, task_id: UUID) -> Optional[Task]:
        """Mark a task as completed."""
        task = await self.task_repository.complete(task_id)
        if task:
            self.logger.info(f"Task {task_id} completed")
        return task

    async def cancel_task(self, task_id: UUID) -> Optional[Task]:
        """Cancel a task."""
        return await self.task_repository.cancel(task_id)

    async def delete_task(self, task_id: UUID) -> bool:
        """Delete a task permanently."""
        return await self.task_repository.delete(task_id)

    async def update_task(
        self,
        task_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[datetime] = None,
        priority: Optional[TaskPriority] = None,
        status: Optional[TaskStatus] = None,
    ) -> Optional[Task]:
        """Update a task's fields."""
        task = await self.task_repository.get_by_id(task_id)
        if not task:
            return None

        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if due_date is not None:
            task.due_date = due_date
        if priority is not None:
            task.priority = priority
        if status is not None:
            task.status = status
            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.utcnow()

        return await self.task_repository.update(task)

    async def get_active_count(self, user_id: UUID) -> int:
        """Get count of active tasks for a user."""
        return await self.task_repository.get_active_count(user_id)

    async def get_tasks_by_tag(
        self,
        user_id: UUID,
        tag: str,
        limit: int = 50,
    ) -> List[Task]:
        """Get tasks with a specific tag."""
        return await self.task_repository.get_by_tag(user_id, tag, limit)

    def format_task_list(self, tasks: List[Task]) -> str:
        """Format a list of tasks for display."""
        if not tasks:
            return "You have no active tasks."

        lines = ["Your tasks:"]
        priority_emoji = {
            TaskPriority.LOW: "🟢",
            TaskPriority.MEDIUM: "🟡",
            TaskPriority.HIGH: "🟠",
            TaskPriority.URGENT: "🔴",
        }

        for i, task in enumerate(tasks, 1):
            emoji = priority_emoji.get(task.priority, "⚪")
            due_str = ""
            if task.due_date:
                due_str = f" (due: {task.due_date.strftime('%Y-%m-%d')})"
            overdue = " ⚠️ OVERDUE" if task.is_overdue else ""
            lines.append(f"{i}. {emoji} {task.title}{due_str}{overdue}")

        return "\n".join(lines)
