"""Inline keyboard builders for Telegram bot."""

from typing import List, Optional, Union
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import t
from app.models import (
    CallbackPrefix,
    ClarificationOption,
    ReminderFlow,
)


class InlineKeyboards:
    """Build inline keyboards for various scenarios."""
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

    # --- Reminder Keyboards (using hierarchical ReminderFlow) ---
    def create_reminder_notification_keyboard(
        self,
        reminder_id: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create buttons for reminder notification: [Done][Snooze]."""
        Notify = ReminderFlow.Notify
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"⏰ {t('button_change_time', locale=locale)}",
                    callback_data=Notify.callback(Notify.Action.CHANGE_TIME, reminder_id),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"✅ {t('button_done', locale=locale)}",
                    callback_data=Notify.callback(Notify.Action.DONE, reminder_id),
                ),
                InlineKeyboardButton(
                    text=f"😴 {t('button_snooze', locale=locale, minutes=15)}",
                    callback_data=Notify.callback(Notify.Action.SNOOZE, reminder_id),
                )
            ]
        ])

    def create_reminder_selected_keyboard(
        self,
        reminder_id: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create SELECT state keyboard: [Edit][OK][Delete].

        Note: Delete uses Delete flow, not Edit flow.
        """
        Edit = ReminderFlow.Edit
        Delete = ReminderFlow.Delete
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"✏️ {t('button_edit', locale=locale)}",
                    callback_data=Edit.callback(Edit.Action.MENU, reminder_id),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"👌 {t('button_ok', locale=locale)}",
                    callback_data=Edit.callback(Edit.Action.OK, reminder_id),
                ),
                InlineKeyboardButton(
                    text=f"🗑️ {t('button_delete', locale=locale)}",
                    callback_data=Delete.callback(Delete.Action.CONFIRM, reminder_id),
                ),
            ]
        ])

    def create_reminder_edit_menu_keyboard(
        self,
        reminder_id: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create MENU state keyboard: [Change Time][Edit Title][Save]."""
        Edit = ReminderFlow.Edit
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"⏰ {t('button_change_time', locale=locale)}",
                    callback_data=Edit.callback(Edit.Action.EDIT_TIME, reminder_id),
                ),
                InlineKeyboardButton(
                    text=f"✏️ {t('button_edit_title', locale=locale)}",
                    callback_data=Edit.callback(Edit.Action.EDIT_TITLE, reminder_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"💾 {t('button_save', locale=locale)}",
                    callback_data=Edit.callback(Edit.Action.SAVE, reminder_id),
                ),
            ],
        ])

    def create_reminder_edit_time_menu_keyboard(
        self,
        reminder_id: str,
        locale: str = "en",
    ) -> InlineKeyboardMarkup:
        """Create MENU state keyboard: [Change Time][Edit Title][Save]."""
        EditTime = ReminderFlow.EditTime
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text=f"⬅️ {t('button_30min_earlier', locale=locale)}",
                    callback_data=EditTime.callback(EditTime.Action.MINUS_30M, reminder_id),
                ),
                InlineKeyboardButton(
                    text=f"➡️ {t('button_30min_later', locale=locale)}",
                    callback_data=EditTime.callback(EditTime.Action.PLUS_30M, reminder_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"⬅️ {t('button_1h_earlier', locale=locale)}",
                    callback_data=EditTime.callback(EditTime.Action.MINUS_1H, reminder_id),
                ),
                InlineKeyboardButton(
                    text=f"➡️ {t('button_1h_later', locale=locale)}",
                    callback_data=EditTime.callback(EditTime.Action.PLUS_1H, reminder_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"✍️ {t('button_enter_time', locale=locale)}",
                    callback_data=EditTime.callback(EditTime.Action.CUSTOM, reminder_id),
                ),
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
