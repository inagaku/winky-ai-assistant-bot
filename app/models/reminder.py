"""Reminder domain model."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ReminderStatus(str, Enum):
    """Status of a reminder."""

    PENDING = "pending"
    SENT = "sent"
    SNOOZED = "snoozed"
    CANCELLED = "cancelled"


# --- Callback flows and actions (hierarchical structure) ---


class ReminderFlow:
    """Reminder callback flows with nested actions.

    Callback format: reminder:{flow}:{action}:{id}

    Each flow is a namespace containing its valid actions.
    This provides compile-time safety and logical grouping.
    """

    ENTITY = "reminder"

    class Edit:
        """Edit flow - ConversationHandler for editing reminders.

        State flow:
            SELECT → [Edit][OK] (Delete links to Delete flow)
                   → MENU → [Change Time][Edit Title][Save]
                          → AWAITING_TIME/TITLE → MENU
                          → SAVE → SELECT
                   → OK → END
        """
        FLOW = "edit"

        class Action(str, Enum):
            SELECT = "select"          # Show [Edit][OK][Delete*]
            MENU = "menu"              # Show [Change Time][Edit Title][Save]
            OK = "ok"                  # Confirm and finish
            EDIT_TIME = "edit_time"  # Prompt for time input
            EDIT_TITLE = "edit_title"    # Prompt for title input
            SAVE = "save"              # Save, back to SELECT

        @classmethod
        def callback(cls, action: "ReminderFlow.Edit.Action", reminder_id: str) -> str:
            """Build edit flow callback: reminder:edit:{action}:{id}"""
            return f"{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:{reminder_id}"

        @classmethod
        def pattern(cls, action: "ReminderFlow.Edit.Action" = None) -> str:
            """Get regex pattern for matching edit callbacks."""
            if action:
                return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:.+$"
            return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:.+$"

    class EditTime:
        """EditTime flow - ConversationHandler for editing reminder's time.
        """
        FLOW = "edit_time"

        class Action(str, Enum):
            MINUS_30M = "minus30m"
            PLUS_30M = "plus30m"
            MINUS_1H = "minus1h"
            PLUS_1H = "plus1h"
            CUSTOM = "custom"

        @classmethod
        def callback(cls, action: "ReminderFlow.EditTime.Action", reminder_id: str) -> str:
            """Build edit flow callback: reminder:edit:{action}:{id}"""
            return f"{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:{reminder_id}"

        @classmethod
        def pattern(cls, action: "ReminderFlow.EditTime.Action" = None) -> str:
            """Get regex pattern for matching edit callbacks."""
            if action:
                return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:.+$"
            return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:.+$"

    class Notify:
        """Notify flow - callback-only actions from notifications."""
        FLOW = "notify"

        class Action(str, Enum):
            SNOOZE = "snooze"  # Snooze reminder
            DONE = "done"      # Mark as done/complete
            CHANGE_TIME = "change_time"      # Arbitrary remind_at time set

        @classmethod
        def callback(cls, action: "ReminderFlow.Notify.Action", reminder_id: str) -> str:
            """Build notify flow callback: reminder:notify:{action}:{id}"""
            return f"{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:{reminder_id}"

        @classmethod
        def pattern(cls, action: "ReminderFlow.Notify.Action" = None) -> str:
            """Get regex pattern for matching notify callbacks."""
            if action:
                return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:.+$"
            return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:.+$"

    class Delete:
        """Delete flow - immediate deletion action."""
        FLOW = "delete"

        class Action(str, Enum):
            CONFIRM = "confirm"  # Delete the reminder

        @classmethod
        def callback(cls, action: "ReminderFlow.Delete.Action", reminder_id: str) -> str:
            """Build delete flow callback: reminder:delete:{action}:{id}"""
            return f"{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:{reminder_id}"

        @classmethod
        def pattern(cls, action: "ReminderFlow.Delete.Action" = None) -> str:
            """Get regex pattern for matching delete callbacks."""
            if action:
                return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:.+$"
            return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:.+$"

    class List:
        """List flow - actions from /reminders list view."""
        FLOW = "list"

        class Action(str, Enum):
            SELECT = "select"  # Select for details
            EDIT = "edit"      # Enter edit flow

        @classmethod
        def callback(cls, action: "ReminderFlow.List.Action", reminder_id: str) -> str:
            """Build list flow callback: reminder:list:{action}:{id}"""
            return f"{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:{reminder_id}"

        @classmethod
        def pattern(cls, action: "ReminderFlow.List.Action" = None) -> str:
            """Get regex pattern for matching list callbacks."""
            if action:
                return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:{action.value}:.+$"
            return f"^{ReminderFlow.ENTITY}:{cls.FLOW}:.+$"

    @classmethod
    def parse(cls, callback_data: str) -> Optional[Tuple[str, str, str]]:
        """Parse callback_data and return (flow, action, id) or None."""
        parts = callback_data.split(":")
        if len(parts) != 4 or parts[0] != cls.ENTITY:
            return None
        return parts[1], parts[2], parts[3]

    @classmethod
    def matches(cls, callback_data: str) -> bool:
        """Check if callback_data is a reminder callback."""
        return callback_data.startswith(f"{cls.ENTITY}:")


# Legacy aliases for backward compatibility during migration
ReminderEditAction = ReminderFlow.Edit.Action
ReminderNotifyAction = ReminderFlow.Notify.Action
ReminderDeleteAction = ReminderFlow.Delete.Action
ReminderListAction = ReminderFlow.List.Action

# Legacy ReminderCallback class
class ReminderCallback:
    """DEPRECATED: Use ReminderFlow.Edit.callback(), etc. instead."""
    ENTITY = ReminderFlow.ENTITY

    @classmethod
    def edit(cls, action, reminder_id: str) -> str:
        return ReminderFlow.Edit.callback(action, reminder_id)

    @classmethod
    def notify(cls, action, reminder_id: str) -> str:
        return ReminderFlow.Notify.callback(action, reminder_id)

    @classmethod
    def delete(cls, action, reminder_id: str) -> str:
        return ReminderFlow.Delete.callback(action, reminder_id)

    @classmethod
    def list(cls, action, reminder_id: str) -> str:
        return ReminderFlow.List.callback(action, reminder_id)

    @classmethod
    def parse(cls, callback_data: str) -> Optional[Tuple[str, str, str]]:
        return ReminderFlow.parse(callback_data)

    @classmethod
    def matches(cls, callback_data: str) -> bool:
        return ReminderFlow.matches(callback_data)

    @classmethod
    def matches_flow(cls, callback_data: str, flow_class) -> bool:
        """Check if callback matches a flow. Pass ReminderFlow.Edit, etc."""
        return callback_data.startswith(f"{cls.ENTITY}:{flow_class.FLOW}:")


class Reminder(BaseModel):
    """Reminder domain model."""

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    title: str
    description: Optional[str] = None
    remind_at: datetime  # UTC
    repeat_rule: Optional[str] = None  # RRULE format for recurring reminders
    status: ReminderStatus = ReminderStatus.PENDING
    snooze_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))