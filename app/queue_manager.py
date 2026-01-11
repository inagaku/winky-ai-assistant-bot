"""
Queue integration module for sending actions to upstream service.
Supports both RabbitMQ and Redis backends.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional
import os

from models import Action, ActionResponse, QUEUE_ACTIONS, QUEUE_RESPONSES

logger = logging.getLogger(__name__)


class QueueBackend(ABC):
    """Abstract base class for queue backends."""

    @abstractmethod
    async def connect(self):
        """Connect to the queue service."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from the queue service."""
        pass

    @abstractmethod
    async def publish(self, queue_name: str, message: dict) -> bool:
        """
        Publish a message to the queue.

        Args:
            queue_name: Name of the queue.
            message: Message dict to publish.

        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def subscribe(self, queue_name: str, callback) -> None:
        """
        Subscribe to a queue and call callback for each message.

        Args:
            queue_name: Name of the queue.
            callback: Async function to call with each message.
        """
        pass


class RabbitMQBackend(QueueBackend):
    """RabbitMQ queue backend."""

    def __init__(self, host: str = "localhost", port: int = 5672,
                 username: str = "guest", password: str = "guest",
                 vhost: str = "/"):
        """
        Initialize RabbitMQ backend.

        Args:
            host: RabbitMQ host.
            port: RabbitMQ port.
            username: RabbitMQ username.
            password: RabbitMQ password.
            vhost: RabbitMQ virtual host.
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.vhost = vhost
        self.connection = None
        self.channel = None

    async def connect(self):
        """Connect to RabbitMQ."""
        try:
            import pika
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials,
                heartbeat=600,
                blocked_connection_timeout=300
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Error connecting to RabbitMQ: {e}")
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ."""
        try:
            if self.connection:
                self.connection.close()
                logger.info("Disconnected from RabbitMQ")
        except Exception as e:
            logger.error(f"Error disconnecting from RabbitMQ: {e}")

    async def publish(self, queue_name: str, message: dict) -> bool:
        """
        Publish a message to RabbitMQ queue.

        Args:
            queue_name: Name of the queue.
            message: Message dict to publish.

        Returns:
            True if successful, False otherwise.
        """
        try:
            if not self.channel:
                await self.connect()

            # Declare queue
            self.channel.queue_declare(queue=queue_name, durable=True)

            # Publish message
            message_json = json.dumps(message)
            self.channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=message_json,
                properties=__import__('pika').BasicProperties(
                    content_type='application/json',
                    delivery_mode=2  # Make message persistent
                )
            )

            logger.info(f"Published message to RabbitMQ queue '{queue_name}'")
            return True

        except Exception as e:
            logger.error(f"Error publishing to RabbitMQ: {e}")
            return False

    async def subscribe(self, queue_name: str, callback) -> None:
        """Subscribe to RabbitMQ queue."""
        try:
            import asyncio
            if not self.channel:
                await self.connect()

            self.channel.queue_declare(queue=queue_name, durable=True)

            def on_message(ch, method, properties, body):
                message = json.loads(body.decode('utf-8'))
                asyncio.create_task(callback(message))
                ch.basic_ack(delivery_tag=method.delivery_tag)

            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(queue=queue_name, on_message_callback=on_message)

            logger.info(f"Subscribed to RabbitMQ queue '{queue_name}'")
            self.channel.start_consuming()

        except Exception as e:
            logger.error(f"Error subscribing to RabbitMQ: {e}")
            raise


class RedisBackend(QueueBackend):
    """Redis queue backend."""

    def __init__(self, host: str = "localhost", port: int = 6379,
                 db: int = 0, password: Optional[str] = None):
        """
        Initialize Redis backend.

        Args:
            host: Redis host.
            port: Redis port.
            db: Redis database number.
            password: Redis password (optional).
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.client = None

    async def connect(self):
        """Connect to Redis."""
        try:
            import redis
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=False
            )
            # Test connection
            self.client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Error connecting to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        try:
            if self.client:
                self.client.close()
                logger.info("Disconnected from Redis")
        except Exception as e:
            logger.error(f"Error disconnecting from Redis: {e}")

    async def publish(self, queue_name: str, message: dict) -> bool:
        """
        Publish a message to Redis queue.

        Args:
            queue_name: Name of the queue.
            message: Message dict to publish.

        Returns:
            True if successful, False otherwise.
        """
        try:
            if not self.client:
                await self.connect()

            message_json = json.dumps(message)
            self.client.rpush(queue_name, message_json)

            logger.info(f"Published message to Redis queue '{queue_name}'")
            return True

        except Exception as e:
            logger.error(f"Error publishing to Redis: {e}")
            return False

    async def subscribe(self, queue_name: str, callback) -> None:
        """Subscribe to Redis queue using blocking pop."""
        import asyncio
        try:
            if not self.client:
                await self.connect()

            logger.info(f"Subscribed to Redis queue '{queue_name}'")

            while True:
                result = self.client.blpop(queue_name, timeout=1)
                if result:
                    _, message_bytes = result
                    message = json.loads(message_bytes.decode('utf-8'))
                    await callback(message)
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error subscribing to Redis: {e}")
            raise


class QueueManager:
    """Manager for queue operations with configurable backend."""

    def __init__(self, backend_type: str = "redis", **kwargs):
        """
        Initialize QueueManager.

        Args:
            backend_type: Type of queue backend ("rabbitmq" or "redis").
            **kwargs: Configuration parameters for the backend.
        """
        self.backend_type = backend_type.lower()

        if self.backend_type == "rabbitmq":
            self.backend = RabbitMQBackend(**kwargs)
        elif self.backend_type == "redis":
            self.backend = RedisBackend(**kwargs)
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")

    async def connect(self):
        """Connect to the queue backend."""
        await self.backend.connect()

    async def disconnect(self):
        """Disconnect from the queue backend."""
        await self.backend.disconnect()

    async def publish_action(self, action: Action, queue_name: str = QUEUE_ACTIONS) -> bool:
        """
        Publish an action to the queue.

        Args:
            action: Action object to publish.
            queue_name: Name of the queue.

        Returns:
            True if successful, False otherwise.
        """
        return await self.backend.publish(queue_name, action.model_dump())

    async def publish_response(self, response: ActionResponse, queue_name: str = QUEUE_RESPONSES) -> bool:
        """
        Publish an action response to the queue.

        Args:
            response: ActionResponse object to publish.
            queue_name: Name of the queue.

        Returns:
            True if successful, False otherwise.
        """
        return await self.backend.publish(queue_name, response.model_dump())

    async def subscribe(self, queue_name: str, callback) -> None:
        """
        Subscribe to a queue and call callback for each message.

        Args:
            queue_name: Name of the queue.
            callback: Async function to call with each message dict.
        """
        await self.backend.subscribe(queue_name, callback)


def create_queue_manager(queue_type: Optional[str] = None) -> QueueManager:
    """
    Factory function to create a queue manager from environment variables.

    Args:
        queue_type: Type of queue ("rabbitmq" or "redis").
                   If None, uses QUEUE_TYPE env var (default: "redis").

    Returns:
        Configured QueueManager instance.
    """
    queue_type = queue_type or os.getenv("QUEUE_TYPE", "redis")

    if queue_type == "rabbitmq":
        return QueueManager(
            backend_type="rabbitmq",
            host=os.getenv("RABBITMQ_HOST", "localhost"),
            port=int(os.getenv("RABBITMQ_PORT", 5672)),
            username=os.getenv("RABBITMQ_USERNAME", "guest"),
            password=os.getenv("RABBITMQ_PASSWORD", "guest"),
            vhost=os.getenv("RABBITMQ_VHOST", "/")
        )
    else:
        return QueueManager(
            backend_type="redis",
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD")
        )

