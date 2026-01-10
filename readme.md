# Telegram AI Assistant Bot

A Telegram bot that accepts text and audio inputs, converts audio to text using OpenAI Whisper, matches input to predefined actions using AI embeddings, and publishes structured action objects to a message queue.

## Features

- **Text & Audio Input**: Accept text messages and voice/audio files from Telegram
- **Audio Transcription**: Convert audio to text using OpenAI Whisper API
- **AI Action Matching**: Match user input to predefined actions using OpenAI embeddings with confidence scoring
- **Parameter Extraction**: Automatically extract required parameters using LLM
- **Queue Integration**: Publish actions to Redis or RabbitMQ
- **Consumer Service**: Process actions from queue with extensible handlers

## Architecture

```
Telegram Users (Text/Audio)
        |
        v
+------------------+
|  Telegram Bot    |  <- Receives messages, downloads audio
+------------------+
        |
        v
+------------------+
| Audio Processor  |  <- Whisper API transcription
+------------------+
        |
        v
+------------------+
| Action Matcher   |  <- Embeddings + parameter extraction
+------------------+
        |
        v
+------------------+
|  Queue Manager   |  <- Redis or RabbitMQ
+------------------+
        |
        v
+------------------+
| Queue Consumer   |  <- Process actions
+------------------+
```

## Predefined Actions

| Action | Description | Example |
|--------|-------------|---------|
| `send_message` | Send message to recipient | "Send a message to John" |
| `schedule_meeting` | Schedule meeting | "Schedule meeting tomorrow at 2 PM" |
| `create_reminder` | Create reminder | "Remind me to call dentist" |
| `get_weather` | Get weather info | "What's the weather in NYC?" |
| `search_information` | Search for info | "Search for Python docs" |
| `send_email` | Send email | "Email team about project" |
| `create_task` | Create task | "Create task to fix bug" |
| `update_calendar` | Update calendar | "Block 2 hours for presentation" |

## Quick Start (Local Development)

### Prerequisites

- Python 3.9+
- Redis (or RabbitMQ)
- Telegram Bot Token (from @BotFather)
- OpenAI API Key

### Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r app/requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN and OPENAI_API_KEY
```

### Run with Docker Compose

```bash
cd app
docker-compose up -d
```

This starts Redis, the Telegram bot, and the queue consumer.

### Run Manually

```bash
# Terminal 1: Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: Start bot
cd app && python telegram_bot.py

# Terminal 3: Start consumer
cd app && python queue_consumer.py
```

## Configuration

### Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_api_key

# Queue (default: redis)
QUEUE_TYPE=redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Or use RabbitMQ
# QUEUE_TYPE=rabbitmq
# RABBITMQ_HOST=localhost
# RABBITMQ_PORT=5672

# Logging
LOG_LEVEL=INFO
```

## Project Structure

```
winky-ai-assistant-bot/
├── app/
│   ├── telegram_bot.py      # Main bot application
│   ├── models.py            # Pydantic data models
│   ├── audio_processor.py   # Whisper transcription
│   ├── action_matcher.py    # AI matching & extraction
│   ├── queue_manager.py     # Redis/RabbitMQ abstraction
│   ├── queue_consumer.py    # Action consumer service
│   ├── requirements.txt     # Python dependencies
│   ├── Dockerfile           # Container image
│   └── docker-compose.yml   # Local development
├── terraform/               # AWS ECS Fargate infrastructure
└── .github/workflows/       # CI/CD pipeline
```

## Action Object Structure

```json
{
  "action_type": "schedule_meeting",
  "user_id": 123456,
  "chat_id": 123456,
  "original_input": "Schedule a meeting with John tomorrow at 2 PM",
  "parameters": {
    "attendee": "John",
    "date": "2025-12-09",
    "time": "14:00"
  },
  "confidence": 0.95,
  "timestamp": "2025-12-08T10:30:00Z"
}
```

## Development

### Adding a New Action Type

1. Add to `ActionType` enum in `app/models.py`
2. Add predefined action in `app/action_matcher.py`
3. Add handler in `app/queue_consumer.py`

### Code Style

```bash
black app/*.py                              # Format
flake8 app/*.py --max-line-length=120       # Lint
mypy app/*.py --ignore-missing-imports      # Type check
```

## Production Deployment

For AWS ECS Fargate deployment with GitOps CI/CD, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't start | Verify `TELEGRAM_BOT_TOKEN` is valid |
| Audio transcription fails | Verify `OPENAI_API_KEY`, check file size (<25MB) |
| Queue connection fails | Verify Redis/RabbitMQ is running: `redis-cli ping` |
| Action not matched | Review predefined actions, add more example inputs |

## Technology Stack

- **Python 3.9+** with asyncio
- **python-telegram-bot** for Telegram API
- **OpenAI API** (Whisper, Embeddings, GPT-3.5)
- **Pydantic** for data validation
- **Redis/RabbitMQ** for message queue
- **Docker** for containerization
- **Terraform** for AWS infrastructure
- **GitHub Actions** for CI/CD
