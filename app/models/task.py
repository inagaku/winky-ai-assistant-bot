"""Task domain model."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of a task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Priority level of a task."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Task(BaseModel):
    """Task domain model."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None  # UTC
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    tags: List[str] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_active(self) -> bool:
        """Check if task is still active."""
        return self.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)

    @property
    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if not self.due_date or not self.is_active:
            return False
        return datetime.utcnow() > self.due_date

    def complete(self) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
