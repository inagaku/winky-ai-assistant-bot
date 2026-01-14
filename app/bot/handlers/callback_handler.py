"""Handler for inline keyboard callbacks."""

import logging
from uuid import UUID
from telegram import Update
from telegram.ext import ContextTypes

from app.models import ParsedAction
from app.services import UserService, AssistantService, ReminderService, TaskService
from app.intelligence import IntentResolver
from app.bot.keyboards import InlineKeyboards
from app.i18n import t
from app.utils import format_time
from .message_handler import PENDING_ACTIONS_KEY
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
            emoji = "✅" if action_result.success else "❌"
            await query.edit_message_text(f"{emoji} {action_result.message}")
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
            # Delete a task
            deleted = await self.task_service.delete_task(item_uuid)
            if deleted:
                await query.edit_message_text(f"🗑️ {t('task_deleted', locale=locale)}")
            else:
                await query.edit_message_text(t("task_not_found", locale=locale))

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

        # Parse: clarify:{action_id}:{option_index}:{response_type}
        parts = callback_data.split(":")
        if len(parts) < 4:
            logger.error(f"Invalid clarification callback data: {callback_data}")
            await query.edit_message_text(t("something_went_wrong_generic", locale=locale))
            return

        action_id = parts[1]
        response_type = parts[3]  # confirm, alt, or cancel

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
                emoji = "✅" if action_result.success else "❌"
                await query.edit_message_text(f"{emoji} {action_result.message}")
            else:
                logger.error(f"Invalid original_action for action_id: {action_id}")
                await query.edit_message_text(t("something_went_wrong_generic", locale=locale))

        elif response_type == "alt":
            # User selected an alternative action
            # For now, ask them to rephrase
            await query.edit_message_text(t("describe_what_to_do", locale=locale))

        elif response_type == "cancel":
            # User wants to cancel or do something else
            await query.edit_message_text(t("no_problem", locale=locale))

        else:
            logger.warning(f"Unknown clarification response type: {response_type}")
            await query.edit_message_text(t("try_again", locale=locale))

        # Clean up the pending action
        if action_id in pending_actions:
            del pending_actions[action_id]

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
