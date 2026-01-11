"""
Main Telegram bot application.
Handles user messages and audio, processes them, and publishes actions to queue.
Listens for responses from the consumer and sends them back to users.
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from telegram import Update, File
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

from models import Action, ActionResponse, ActionStatus, Message, QUEUE_RESPONSES
from audio_processor import AudioProcessor
from action_matcher import ActionMatcher
from queue_manager import create_queue_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelegramAIBot:
    """Main Telegram AI Assistant Bot."""

    def __init__(self, telegram_token: str, openai_api_key: str,
                 queue_type: str = "redis", queue_config: Optional[dict] = None):
        """
        Initialize the Telegram AI Bot.

        Args:
            telegram_token: Telegram bot token.
            openai_api_key: OpenAI API key.
            queue_type: Type of queue backend ("redis" or "rabbitmq").
            queue_config: Additional queue configuration.
        """
        self.telegram_token = telegram_token
        self.openai_api_key = openai_api_key
        self.queue_type = queue_type
        self.queue_config = queue_config or {}

        # Initialize components
        self.audio_processor = AudioProcessor(api_key=openai_api_key)
        self.action_matcher = ActionMatcher(api_key=openai_api_key)
        self.queue_manager = create_queue_manager(queue_type=queue_type)
        self.response_queue_manager = create_queue_manager(queue_type=queue_type)

        # Telegram application
        self.application: Optional[Application] = None
        self._response_listener_task: Optional[asyncio.Task] = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        logger.info(f"User {update.effective_user.id} started the bot")
        await update.message.reply_text(
            "🤖 Welcome to AI Assistant Bot!\n\n"
            "I can help you with:\n"
            "• Send messages\n"
            "• Schedule meetings\n"
            "• Create reminders\n"
            "• Get weather information\n"
            "• Search for information\n"
            "• Send emails\n"
            "• Create tasks\n\n"
            "Just send me text or voice messages and I'll understand what you need!"
        )

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages."""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            message_id = update.message.message_id
            text = update.message.text

            logger.info(f"Received text message from user {user_id}: {text[:100]}...")

            # Show processing indicator
            await update.message.chat.send_action("typing")

            # Match action
            action_type, confidence, embedding = await self.action_matcher.match_action(text)

            # Extract parameters
            parameters = self.action_matcher.extract_parameters(text, action_type)

            # Create Action object
            action = Action(
                action_type=action_type,
                user_id=user_id,
                chat_id=chat_id,
                original_input=text,
                parameters=parameters,
                confidence=confidence,
                embedding=embedding,
                timestamp=datetime.utcnow().isoformat() + "Z",
                message_id=message_id
            )

            # Publish to queue
            success = await self.queue_manager.publish_action(action)

            if success:
                await update.message.reply_text(
                    f"✅ Got it! I understood you want to:\n"
                    f"*Action*: `{action_type}`\n"
                    f"*Confidence*: {confidence:.0%}\n\n"
                    f"Processing your request...",
                    parse_mode="Markdown"
                )
                logger.info(f"Successfully published action {action_type} to queue")
            else:
                await update.message.reply_text(
                    "❌ Sorry, I had trouble processing your request. Please try again."
                )
                logger.error("Failed to publish action to queue")

        except Exception as e:
            logger.error(f"Error handling text message: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ An error occurred: {str(e)[:100]}"
            )

    async def handle_audio_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle audio/voice messages."""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id
            message_id = update.message.message_id

            logger.info(f"Received audio message from user {user_id}")

            # Show processing indicator
            await update.message.chat.send_action("typing")
            await update.message.reply_text("🎙️ Transcribing audio...")

            # Get audio file
            if update.message.voice:
                audio_file = await update.message.voice.get_file()
                logger.info(f"Processing voice message: {audio_file.file_id}")
            elif update.message.audio:
                audio_file = await update.message.audio.get_file()
                logger.info(f"Processing audio message: {audio_file.file_id}")
            else:
                await update.message.reply_text("❌ Unsupported audio format")
                return

            # Download audio file
            audio_path = await audio_file.download_to_drive()
            logger.info(f"Downloaded audio file to: {audio_path}")

            # Transcribe audio
            text = await self.audio_processor.transcribe_audio(audio_path)
            logger.info(f"Transcribed audio: {text[:100]}...")

            await update.message.reply_text(
                f"📝 Transcribed text:\n`{text}`",
                parse_mode="Markdown"
            )

            # Clean up audio file
            os.remove(audio_path)

            # Match action
            await update.message.chat.send_action("typing")
            action_type, confidence, embedding = await self.action_matcher.match_action(text)

            # Extract parameters
            parameters = self.action_matcher.extract_parameters(text, action_type)

            # Create Action object
            action = Action(
                action_type=action_type,
                user_id=user_id,
                chat_id=chat_id,
                original_input=text,
                parameters=parameters,
                confidence=confidence,
                embedding=embedding,
                timestamp=datetime.utcnow().isoformat() + "Z",
                message_id=message_id
            )

            # Publish to queue
            success = await self.queue_manager.publish_action(action)

            if success:
                await update.message.reply_text(
                    f"✅ Understood! I will:\n"
                    f"*Action*: `{action_type.value}`\n"
                    f"*Confidence*: {confidence:.0%}\n\n"
                    f"Processing your request...",
                    parse_mode="Markdown"
                )
                logger.info(f"Successfully published action {action_type} to queue")
            else:
                await update.message.reply_text(
                    "❌ Sorry, I had trouble processing your request. Please try again."
                )
                logger.error("Failed to publish action to queue")

        except Exception as e:
            logger.error(f"Error handling audio message: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ An error occurred: {str(e)[:100]}"
            )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = """
*AI Assistant Bot Help*

*Available Actions:*
• `schedule_meeting` - Schedule a meeting with attendees
• `create_reminder` - Create a reminder for later
• `create_task` - Create a task
• `update_calendar` - Update your calendar

*How to use:*
1. Send a text message or voice message
2. The bot will transcribe audio to text
3. It will understand what action you want
4. Parameters will be extracted automatically
5. You'll receive a confirmation once processed

*Examples:*
• "Schedule a meeting with John tomorrow at 2 PM"
• "Remind me to call the dentist on Friday"
• "Create a task to review the document"
• "Block 2 hours on my calendar for the presentation"
        """
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def _handle_response(self, response_data: dict):
        """
        Handle a response from the consumer queue.

        Args:
            response_data: Response data dict from the queue.
        """
        try:
            response = ActionResponse(**response_data)
            logger.info(f"Received response for {response.action_type} (correlation_id: {response.correlation_id})")

            # Determine status emoji
            if response.status == ActionStatus.COMPLETED:
                status_emoji = "✅"
            elif response.status == ActionStatus.FAILED:
                status_emoji = "❌"
            else:
                status_emoji = "⏳"

            # Send message to user
            await self.application.bot.send_message(
                chat_id=response.chat_id,
                text=f"{status_emoji} {response.message}",
                reply_to_message_id=response.reply_to_message_id
            )

            logger.info(f"Sent response to chat {response.chat_id}")

        except Exception as e:
            logger.error(f"Error handling response: {e}", exc_info=True)

    async def _start_response_listener(self):
        """Start listening for responses from the consumer."""
        try:
            logger.info(f"Starting response listener on queue: {QUEUE_RESPONSES}")
            await self.response_queue_manager.subscribe(QUEUE_RESPONSES, self._handle_response)
        except asyncio.CancelledError:
            logger.info("Response listener cancelled")
        except Exception as e:
            logger.error(f"Error in response listener: {e}", exc_info=True)

    def run(self):
        """Start the bot (synchronous entry point)."""
        try:
            logger.info("Starting Telegram AI Assistant Bot...")

            # Create application first
            self.application = Application.builder().token(self.telegram_token).build()

            # Setup handlers
            self._setup_handlers_sync(self.application)

            # Add post-init and post-shutdown handlers for async setup/cleanup
            self.application.post_init = self._post_init
            self.application.post_shutdown = self._post_shutdown

            # Start bot - run_polling handles its own event loop
            logger.info("Bot is running. Press Ctrl+C to stop.")
            self.application.run_polling(allowed_updates=[])

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            logger.info("Bot shutdown complete")

    async def _post_init(self, application: Application):
        """Called after application is initialized."""
        try:
            await self.queue_manager.connect()
            logger.info("Connected to message queue")

            # Start the response listener as a background task in the running event loop
            self._response_listener_task = asyncio.create_task(self._start_response_listener())
        except Exception as e:
            logger.error(f"Failed to connect to queue: {e}", exc_info=True)
            raise

    async def _post_shutdown(self, application: Application):
        """Called after application is shutdown."""
        try:
            # Cancel and await the response listener task if running
            if self._response_listener_task:
                self._response_listener_task.cancel()
                try:
                    await self._response_listener_task
                except asyncio.CancelledError:
                    logger.info("Response listener task cancelled")

            await self.queue_manager.disconnect()
            logger.info("Disconnected from message queue")
        except Exception as e:
            logger.error(f"Error disconnecting from queue: {e}", exc_info=True)

    def _setup_handlers_sync(self, app: Application):
        """Setup message handlers (synchronous version)."""
        # Commands
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_command))

        # Messages
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
        app.add_handler(MessageHandler(filters.VOICE, self.handle_audio_message))
        app.add_handler(MessageHandler(filters.AUDIO, self.handle_audio_message))


def main():
    """Main entry point."""
    # Load configuration from environment
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    queue_type = os.getenv("QUEUE_TYPE", "redis")

    if not telegram_token or not openai_api_key:
        raise ValueError(
            "Missing required environment variables:\n"
            "- TELEGRAM_BOT_TOKEN\n"
            "- OPENAI_API_KEY"
        )

    # Create and run bot
    bot = TelegramAIBot(
        telegram_token=telegram_token,
        openai_api_key=openai_api_key,
        queue_type=queue_type
    )

    bot.run()


if __name__ == "__main__":
    main()

