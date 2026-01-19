"""Inline keyboard builders for Telegram bot."""

from typing import List, Optional, Union
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t
from app.models import CallbackPrefix, ClarificationOption


class InlineKeyboards:
    """Build inline keyboards for various scenarios."""

    def create_options_keyboard(
        self,
        options: List[str],
        columns: int = 1,
    ) -> InlineKeyboardMarkup:
        """Create a keyboard with option buttons."""
        buttons = []
        row = []

        for option in options:
            # Truncate long options for callback data
            callback_data = CallbackPrefix.OPTION.format(option[:50])
            button = InlineKeyboardButton(text=option, callback_data=callback_data)
            row.append(button)

            if len(row) >= columns:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        return InlineKeyboardMarkup(buttons)

    def create_clarification_keyboard(
        self,
        options: List[ClarificationOption],
        action_id: str,
        columns: int = 1,
    ) -> InlineKeyboardMarkup:
        """Create a keyboard for clarification with action_id for tracking.

        Args:
            options: List of ClarificationOption with text and callback_data template
            action_id: The action ID to substitute into callback_data templates
            columns: Number of buttons per row
        """
        buttons = []
        row = []

        for option in options:
            # Replace {action_id} placeholder in callback_data template
            callback_data = option.callback_data.format(action_id=action_id)
            button = InlineKeyboardButton(text=option.text, callback_data=callback_data)
            row.append(button)

            if len(row) >= columns:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        return InlineKeyboardMarkup(buttons)

    def create_confirmation_keyboard(
        self,
        locale: str = "en",
        confirm_data: str = "confirm",
        cancel_data: str = "cancel",
    ) -> InlineKeyboardMarkup:
        """Create a simple Yes/No confirmation keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=t("button_yes", locale=locale),
                    callback_data=confirm_data
                ),
                InlineKeyboardButton(
                    text=t("button_cancel", locale=locale),
                    callback_data=cancel_data
                ),
            ]
        ])

    def create_reminder_actions_keyboard(
        self,
        reminder_id: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create action buttons for a reminder notification."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"✅ {t('button_done', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("complete", reminder_id),
                ),
                InlineKeyboardButton(
                    text=f"😴 {t('button_snooze', locale=locale, minutes=15)}",
                    callback_data=CallbackPrefix.ACTION.format("snooze", reminder_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⏰ {t('button_change_time', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("change_time", reminder_id),
                ),
            ],
        ])

    def create_reminder_created_keyboard(
        self,
        reminder_id: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create action buttons shown after reminder creation."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"⏰ {t('button_change_time', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("change_time", reminder_id),
                ),
                InlineKeyboardButton(
                    text=f"✏️ {t('button_edit_title', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("edit_title", reminder_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"👌 {t('button_ok', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("ok", reminder_id),
                ),
                InlineKeyboardButton(
                    text=f"❌ {t('button_cancel_reminder', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("delete", reminder_id),
                ),
            ],
        ])

    def create_time_adjustment_keyboard(
        self,
        reminder_id: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create quick time adjustment options."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=t('button_30min_earlier', locale=locale),
                    callback_data=CallbackPrefix.ADJUST_TIME.format(reminder_id, "-30"),
                ),
                InlineKeyboardButton(
                    text=t('button_30min_later', locale=locale),
                    callback_data=CallbackPrefix.ADJUST_TIME.format(reminder_id, "30"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t('button_1h_earlier', locale=locale),
                    callback_data=CallbackPrefix.ADJUST_TIME.format(reminder_id, "-60"),
                ),
                InlineKeyboardButton(
                    text=t('button_1h_later', locale=locale),
                    callback_data=CallbackPrefix.ADJUST_TIME.format(reminder_id, "60"),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⌨️ {t('button_enter_time', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("enter_time", reminder_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⬅️ {t('button_back', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("back_to_reminder", reminder_id),
                ),
            ],
        ])

    def create_task_actions_keyboard(
        self,
        task_id: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create action buttons for a task."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"✅ {t('button_complete', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("complete", task_id),
                ),
                InlineKeyboardButton(
                    text=f"📝 {t('button_edit', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("edit", task_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🗑️ {t('button_delete', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("delete", task_id),
                ),
            ],
        ])

    def create_meeting_actions_keyboard(
        self,
        meeting_id: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create action buttons for a meeting."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"📝 {t('button_edit', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("edit", meeting_id),
                ),
                InlineKeyboardButton(
                    text=f"❌ {t('button_cancel', locale=locale)}",
                    callback_data=CallbackPrefix.ACTION.format("cancel", meeting_id),
                ),
            ],
        ])

    def create_time_options_keyboard(self) -> InlineKeyboardMarkup:
        """Create quick time selection options."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text="In 1 hour", callback_data=CallbackPrefix.OPTION.format("in 1 hour")),
                InlineKeyboardButton(text="In 2 hours", callback_data=CallbackPrefix.OPTION.format("in 2 hours")),
            ],
            [
                InlineKeyboardButton(text="Tomorrow 9am", callback_data=CallbackPrefix.OPTION.format("tomorrow at 9am")),
                InlineKeyboardButton(text="Tomorrow 2pm", callback_data=CallbackPrefix.OPTION.format("tomorrow at 2pm")),
            ],
            [
                InlineKeyboardButton(text="Next week", callback_data=CallbackPrefix.OPTION.format("next week")),
            ],
        ])

    def create_priority_keyboard(self) -> InlineKeyboardMarkup:
        """Create priority selection keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text="🟢 Low", callback_data=CallbackPrefix.OPTION.format("low")),
                InlineKeyboardButton(text="🟡 Medium", callback_data=CallbackPrefix.OPTION.format("medium")),
            ],
            [
                InlineKeyboardButton(text="🟠 High", callback_data=CallbackPrefix.OPTION.format("high")),
                InlineKeyboardButton(text="🔴 Urgent", callback_data=CallbackPrefix.OPTION.format("urgent")),
            ],
        ])

    def create_timezone_region_keyboard(self) -> InlineKeyboardMarkup:
        """Create timezone region selection keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text="🌎 Americas", callback_data=CallbackPrefix.TZ_REGION.format("americas")),
                InlineKeyboardButton(text="🌍 Europe", callback_data=CallbackPrefix.TZ_REGION.format("europe")),
            ],
            [
                InlineKeyboardButton(text="🌏 Asia", callback_data=CallbackPrefix.TZ_REGION.format("asia")),
                InlineKeyboardButton(text="🌏 Pacific", callback_data=CallbackPrefix.TZ_REGION.format("pacific")),
            ],
            [
                InlineKeyboardButton(text="🌍 Africa", callback_data=CallbackPrefix.TZ_REGION.format("africa")),
            ],
        ])

    def create_timezone_keyboard(
        self,
        region: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create timezone selection keyboard for a specific region."""
        timezones = {
            "americas": [
                ("🇺🇸 New York (EST)", "America/New_York"),
                ("🇺🇸 Chicago (CST)", "America/Chicago"),
                ("🇺🇸 Denver (MST)", "America/Denver"),
                ("🇺🇸 Los Angeles (PST)", "America/Los_Angeles"),
                ("🇧🇷 São Paulo", "America/Sao_Paulo"),
                ("🇲🇽 Mexico City", "America/Mexico_City"),
                ("🇦🇷 Buenos Aires", "America/Argentina/Buenos_Aires"),
            ],
            "europe": [
                ("🇬🇧 London (GMT)", "Europe/London"),
                ("🇫🇷 Paris (CET)", "Europe/Paris"),
                ("🇩🇪 Berlin (CET)", "Europe/Berlin"),
                ("🇳🇱 Amsterdam (CET)", "Europe/Amsterdam"),
                ("🇪🇸 Madrid (CET)", "Europe/Madrid"),
                ("🇮🇹 Rome (CET)", "Europe/Rome"),
                ("🇷🇺 Moscow (MSK)", "Europe/Moscow"),
                ("🇺🇦 Kyiv", "Europe/Kyiv"),
            ],
            "asia": [
                ("🇯🇵 Tokyo (JST)", "Asia/Tokyo"),
                ("🇨🇳 Shanghai (CST)", "Asia/Shanghai"),
                ("🇮🇳 Mumbai (IST)", "Asia/Kolkata"),
                ("🇸🇬 Singapore (SGT)", "Asia/Singapore"),
                ("🇭🇰 Hong Kong", "Asia/Hong_Kong"),
                ("🇰🇷 Seoul", "Asia/Seoul"),
                ("🇦🇪 Dubai", "Asia/Dubai"),
                ("🇮🇱 Tel Aviv", "Asia/Tel_Aviv"),
            ],
            "pacific": [
                ("🇦🇺 Sydney (AEST)", "Australia/Sydney"),
                ("🇦🇺 Melbourne", "Australia/Melbourne"),
                ("🇳🇿 Auckland (NZST)", "Pacific/Auckland"),
                ("🇦🇺 Perth (AWST)", "Australia/Perth"),
            ],
            "africa": [
                ("🇿🇦 Johannesburg", "Africa/Johannesburg"),
                ("🇪🇬 Cairo", "Africa/Cairo"),
                ("🇳🇬 Lagos", "Africa/Lagos"),
                ("🇰🇪 Nairobi", "Africa/Nairobi"),
            ],
        }

        tz_list = timezones.get(region, [])
        buttons = []

        for label, tz_id in tz_list:
            buttons.append([
                InlineKeyboardButton(text=label, callback_data=CallbackPrefix.TZ.format(tz_id))
            ])

        # Add back button
        buttons.append([
            InlineKeyboardButton(
                text=f"⬅️ {t('button_back_to_regions', locale=locale)}",
                callback_data=CallbackPrefix.TZ_REGION.format("back")
            )
        ])

        return InlineKeyboardMarkup(buttons)

    def create_settings_keyboard(
        self,
        current_timezone: str,
        current_language: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create settings menu keyboard."""
        # Map language codes to display names
        language_names = {
            "en": "English",
            "ru": "Русский",
        }
        lang_display = language_names.get(current_language, current_language)

        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"🕐 Timezone: {current_timezone}",
                    callback_data=CallbackPrefix.SETTINGS.format("timezone")
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🌐 Language: {lang_display}",
                    callback_data=CallbackPrefix.SETTINGS.format("language")
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"✅ {t('button_done', locale=locale)}",
                    callback_data=CallbackPrefix.SETTINGS.format("done")
                ),
            ],
        ])

    def create_language_keyboard(
        self,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create language selection keyboard."""
        languages = [
            ("🇬🇧 English", "en"),
            ("🇷🇺 Русский", "ru"),
        ]

        buttons = []
        for label, lang_code in languages:
            buttons.append([
                InlineKeyboardButton(text=label, callback_data=CallbackPrefix.LANG.format(lang_code))
            ])

        # Add back button
        buttons.append([
            InlineKeyboardButton(
                text=f"⬅️ {t('button_back', locale=locale)}",
                callback_data=CallbackPrefix.SETTINGS.format("back")
            )
        ])

        return InlineKeyboardMarkup(buttons)
