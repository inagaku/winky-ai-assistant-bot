"""
Consumer service that processes actions from the queue.
This service would be run on the upstream system.
"""
import asyncio
import json
import logging
import os
from typing import Callable, Dict, Optional

from models import Action, ActionResponse, ActionStatus, get_available_actions, QUEUE_ACTIONS, QUEUE_RESPONSES
from queue_manager import create_queue_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ActionProcessor:
    """Processes actions from the queue and generates responses."""

    def __init__(self):
        """Initialize action processor with handlers for configured actions."""
        self.handlers: Dict[str, Callable] = {
            "schedule_meeting": self._handle_schedule_meeting,
            "create_reminder": self._handle_create_reminder,
            "create_task": self._handle_create_task,
            "update_calendar": self._handle_update_calendar,
        }

        # Log available actions from config
        available = get_available_actions()
        logger.info(f"Available actions from config: {available}")

        # Warn if any configured action has no handler
        for action in available:
            if action not in self.handlers:
                logger.warning(f"No handler registered for action: {action}")

    async def process_action(self, action: Action) -> ActionResponse:
        """
        Process an action and return a response.

        Args:
            action: Action object to process.

        Returns:
            ActionResponse with the result.
        """
        try:
            logger.info(f"Processing action: {action.action_type} for user {action.user_id}")

            handler = self.handlers.get(action.action_type)
            if not handler:
                logger.error(f"No handler registered for action type: {action.action_type}")
                return ActionResponse(
                    correlation_id=action.correlation_id,
                    chat_id=action.chat_id,
                    user_id=action.user_id,
                    reply_to_message_id=action.message_id,
                    action_type=action.action_type,
                    status=ActionStatus.FAILED,
                    message=f"Unknown action type: {action.action_type}",
                    error="No handler registered"
                )

            message, data = await handler(action)
            logger.info(f"Successfully processed action: {action.action_type}")

            return ActionResponse(
                correlation_id=action.correlation_id,
                chat_id=action.chat_id,
                user_id=action.user_id,
                reply_to_message_id=action.message_id,
                action_type=action.action_type,
                status=ActionStatus.COMPLETED,
                message=message,
                data=data
            )

        except Exception as e:
            logger.error(f"Error processing action: {e}", exc_info=True)
            return ActionResponse(
                correlation_id=action.correlation_id,
                chat_id=action.chat_id,
                user_id=action.user_id,
                reply_to_message_id=action.message_id,
                action_type=action.action_type,
                status=ActionStatus.FAILED,
                message="An error occurred while processing your request.",
                error=str(e)
            )

    async def _handle_schedule_meeting(self, action: Action) -> tuple[str, dict]:
        """Handle schedule_meeting action."""
        logger.info(f"Executing SCHEDULE_MEETING action with parameters: {action.parameters}")

        # Mock database storage
        meeting_id = f"mtg_{action.correlation_id[:8]}"
        attendee = action.parameters.get('attendee', 'someone')
        datetime_start = action.parameters.get('datetime_start', 'scheduled time')
        datetime_end = action.parameters.get('datetime_end', '')

        await asyncio.sleep(0.1)  # Simulate processing
        logger.info(f"Meeting scheduled successfully: {meeting_id}")

        message = f"Meeting with {attendee} scheduled for {datetime_start}."
        if datetime_end:
            message = f"Meeting with {attendee} scheduled from {datetime_start} to {datetime_end}."

        return message, {"meeting_id": meeting_id}

    async def _handle_create_reminder(self, action: Action) -> tuple[str, dict]:
        """Handle create_reminder action."""
        logger.info(f"Executing CREATE_REMINDER action with parameters: {action.parameters}")

        # Mock database storage
        reminder_id = f"rem_{action.correlation_id[:8]}"
        task = action.parameters.get('task', 'your task')
        datetime_str = action.parameters.get('datetime', 'the scheduled time')

        await asyncio.sleep(0.1)  # Simulate processing
        logger.info(f"Reminder created successfully: {reminder_id}")

        message = f"Got it! I'll remind you to {task} at {datetime_str}."
        return message, {"reminder_id": reminder_id}

    async def _handle_create_task(self, action: Action) -> tuple[str, dict]:
        """Handle create_task action."""
        logger.info(f"Executing CREATE_TASK action with parameters: {action.parameters}")

        # Mock database storage
        task_id = f"task_{action.correlation_id[:8]}"
        task_name = action.parameters.get('task_name', 'your task')
        datetime_str = action.parameters.get('datetime', '')

        await asyncio.sleep(0.1)  # Simulate processing
        logger.info(f"Task created successfully: {task_id}")

        message = f"Task '{task_name}' has been created."
        if datetime_str:
            message = f"Task '{task_name}' has been created for {datetime_str}."

        return message, {"task_id": task_id}

    async def _handle_update_calendar(self, action: Action) -> tuple[str, dict]:
        """Handle update_calendar action."""
        logger.info(f"Executing UPDATE_CALENDAR action with parameters: {action.parameters}")

        # Mock database storage
        event_id = f"evt_{action.correlation_id[:8]}"
        event_name = action.parameters.get('event_name', 'event')
        datetime_start = action.parameters.get('datetime_start', 'scheduled time')
        datetime_end = action.parameters.get('datetime_end', '')

        await asyncio.sleep(0.1)  # Simulate processing
        logger.info(f"Calendar updated successfully: {event_id}")

        message = f"'{event_name}' has been added to your calendar for {datetime_start}."
        if datetime_end:
            message = f"'{event_name}' has been added to your calendar from {datetime_start} to {datetime_end}."

        return message, {"event_id": event_id}


class QueueConsumer:
    """Consumes actions from the queue and publishes responses."""

    def __init__(self, backend_type: str = "redis"):
        """
        Initialize queue consumer.

        Args:
            backend_type: Type of queue backend ("redis" or "rabbitmq").
        """
        self.backend_type = backend_type.lower()
        self.client = None
        self.processor = ActionProcessor()
        self.queue_manager = create_queue_manager(queue_type=backend_type)

    async def connect(self):
        """Connect to the queue."""
        if self.backend_type == "redis":
            await self._connect_redis()
        elif self.backend_type == "rabbitmq":
            await self._connect_rabbitmq()
        else:
            raise ValueError(f"Unknown backend type: {self.backend_type}")

        # Connect queue manager for publishing responses
        await self.queue_manager.connect()

    async def _connect_redis(self):
        """Connect to Redis."""
        try:
            import redis
            self.client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                password=os.getenv("REDIS_PASSWORD"),
                decode_responses=False
            )
            self.client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Error connecting to Redis: {e}")
            raise

    async def _connect_rabbitmq(self):
        """Connect to RabbitMQ."""
        try:
            import pika
            credentials = pika.PlainCredentials(
                os.getenv("RABBITMQ_USERNAME", "guest"),
                os.getenv("RABBITMQ_PASSWORD", "guest")
            )
            parameters = pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST", "localhost"),
                port=int(os.getenv("RABBITMQ_PORT", 5672)),
                virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
                credentials=credentials
            )
            self.client = pika.BlockingConnection(parameters)
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Error connecting to RabbitMQ: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the queue."""
        try:
            if self.client:
                self.client.close()
            await self.queue_manager.disconnect()
            logger.info("Disconnected from queue")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

    async def start_consuming(self, queue_name: str = QUEUE_ACTIONS):
        """
        Start consuming actions from the queue.

        Args:
            queue_name: Name of the queue to consume from.
        """
        try:
            logger.info(f"Starting to consume from queue: {queue_name}")

            if self.backend_type == "redis":
                await self._consume_redis(queue_name)
            elif self.backend_type == "rabbitmq":
                await self._consume_rabbitmq(queue_name)

        except Exception as e:
            logger.error(f"Error consuming from queue: {e}", exc_info=True)
            raise

    async def _consume_redis(self, queue_name: str):
        """Consume from Redis queue."""
        try:
            while True:
                # Use blocking pop with timeout
                result = self.client.blpop(queue_name, timeout=1)

                if result:
                    _, message = result
                    await self._process_message(message)

                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Consumer stopped")
        except Exception as e:
            logger.error(f"Error in Redis consumer: {e}", exc_info=True)

    async def _consume_rabbitmq(self, queue_name: str):
        """Consume from RabbitMQ queue."""
        try:
            channel = self.client.channel()
            channel.queue_declare(queue=queue_name, durable=True)

            def callback(ch, method, properties, body):
                asyncio.create_task(self._process_message(body))
                ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name, on_message_callback=callback)

            logger.info(f"Waiting for messages on {queue_name}...")
            channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Consumer stopped")
            if hasattr(self, 'client') and self.client:
                self.client.close()
        except Exception as e:
            logger.error(f"Error in RabbitMQ consumer: {e}", exc_info=True)

    async def _process_message(self, message: bytes):
        """
        Process a message from the queue and publish response.

        Args:
            message: Raw message bytes from queue.
        """
        try:
            # Parse JSON message
            message_str = message.decode('utf-8') if isinstance(message, bytes) else message
            message_data = json.loads(message_str)

            # Create Action object
            action = Action(**message_data)

            # Validate action type against config
            if not action.validate_action_type():
                logger.error(f"Invalid action type: {action.action_type}")
                # Still send a response for invalid actions
                response = ActionResponse(
                    correlation_id=action.correlation_id,
                    chat_id=action.chat_id,
                    user_id=action.user_id,
                    reply_to_message_id=action.message_id,
                    action_type=action.action_type,
                    status=ActionStatus.FAILED,
                    message=f"Unknown action type: {action.action_type}",
                    error="Invalid action type"
                )
                await self.queue_manager.publish_response(response)
                return

            logger.info(f"Received action from queue: {action.action_type}")

            # Process the action and get response
            response = await self.processor.process_action(action)

            # Publish response to responses queue
            success = await self.queue_manager.publish_response(response)
            if success:
                logger.info(f"Published response for {action.action_type} to {QUEUE_RESPONSES}")
            else:
                logger.error(f"Failed to publish response for {action.action_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)


async def main():
    """Main entry point for consumer."""
    queue_type = os.getenv("QUEUE_TYPE", "redis")

    consumer = QueueConsumer(backend_type=queue_type)

    try:
        await consumer.connect()
        await consumer.start_consuming()
    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
    finally:
        await consumer.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
