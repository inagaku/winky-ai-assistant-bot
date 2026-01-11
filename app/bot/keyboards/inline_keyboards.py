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
            [
                InlineKeyboardButton(
                    text="❌ Dismiss",
                    callback_data=f"action:dismiss:{reminder_id}",
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
