"""Handler for inline keyboard callbacks."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from app.services import UserService, AssistantService
from app.intelligence import IntentResolver

logger = logging.getLogger(__name__)


class CallbackHandler:
    """Handle inline keyboard button callbacks."""

    def __init__(
        self,
        user_service: UserService,
        assistant_service: AssistantService,
        intent_resolver: IntentResolver,
    ):
        self.user_service = user_service
        self.assistant_service = assistant_service
        self.intent_resolver = intent_resolver

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
        if callback_data.startswith("option:"):
            # User selected an option from clarification
            option_text = callback_data[7:]  # Remove "option:" prefix
            await self._handle_option_selection(query, context, user, option_text)
        elif callback_data.startswith("action:"):
            # Direct action callback
            action_data = callback_data[7:]
            await self._handle_action_callback(query, context, user, action_data)
        elif callback_data == "cancel":
            await query.edit_message_text("Cancelled.")
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
        # Process the option as a new input
        result = await self.intent_resolver.resolve(
            user_input=option_text,
            user_id=user.telegram_id,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            skip_clarification=True,  # User already made a choice
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
        # Parse action:type:params format
        parts = action_data.split(":", 1)
        action_type = parts[0]

        # Handle specific actions
        if action_type == "snooze":
            # Snooze a reminder
            if len(parts) > 1:
                reminder_id = parts[1]
                # TODO: Implement snooze via reminder service
                await query.edit_message_text("Snoozed for 15 minutes.")
        elif action_type == "complete":
            # Complete a task
            if len(parts) > 1:
                task_id = parts[1]
                # TODO: Implement complete via task service
                await query.edit_message_text("Task marked as complete!")
        else:
            await query.edit_message_text(f"Unknown action: {action_type}")
