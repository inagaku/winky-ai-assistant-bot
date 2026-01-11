"""Handler for text and audio messages."""

import logging
import os
import tempfile
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.models import ClarificationRequest, ParsedAction
from app.services import UserService, AssistantService
from app.intelligence import IntentResolver
from app.bot.keyboards import InlineKeyboards

logger = logging.getLogger(__name__)


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
        openai_api_key: str,
    ):
        self.user_service = user_service
        self.assistant_service = assistant_service
        self.intent_resolver = intent_resolver
        self.audio_processor = AudioProcessor(openai_api_key)
        self.keyboards = InlineKeyboards()

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages."""
        if not update.message or not update.message.text:
            return
        if not update.effective_user or not update.effective_chat:
            return

        text = update.message.text.strip()
        if not text:
            return

        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing",
        )

        # Get or create user
        telegram_user = update.effective_user
        user = await self.user_service.get_or_create_user(
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
        )

        # Resolve intent
        result = await self.intent_resolver.resolve(
            user_input=text,
            user_id=telegram_user.id,
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )

        # Handle result
        if isinstance(result, ClarificationRequest):
            await self._send_clarification(update, result)
        elif isinstance(result, ParsedAction):
            await self._execute_action(update, result, user)
        else:
            await update.message.reply_text(
                "I'm not sure what you mean. Try /help to see what I can do."
            )

    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice and audio messages."""
        if not update.effective_user or not update.effective_chat:
            return

        # Get the audio file
        if update.message.voice:
            audio = update.message.voice
        elif update.message.audio:
            audio = update.message.audio
        else:
            await update.message.reply_text("Please send a voice message or audio file.")
            return

        # Show typing indicator
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing",
        )

        # Download and transcribe
        try:
            file = await context.bot.get_file(audio.file_id)

            # Create temp file
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp_path = tmp.name

            await file.download_to_drive(tmp_path)

            # Transcribe
            transcribed_text = await self.audio_processor.transcribe(tmp_path)

            # Clean up
            os.unlink(tmp_path)

            # Show transcription
            await update.message.reply_text(f"I heard: \"{transcribed_text}\"")

            # Process as text
            telegram_user = update.effective_user
            user = await self.user_service.get_or_create_user(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name,
            )

            result = await self.intent_resolver.resolve(
                user_input=transcribed_text,
                user_id=telegram_user.id,
                chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
            )

            if isinstance(result, ClarificationRequest):
                await self._send_clarification(update, result)
            elif isinstance(result, ParsedAction):
                await self._execute_action(update, result, user)

        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)
            await update.message.reply_text(
                "Sorry, I couldn't process that audio. Please try again or send a text message."
            )

    async def _send_clarification(
        self,
        update: Update,
        clarification: ClarificationRequest,
    ) -> None:
        """Send a clarification request to the user."""
        keyboard = None
        if clarification.options:
            keyboard = self.keyboards.create_options_keyboard(clarification.options)

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

        # Choose emoji based on success
        emoji = "✅" if result.success else "❌"

        await update.message.reply_text(
            f"{emoji} {result.message}",
            reply_to_message_id=update.message.message_id,
        )
