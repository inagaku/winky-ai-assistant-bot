"""Handler for bot commands (/start, /help, etc.)."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.services import UserService, AssistantService
from app.models import ActionType, ActionIntent, ActionStatus, ParsedAction

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handle bot commands."""

    def __init__(
        self,
        user_service: UserService,
        assistant_service: AssistantService,
    ):
        self.user_service = user_service
        self.assistant_service = assistant_service

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.effective_user or not update.effective_chat:
            return

        telegram_user = update.effective_user
        user = await self.user_service.get_or_create_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        welcome_message = f"""Hi {user.display_name}! I'm your personal assistant.

I can help you manage:
- Reminders ("Remind me to...")
- Tasks ("Create a task to...")
- Meetings ("Schedule a meeting with...")

Just tell me what you need in natural language, or use /help to see all commands.

Let's get started! What would you like to do?"""

        await update.message.reply_text(welcome_message)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not update.effective_user or not update.effective_chat:
            return

        # Get or create user
        telegram_user = update.effective_user
        user = await self.user_service.get_or_create_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        # Create a help action and execute it
        intent = ActionIntent(
            action_type=ActionType.HELP,
            confidence=1.0,
            original_input="/help",
        )
        action = ParsedAction(
            intent=intent,
            parameters={},
            user_id=telegram_user.id,
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id if update.message else None,
            status=ActionStatus.PENDING,
        )

        result = await self.assistant_service.execute_action(action, user)
        await update.message.reply_text(result.message, parse_mode="Markdown")

    async def summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /summary command."""
        if not update.effective_user or not update.effective_chat:
            return

        telegram_user = update.effective_user
        user = await self.user_service.get_or_create_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        intent = ActionIntent(
            action_type=ActionType.SHOW_SUMMARY,
            confidence=1.0,
            original_input="/summary",
        )
        action = ParsedAction(
            intent=intent,
            parameters={},
            user_id=telegram_user.id,
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id if update.message else None,
            status=ActionStatus.PENDING,
        )

        result = await self.assistant_service.execute_action(action, user)
        await update.message.reply_text(result.message)

    async def reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reminders command."""
        if not update.effective_user or not update.effective_chat:
            return

        telegram_user = update.effective_user
        user = await self.user_service.get_or_create_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        intent = ActionIntent(
            action_type=ActionType.LIST_REMINDERS,
            confidence=1.0,
            original_input="/reminders",
        )
        action = ParsedAction(
            intent=intent,
            parameters={},
            user_id=telegram_user.id,
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id if update.message else None,
            status=ActionStatus.PENDING,
        )

        result = await self.assistant_service.execute_action(action, user)
        await update.message.reply_text(result.message)

    async def tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tasks command."""
        if not update.effective_user or not update.effective_chat:
            return

        telegram_user = update.effective_user
        user = await self.user_service.get_or_create_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        intent = ActionIntent(
            action_type=ActionType.LIST_TASKS,
            confidence=1.0,
            original_input="/tasks",
        )
        action = ParsedAction(
            intent=intent,
            parameters={},
            user_id=telegram_user.id,
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id if update.message else None,
            status=ActionStatus.PENDING,
        )

        result = await self.assistant_service.execute_action(action, user)
        await update.message.reply_text(result.message)

    async def meetings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /meetings command."""
        if not update.effective_user or not update.effective_chat:
            return

        telegram_user = update.effective_user
        user = await self.user_service.get_or_create_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        intent = ActionIntent(
            action_type=ActionType.LIST_MEETINGS,
            confidence=1.0,
            original_input="/meetings",
        )
        action = ParsedAction(
            intent=intent,
            parameters={},
            user_id=telegram_user.id,
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id if update.message else None,
            status=ActionStatus.PENDING,
        )

        result = await self.assistant_service.execute_action(action, user)
        await update.message.reply_text(result.message)
