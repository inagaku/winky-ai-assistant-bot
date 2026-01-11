"""Assistant service - main orchestrator for handling user requests."""

import logging
from typing import Optional, Union
from uuid import UUID

from app.models import (
    ActionType,
    ActionStatus,
    ParsedAction,
    ClarificationRequest,
    ClarificationType,
    User,
)
from app.repositories import UserRepository

from .user_service import UserService
from .reminder_service import ReminderService
from .task_service import TaskService
from .meeting_service import MeetingService
from .base_service import BaseService

logger = logging.getLogger(__name__)


class ActionResult:
    """Result of executing an action."""

    def __init__(
        self,
        success: bool,
        message: str,
        data: Optional[dict] = None,
    ):
        self.success = success
        self.message = message
        self.data = data or {}


class AssistantService(BaseService):
    """Main service for orchestrating assistant operations."""

    def __init__(
        self,
        user_service: UserService,
        reminder_service: ReminderService,
        task_service: TaskService,
        meeting_service: MeetingService,
    ):
        super().__init__()
        self.user_service = user_service
        self.reminder_service = reminder_service
        self.task_service = task_service
        self.meeting_service = meeting_service

    async def execute_action(
        self,
        action: ParsedAction,
        user: User,
    ) -> ActionResult:
        """Execute a parsed action and return the result."""
        self.logger.info(
            f"Executing action {action.action_type} for user {user.telegram_id}"
        )

        try:
            # Route to appropriate handler
            handler = self._get_handler(action.action_type)
            if not handler:
                return ActionResult(
                    success=False,
                    message=f"Unknown action type: {action.action_type}",
                )

            result = await handler(action, user)
            action.status = ActionStatus.COMPLETED
            action.result_message = result.message
            return result

        except Exception as e:
            self.logger.error(f"Error executing action: {e}", exc_info=True)
            action.status = ActionStatus.FAILED
            return ActionResult(
                success=False,
                message=f"Sorry, something went wrong: {str(e)}",
            )

    def _get_handler(self, action_type: ActionType):
        """Get the handler function for an action type."""
        handlers = {
            # Reminders
            ActionType.CREATE_REMINDER: self._handle_create_reminder,
            ActionType.LIST_REMINDERS: self._handle_list_reminders,
            ActionType.DELETE_REMINDER: self._handle_delete_reminder,
            # Tasks
            ActionType.CREATE_TASK: self._handle_create_task,
            ActionType.LIST_TASKS: self._handle_list_tasks,
            ActionType.COMPLETE_TASK: self._handle_complete_task,
            ActionType.DELETE_TASK: self._handle_delete_task,
            # Meetings
            ActionType.SCHEDULE_MEETING: self._handle_schedule_meeting,
            ActionType.LIST_MEETINGS: self._handle_list_meetings,
            ActionType.CANCEL_MEETING: self._handle_cancel_meeting,
            # General
            ActionType.SHOW_SUMMARY: self._handle_show_summary,
            ActionType.HELP: self._handle_help,
        }
        return handlers.get(action_type)

    # Reminder handlers
    async def _handle_create_reminder(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle creating a reminder."""
        reminder = await self.reminder_service.create_from_params(
            user_id=user.id,
            params=action.parameters,
        )
        time_str = reminder.remind_at.strftime("%Y-%m-%d %H:%M")
        return ActionResult(
            success=True,
            message=f"Got it! I'll remind you about \"{reminder.title}\" at {time_str}.",
            data={"reminder_id": str(reminder.id)},
        )

    async def _handle_list_reminders(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle listing reminders."""
        reminders = await self.reminder_service.get_user_reminders(user.id)
        message = self.reminder_service.format_reminder_list(reminders)
        return ActionResult(
            success=True,
            message=message,
            data={"count": len(reminders)},
        )

    async def _handle_delete_reminder(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle deleting a reminder."""
        reminder_id = action.parameters.get("reminder_id")
        if not reminder_id:
            return ActionResult(
                success=False,
                message="Which reminder should I delete? Please specify the reminder.",
            )

        try:
            reminder_uuid = UUID(reminder_id)
            deleted = await self.reminder_service.delete_reminder(reminder_uuid)
            if deleted:
                return ActionResult(success=True, message="Reminder deleted.")
            return ActionResult(success=False, message="Reminder not found.")
        except ValueError:
            return ActionResult(success=False, message="Invalid reminder ID.")

    # Task handlers
    async def _handle_create_task(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle creating a task."""
        task = await self.task_service.create_from_params(
            user_id=user.id,
            params=action.parameters,
        )
        due_str = ""
        if task.due_date:
            due_str = f" (due: {task.due_date.strftime('%Y-%m-%d')})"
        return ActionResult(
            success=True,
            message=f"Task created: \"{task.title}\"{due_str}",
            data={"task_id": str(task.id)},
        )

    async def _handle_list_tasks(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle listing tasks."""
        tasks = await self.task_service.get_user_tasks(user.id)
        message = self.task_service.format_task_list(tasks)
        return ActionResult(
            success=True,
            message=message,
            data={"count": len(tasks)},
        )

    async def _handle_complete_task(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle completing a task."""
        task_id = action.parameters.get("task_id")
        if not task_id:
            return ActionResult(
                success=False,
                message="Which task should I mark as complete?",
            )

        try:
            task_uuid = UUID(task_id)
            task = await self.task_service.complete_task(task_uuid)
            if task:
                return ActionResult(
                    success=True,
                    message=f"Task \"{task.title}\" marked as complete! Great job!",
                )
            return ActionResult(success=False, message="Task not found.")
        except ValueError:
            return ActionResult(success=False, message="Invalid task ID.")

    async def _handle_delete_task(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle deleting a task."""
        task_id = action.parameters.get("task_id")
        if not task_id:
            return ActionResult(
                success=False,
                message="Which task should I delete?",
            )

        try:
            task_uuid = UUID(task_id)
            deleted = await self.task_service.delete_task(task_uuid)
            if deleted:
                return ActionResult(success=True, message="Task deleted.")
            return ActionResult(success=False, message="Task not found.")
        except ValueError:
            return ActionResult(success=False, message="Invalid task ID.")

    # Meeting handlers
    async def _handle_schedule_meeting(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle scheduling a meeting."""
        meeting = await self.meeting_service.create_from_params(
            user_id=user.id,
            params=action.parameters,
        )
        time_str = meeting.start_time.strftime("%Y-%m-%d %H:%M")
        participants_str = ""
        if meeting.participants:
            participants_str = f" with {', '.join(meeting.participants)}"
        return ActionResult(
            success=True,
            message=f"Meeting scheduled: \"{meeting.title}\"{participants_str} at {time_str}",
            data={"meeting_id": str(meeting.id)},
        )

    async def _handle_list_meetings(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle listing meetings."""
        meetings = await self.meeting_service.get_user_meetings(user.id)
        message = self.meeting_service.format_meeting_list(meetings)
        return ActionResult(
            success=True,
            message=message,
            data={"count": len(meetings)},
        )

    async def _handle_cancel_meeting(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle cancelling a meeting."""
        meeting_id = action.parameters.get("meeting_id")
        if not meeting_id:
            return ActionResult(
                success=False,
                message="Which meeting should I cancel?",
            )

        try:
            meeting_uuid = UUID(meeting_id)
            meeting = await self.meeting_service.cancel_meeting(meeting_uuid)
            if meeting:
                return ActionResult(
                    success=True,
                    message=f"Meeting \"{meeting.title}\" has been cancelled.",
                )
            return ActionResult(success=False, message="Meeting not found.")
        except ValueError:
            return ActionResult(success=False, message="Invalid meeting ID.")

    # General handlers
    async def _handle_show_summary(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle showing a summary of all items."""
        reminders = await self.reminder_service.get_user_reminders(user.id, limit=5)
        tasks = await self.task_service.get_user_tasks(user.id, limit=5)
        meetings = await self.meeting_service.get_upcoming_meetings(user.id)

        lines = [f"Here's your summary, {user.display_name}:", ""]

        # Reminders section
        reminder_count = await self.reminder_service.get_active_count(user.id)
        lines.append(f"🔔 Reminders ({reminder_count} active):")
        if reminders:
            for r in reminders[:3]:
                time_str = r.remind_at.strftime("%m/%d %H:%M")
                lines.append(f"  • {r.title} - {time_str}")
        else:
            lines.append("  No active reminders")
        lines.append("")

        # Tasks section
        task_count = await self.task_service.get_active_count(user.id)
        overdue = await self.task_service.get_overdue_tasks(user.id)
        overdue_str = f" ({len(overdue)} overdue)" if overdue else ""
        lines.append(f"✅ Tasks ({task_count} active{overdue_str}):")
        if tasks:
            for t in tasks[:3]:
                priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴"}
                emoji = priority_emoji.get(t.priority.value, "⚪")
                lines.append(f"  {emoji} {t.title}")
        else:
            lines.append("  No active tasks")
        lines.append("")

        # Meetings section
        meeting_count = await self.meeting_service.get_active_count(user.id)
        lines.append(f"📅 Upcoming meetings ({meeting_count} scheduled):")
        if meetings:
            for m in meetings[:3]:
                time_str = m.start_time.strftime("%m/%d %H:%M")
                lines.append(f"  • {m.title} - {time_str}")
        else:
            lines.append("  No upcoming meetings")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            data={
                "reminder_count": reminder_count,
                "task_count": task_count,
                "meeting_count": meeting_count,
            },
        )

    async def _handle_help(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle help request."""
        help_text = """Here's what I can help you with:

🔔 **Reminders**
• "Remind me to call mom tomorrow at 3pm"
• "Set a reminder for the meeting in 30 minutes"
• "Show my reminders"

✅ **Tasks**
• "Create a task to review the report"
• "Add a high priority task: fix the bug"
• "Show my tasks"
• "Complete task..."

📅 **Meetings**
• "Schedule a meeting with John tomorrow at 2pm"
• "Book an appointment for next Monday"
• "Show my meetings"

📊 **Summary**
• "Show my summary"
• "What's on my agenda?"

Just tell me what you need in natural language!"""

        return ActionResult(success=True, message=help_text)
