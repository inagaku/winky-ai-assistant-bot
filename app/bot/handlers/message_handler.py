"""Handler for text and audio messages."""

import logging
import os
import tempfile
import uuid

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards import InlineKeyboards
from app.bot.user_cache import get_cached_user
from app.i18n import t
from app.intelligence import IntentResolver
from app.models import ClarificationRequest, ParsedAction, ActionType
from app.services import UserService, AssistantService, ReminderService

logger = logging.getLogger(__name__)

# Key for storing pending actions in user_data
PENDING_ACTIONS_KEY = "pending_actions"
# Key for storing pending edit operations in user_data
PENDING_EDIT_KEY = "pending_edit"


class AudioProcessor:
    """Handles audio transcription using OpenAI Whisper."""

    def __init__(self, openai_api_key: str):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=openai_api_key)

    async def transcribe(self, audio_file_path: str) -> str:
        """Transcribe audio file to text."""
        with open(audio_file_path, "rb") as audio_file:
            transcript = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        return transcript.text


class MessageHandler:
    """Handle text and audio messages."""

    def __init__(
        self,
        user_service: UserService,
        assistant_service: AssistantService,
        intent_resolver: IntentResolver,
        reminder_service: ReminderService,
        openai_api_key: str,
    ):
        self.user_service = user_service
        self.assistant_service = assistant_service
        self.intent_resolver = intent_resolver
        self.reminder_service = reminder_service
        self.audio_processor = AudioProcessor(openai_api_key)
        self.keyboards = InlineKeyboards()

    async def handle_text(self, update: Update, callback_context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages."""
        if not update.message or not update.message.text:
            return
        if not update.effective_user or not update.effective_chat:
            return

        text = update.message.text.strip()
        if not text:
            return

        # Show typing indicator
        await callback_context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing",
        )

        # Get or create user (from cache if available)
        user = await get_cached_user(update, callback_context, self.user_service)
        locale = user.preferences.language

        # Resolve intent
        result = await self.intent_resolver.resolve(
            user_input=text,
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
            locale=locale,
        )

        # Handle result
        if isinstance(result, ClarificationRequest):
            await self._send_clarification(update, callback_context, result)
        elif isinstance(result, ParsedAction):
            await self._execute_action(update, result, user)
        else:
            locale = user.preferences.language
            await update.message.reply_text(t("not_sure", locale=locale))

    async def handle_audio(self, update: Update, callback_context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice and audio messages."""
        if not update.effective_user or not update.effective_chat:
            return

        # Get or create user first for language preference (from cache if available)
        user = await get_cached_user(update, callback_context, self.user_service)
        locale = user.preferences.language

        # Get the audio file
        if update.message.voice:
            audio = update.message.voice
        elif update.message.audio:
            audio = update.message.audio
        else:
            await update.message.reply_text("Please send a voice message or audio file.")
            return

        # Show typing indicator
        await callback_context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing",
        )

        # Download and transcribe
        try:
            file = await callback_context.bot.get_file(audio.file_id)

            # Create temp file
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp_path = tmp.name

            await file.download_to_drive(tmp_path)

            # Transcribe
            transcribed_text = await self.audio_processor.transcribe(tmp_path)

            # Clean up
            os.unlink(tmp_path)

            # Show transcription
            await update.message.reply_text(t("audio_heard", locale=locale, text=transcribed_text))

            result = await self.intent_resolver.resolve(
                user_input=transcribed_text,
                user_id=update.effective_user.id,
                chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
                locale=locale,
            )

            if isinstance(result, ClarificationRequest):
                await self._send_clarification(update, callback_context, result)
            elif isinstance(result, ParsedAction):
                await self._execute_action(update, result, user)

        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)
            await update.message.reply_text(t("audio_error", locale=locale))

    async def _send_clarification(
        self,
        update: Update,
        callback_context: ContextTypes.DEFAULT_TYPE,
        clarification: ClarificationRequest,
    ) -> None:
        """Send a clarification request to the user."""
        # Generate unique ID for this pending action
        action_id = str(uuid.uuid4())[:8]

        # Store the pending action in user_data
        if PENDING_ACTIONS_KEY not in callback_context.user_data:
            callback_context.user_data[PENDING_ACTIONS_KEY] = {}

        callback_context.user_data[PENDING_ACTIONS_KEY][action_id] = {
            "original_action": clarification.original_action,
            "clarification_type": clarification.type.value if clarification.type else None,
            "parameter": clarification.parameter,
            "alternatives": clarification.alternatives,  # Store alternatives for "alt" callback
            "original_input": clarification.original_action.intent.original_input if clarification.original_action else None,
            "clarification": clarification,  # Store full clarification for param options lookup
        }

        # Create keyboard with action_id encoded in callback data
        keyboard = None
        if clarification.options:
            keyboard = self.keyboards.create_clarification_keyboard(
                options=clarification.options,
                action_id=action_id,
            )

        await update.message.reply_text(
            clarification.message,
            reply_markup=keyboard,
        )

    async def _execute_action(
        self,
        update: Update,
        action: ParsedAction,
        user,
    ) -> None:
        """Execute an action and send the result."""
        result = await self.assistant_service.execute_action(action, user)
        locale = user.preferences.language

        # Skip emoji prefix for create actions, show ❌ only for failures
        create_actions = {ActionType.CREATE_REMINDER, ActionType.CREATE_TASK, ActionType.SCHEDULE_MEETING}
        if action.action_type in create_actions:
            message = result.message if result.success else f"❌ {result.message}"
        else:
            emoji = "✅" if result.success else "❌"
            message = f"{emoji} {result.message}"

        # Add edit keyboard for successful reminder creation
        keyboard = None
        if result.success and action.action_type == ActionType.CREATE_REMINDER:
            reminder_id = result.data.get("reminder_id")
            if reminder_id:
                keyboard = self.keyboards.create_reminder_selected_keyboard(
                    reminder_id, locale=locale
                )

        await update.message.reply_text(
            message,
            reply_to_message_id=update.message.message_id,
            reply_markup=keyboard,
        )