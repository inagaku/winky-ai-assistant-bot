"""Inline keyboard builders for Telegram bot."""

from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


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
            callback_data = f"option:{option[:50]}"
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
        options: List[str],
        action_id: str,
        columns: int = 1,
    ) -> InlineKeyboardMarkup:
        """Create a keyboard for clarification with action_id for tracking."""
        buttons = []
        row = []

        for i, option in enumerate(options):
            # Format: clarify:{action_id}:{option_index}:{confirm|alt|cancel}
            if option.lower().startswith("yes"):
                callback_data = f"clarify:{action_id}:{i}:confirm"
            elif option.lower() == "something else":
                callback_data = f"clarify:{action_id}:{i}:cancel"
            else:
                callback_data = f"clarify:{action_id}:{i}:alt"

            button = InlineKeyboardButton(text=option, callback_data=callback_data)
            row.append(button)

            if len(row) >= columns:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        return InlineKeyboardMarkup(buttons)

    def create_confirmation_keyboard(
        self,
        confirm_text: str = "Yes",
        cancel_text: str = "No",
        confirm_data: str = "confirm",
        cancel_data: str = "cancel",
    ) -> InlineKeyboardMarkup:
        """Create a simple Yes/No confirmation keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text=confirm_text, callback_data=confirm_data),
                InlineKeyboardButton(text=cancel_text, callback_data=cancel_data),
            ]
        ])

    def create_reminder_actions_keyboard(
        self,
        reminder_id: str,
    ) -> InlineKeyboardMarkup:
        """Create action buttons for a reminder notification."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="✅ Done",
                    callback_data=f"action:complete:{reminder_id}",
                ),
                InlineKeyboardButton(
                    text="😴 Snooze 15m",
                    callback_data=f"action:snooze:{reminder_id}",
                ),
            ],
        ])

    def create_task_actions_keyboard(
        self,
        task_id: str,
    ) -> InlineKeyboardMarkup:
        """Create action buttons for a task."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="✅ Complete",
                    callback_data=f"action:complete:{task_id}",
                ),
                InlineKeyboardButton(
                    text="📝 Edit",
                    callback_data=f"action:edit:{task_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Delete",
                    callback_data=f"action:delete:{task_id}",
                ),
            ],
        ])

    def create_meeting_actions_keyboard(
        self,
        meeting_id: str,
    ) -> InlineKeyboardMarkup:
        """Create action buttons for a meeting."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    text="📝 Edit",
                    callback_data=f"action:edit:{meeting_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data=f"action:cancel:{meeting_id}",
                ),
            ],
        ])

    def create_time_options_keyboard(self) -> InlineKeyboardMarkup:
        """Create quick time selection options."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text="In 1 hour", callback_data="option:in 1 hour"),
                InlineKeyboardButton(text="In 2 hours", callback_data="option:in 2 hours"),
            ],
            [
                InlineKeyboardButton(text="Tomorrow 9am", callback_data="option:tomorrow at 9am"),
                InlineKeyboardButton(text="Tomorrow 2pm", callback_data="option:tomorrow at 2pm"),
            ],
            [
                InlineKeyboardButton(text="Next week", callback_data="option:next week"),
            ],
        ])

    def create_priority_keyboard(self) -> InlineKeyboardMarkup:
        """Create priority selection keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text="🟢 Low", callback_data="option:low"),
                InlineKeyboardButton(text="🟡 Medium", callback_data="option:medium"),
            ],
            [
                InlineKeyboardButton(text="🟠 High", callback_data="option:high"),
                InlineKeyboardButton(text="🔴 Urgent", callback_data="option:urgent"),
            ],
        ])

    def create_timezone_region_keyboard(self) -> InlineKeyboardMarkup:
        """Create timezone region selection keyboard."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text="🌎 Americas", callback_data="tz_region:americas"),
                InlineKeyboardButton(text="🌍 Europe", callback_data="tz_region:europe"),
            ],
            [
                InlineKeyboardButton(text="🌏 Asia", callback_data="tz_region:asia"),
                InlineKeyboardButton(text="🌏 Pacific", callback_data="tz_region:pacific"),
            ],
            [
                InlineKeyboardButton(text="🌍 Africa", callback_data="tz_region:africa"),
            ],
        ])

    def create_timezone_keyboard(self, region: str) -> InlineKeyboardMarkup:
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
                InlineKeyboardButton(text=label, callback_data=f"tz:{tz_id}")
            ])

        # Add back button
        buttons.append([
            InlineKeyboardButton(text="⬅️ Back to regions", callback_data="tz_region:back")
        ])

        return InlineKeyboardMarkup(buttons)

    def create_settings_keyboard(
        self,
        current_timezone: str,
        current_language: str,
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
                    callback_data="settings:timezone"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"🌐 Language: {lang_display}",
                    callback_data="settings:language"
                ),
            ],
            [
                InlineKeyboardButton(text="✅ Done", callback_data="settings:done"),
            ],
        ])

    def create_language_keyboard(self) -> InlineKeyboardMarkup:
        """Create language selection keyboard."""
        languages = [
            ("🇬🇧 English", "en"),
            ("🇷🇺 Русский", "ru"),
        ]

        buttons = []
        for label, lang_code in languages:
            buttons.append([
                InlineKeyboardButton(text=label, callback_data=f"lang:{lang_code}")
            ])

        # Add back button
        buttons.append([
            InlineKeyboardButton(text="⬅️ Back", callback_data="settings:back")
        ])

        return InlineKeyboardMarkup(buttons)
