"""Handler for inline keyboard callbacks (fallback for non-conversation callbacks).

This handler processes callbacks NOT handled by ConversationHandlers:
- Notification actions (snooze, complete/done)
- Task/meeting actions
- Clarification responses
- Quick actions (help, summary)

Reminder edit callbacks (change_time, edit_title, ok, delete) are handled by
ReminderEditConversation when user is in the edit flow.
Settings callbacks are handled by SettingsConversation.
"""

import logging
from uuid import UUID
from telegram import Update
from telegram.ext import ContextTypes

from app.models import (
    ParsedAction,
    ActionIntent,
    ActionStatus,
    ActionType,
    CallbackPrefix,
    ReminderFlow,
)
from app.services import UserService, AssistantService, ReminderService, TaskService
from app.intelligence import IntentResolver
from app.bot.keyboards import InlineKeyboards
from app.i18n import t
from app.utils import format_time, format_datetime
from app.bot.user_cache import get_cached_user
from .message_handler import PENDING_ACTIONS_KEY

logger = logging.getLogger(__name__)


class CallbackHandler:
    """Handle inline keyboard callbacks not handled by conversations."""

    def __init__(
        self,
        user_service: UserService,
        assistant_service: AssistantService,
        intent_resolver: IntentResolver,
        reminder_service: ReminderService,
        task_service: TaskService,
    ):
        self.user_service = user_service
        self.assistant_service = assistant_service
        self.intent_resolver = intent_resolver
        self.reminder_service = reminder_service
        self.task_service = task_service
        self.keyboards = InlineKeyboards()

    async def handle_callback(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        callback_data = query.data
        if not callback_data:
            return

        logger.info(f"Fallback callback received: {callback_data}")

        # Get user
        if not query.from_user:
            return

        user = await get_cached_user(update, callback_context, self.user_service)

        # Route callbacks by prefix
        # New entity-based callbacks (reminder:{flow}:{action}:{id})
        # Note: Edit and Delete flows are handled by ReminderEditConversation
        if callback_data.startswith(f"{ReminderFlow.ENTITY}:{ReminderFlow.Notify.FLOW}:"):
            await self._handle_reminder_notify(query, callback_context, user, callback_data)
        # Legacy prefixed callbacks
        elif CallbackPrefix.CLARIFY.matches(callback_data):
            await self._handle_clarification_response(query, callback_context, user, callback_data)
        elif CallbackPrefix.OPTION.matches(callback_data):
            option_text = callback_data[len(CallbackPrefix.OPTION.value) + 1:]
            await self._handle_option_selection(query, callback_context, user, option_text)
        elif CallbackPrefix.ACTION.matches(callback_data):
            action_data = callback_data[len(CallbackPrefix.ACTION.value) + 1:]
            await self._handle_action_callback(query, callback_context, user, action_data)
        elif CallbackPrefix.PARAM.matches(callback_data):
            await self._handle_param_option(query, callback_context, user, callback_data)
        elif CallbackPrefix.QUICK.matches(callback_data):
            await self._handle_quick_action(query, callback_context, user, callback_data)
        elif callback_data == "cancel":
            await query.edit_message_text(t("cancelled", locale=user.preferences.language))
        else:
            logger.warning(f"Unknown callback data: {callback_data}")

    async def _handle_reminder_notify(
        self,
        query,
        callback_context: ContextTypes.DEFAULT_TYPE,
        user,
        callback_data: str,
    ) -> None:
        """Handle reminder notification callbacks (snooze, done).

        Callback format: reminder:notify:{action}:{id}
        """
        Notify = ReminderFlow.Notify
        locale = user.preferences.language
        timezone = user.preferences.timezone

        parsed = ReminderFlow.parse(callback_data)
        if not parsed:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        flow, action, reminder_id = parsed

        try:
            item_uuid = UUID(reminder_id)
        except ValueError:
            await query.edit_message_text(t("invalid_id", locale=locale))
            return

        if action == Notify.Action.SNOOZE.value:
            # Snooze reminder for 15 minutes
            reminder = await self.reminder_service.snooze_reminder(item_uuid, minutes=15)
            if reminder:
                try:
                    await query.delete_message()
                except Exception as e:
                    logger.warning(f"Could not delete message: {e}")
                    new_time = format_time(reminder.remind_at, timezone=timezone)
                    await query.edit_message_text(f"😴 {t('reminder_snoozed', locale=locale, time=new_time)}")
            else:
                await query.edit_message_text(t("reminder_not_found", locale=locale))

        elif action == Notify.Action.DONE.value:
            # Mark reminder as done
            reminder = await self.reminder_service.mark_sent(item_uuid)
            if reminder:
                completed_text = t("reminder_completed_text", locale=locale, title=reminder.title)
                await query.edit_message_text(
                    completed_text,
                    reply_markup=None,
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(t("reminder_not_found", locale=locale))

        else:
            logger.warning(f"Unknown reminder notify action: {action}")
            await query.edit_message_text(t("unknown_action", locale=locale, action=action))

    async def _handle_option_selection(
        self,
        query,
        callback_context: ContextTypes.DEFAULT_TYPE,
        user,
        option_text: str,
    ) -> None:
        """Handle when user selects an option from clarification."""
        locale = user.preferences.language

        # Process the option as a new input
        result = await self.intent_resolver.resolve(
            user_input=option_text,
            user_id=user.telegram_id,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            skip_clarification=True,
            locale=locale,
        )

        if hasattr(result, 'intent'):
            # It's a ParsedAction
            action_result = await self.assistant_service.execute_action(result, user)
            create_actions = {ActionType.CREATE_REMINDER, ActionType.CREATE_TASK, ActionType.SCHEDULE_MEETING}
            if result.action_type in create_actions:
                message = action_result.message if action_result.success else f"❌ {action_result.message}"
            else:
                emoji = "✅" if action_result.success else "❌"
                message = f"{emoji} {action_result.message}"

            # Add edit keyboard for successful reminder creation
            keyboard = None
            if action_result.success and result.action_type == ActionType.CREATE_REMINDER:
                reminder_id = action_result.data.get("reminder_id")
                if reminder_id:
                    keyboard = self.keyboards.create_reminder_selected_keyboard(reminder_id, locale=locale)

            await query.edit_message_text(message, reply_markup=keyboard)
        else:
            await query.edit_message_text(result.message)

    async def _handle_action_callback(
        self,
        query,
        callback_context: ContextTypes.DEFAULT_TYPE,
        user,
        action_data: str,
    ) -> None:
        """Handle direct action callbacks (notification buttons, task/meeting actions)."""
        # Parse action:type:id format
        parts = action_data.split(":", 1)
        action_type = parts[0]
        item_id = parts[1] if len(parts) > 1 else None

        locale = user.preferences.language

        if not item_id:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        try:
            item_uuid = UUID(item_id)
        except ValueError:
            await query.edit_message_text(t("invalid_id", locale=locale))
            return

        # Handle specific actions
        if action_type == "snooze":
            # Snooze a reminder for 15 minutes
            reminder = await self.reminder_service.snooze_reminder(item_uuid, minutes=15)
            if reminder:
                try:
                    await query.delete_message()
                except Exception as e:
                    logger.warning(f"Could not delete message: {e}")
                    timezone = user.preferences.timezone
                    new_time = format_time(reminder.remind_at, timezone=timezone)
                    await query.edit_message_text(f"😴 {t('reminder_snoozed', locale=locale, time=new_time)}")
            else:
                await query.edit_message_text(t("reminder_not_found", locale=locale))

        elif action_type == "complete":
            # Complete a reminder (mark as done) or task
            reminder = await self.reminder_service.mark_sent(item_uuid)
            if reminder:
                completed_text = t("reminder_completed_text", locale=locale, title=reminder.title)
                await query.edit_message_text(
                    completed_text,
                    reply_markup=None,
                    parse_mode="Markdown",
                )
            else:
                # Try as task
                task = await self.task_service.complete_task(item_uuid)
                if task:
                    completed_text = t("task_completed_text", locale=locale, title=task.title)
                    await query.edit_message_text(
                        completed_text,
                        reply_markup=None,
                        parse_mode="Markdown",
                    )
                else:
                    await query.edit_message_text(t("item_not_found", locale=locale))

        elif action_type == "cancel":
            # Cancel a meeting
            meeting = await self.assistant_service.meeting_service.cancel_meeting(item_uuid)
            if meeting:
                await query.edit_message_text(f"❌ {t('meeting_cancelled', locale=locale, title=meeting.title)}")
            else:
                await query.edit_message_text(t("meeting_not_found", locale=locale))

        elif action_type == "edit":
            # Edit functionality (for tasks/meetings)
            await query.edit_message_text(t("edit_coming_soon", locale=locale))

        elif action_type == "delete":
            # Delete (could be task if not handled by conversation)
            deleted = await self.task_service.delete_task(item_uuid)
            if deleted:
                await query.edit_message_text(f"🗑️ {t('task_deleted', locale=locale)}")
            else:
                await query.edit_message_text(t("item_not_found", locale=locale))

        else:
            # Unknown action type - might be handled by conversation
            logger.debug(f"Action type '{action_type}' not handled by fallback, might be for conversation")
            await query.edit_message_text(t("unknown_action", locale=locale, action=action_type))

    async def _handle_clarification_response(
        self,
        query,
        callback_context: ContextTypes.DEFAULT_TYPE,
        user,
        callback_data: str,
    ) -> None:
        """Handle user response to a clarification request."""
        locale = user.preferences.language

        # Parse: clarify:{action_id}:{response_type}
        parts = callback_data.split(":")
        if len(parts) < 3:
            logger.error(f"Invalid clarification callback data: {callback_data}")
            await query.edit_message_text(t("something_went_wrong_generic", locale=locale))
            return

        action_id = parts[1]
        response_type = parts[2]

        # Retrieve the pending action from user_data
        pending_actions = callback_context.user_data.get(PENDING_ACTIONS_KEY, {})
        pending_data = pending_actions.get(action_id)

        if not pending_data:
            logger.warning(f"No pending action found for action_id: {action_id}")
            await query.edit_message_text(t("expired_action", locale=locale))
            return

        if response_type == "confirm":
            original_action = pending_data.get("original_action")
            if original_action and isinstance(original_action, ParsedAction):
                action_result = await self.assistant_service.execute_action(original_action, user)
                create_actions = {ActionType.CREATE_REMINDER, ActionType.CREATE_TASK, ActionType.SCHEDULE_MEETING}
                if original_action.action_type in create_actions:
                    message = action_result.message if action_result.success else f"❌ {action_result.message}"
                else:
                    emoji = "✅" if action_result.success else "❌"
                    message = f"{emoji} {action_result.message}"

                keyboard = None
                if action_result.success and original_action.action_type == ActionType.CREATE_REMINDER:
                    reminder_id = action_result.data.get("reminder_id")
                    if reminder_id:
                        keyboard = self.keyboards.create_reminder_selected_keyboard(reminder_id, locale=locale)

                await query.edit_message_text(message, reply_markup=keyboard)
            else:
                await query.edit_message_text(t("something_went_wrong_generic", locale=locale))

        elif response_type.startswith("alt_"):
            try:
                alt_index = int(response_type[4:])
            except ValueError:
                await query.edit_message_text(t("invalid_action", locale=locale))
                return

            alternatives = pending_data.get("alternatives")
            original_input = pending_data.get("original_input")
            actual_index = alt_index + 1

            if not alternatives or actual_index >= len(alternatives):
                await query.edit_message_text(t("describe_what_to_do", locale=locale))
                return

            selected_action_type, _ = alternatives[actual_index]

            if original_input:
                parameters = await self.intent_resolver.parameter_extractor.extract(
                    original_input, selected_action_type
                )
                new_intent = ActionIntent(
                    action_type=selected_action_type,
                    confidence=1.0,
                    original_input=original_input,
                )
                new_action = ParsedAction(
                    intent=new_intent,
                    parameters=parameters,
                    user_id=user.telegram_id,
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    status=ActionStatus.PENDING,
                )

                action_result = await self.assistant_service.execute_action(new_action, user)
                create_actions = {ActionType.CREATE_REMINDER, ActionType.CREATE_TASK, ActionType.SCHEDULE_MEETING}
                if selected_action_type in create_actions:
                    message = action_result.message if action_result.success else f"❌ {action_result.message}"
                else:
                    emoji = "✅" if action_result.success else "❌"
                    message = f"{emoji} {action_result.message}"

                keyboard = None
                if action_result.success and selected_action_type == ActionType.CREATE_REMINDER:
                    reminder_id = action_result.data.get("reminder_id")
                    if reminder_id:
                        keyboard = self.keyboards.create_reminder_selected_keyboard(reminder_id, locale=locale)

                await query.edit_message_text(message, reply_markup=keyboard)
            else:
                await query.edit_message_text(t("describe_what_to_do", locale=locale))

        elif response_type == "another":
            await query.edit_message_text(t("no_problem", locale=locale))

        else:
            await query.edit_message_text(t("try_again", locale=locale))

        # Clean up
        if action_id in pending_actions:
            del pending_actions[action_id]

    async def _handle_param_option(
        self,
        query,
        callback_context: ContextTypes.DEFAULT_TYPE,
        user,
        callback_data: str,
    ) -> None:
        """Handle parameter option selection for missing parameter clarification."""
        locale = user.preferences.language

        # Parse: param:{action_id}:option_{index}
        parts = callback_data.split(":")
        if len(parts) < 3:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        action_id = parts[1]
        option_part = parts[2]

        if not option_part.startswith("option_"):
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        try:
            option_index = int(option_part[7:])
        except ValueError:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        pending_actions = callback_context.user_data.get(PENDING_ACTIONS_KEY, {})
        pending_data = pending_actions.get(action_id)

        if not pending_data:
            await query.edit_message_text(t("expired_action", locale=locale))
            return

        clarification = pending_data.get("clarification")
        if not clarification or option_index >= len(clarification.options):
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        selected_option = clarification.options[option_index]
        selected_text = selected_option.text

        original_action = pending_data.get("original_action")
        if original_action and isinstance(original_action, ParsedAction):
            param_name = clarification.parameter
            original_action.parameters[param_name] = selected_text

            action_result = await self.assistant_service.execute_action(original_action, user)
            create_actions = {ActionType.CREATE_REMINDER, ActionType.CREATE_TASK, ActionType.SCHEDULE_MEETING}
            if original_action.action_type in create_actions:
                message = action_result.message if action_result.success else f"❌ {action_result.message}"
            else:
                emoji = "✅" if action_result.success else "❌"
                message = f"{emoji} {action_result.message}"

            keyboard = None
            if action_result.success and original_action.action_type == ActionType.CREATE_REMINDER:
                reminder_id = action_result.data.get("reminder_id")
                if reminder_id:
                    keyboard = self.keyboards.create_reminder_selected_keyboard(reminder_id, locale=locale)

            await query.edit_message_text(message, reply_markup=keyboard)
        else:
            await query.edit_message_text(t("expired_action", locale=locale))

        # Clean up
        if action_id in pending_actions:
            del pending_actions[action_id]

    async def _handle_quick_action(
        self,
        query,
        callback_context: ContextTypes.DEFAULT_TYPE,
        user,
        callback_data: str,
    ) -> None:
        """Handle quick actions for ambiguous input (help, summary)."""
        locale = user.preferences.language

        # Parse: quick:{action}
        action = callback_data[len(CallbackPrefix.QUICK.value) + 1:]

        if action == "help":
            help_intent = ActionIntent(
                action_type=ActionType.HELP,
                confidence=1.0,
                original_input="help",
            )
            help_action = ParsedAction(
                intent=help_intent,
                parameters={},
                user_id=user.telegram_id,
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                status=ActionStatus.PENDING,
            )
            action_result = await self.assistant_service.execute_action(help_action, user)
            await query.edit_message_text(action_result.message)

        elif action == "summary":
            summary_intent = ActionIntent(
                action_type=ActionType.SHOW_SUMMARY,
                confidence=1.0,
                original_input="show summary",
            )
            summary_action = ParsedAction(
                intent=summary_intent,
                parameters={},
                user_id=user.telegram_id,
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                status=ActionStatus.PENDING,
            )
            action_result = await self.assistant_service.execute_action(summary_action, user)
            await query.edit_message_text(action_result.message)

        else:
            logger.warning(f"Unknown quick action: {action}")
            await query.edit_message_text(t("invalid_action", locale=locale))
