"""
Consumer service that processes actions from the queue.
This service would be run on the upstream system.
"""
import asyncio
import json
import logging
from typing import Callable, Optional
import os

from models import Action, ActionType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ActionProcessor:
    """Processes actions from the queue."""

    def __init__(self):
        """Initialize action processor."""
        self.handlers = self._register_handlers()

    def _register_handlers(self) -> dict:
        """
        Register handlers for different action types.

        Returns:
            Dictionary mapping action types to handler functions.
        """
        return {
            ActionType.SEND_MESSAGE: self._handle_send_message,
            ActionType.SCHEDULE_MEETING: self._handle_schedule_meeting,
            ActionType.CREATE_REMINDER: self._handle_create_reminder,
            ActionType.GET_WEATHER: self._handle_get_weather,
            ActionType.SEARCH_INFORMATION: self._handle_search_information,
            ActionType.SEND_EMAIL: self._handle_send_email,
            ActionType.CREATE_TASK: self._handle_create_task,
            ActionType.UPDATE_CALENDAR: self._handle_update_calendar,
        }

    async def process_action(self, action: Action) -> bool:
        """
        Process an action.

        Args:
            action: Action object to process.

        Returns:
            True if processing was successful, False otherwise.
        """
        try:
            logger.info(f"Processing action: {action.action_type} for user {action.user_id}")

            handler = self.handlers.get(action.action_type)
            if not handler:
                logger.error(f"No handler registered for action type: {action.action_type}")
                return False

            await handler(action)
            logger.info(f"Successfully processed action: {action.action_type}")
            return True

        except Exception as e:
            logger.error(f"Error processing action: {e}", exc_info=True)
            return False

    async def _handle_send_message(self, action: Action):
        """Handle send_message action."""
        logger.info(f"Executing SEND_MESSAGE action with parameters: {action.parameters}")
        # TODO: Implement actual message sending logic
        # Example: call your messaging service API
        # await messaging_service.send(action.parameters['recipient'], action.parameters['message'])
        await asyncio.sleep(1)  # Simulate processing
        logger.info("Message sent successfully")

    async def _handle_schedule_meeting(self, action: Action):
        """Handle schedule_meeting action."""
        logger.info(f"Executing SCHEDULE_MEETING action with parameters: {action.parameters}")
        # TODO: Implement actual meeting scheduling logic
        # Example: call your calendar service API
        # await calendar_service.create_event(
        #     attendee=action.parameters['attendee'],
        #     date=action.parameters['date'],
        #     time=action.parameters['time']
        # )
        await asyncio.sleep(1)  # Simulate processing
        logger.info("Meeting scheduled successfully")

    async def _handle_create_reminder(self, action: Action):
        """Handle create_reminder action."""
        logger.info(f"Executing CREATE_REMINDER action with parameters: {action.parameters}")
        # TODO: Implement actual reminder creation logic
        await asyncio.sleep(1)  # Simulate processing
        logger.info("Reminder created successfully")

    async def _handle_get_weather(self, action: Action):
        """Handle get_weather action."""
        logger.info(f"Executing GET_WEATHER action with parameters: {action.parameters}")
        # TODO: Implement actual weather fetching logic
        # Example: call weather API
        # weather_data = await weather_service.get_weather(action.parameters['location'])
        await asyncio.sleep(1)  # Simulate processing
        logger.info("Weather information retrieved successfully")

    async def _handle_search_information(self, action: Action):
        """Handle search_information action."""
        logger.info(f"Executing SEARCH_INFORMATION action with parameters: {action.parameters}")
        # TODO: Implement actual search logic
        # Example: call search service
        # results = await search_service.search(action.parameters['query'])
        await asyncio.sleep(1)  # Simulate processing
        logger.info("Search completed successfully")

    async def _handle_send_email(self, action: Action):
        """Handle send_email action."""
        logger.info(f"Executing SEND_EMAIL action with parameters: {action.parameters}")
        # TODO: Implement actual email sending logic
        # Example: call email service
        # await email_service.send(
        #     to=action.parameters['recipient'],
        #     subject=action.parameters['subject'],
        #     body=action.parameters['body']
        # )
        await asyncio.sleep(1)  # Simulate processing
        logger.info("Email sent successfully")

    async def _handle_create_task(self, action: Action):
        """Handle create_task action."""
        logger.info(f"Executing CREATE_TASK action with parameters: {action.parameters}")
        # TODO: Implement actual task creation logic
        # Example: call task service
        # await task_service.create(
        #     name=action.parameters['task_name'],
        #     user_id=action.user_id
        # )
        await asyncio.sleep(1)  # Simulate processing
        logger.info("Task created successfully")

    async def _handle_update_calendar(self, action: Action):
        """Handle update_calendar action."""
        logger.info(f"Executing UPDATE_CALENDAR action with parameters: {action.parameters}")
        # TODO: Implement actual calendar update logic
        # Example: call calendar service
        # await calendar_service.update(
        #     event_name=action.parameters['event_name'],
        #     date=action.parameters['date'],
        #     time=action.parameters['time'],
        #     user_id=action.user_id
        # )
        await asyncio.sleep(1)  # Simulate processing
        logger.info("Calendar updated successfully")


class QueueConsumer:
    """Consumes actions from the queue."""

    def __init__(self, backend_type: str = "redis"):
        """
        Initialize queue consumer.

        Args:
            backend_type: Type of queue backend ("redis" or "rabbitmq").
        """
        self.backend_type = backend_type.lower()
        self.client = None
        self.processor = ActionProcessor()

    async def connect(self):
        """Connect to the queue."""
        if self.backend_type == "redis":
            await self._connect_redis()
        elif self.backend_type == "rabbitmq":
            await self._connect_rabbitmq()
        else:
            raise ValueError(f"Unknown backend type: {self.backend_type}")

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
                if self.backend_type == "rabbitmq":
                    self.client.close()
                else:
                    self.client.close()
                logger.info("Disconnected from queue")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

    async def start_consuming(self, queue_name: str = "actions"):
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
        Process a message from the queue.

        Args:
            message: Raw message bytes from queue.
        """
        try:
            # Parse JSON message
            message_str = message.decode('utf-8') if isinstance(message, bytes) else message
            message_data = json.loads(message_str)

            # Create Action object
            action = Action(**message_data)

            logger.info(f"Received action from queue: {action.action_type}")

            # Process the action
            await self.processor.process_action(action)

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

