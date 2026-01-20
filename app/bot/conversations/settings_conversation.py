"""Conversation handler for settings and onboarding flow."""

import logging

from telegram import Update
from telegram.ext import (
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler as TelegramCommandHandler,
    ContextTypes,
)

from app.models import CallbackPrefix
from app.services import UserService
from app.bot.keyboards import InlineKeyboards
from app.i18n import t
from app.bot.user_cache import get_cached_user, update_cached_user

from .states import SettingsState

logger = logging.getLogger(__name__)

# Key for tracking if this is onboarding
ONBOARDING_KEY = "is_onboarding"


class SettingsConversation:
    """Handle settings and onboarding flow."""

    def __init__(self, user_service: UserService):
        self.user_service = user_service
        self.keyboards = InlineKeyboards()

    def get_handler(self) -> ConversationHandler:
        """Build and return the ConversationHandler."""
        return ConversationHandler(
            entry_points=[
                TelegramCommandHandler("settings", self.start_settings),
            ],
            states={
                SettingsState.MAIN_MENU: [
                    CallbackQueryHandler(
                        self.show_timezone_regions,
                        pattern=f"^{CallbackPrefix.SETTINGS.value}:timezone$"
                    ),
                    CallbackQueryHandler(
                        self.show_languages,
                        pattern=f"^{CallbackPrefix.SETTINGS.value}:language$"
                    ),
                    CallbackQueryHandler(
                        self.done,
                        pattern=f"^{CallbackPrefix.SETTINGS.value}:done$"
                    ),
                ],
                SettingsState.SELECTING_REGION: [
                    CallbackQueryHandler(
                        self.select_region,
                        pattern=f"^{CallbackPrefix.TZ_REGION.value}:.+$"
                    ),
                ],
                SettingsState.SELECTING_TIMEZONE: [
                    CallbackQueryHandler(
                        self.select_timezone,
                        pattern=f"^{CallbackPrefix.TZ.value}:.+$"
                    ),
                    CallbackQueryHandler(
                        self.back_to_regions,
                        pattern=f"^{CallbackPrefix.TZ_REGION.value}:back$"
                    ),
                ],
                SettingsState.SELECTING_LANGUAGE: [
                    CallbackQueryHandler(
                        self.select_language,
                        pattern=f"^{CallbackPrefix.LANG.value}:.+$"
                    ),
                    CallbackQueryHandler(
                        self.back_to_settings,
                        pattern=f"^{CallbackPrefix.SETTINGS.value}:back$"
                    ),
                ],
            },
            fallbacks=[
                CallbackQueryHandler(self.cancel, pattern="^cancel$"),
            ],
            per_user=True,
            per_chat=True,
            name="settings_conversation",
            persistent=False,
            allow_reentry=True,
        )

    def get_onboarding_handler(self) -> ConversationHandler:
        """Build handler for onboarding (new user timezone selection)."""
        return ConversationHandler(
            entry_points=[
                # Onboarding is triggered by /start for new users
                # This is handled separately in command_handler
                # Entry via callback from welcome message
                CallbackQueryHandler(
                    self.onboarding_select_region,
                    pattern=f"^{CallbackPrefix.TZ_REGION.value}:.+$"
                ),
            ],
            states={
                SettingsState.SELECTING_REGION: [
                    CallbackQueryHandler(
                        self.onboarding_select_region,
                        pattern=f"^{CallbackPrefix.TZ_REGION.value}:.+$"
                    ),
                ],
                SettingsState.SELECTING_TIMEZONE: [
                    CallbackQueryHandler(
                        self.onboarding_select_timezone,
                        pattern=f"^{CallbackPrefix.TZ.value}:.+$"
                    ),
                    CallbackQueryHandler(
                        self.onboarding_back_to_regions,
                        pattern=f"^{CallbackPrefix.TZ_REGION.value}:back$"
                    ),
                ],
            },
            fallbacks=[],
            per_user=True,
            per_chat=True,
            name="onboarding_conversation",
            persistent=False,
        )

    async def _get_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user from cache or fetch from DB."""
        return await get_cached_user(update, context, self.user_service)

    # --- Main Settings Flow ---

    async def start_settings(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Entry point for /settings command."""
        user = await self._get_user(update, callback_context)
        locale = user.preferences.language

        await update.message.reply_text(
            t("settings_title", locale=locale, name=user.display_name),
            reply_markup=self.keyboards.create_settings_keyboard(
                current_timezone=user.preferences.timezone,
                current_language=user.preferences.language,
                locale=locale,
            ),
        )
        return SettingsState.MAIN_MENU

    async def show_timezone_regions(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Show timezone region selection."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)
        locale = user.preferences.language

        await query.edit_message_text(
            t("select_region", locale=locale),
            reply_markup=self.keyboards.create_timezone_region_keyboard(),
        )
        return SettingsState.SELECTING_REGION

    async def select_region(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Handle region selection."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)
        locale = user.preferences.language

        # Extract region: tz_region:{region}
        region = query.data.split(":")[1]

        if region == "back":
            # Back to settings menu
            await query.edit_message_text(
                t("settings_title", locale=locale, name=user.display_name),
                reply_markup=self.keyboards.create_settings_keyboard(
                    current_timezone=user.preferences.timezone,
                    current_language=user.preferences.language,
                    locale=locale,
                ),
            )
            return SettingsState.MAIN_MENU

        await query.edit_message_text(
            t("select_timezone", locale=locale),
            reply_markup=self.keyboards.create_timezone_keyboard(region, locale=locale),
        )
        return SettingsState.SELECTING_TIMEZONE

    async def select_timezone(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Handle timezone selection."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)

        # Extract timezone: tz:{timezone}
        timezone = query.data.split(":", 1)[1]

        # Update user timezone
        updated_user = await self.user_service.update_timezone(user.id, timezone)
        if not updated_user:
            locale = user.preferences.language
            await query.edit_message_text(t("update_failed", locale=locale))
            return ConversationHandler.END

        # Update cache with new user data
        update_cached_user(callback_context, updated_user)

        locale = updated_user.preferences.language

        # Go back to settings menu
        await query.edit_message_text(
            t("timezone_updated", locale=locale, timezone=timezone),
            reply_markup=self.keyboards.create_settings_keyboard(
                current_timezone=timezone,
                current_language=updated_user.preferences.language,
                locale=locale,
            ),
        )
        return SettingsState.MAIN_MENU

    async def back_to_regions(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Go back to region selection."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)
        locale = user.preferences.language

        await query.edit_message_text(
            t("select_region", locale=locale),
            reply_markup=self.keyboards.create_timezone_region_keyboard(),
        )
        return SettingsState.SELECTING_REGION

    async def show_languages(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Show language selection."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)
        locale = user.preferences.language

        await query.edit_message_text(
            t("select_language", locale=locale),
            reply_markup=self.keyboards.create_language_keyboard(locale=locale),
        )
        return SettingsState.SELECTING_LANGUAGE

    async def select_language(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Handle language selection."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)

        # Extract language: lang:{code}
        language = query.data.split(":")[1]

        # Update user language
        updated_user = await self.user_service.update_language(user.id, language)
        if not updated_user:
            locale = user.preferences.language
            await query.edit_message_text(t("update_failed", locale=locale))
            return ConversationHandler.END

        # Update cache with new user data
        update_cached_user(callback_context, updated_user)

        # Use new language for response
        locale = language
        language_names = {"en": "English", "ru": "Русский"}
        lang_display = language_names.get(language, language)

        # Go back to settings menu
        await query.edit_message_text(
            t("language_updated", locale=locale, language=lang_display),
            reply_markup=self.keyboards.create_settings_keyboard(
                current_timezone=updated_user.preferences.timezone,
                current_language=language,
                locale=locale,
            ),
        )
        return SettingsState.MAIN_MENU

    async def back_to_settings(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Go back to settings menu."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)
        locale = user.preferences.language

        await query.edit_message_text(
            t("settings_title", locale=locale, name=user.display_name),
            reply_markup=self.keyboards.create_settings_keyboard(
                current_timezone=user.preferences.timezone,
                current_language=user.preferences.language,
                locale=locale,
            ),
        )
        return SettingsState.MAIN_MENU

    async def done(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User finished with settings."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)
        locale = user.preferences.language

        await query.edit_message_text(
            t("settings_saved", locale=locale,
              timezone=user.preferences.timezone,
              language=user.preferences.language)
        )
        return ConversationHandler.END

    async def cancel(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """User cancelled settings."""
        query = update.callback_query
        if query:
            await query.answer()
            user = await self._get_user(update, callback_context)
            locale = user.preferences.language
            await query.edit_message_text(t("cancelled", locale=locale))

        return ConversationHandler.END

    # --- Onboarding Flow ---

    async def onboarding_select_region(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Handle region selection during onboarding."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)
        locale = user.preferences.language

        # Extract region
        region = query.data.split(":")[1]

        await query.edit_message_text(
            t("select_timezone", locale=locale),
            reply_markup=self.keyboards.create_timezone_keyboard(region, locale=locale),
        )
        return SettingsState.SELECTING_TIMEZONE

    async def onboarding_select_timezone(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Handle timezone selection during onboarding."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)

        # Extract timezone
        timezone = query.data.split(":", 1)[1]

        # Update user timezone
        updated_user = await self.user_service.update_timezone(user.id, timezone)
        if not updated_user:
            locale = user.preferences.language
            await query.edit_message_text(t("update_failed", locale=locale))
            return ConversationHandler.END

        # Update cache with new user data
        update_cached_user(callback_context, updated_user)

        locale = updated_user.preferences.language

        # Show onboarding complete message
        await query.edit_message_text(
            t("onboarding_complete", locale=locale, timezone=timezone)
        )
        return ConversationHandler.END

    async def onboarding_back_to_regions(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
    ) -> int:
        """Go back to region selection during onboarding."""
        query = update.callback_query
        await query.answer()

        user = await self._get_user(update, callback_context)
        locale = user.preferences.language

        await query.edit_message_text(
            t("select_region", locale=locale),
            reply_markup=self.keyboards.create_timezone_region_keyboard(),
        )
        return SettingsState.SELECTING_REGION
