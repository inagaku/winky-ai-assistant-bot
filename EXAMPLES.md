"""
Example configurations and deployment scenarios.
"""

# ============================================================================
# SCENARIO 1: Development with Redis and Local Services
# ============================================================================
"""
.env.development
"""
TELEGRAM_BOT_TOKEN=6123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
QUEUE_TYPE=redis

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

LOG_LEVEL=DEBUG


# ============================================================================
# SCENARIO 2: Production with RabbitMQ and Remote Services
# ============================================================================
"""
.env.production
"""
TELEGRAM_BOT_TOKEN=prod_token_from_botfather
OPENAI_API_KEY=prod_openai_key
QUEUE_TYPE=rabbitmq

RABBITMQ_HOST=rabbitmq.prod.example.com
RABBITMQ_PORT=5672
RABBITMQ_USERNAME=telegram_bot_user
RABBITMQ_PASSWORD=secure_password_here
RABBITMQ_VHOST=/telegram_bot

LOG_LEVEL=INFO


# ============================================================================
# SCENARIO 3: Docker Compose with Multiple Instances
# ============================================================================
"""
docker-compose.prod.yml
"""
version: '3.8'

services:
  redis-master:
    image: redis:7-alpine
    command: redis-server
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - bot-network

  telegram-bot-1:
    build: .
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      QUEUE_TYPE: redis
      REDIS_HOST: redis-master
      REDIS_PORT: 6379
      LOG_LEVEL: INFO
    depends_on:
      - redis-master
    networks:
      - bot-network
    restart: unless-stopped

  telegram-bot-2:
    build: .
    environment:
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      QUEUE_TYPE: redis
      REDIS_HOST: redis-master
      REDIS_PORT: 6379
      LOG_LEVEL: INFO
    depends_on:
      - redis-master
    networks:
      - bot-network
    restart: unless-stopped

  queue-consumer-1:
    build: .
    command: python queue_consumer.py
    environment:
      QUEUE_TYPE: redis
      REDIS_HOST: redis-master
      LOG_LEVEL: INFO
    depends_on:
      - redis-master
    networks:
      - bot-network
    restart: unless-stopped

  queue-consumer-2:
    build: .
    command: python queue_consumer.py
    environment:
      QUEUE_TYPE: redis
      REDIS_HOST: redis-master
      LOG_LEVEL: INFO
    depends_on:
      - redis-master
    networks:
      - bot-network
    restart: unless-stopped

volumes:
  redis_data:

networks:
  bot-network:
    driver: bridge


# ============================================================================
# SCENARIO 4: Kubernetes Deployment
# ============================================================================
"""
kubernetes/deployment.yaml
"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: telegram-bot
  labels:
    app: telegram-bot
spec:
  replicas: 2
  selector:
    matchLabels:
      app: telegram-bot
  template:
    metadata:
      labels:
        app: telegram-bot
    spec:
      containers:
      - name: telegram-bot
        image: your-registry/telegram-bot:latest
        imagePullPolicy: Always
        env:
        - name: TELEGRAM_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: telegram-secrets
              key: bot-token
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: telegram-secrets
              key: openai-key
        - name: QUEUE_TYPE
          value: "redis"
        - name: REDIS_HOST
          value: "redis-service"
        - name: REDIS_PORT
          value: "6379"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: queue-consumer
  labels:
    app: queue-consumer
spec:
  replicas: 2
  selector:
    matchLabels:
      app: queue-consumer
  template:
    metadata:
      labels:
        app: queue-consumer
    spec:
      containers:
      - name: queue-consumer
        image: your-registry/telegram-bot:latest
        imagePullPolicy: Always
        command: ["python", "queue_consumer.py"]
        env:
        - name: QUEUE_TYPE
          value: "redis"
        - name: REDIS_HOST
          value: "redis-service"
        - name: REDIS_PORT
          value: "6379"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
spec:
  selector:
    app: redis
  ports:
  - protocol: TCP
    port: 6379
    targetPort: 6379


# ============================================================================
# SCENARIO 5: Custom Action Handler Example
# ============================================================================
"""
Example of adding custom business logic to queue_consumer.py
"""

from models import Action, ActionType

async def _handle_custom_notification(self, action: Action):
    """
    Custom handler for sending notifications.
    
    Action example:
    {
        "action_type": "send_email",
        "parameters": {
            "recipient": "user@example.com",
            "subject": "Meeting Reminder",
            "body": "You have a meeting tomorrow at 2 PM"
        }
    }
    """
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        recipient = action.parameters.get('recipient')
        subject = action.parameters.get('subject')
        body = action.parameters.get('body')
        
        # Connect to SMTP server
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()
        smtp_server.login('your_email@gmail.com', 'your_password')
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = 'your_email@gmail.com'
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        smtp_server.send_message(msg)
        smtp_server.quit()
        
        logger.info(f"Email sent to {recipient}")
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")


# ============================================================================
# SCENARIO 6: Database Integration Example
# ============================================================================
"""
Adding database persistence to track actions
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import AsyncSession
from datetime import datetime

Base = declarative_base()

class ActionRecord(Base):
    __tablename__ = "actions"
    
    id = Column(Integer, primary_key=True)
    action_type = Column(String(50), nullable=False)
    user_id = Column(Integer, nullable=False)
    chat_id = Column(Integer, nullable=False)
    original_input = Column(String(500), nullable=False)
    parameters = Column(JSON, nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    result = Column(String(500), nullable=True)


# Example usage in queue_consumer.py
async def _process_message_with_db(self, message: bytes, db_session: AsyncSession):
    """Process message and store in database"""
    try:
        # Parse action
        message_str = message.decode('utf-8')
        action_data = json.loads(message_str)
        action = Action(**action_data)
        
        # Create database record
        db_record = ActionRecord(
            action_type=action.action_type.value,
            user_id=action.user_id,
            chat_id=action.chat_id,
            original_input=action.original_input,
            parameters=action.parameters,
            confidence=action.confidence,
            status="processing"
        )
        db_session.add(db_record)
        await db_session.commit()
        
        # Process action
        success = await self.processor.process_action(action)
        
        # Update record
        db_record.status = "completed" if success else "failed"
        db_record.result = "Success" if success else "Failed to process"
        await db_session.commit()
        
        logger.info(f"Action {db_record.id} processed successfully")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        if db_record:
            db_record.status = "failed"
            db_record.result = str(e)
            await db_session.commit()


# ============================================================================
# SCENARIO 7: Webhook Integration for Telegram
# ============================================================================
"""
Using webhooks instead of polling (recommended for production)
"""

from telegram import Update
from telegram.ext import Application
from fastapi import FastAPI, Request
import json

app = FastAPI()

@app.post(f"/telegram/{TELEGRAM_BOT_TOKEN}")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    data = await request.json()
    update = Update.de_json(data, bot)
    
    # Process update through your bot application
    await application.process_update(update)
    
    return {"ok": True}


# In your telegram_bot.py:
async def setup_webhook():
    """Configure webhook for Telegram"""
    await self.application.bot.set_webhook(
        url=f"https://your-domain.com/telegram/{self.telegram_token}",
        allowed_updates=Update.ALL_TYPES
    )
    logger.info("Webhook configured successfully")


# ============================================================================
# SCENARIO 8: Monitoring and Health Checks
# ============================================================================
"""
Add health check and metrics endpoints
"""

from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest
import time

app = FastAPI()

# Metrics
actions_processed = Counter('actions_processed_total', 'Total actions processed')
action_duration = Histogram('action_duration_seconds', 'Action processing duration')
queue_size = Gauge('queue_size', 'Current queue size')

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check queue connection
        await queue_manager.backend.client.ping()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "queue": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()

@app.get("/stats")
async def stats():
    """Application statistics"""
    return {
        "actions_processed": actions_processed._value.get(),
        "queue_size": queue_size._value.get(),
        "uptime": time.time() - start_time
    }


# ============================================================================
# SCENARIO 9: Advanced Logging Configuration
# ============================================================================
"""
Configure structured logging for better monitoring
"""

import logging
import json
from pythonjsonlogger import jsonlogger

# Create JSON logger
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)


# ============================================================================
# SCENARIO 10: Rate Limiting and Throttling
# ============================================================================
"""
Add rate limiting to prevent abuse
"""

from collections import defaultdict
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_requests = defaultdict(list)
    
    async def check_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limit"""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if req_time > window_start
        ]
        
        # Check limit
        if len(self.user_requests[user_id]) >= self.max_requests:
            return False
        
        # Add current request
        self.user_requests[user_id].append(now)
        return True


# Usage in telegram_bot.py
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not await rate_limiter.check_rate_limit(user_id):
        await update.message.reply_text(
            "⏰ You're sending messages too quickly. Please slow down."
        )
        return
    
    # Process message...

