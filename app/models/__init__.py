"""Domain models for the AI Assistant Bot."""

from .user import User, UserPreferences
from .reminder import (
    Reminder,
    ReminderStatus,
    ReminderFlow,
    ReminderCallback,
    # Legacy aliases
    ReminderEditAction,
    ReminderNotifyAction,
    ReminderDeleteAction,
    ReminderListAction,
)
from .task import Task, TaskStatus, TaskPriority
from .meeting import Meeting, MeetingStatus
from .action import (
    ActionIntent,
    ActionType,
    ActionStatus,
    CallbackPrefix,
    ClarificationOption,
    ClarificationRequest,
    ClarificationType,
    ParsedAction,
)

__all__ = [
    "User",
    "UserPreferences",
    "Reminder",
    "ReminderStatus",
    "ReminderFlow",
    "ReminderCallback",
    "ReminderEditAction",
    "ReminderNotifyAction",
    "ReminderDeleteAction",
    "ReminderListAction",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "Meeting",
    "MeetingStatus",
    "ActionIntent",
    "ActionType",
    "ActionStatus",
    "CallbackPrefix",
    "ClarificationOption",
    "ClarificationRequest",
    "ClarificationType",
    "ParsedAction",
]
