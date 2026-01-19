"""Handler for inline keyboard callbacks."""

import logging
from uuid import UUID
from telegram import Update
from telegram.ext import ContextTypes

from app.models import ParsedAction, ActionIntent, ActionStatus, ActionType
from app.services import UserService, AssistantService, ReminderService, TaskService
from app.intelligence import IntentResolver
from app.bot.keyboards import InlineKeyboards
from app.i18n import t
from app.utils import format_time, format_datetime, parse_time_adjustment
from .message_handler import PENDING_ACTIONS_KEY, PENDING_EDIT_KEY
from .command_handler import ONBOARDING_STATE_KEY

logger = logging.getLogger(__name__)


class CallbackHandler:
    """Handle inline keyboard button callbacks."""

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
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        if not query:
            return

        await query.answer()

        callback_data = query.data
        if not callback_data:
            return

        logger.info(f"Callback received: {callback_data}")

        # Get user
        if not query.from_user:
            return

        user = await self.user_service.get_or_create_user(
            telegram_id=query.from_user.id,
            username=query.from_user.username,
            first_name=query.from_user.first_name,
            last_name=query.from_user.last_name,
        )

        # Parse callback data
        if callback_data.startswith("clarify:"):
            # User responded to a clarification request
            await self._handle_clarification_response(query, context, user, callback_data)
        elif callback_data.startswith("option:"):
            # User selected an option from clarification
            option_text = callback_data[7:]  # Remove "option:" prefix
            await self._handle_option_selection(query, context, user, option_text)
        elif callback_data.startswith("action:"):
            # Direct action callback
            action_data = callback_data[7:]
            await self._handle_action_callback(query, context, user, action_data)
        elif callback_data.startswith("tz_region:"):
            # Timezone region selection
            region = callback_data[10:]  # Remove "tz_region:" prefix
            await self._handle_timezone_region(query, context, user, region)
        elif callback_data.startswith("tz:"):
            # Timezone selection
            timezone = callback_data[3:]  # Remove "tz:" prefix
            await self._handle_timezone_selection(query, context, user, timezone)
        elif callback_data.startswith("settings:"):
            # Settings callback
            setting = callback_data[9:]  # Remove "settings:" prefix
            await self._handle_settings_callback(query, context, user, setting)
        elif callback_data.startswith("lang:"):
            # Language selection
            language = callback_data[5:]  # Remove "lang:" prefix
            await self._handle_language_selection(query, context, user, language)
        elif callback_data.startswith("adjust_time:"):
            # Quick time adjustment: adjust_time:{reminder_id}:{minutes}
            await self._handle_time_adjustment(query, context, user, callback_data)
        elif callback_data.startswith("param:"):
            # Parameter option selection: param:{action_id}:option_{index}
            await self._handle_param_option(query, context, user, callback_data)
        elif callback_data.startswith("quick:"):
            # Quick action: quick:help, quick:summary
            await self._handle_quick_action(query, context, user, callback_data)
        elif callback_data == "cancel":
            await query.edit_message_text(t("cancelled", locale=user.preferences.language))
        else:
            logger.warning(f"Unknown callback data: {callback_data}")

    async def _handle_option_selection(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
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
            skip_clarification=True,  # User already made a choice
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
                    keyboard = self.keyboards.create_reminder_created_keyboard(reminder_id, locale=locale)

            await query.edit_message_text(message, reply_markup=keyboard)
        else:
            # It's still a clarification
            await query.edit_message_text(result.message)

    async def _handle_action_callback(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        action_data: str,
    ) -> None:
        """Handle direct action callbacks."""
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
            # Snooze a reminder for 15 minutes and delete the notification
            reminder = await self.reminder_service.snooze_reminder(item_uuid, minutes=15)
            if reminder:
                # Delete the notification message - user will get a new one when due
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
            # Could be a reminder "Done" or a task "Complete"
            # Try reminder first (mark as sent), then task
            reminder = await self.reminder_service.mark_sent(item_uuid)
            if reminder:
                # Update message to show completed, remove buttons
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
            # Edit functionality - for now just acknowledge
            await query.edit_message_text(t("edit_coming_soon", locale=locale))

        elif action_type == "delete":
            # Delete a reminder or task
            # Try reminder first
            deleted = await self.reminder_service.delete_reminder(item_uuid)
            if deleted:
                await query.edit_message_text(f"🗑️ {t('reminder_deleted', locale=locale)}")
            else:
                # Try as task
                deleted = await self.task_service.delete_task(item_uuid)
                if deleted:
                    await query.edit_message_text(f"🗑️ {t('task_deleted', locale=locale)}")
                else:
                    await query.edit_message_text(t("item_not_found", locale=locale))

        elif action_type == "change_time":
            # Show time adjustment options
            reminder = await self.reminder_service.get_reminder(item_uuid)
            if reminder:
                timezone = user.preferences.timezone
                current_time = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
                message = t("change_time_prompt", locale=locale, current_time=current_time)
                keyboard = self.keyboards.create_time_adjustment_keyboard(item_id, locale=locale)
                await query.edit_message_text(message, reply_markup=keyboard)
            else:
                await query.edit_message_text(t("reminder_not_found", locale=locale))

        elif action_type == "edit_title":
            # Ask user for new title - store pending edit
            reminder = await self.reminder_service.get_reminder(item_uuid)
            if reminder:
                context.user_data[PENDING_EDIT_KEY] = {
                    "type": "title",
                    "reminder_id": item_id,
                    "chat_id": query.message.chat_id,
                    "message_id": query.message.message_id,
                }
                await query.edit_message_text(
                    t("enter_new_title", locale=locale, current_title=reminder.title)
                )
            else:
                await query.edit_message_text(t("reminder_not_found", locale=locale))

        elif action_type == "enter_time":
            # Ask user for custom time - store pending edit
            reminder = await self.reminder_service.get_reminder(item_uuid)
            if reminder:
                context.user_data[PENDING_EDIT_KEY] = {
                    "type": "time",
                    "reminder_id": item_id,
                    "current_time": reminder.remind_at,
                    "chat_id": query.message.chat_id,
                    "message_id": query.message.message_id,
                }
                await query.edit_message_text(t("enter_new_time", locale=locale))
            else:
                await query.edit_message_text(t("reminder_not_found", locale=locale))

        elif action_type == "back_to_reminder":
            # Go back to reminder confirmation view
            reminder = await self.reminder_service.get_reminder(item_uuid)
            if reminder:
                timezone = user.preferences.timezone
                time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
                message = t("reminder_created", locale=locale, title=reminder.title, time=time_str)
                keyboard = self.keyboards.create_reminder_created_keyboard(item_id, locale=locale)
                await query.edit_message_text(message, reply_markup=keyboard)
            else:
                await query.edit_message_text(t("reminder_not_found", locale=locale))

        elif action_type == "ok":
            # Accept and remove keyboard - keep message as is
            await query.edit_message_reply_markup(reply_markup=None)

        else:
            await query.edit_message_text(t("unknown_action", locale=locale, action=action_type))

    async def _handle_clarification_response(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        callback_data: str,
    ) -> None:
        """Handle user response to a clarification request."""
        locale = user.preferences.language

        # Parse: clarify:{action_id}:{response_type} where response_type is confirm|alt_N|another
        parts = callback_data.split(":")
        if len(parts) < 3:
            logger.error(f"Invalid clarification callback data: {callback_data}")
            await query.edit_message_text(t("something_went_wrong_generic", locale=locale))
            return

        action_id = parts[1]
        response_type = parts[2]  # confirm, alt_N, or another

        # Retrieve the pending action from user_data
        pending_actions = context.user_data.get(PENDING_ACTIONS_KEY, {})
        pending_data = pending_actions.get(action_id)

        if not pending_data:
            logger.warning(f"No pending action found for action_id: {action_id}")
            await query.edit_message_text(t("expired_action", locale=locale))
            return

        if response_type == "confirm":
            # User confirmed - execute the original action with original parameters
            original_action = pending_data.get("original_action")
            if original_action and isinstance(original_action, ParsedAction):
                action_result = await self.assistant_service.execute_action(
                    original_action, user
                )
                create_actions = {ActionType.CREATE_REMINDER, ActionType.CREATE_TASK, ActionType.SCHEDULE_MEETING}
                if original_action.action_type in create_actions:
                    message = action_result.message if action_result.success else f"❌ {action_result.message}"
                else:
                    emoji = "✅" if action_result.success else "❌"
                    message = f"{emoji} {action_result.message}"

                # Add edit keyboard for successful reminder creation
                keyboard = None
                if action_result.success and original_action.action_type == ActionType.CREATE_REMINDER:
                    reminder_id = action_result.data.get("reminder_id")
                    if reminder_id:
                        keyboard = self.keyboards.create_reminder_created_keyboard(reminder_id, locale=locale)

                await query.edit_message_text(message, reply_markup=keyboard)
            else:
                logger.error(f"Invalid original_action for action_id: {action_id}")
                await query.edit_message_text(t("something_went_wrong_generic", locale=locale))

        elif response_type.startswith("alt_"):
            # User selected an alternative action: alt_0, alt_1, etc.
            try:
                alt_index = int(response_type[4:])  # Extract index from alt_N
            except ValueError:
                await query.edit_message_text(t("invalid_action", locale=locale))
                return

            alternatives = pending_data.get("alternatives")
            original_input = pending_data.get("original_input")

            # alt_0 corresponds to alternatives[1], alt_1 to alternatives[2], etc.
            # (alternatives[0] is the primary action that was shown as "confirm")
            actual_index = alt_index + 1

            if not alternatives or actual_index < 1 or actual_index >= len(alternatives):
                await query.edit_message_text(t("describe_what_to_do", locale=locale))
                return

            selected_action_type, _ = alternatives[actual_index]

            # Re-resolve with the selected action type
            if original_input:
                # Extract parameters for the new action type
                parameters = await self.intent_resolver.parameter_extractor.extract(
                    original_input, selected_action_type
                )

                # Create new intent with high confidence (user explicitly chose this)
                new_intent = ActionIntent(
                    action_type=selected_action_type,
                    confidence=1.0,
                    original_input=original_input,
                )

                # Create the action
                new_action = ParsedAction(
                    intent=new_intent,
                    parameters=parameters,
                    user_id=user.telegram_id,
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    status=ActionStatus.PENDING,
                )

                # Execute it
                action_result = await self.assistant_service.execute_action(new_action, user)
                create_actions = {ActionType.CREATE_REMINDER, ActionType.CREATE_TASK, ActionType.SCHEDULE_MEETING}
                if selected_action_type in create_actions:
                    message = action_result.message if action_result.success else f"❌ {action_result.message}"
                else:
                    emoji = "✅" if action_result.success else "❌"
                    message = f"{emoji} {action_result.message}"

                # Add edit keyboard for successful reminder creation
                keyboard = None
                if action_result.success and selected_action_type == ActionType.CREATE_REMINDER:
                    reminder_id = action_result.data.get("reminder_id")
                    if reminder_id:
                        keyboard = self.keyboards.create_reminder_created_keyboard(reminder_id, locale=locale)

                await query.edit_message_text(message, reply_markup=keyboard)
            else:
                await query.edit_message_text(t("describe_what_to_do", locale=locale))

        elif response_type == "another":
            # User wants to do something else
            await query.edit_message_text(t("no_problem", locale=locale))

        else:
            logger.warning(f"Unknown clarification response type: {response_type}")
            await query.edit_message_text(t("try_again", locale=locale))

        # Clean up the pending action
        if action_id in pending_actions:
            del pending_actions[action_id]

    async def _handle_param_option(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
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
        option_part = parts[2]  # option_N

        if not option_part.startswith("option_"):
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        try:
            option_index = int(option_part[7:])  # Extract N from option_N
        except ValueError:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        # Retrieve the pending action from user_data
        pending_actions = context.user_data.get(PENDING_ACTIONS_KEY, {})
        pending_data = pending_actions.get(action_id)

        if not pending_data:
            await query.edit_message_text(t("expired_action", locale=locale))
            return

        # Get the clarification options to find what the user selected
        clarification = pending_data.get("clarification")
        if not clarification or option_index >= len(clarification.options):
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        # Get the selected option's text (this is what we'll use as the parameter value)
        selected_option = clarification.options[option_index]
        selected_text = selected_option.text

        # Process the selected option as if user typed it
        original_action = pending_data.get("original_action")
        if original_action and isinstance(original_action, ParsedAction):
            # Update the missing parameter with the selected option
            param_name = clarification.parameter
            original_action.parameters[param_name] = selected_text

            # Execute the action
            action_result = await self.assistant_service.execute_action(original_action, user)
            create_actions = {ActionType.CREATE_REMINDER, ActionType.CREATE_TASK, ActionType.SCHEDULE_MEETING}
            if original_action.action_type in create_actions:
                message = action_result.message if action_result.success else f"❌ {action_result.message}"
            else:
                emoji = "✅" if action_result.success else "❌"
                message = f"{emoji} {action_result.message}"

            # Add edit keyboard for successful reminder creation
            keyboard = None
            if action_result.success and original_action.action_type == ActionType.CREATE_REMINDER:
                reminder_id = action_result.data.get("reminder_id")
                if reminder_id:
                    keyboard = self.keyboards.create_reminder_created_keyboard(reminder_id, locale=locale)

            await query.edit_message_text(message, reply_markup=keyboard)
        else:
            await query.edit_message_text(t("expired_action", locale=locale))

        # Clean up the pending action
        if action_id in pending_actions:
            del pending_actions[action_id]

    async def _handle_quick_action(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        callback_data: str,
    ) -> None:
        """Handle quick actions for ambiguous input (help, summary)."""
        locale = user.preferences.language

        # Parse: quick:{action}
        action = callback_data[6:]  # Remove "quick:" prefix

        if action == "help":
            # Create a help action and execute it
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
            # Create a summary action and execute it
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

    async def _handle_timezone_region(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        region: str,
    ) -> None:
        """Handle timezone region selection."""
        locale = user.preferences.language

        if region == "back":
            # Go back to region selection
            await query.edit_message_text(
                t("select_region", locale=locale),
                reply_markup=self.keyboards.create_timezone_region_keyboard(),
            )
        else:
            # Show timezones for the selected region
            await query.edit_message_text(
                t("select_timezone", locale=locale),
                reply_markup=self.keyboards.create_timezone_keyboard(region),
            )

    async def _handle_timezone_selection(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        timezone: str,
    ) -> None:
        """Handle timezone selection."""
        locale = user.preferences.language

        # Update user's timezone
        updated_user = await self.user_service.update_timezone(user.id, timezone)

        if not updated_user:
            await query.edit_message_text(t("update_failed", locale=locale))
            return

        # Check if this is during onboarding
        onboarding_state = context.user_data.get(ONBOARDING_STATE_KEY)

        if onboarding_state and onboarding_state.get("step") == "timezone":
            # Complete onboarding
            del context.user_data[ONBOARDING_STATE_KEY]

            completion_message = t("onboarding_complete", locale=locale, timezone=timezone)
            await query.edit_message_text(completion_message)
        else:
            # Regular settings update - go back to settings menu
            await query.edit_message_text(
                t("timezone_updated", locale=locale, timezone=timezone),
                reply_markup=self.keyboards.create_settings_keyboard(
                    current_timezone=timezone,
                    current_language=user.preferences.language,
                ),
            )

    async def _handle_language_selection(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        language: str,
    ) -> None:
        """Handle language selection."""
        # Update user's language
        updated_user = await self.user_service.update_language(user.id, language)

        if not updated_user:
            await query.edit_message_text(t("update_failed", locale=user.preferences.language))
            return

        # Use the NEW language for the confirmation message
        locale = language

        # Map language codes to display names
        language_names = {
            "en": "English",
            "ru": "Русский",
        }
        lang_display = language_names.get(language, language)

        # Go back to settings menu
        await query.edit_message_text(
            t("language_updated", locale=locale, language=lang_display),
            reply_markup=self.keyboards.create_settings_keyboard(
                current_timezone=user.preferences.timezone,
                current_language=language,
            ),
        )

    async def _handle_settings_callback(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        setting: str,
    ) -> None:
        """Handle settings menu callbacks."""
        locale = user.preferences.language

        if setting == "timezone":
            # Show timezone region selection
            await query.edit_message_text(
                t("select_region", locale=locale),
                reply_markup=self.keyboards.create_timezone_region_keyboard(),
            )
        elif setting == "language":
            # Show language selection
            await query.edit_message_text(
                t("select_language", locale=locale),
                reply_markup=self.keyboards.create_language_keyboard(),
            )
        elif setting == "back":
            # Go back to settings menu
            await query.edit_message_text(
                t("settings_title", locale=locale, name=user.display_name),
                reply_markup=self.keyboards.create_settings_keyboard(
                    current_timezone=user.preferences.timezone,
                    current_language=user.preferences.language,
                ),
            )
        elif setting == "done":
            # Close settings menu
            await query.edit_message_text(
                t("settings_saved", locale=locale, timezone=user.preferences.timezone, language=user.preferences.language)
            )

    async def _handle_time_adjustment(
        self,
        query,
        context: ContextTypes.DEFAULT_TYPE,
        user,
        callback_data: str,
    ) -> None:
        """Handle quick time adjustment callbacks."""
        locale = user.preferences.language
        timezone = user.preferences.timezone

        # Parse: adjust_time:{reminder_id}:{minutes}
        parts = callback_data.split(":")
        if len(parts) != 3:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        reminder_id = parts[1]
        try:
            minutes = int(parts[2])
            item_uuid = UUID(reminder_id)
        except ValueError:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return

        # Apply the adjustment
        reminder = await self.reminder_service.adjust_time(item_uuid, minutes)
        if reminder:
            new_time = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
            message = t("time_updated", locale=locale, new_time=new_time)
            keyboard = self.keyboards.create_reminder_created_keyboard(reminder_id, locale=locale)
            await query.edit_message_text(message, reply_markup=keyboard)
        else:
            await query.edit_message_text(t("reminder_not_found", locale=locale))

    async def handle_pending_edit(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user,
    ) -> bool:
        """
        Handle text input for pending edits (title or time).

        Returns True if a pending edit was processed, False otherwise.
        """
        pending_edit = context.user_data.get(PENDING_EDIT_KEY)
        if not pending_edit:
            return False

        locale = user.preferences.language
        timezone = user.preferences.timezone
        text = update.message.text.strip()

        edit_type = pending_edit.get("type")
        reminder_id = pending_edit.get("reminder_id")

        try:
            item_uuid = UUID(reminder_id)
        except ValueError:
            del context.user_data[PENDING_EDIT_KEY]
            return False

        if edit_type == "title":
            # Update the title
            reminder = await self.reminder_service.update_title(item_uuid, text)
            if reminder:
                time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
                message = t("title_updated", locale=locale, new_title=text)
                message += f"\n\n{t('reminder_created', locale=locale, title=reminder.title, time=time_str)}"
                keyboard = self.keyboards.create_reminder_created_keyboard(reminder_id, locale=locale)
                await update.message.reply_text(message, reply_markup=keyboard)
            else:
                await update.message.reply_text(t("reminder_not_found", locale=locale))

        elif edit_type == "time":
            # Parse and update the time
            current_time = pending_edit.get("current_time")
            new_time = parse_time_adjustment(text, current_time)

            if new_time:
                reminder = await self.reminder_service.update_remind_at(item_uuid, new_time)
                if reminder:
                    time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
                    message = t("time_updated", locale=locale, new_time=time_str)
                    keyboard = self.keyboards.create_reminder_created_keyboard(reminder_id, locale=locale)
                    await update.message.reply_text(message, reply_markup=keyboard)
                else:
                    await update.message.reply_text(t("reminder_not_found", locale=locale))
            else:
                await update.message.reply_text(t("invalid_time_format", locale=locale))
                return True  # Keep the pending edit active

        # Clear the pending edit
        del context.user_data[PENDING_EDIT_KEY]
        return True
