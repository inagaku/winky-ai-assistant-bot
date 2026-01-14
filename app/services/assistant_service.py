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
from app.i18n import t

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

        locale = user.preferences.language

        try:
            # Route to appropriate handler
            handler = self._get_handler(action.action_type)
            if not handler:
                return ActionResult(
                    success=False,
                    message=t("unknown_action", locale=locale, action=str(action.action_type)),
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
                message=t("something_went_wrong", locale=locale, error=str(e)),
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
        locale = user.preferences.language
        reminder = await self.reminder_service.create_from_params(
            user_id=user.id,
            params=action.parameters,
            user_timezone=user.preferences.timezone,
        )
        time_str = reminder.remind_at.strftime("%Y-%m-%d %H:%M")

        # Build a helpful message showing when they'll be notified
        message = t("reminder_created", locale=locale, title=reminder.title, time=time_str)

        # If description contains action time info, include it
        if reminder.description and reminder.description.startswith("Action scheduled"):
            message += f"\n\n{reminder.description}"

        return ActionResult(
            success=True,
            message=message,
            data={"reminder_id": str(reminder.id)},
        )

    async def _handle_list_reminders(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle listing reminders."""
        locale = user.preferences.language
        reminders = await self.reminder_service.get_user_reminders(user.id)
        message = self.reminder_service.format_reminder_list(reminders, locale=locale)
        return ActionResult(
            success=True,
            message=message,
            data={"count": len(reminders)},
        )

    async def _handle_delete_reminder(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle deleting a reminder."""
        locale = user.preferences.language
        reminder_id = action.parameters.get("reminder_id")
        if not reminder_id:
            return ActionResult(
                success=False,
                message=t("which_reminder_delete", locale=locale),
            )

        try:
            reminder_uuid = UUID(reminder_id)
            deleted = await self.reminder_service.delete_reminder(reminder_uuid)
            if deleted:
                return ActionResult(success=True, message=t("reminder_deleted", locale=locale))
            return ActionResult(success=False, message=t("reminder_not_found", locale=locale))
        except ValueError:
            return ActionResult(success=False, message=t("invalid_id", locale=locale))

    # Task handlers
    async def _handle_create_task(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle creating a task."""
        locale = user.preferences.language
        task = await self.task_service.create_from_params(
            user_id=user.id,
            params=action.parameters,
            user_timezone=user.preferences.timezone,
        )
        if task.due_date:
            due_str = task.due_date.strftime('%Y-%m-%d')
            message = t("task_created_with_due", locale=locale, title=task.title, due_date=due_str)
        else:
            message = t("task_created", locale=locale, title=task.title)
        return ActionResult(
            success=True,
            message=message,
            data={"task_id": str(task.id)},
        )

    async def _handle_list_tasks(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle listing tasks."""
        locale = user.preferences.language
        tasks = await self.task_service.get_user_tasks(user.id)
        message = self.task_service.format_task_list(tasks, locale=locale)
        return ActionResult(
            success=True,
            message=message,
            data={"count": len(tasks)},
        )

    async def _handle_complete_task(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle completing a task."""
        locale = user.preferences.language
        task_id = action.parameters.get("task_id")
        if not task_id:
            return ActionResult(
                success=False,
                message=t("which_task_complete", locale=locale),
            )

        try:
            task_uuid = UUID(task_id)
            task = await self.task_service.complete_task(task_uuid)
            if task:
                return ActionResult(
                    success=True,
                    message=t("task_completed", locale=locale, title=task.title),
                )
            return ActionResult(success=False, message=t("task_not_found", locale=locale))
        except ValueError:
            return ActionResult(success=False, message=t("invalid_id", locale=locale))

    async def _handle_delete_task(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle deleting a task."""
        locale = user.preferences.language
        task_id = action.parameters.get("task_id")
        if not task_id:
            return ActionResult(
                success=False,
                message=t("which_task_delete", locale=locale),
            )

        try:
            task_uuid = UUID(task_id)
            deleted = await self.task_service.delete_task(task_uuid)
            if deleted:
                return ActionResult(success=True, message=t("task_deleted", locale=locale))
            return ActionResult(success=False, message=t("task_not_found", locale=locale))
        except ValueError:
            return ActionResult(success=False, message=t("invalid_id", locale=locale))

    # Meeting handlers
    async def _handle_schedule_meeting(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle scheduling a meeting."""
        locale = user.preferences.language
        meeting = await self.meeting_service.create_from_params(
            user_id=user.id,
            params=action.parameters,
            user_timezone=user.preferences.timezone,
        )
        time_str = meeting.start_time.strftime("%Y-%m-%d %H:%M")
        if meeting.participants:
            participants_str = ', '.join(meeting.participants)
            message = t("meeting_scheduled_with_participants", locale=locale,
                       title=meeting.title, participants=participants_str, time=time_str)
        else:
            message = t("meeting_scheduled", locale=locale, title=meeting.title, time=time_str)
        return ActionResult(
            success=True,
            message=message,
            data={"meeting_id": str(meeting.id)},
        )

    async def _handle_list_meetings(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle listing meetings."""
        locale = user.preferences.language
        meetings = await self.meeting_service.get_user_meetings(user.id)
        message = self.meeting_service.format_meeting_list(meetings, locale=locale)
        return ActionResult(
            success=True,
            message=message,
            data={"count": len(meetings)},
        )

    async def _handle_cancel_meeting(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle cancelling a meeting."""
        locale = user.preferences.language
        meeting_id = action.parameters.get("meeting_id")
        if not meeting_id:
            return ActionResult(
                success=False,
                message=t("which_meeting_cancel", locale=locale),
            )

        try:
            meeting_uuid = UUID(meeting_id)
            meeting = await self.meeting_service.cancel_meeting(meeting_uuid)
            if meeting:
                return ActionResult(
                    success=True,
                    message=t("meeting_cancelled", locale=locale, title=meeting.title),
                )
            return ActionResult(success=False, message=t("meeting_not_found", locale=locale))
        except ValueError:
            return ActionResult(success=False, message=t("invalid_id", locale=locale))

    # General handlers
    async def _handle_show_summary(
        self, action: ParsedAction, user: User
    ) -> ActionResult:
        """Handle showing a summary of all items."""
        locale = user.preferences.language
        reminders = await self.reminder_service.get_user_reminders(user.id, limit=5)
        tasks = await self.task_service.get_user_tasks(user.id, limit=5)
        meetings = await self.meeting_service.get_upcoming_meetings(user.id)

        lines = [t("summary_title", locale=locale, name=user.display_name), ""]

        # Reminders section
        reminder_count = await self.reminder_service.get_active_count(user.id)
        lines.append(f"🔔 {t('summary_reminders', locale=locale, count=reminder_count)}")
        if reminders:
            for r in reminders[:3]:
                time_str = r.remind_at.strftime("%m/%d %H:%M")
                lines.append(f"  • {r.title} - {time_str}")
        else:
            lines.append(f"  {t('no_active_reminders', locale=locale)}")
        lines.append("")

        # Tasks section
        task_count = await self.task_service.get_active_count(user.id)
        overdue = await self.task_service.get_overdue_tasks(user.id)
        if overdue:
            lines.append(f"✅ {t('summary_tasks_overdue', locale=locale, count=task_count, overdue=len(overdue))}")
        else:
            lines.append(f"✅ {t('summary_tasks', locale=locale, count=task_count)}")
        if tasks:
            for task in tasks[:3]:
                priority_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴"}
                emoji = priority_emoji.get(task.priority.value, "⚪")
                lines.append(f"  {emoji} {task.title}")
        else:
            lines.append(f"  {t('no_active_tasks', locale=locale)}")
        lines.append("")

        # Meetings section
        meeting_count = await self.meeting_service.get_active_count(user.id)
        lines.append(f"📅 {t('summary_meetings', locale=locale, count=meeting_count)}")
        if meetings:
            for m in meetings[:3]:
                time_str = m.start_time.strftime("%m/%d %H:%M")
                lines.append(f"  • {m.title} - {time_str}")
        else:
            lines.append(f"  {t('no_upcoming_meetings', locale=locale)}")

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
        locale = user.preferences.language
        help_text = f"""{t('help_title', locale=locale)}

🔔 {t('help_reminders', locale=locale)}

✅ {t('help_tasks', locale=locale)}

📅 {t('help_meetings', locale=locale)}

📊 {t('help_summary', locale=locale)}

{t('help_footer', locale=locale)}"""

        return ActionResult(success=True, message=help_text)
