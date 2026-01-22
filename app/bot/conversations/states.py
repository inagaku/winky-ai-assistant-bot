"""Conversation states for multi-step interactions."""

from enum import IntEnum, auto


class ReminderEditState(IntEnum):
    """States for reminder editing conversation.

    State flow:
        Entry (SELECT) → SELECTING → [Edit][OK] (Delete is separate flow)
                                   → Edit → MENU → [Change Time][Edit Title][Save]
                                                 → AWAITING_TIME/TITLE → MENU
                                                 → Save → SELECTING
                                   → OK → END
    """

    SELECTED = auto()       # Showing [Edit][OK][Delete*] (*Delete is separate flow)
    TIME_MENU = auto()       # Showing [30m earlier][30m later][1h earlier][1h later][Enter time]
    MENU = auto()            # Showing [Change Time][Edit Title][Save]
    AWAITING_TIME = auto()   # Waiting for time text input
    AWAITING_TITLE = auto()  # Waiting for title text input


# Legacy alias for backward compatibility
ReminderState = ReminderEditState


class SettingsState(IntEnum):
    """States for settings/onboarding conversation."""

    SELECTING_REGION = auto()       # User selecting timezone region
    SELECTING_TIMEZONE = auto()     # User selecting specific timezone
    SELECTING_LANGUAGE = auto()     # User selecting language
    MAIN_MENU = auto()              # Main settings menu
