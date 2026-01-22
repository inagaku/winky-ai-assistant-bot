"""Conversation handler for reminder editing flow.

This conversation is entered via CALLBACKS only (not text messages).
Text messages go through MessageHandler which resolves intent and executes actions.

State flow:
    Entry (SELECT) → SELECTING → [Edit][OK] (Delete is handled by Delete flow)
                               → Edit → MENU → [Change Time][Edit Title][Save]
                                             → AWAITING_TIME/TITLE → MENU
                                             → Save → SELECTING
                               → OK → END
"""
import logging
from uuid import UUID

from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler as TelegramMessageHandler,
    filters,
    ContextTypes,
)

from app.bot.keyboards import InlineKeyboards
from app.bot.user_cache import get_cached_user
from app.i18n import t
from app.models import ReminderFlow
from app.services import UserService, ReminderService
from app.utils import format_datetime, DateTimeParser, time_utils
from .states import ReminderEditState

logger = logging.getLogger(__name__)

# Key for storing reminder data in context.user_data during conversation
REMINDER_EDIT_CONV_KEY = "reminder_edit_conv"

# Shortcuts for cleaner code
EditAction = ReminderFlow.Edit.Action
EditTimeAction = ReminderFlow.EditTime.Action
DeleteAction = ReminderFlow.Delete.Action


class ReminderEditConversation:
    """Handle reminder editing flow (entered via callbacks only).

    Callback format: reminder:edit:{action}:{id}

    This conversation handles the Edit flow. The Delete flow is handled
    separately by the callback handler (immediate action, no conversation).
    """

    def __init__(
        self,
        user_service: UserService,
        reminder_service: ReminderService,
        openai_api_key: str
    ):
        self.user_service = user_service
        self.reminder_service = reminder_service
        self.keyboards = InlineKeyboards()
        self.datetime_parser = DateTimeParser(openai_api_key)

    def get_handler(self) -> ConversationHandler:
        """Build and return the ConversationHandler for reminder editing."""
        return ConversationHandler(
            # Entry points - OK, MENU, and DELETE can start the conversation
            entry_points=[
                # OK action → END (user confirmed without editing)
                CallbackQueryHandler(
                    self.handle_ok,
                    pattern=ReminderFlow.Edit.pattern(EditAction.OK)
                ),
                # MENU action → MENU state (user clicked Edit)
                CallbackQueryHandler(
                    self.enter_menu,
                    pattern=ReminderFlow.Edit.pattern(EditAction.MENU)
                ),
                # DELETE action → END (delete reminder) - uses Delete flow
                CallbackQueryHandler(
                    self.handle_delete,
                    pattern=ReminderFlow.Delete.pattern(DeleteAction.CONFIRM)
                ),
            ],
            states={
                ReminderEditState.SELECTED: [
                    # Edit button → MENU state
                    CallbackQueryHandler(
                        self.enter_menu,
                        pattern=ReminderFlow.Edit.pattern(EditAction.MENU)
                    ),
                    # OK button → END
                    CallbackQueryHandler(
                        self.handle_ok,
                        pattern=ReminderFlow.Edit.pattern(EditAction.OK)
                    ),
                    # Delete button → END (uses Delete flow callback)
                    CallbackQueryHandler(
                        self.handle_delete,
                        pattern=ReminderFlow.Delete.pattern(DeleteAction.CONFIRM)
                    ),
                ],
                ReminderEditState.MENU: [
                    # Change time button → TIME_MENU
                    CallbackQueryHandler(
                        self.enter_time_menu,
                        pattern=ReminderFlow.Edit.pattern(EditAction.EDIT_TIME)
                    ),
                    # Edit title button → AWAITING_TITLE
                    CallbackQueryHandler(
                        self.start_edit_title,
                        pattern=ReminderFlow.Edit.pattern(EditAction.EDIT_TITLE)
                    ),
                    # Save button → SELECTING
                    CallbackQueryHandler(
                        self.handle_save,
                        pattern=ReminderFlow.Edit.pattern(EditAction.SAVE)
                    ),
                ],
                ReminderEditState.TIME_MENU: [
                    # [Enter time] → AWAITING_TIME
                    CallbackQueryHandler(
                        self.start_edit_time,
                        pattern=ReminderFlow.EditTime.pattern(EditTimeAction.CUSTOM)
                    ),
                    # [30m earlier][30m later][1h earlier][1h later] → END
                    CallbackQueryHandler(
                        self.handle_time_preset,
                        pattern=ReminderFlow.EditTime.pattern()
                    )
                ],
                ReminderEditState.AWAITING_TIME: [
                    # Text input for new time
                    TelegramMessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.handle_time_input,
                    ),
                ],
                ReminderEditState.AWAITING_TITLE: [
                    # Text input for new title
                    TelegramMessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.handle_title_input,
                    ),
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.handle_cancel, pattern="^cancel$"),
            ],
            per_user=True,
            per_chat=True,
            name="reminder_edit_conversation",
            persistent=False,
            allow_reentry=True,
        )

    async def _get_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user from cache or fetch from DB."""
        return await get_cached_user(update, context, self.user_service)

    def _extract_reminder_id(self, callback_data: str) -> str | None:
        """Extract reminder_id from callback_data like 'reminder:edit:select:{id}'."""
        parsed = ReminderFlow.parse(callback_data)
        if parsed:
            return parsed[2]  # (flow, action, id) -> id
        return None

    async def _get_reminder_or_error(self, query, reminder_id: str, locale: str):
        """Get reminder by ID or show error message."""
        try:
            reminder = await self.reminder_service.get_reminder(UUID(reminder_id))
        except ValueError:
            await query.edit_message_text(t("invalid_id", locale=locale))
            return None

        if not reminder:
            await query.edit_message_text(t("reminder_not_found", locale=locale))
            return None

        return reminder

    async def enter_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User clicked 'Edit' → show MENU state."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, context)
        locale = user.preferences.language
        timezone = user.preferences.timezone

        reminder_id = self._extract_reminder_id(query.data)
        if not reminder_id:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return ConversationHandler.END

        reminder = context.user_data.get(REMINDER_EDIT_CONV_KEY)
        if not reminder or (reminder_id != str(reminder.id)):
            reminder = await self._get_reminder_or_error(query, reminder_id, locale)
            if not reminder:
                return ConversationHandler.END

            # Update stored reminder
            context.user_data[REMINDER_EDIT_CONV_KEY] = reminder

        # Show reminder with MENU keyboard
        time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
        message = t("reminder_editing", locale=locale, title=reminder.title, time=time_str)
        keyboard = self.keyboards.create_reminder_edit_menu_keyboard(str(reminder.id), locale=locale)
        await query.edit_message_text(message, reply_markup=keyboard)

        return ReminderEditState.MENU

    async def handle_ok(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User clicked OK → keep message, remove keyboard, end."""
        query = update.callback_query
        await query.answer()

        # Remove keyboard, keep message
        await query.edit_message_reply_markup(reply_markup=None)

        # Clean up
        context.user_data.pop(REMINDER_EDIT_CONV_KEY, None)

        return ConversationHandler.END

    async def handle_delete(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User clicked Delete → delete reminder, end.

        Note: Uses Delete flow callback (reminder:delete:confirm:{id})
        but handled within this conversation for UX continuity.
        """
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, context)
        locale = user.preferences.language

        # Parse Delete flow callback
        reminder_id = self._extract_reminder_id(query.data)
        if not reminder_id:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return ConversationHandler.END

        try:
            deleted = await self.reminder_service.delete_reminder(UUID(reminder_id))
        except ValueError:
            await query.edit_message_text(t("invalid_id", locale=locale))
            return ConversationHandler.END

        if deleted:
            await query.edit_message_text(f"🗑️ {t('reminder_deleted', locale=locale)}")
        else:
            await query.edit_message_text(t("reminder_not_found", locale=locale))

        # Clean up
        context.user_data.pop(REMINDER_EDIT_CONV_KEY, None)

        return ConversationHandler.END

    # --- MENU State ---
    async def enter_time_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User clicked 'Change Time' → prompt for new time."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, context)
        locale = user.preferences.language
        timezone = user.preferences.timezone

        reminder_id = self._extract_reminder_id(query.data)
        if not reminder_id:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return ConversationHandler.END

        reminder = context.user_data.get(REMINDER_EDIT_CONV_KEY)
        if not reminder or (reminder_id != str(reminder.id)):
            reminder = await self._get_reminder_or_error(query, reminder_id, locale)
            if not reminder:
                return ConversationHandler.END

            # Update stored reminder
            context.user_data[REMINDER_EDIT_CONV_KEY] = reminder

        # Show reminder with SELECT keyboard
        time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
        message = t("change_time_prompt", locale=locale, time=time_str)
        keyboard = self.keyboards.create_reminder_edit_time_menu_keyboard(str(reminder.id), locale=locale)
        await query.edit_message_text(message, reply_markup=keyboard)

        return ReminderEditState.TIME_MENU

    async def start_edit_time(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User clicked 'Edit Title' → prompt for new title."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, context)
        locale = user.preferences.language

        reminder_id = self._extract_reminder_id(query.data)
        if not reminder_id:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return ConversationHandler.END

        reminder = context.user_data.get(REMINDER_EDIT_CONV_KEY)
        if not reminder or (reminder_id != str(reminder.id)):
            reminder = await self._get_reminder_or_error(query, reminder_id, locale)
            if not reminder:
                return ConversationHandler.END

            # Update stored reminder
            context.user_data[REMINDER_EDIT_CONV_KEY] = reminder

        await query.edit_message_text(
            t("enter_new_time", locale=locale)
        )

        return ReminderEditState.AWAITING_TIME

    async def handle_time_preset(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User clicked 'Change Time' → prompt for new time."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, context)
        locale = user.preferences.language
        timezone = user.preferences.timezone

        reminder_id = self._extract_reminder_id(query.data)
        if not reminder_id:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return ConversationHandler.END

        reminder = context.user_data.get(REMINDER_EDIT_CONV_KEY)
        if not reminder or (reminder_id != str(reminder.id)):
            reminder = await self._get_reminder_or_error(query, reminder_id, locale)
            if not reminder:
                return ConversationHandler.END

            # Update stored reminder
            context.user_data[REMINDER_EDIT_CONV_KEY] = reminder

        _, time_preset, _ = ReminderFlow.parse(query.data)
        time_delta = time_utils.get_time_delta(time_preset)
        new_time = reminder.remind_at + time_delta

        try:
            reminder = await self.reminder_service.update_remind_at(reminder.id, new_time)
            context.user_data[REMINDER_EDIT_CONV_KEY] = reminder
        except ValueError:
            await update.message.reply_text(t("invalid_id", locale=locale))
            return ConversationHandler.END

        if not reminder:
            await update.message.reply_text(t("reminder_not_found", locale=locale))
            return ConversationHandler.END

        # Show reminder with MENU keyboard
        time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
        message = t("time_updated", locale=locale, new_time=time_str)
        message += f"\n\n{t('reminder_editing', locale=locale, title=reminder.title, time=time_str)}"
        keyboard = self.keyboards.create_reminder_edit_menu_keyboard(str(reminder.id), locale=locale)
        await query.edit_message_text(message, reply_markup=keyboard)

        return ReminderEditState.MENU

    # --- Text Input Handlers ---

    async def handle_time_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User typed a time value."""
        text = update.message.text.strip()
        user = await self._get_user(update, context)
        locale = user.preferences.language
        timezone = user.preferences.timezone

        reminder = context.user_data.get(REMINDER_EDIT_CONV_KEY)
        if not reminder:
            await update.message.reply_text(t("expired_action", locale=locale))
            return ConversationHandler.END

        # Parse the time input (supports relative: "1 hour earlier", absolute: "3pm")
        new_time, _, _ = await self.datetime_parser.parse(text, reminder.remind_at, timezone)

        if not new_time:
            await update.message.reply_text(t("invalid_time_format", locale=locale))
            return ReminderEditState.AWAITING_TIME  # Stay in same state

        try:
            reminder = await self.reminder_service.update_remind_at(reminder.id, new_time)
            context.user_data[REMINDER_EDIT_CONV_KEY] = reminder

        except ValueError:
            await update.message.reply_text(t("invalid_id", locale=locale))
            return ConversationHandler.END

        if not reminder:
            await update.message.reply_text(t("reminder_not_found", locale=locale))
            return ConversationHandler.END

        # Show success and MENU keyboard
        time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
        message = t("time_updated", locale=locale, new_time=time_str)
        message += f"\n\n{t('reminder_editing', locale=locale, title=reminder.title, time=time_str)}"
        keyboard = self.keyboards.create_reminder_edit_menu_keyboard(str(reminder.id), locale=locale)
        await update.message.reply_text(message, reply_markup=keyboard)

        return ReminderEditState.MENU

    async def start_edit_title(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User clicked 'Edit Title' → prompt for new title."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, context)
        locale = user.preferences.language

        reminder_id = self._extract_reminder_id(query.data)
        if not reminder_id:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return ConversationHandler.END

        reminder = context.user_data.get(REMINDER_EDIT_CONV_KEY)
        if not reminder or (reminder_id != str(reminder.id)):
            reminder = await self._get_reminder_or_error(query, reminder_id, locale)
            if not reminder:
                return ConversationHandler.END

            # Update stored reminder
            context.user_data[REMINDER_EDIT_CONV_KEY] = reminder

        await query.edit_message_text(
            t("enter_new_title", locale=locale, current_title=reminder.title)
        )

        return ReminderEditState.AWAITING_TITLE

    async def handle_title_input(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User provided a new title."""
        new_title = update.message.text.strip()
        user = await self._get_user(update, context)
        locale = user.preferences.language
        timezone = user.preferences.timezone

        reminder = context.user_data.get(REMINDER_EDIT_CONV_KEY)
        if not reminder:
            await update.message.reply_text(t("expired_action", locale=locale))
            return ConversationHandler.END


        try:
            reminder = await self.reminder_service.update_title(reminder.id, new_title)
            context.user_data[REMINDER_EDIT_CONV_KEY] = reminder

        except ValueError:
            await update.message.reply_text(t("invalid_id", locale=locale))
            return ConversationHandler.END

        if not reminder:
            await update.message.reply_text(t("reminder_not_found", locale=locale))
            return ConversationHandler.END

        # Show success and MENU keyboard
        time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
        message = t("title_updated", locale=locale, new_title=new_title)
        message += f"\n\n{t('reminder_editing', locale=locale, title=reminder.title, time=time_str)}"
        keyboard = self.keyboards.create_reminder_edit_menu_keyboard(str(reminder.id), locale=locale)
        await update.message.reply_text(message, reply_markup=keyboard)

        return ReminderEditState.MENU

    async def handle_save(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User clicked 'Save' → go back to SELECTING state."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, context)
        locale = user.preferences.language
        timezone = user.preferences.timezone

        reminder_id = self._extract_reminder_id(query.data)
        if not reminder_id:
            await query.edit_message_text(t("invalid_action", locale=locale))
            return ConversationHandler.END

        reminder = context.user_data.get(REMINDER_EDIT_CONV_KEY)
        if not reminder or (reminder_id != str(reminder.id)):
            reminder = await self._get_reminder_or_error(query, reminder_id, locale)
            if not reminder:
                return ConversationHandler.END

            # Update stored reminder
            context.user_data[REMINDER_EDIT_CONV_KEY] = reminder

        # Show SELECTING state with [Edit][OK][Delete]
        time_str = format_datetime(reminder.remind_at, locale=locale, timezone=timezone)
        message = t("reminder_created", locale=locale, title=reminder.title, time=time_str)
        keyboard = self.keyboards.create_reminder_selected_keyboard(str(reminder.id), locale=locale)
        await query.edit_message_text(message, reply_markup=keyboard)

        return ReminderEditState.SELECTED

    # --- Fallbacks ---

    async def handle_cancel(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User cancelled."""
        query = update.callback_query
        if query:
            await query.answer()
            user = await self._get_user(update, context)
            locale = user.preferences.language
            await query.edit_message_text(t("cancelled", locale=locale))

        # Clean up
        context.user_data.pop(REMINDER_EDIT_CONV_KEY, None)

        return ConversationHandler.END
