"""Action and intent models for NLP processing."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Types of actions the assistant can perform."""

    CREATE_REMINDER = "create_reminder"
    UPDATE_REMINDER = "update_reminder"
    DELETE_REMINDER = "delete_reminder"
    LIST_REMINDERS = "list_reminders"

    CREATE_TASK = "create_task"
    UPDATE_TASK = "update_task"
    DELETE_TASK = "delete_task"
    COMPLETE_TASK = "complete_task"
    LIST_TASKS = "list_tasks"

    SCHEDULE_MEETING = "schedule_meeting"
    UPDATE_MEETING = "update_meeting"
    CANCEL_MEETING = "cancel_meeting"
    LIST_MEETINGS = "list_meetings"

    SHOW_SUMMARY = "show_summary"
    HELP = "help"
    UNKNOWN = "unknown"


class ActionStatus(str, Enum):
    """Status of an action execution."""

    PENDING = "pending"
    NEEDS_CLARIFICATION = "needs_clarification"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ClarificationType(str, Enum):
    """Types of clarification needed."""

    CONFIRM_ACTION = "confirm_action"
    MISSING_PARAMETER = "missing_parameter"
    AMBIGUOUS_INPUT = "ambiguous_input"
    INVALID_VALUE = "invalid_value"


class ClarificationRequest(BaseModel):
    """Request for clarification from user."""

    type: ClarificationType
    message: str
    parameter: Optional[str] = None  # Which parameter needs clarification
    options: List[str] = Field(default_factory=list)  # Suggested options
    original_action: Optional["ParsedAction"] = None

    class Config:
        arbitrary_types_allowed = True


class ActionIntent(BaseModel):
    """Represents the detected intent from user input."""

    action_type: ActionType
    confidence: float = Field(ge=0.0, le=1.0)
    original_input: str
    embedding: Optional[List[float]] = None


class ParsedAction(BaseModel):
    """Fully parsed action ready for execution."""

    id: UUID = Field(default_factory=uuid4)
    intent: ActionIntent
    parameters: Dict[str, Any] = Field(default_factory=dict)
    user_id: int  # Telegram user ID
    chat_id: int
    message_id: Optional[int] = None
    status: ActionStatus = ActionStatus.PENDING
    result_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def action_type(self) -> ActionType:
        """Shortcut to get action type."""
        return self.intent.action_type

    @property
    def confidence(self) -> float:
        """Shortcut to get confidence."""
        return self.intent.confidence

    @property
    def original_input(self) -> str:
        """Shortcut to get original input."""
        return self.intent.original_input


# Update forward reference
ClarificationRequest.model_rebuild()
