# Telegram AI Assistant Bot

A Telegram bot that helps you manage reminders, tasks, and meetings using natural language. Simply tell the bot what you need, and it will understand and act on your requests.

## Features

- **Natural Language Understanding**: Just type what you need in plain language
  - "Remind me to call mom tomorrow at 3pm"
  - "Create a task to review the report"
  - "Schedule a meeting with John for Friday afternoon"
- **Text & Audio Input**: Send text messages or voice notes
- **Smart Clarification**: When unsure, the bot asks for clarification instead of guessing
- **Persistent Storage**: All your data is stored securely in PostgreSQL
- **Scheduled Notifications**: Get reminded at the right time

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TELEGRAM USERS                                │
│              (Send text/audio messages)                             │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CONVERSATION LAYER (Bot)                          │
│  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────────┐    │
│  │ Message     │  │ Audio           │  │ Command              │    │
│  │ Handler     │──│ Processor       │──│ Handler              │    │
│  └─────────────┘  └─────────────────┘  └──────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE LAYER                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────┐   │
│  │ Semantic        │  │ Parameter       │  │ Clarification     │   │
│  │ Matcher         │──│ Extractor       │──│ Manager           │   │
│  │ (Embeddings)    │  │ (LLM)           │  │ (Low confidence)  │   │
│  └─────────────────┘  └─────────────────┘  └───────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER (Business Logic)                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │
│  │ Reminder  │  │ Task      │  │ Meeting   │  │ User      │        │
│  │ Service   │  │ Service   │  │ Service   │  │ Service   │        │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    REPOSITORY LAYER (Data Access)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Reminder     │  │ Task         │  │ Meeting      │              │
│  │ Repository   │  │ Repository   │  │ Repository   │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PostgreSQL Database                             │
└─────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────┐
                    │      SCHEDULER SERVICE       │
                    │  (Notification delivery)     │
                    └──────────────────────────────┘
```

## Quick Start (Local Development)

### Prerequisites

- Python 3.9+
- PostgreSQL 15+
- Telegram Bot Token (from @BotFather)
- OpenAI API Key

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/winky-ai-assistant-bot.git
cd winky-ai-assistant-bot

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

This starts PostgreSQL and the Telegram bot.

### Run Manually

```bash
# Terminal 1: Start PostgreSQL
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=winky_bot \
  postgres:15-alpine

# Terminal 2: Run the bot
cd app && python -m app.main
```

## Configuration

### Environment Variables

```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_api_key

# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=winky_bot
DATABASE_USER=postgres
DATABASE_PASSWORD=your_password

# Optional
LOG_LEVEL=INFO
SCHEDULER_CHECK_INTERVAL=60
CONFIDENCE_THRESHOLD=0.75
```

## Project Structure

```
winky-ai-assistant-bot/
├── app/
│   ├── bot/                    # Telegram bot layer
│   │   ├── handlers/           # Message, command, callback handlers
│   │   ├── keyboards/          # Inline keyboard builders
│   │   └── telegram_bot.py     # Main bot application
│   ├── intelligence/           # NLP layer
│   │   ├── semantic_matcher.py # Embedding-based action matching
│   │   ├── parameter_extractor.py # LLM parameter extraction
│   │   ├── clarification_manager.py # Handle ambiguous inputs
│   │   └── intent_resolver.py  # Main NLP orchestrator
│   ├── services/               # Business logic
│   │   ├── reminder_service.py
│   │   ├── task_service.py
│   │   ├── meeting_service.py
│   │   └── assistant_service.py # Main action executor
│   ├── repositories/           # Data access layer
│   │   ├── reminder_repository.py
│   │   ├── task_repository.py
│   │   └── meeting_repository.py
│   ├── models/                 # Domain entities
│   │   ├── reminder.py
│   │   ├── task.py
│   │   ├── meeting.py
│   │   └── action.py
│   ├── database/               # Database connection & migrations
│   ├── scheduler/              # Background notification scheduler
│   ├── config/                 # Settings & configuration
│   ├── main.py                 # Application entry point
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
├── terraform/                  # AWS ECS Fargate infrastructure
└── .github/workflows/          # CI/CD pipeline
```

## Supported Actions

### Reminders
| Example Input | What It Does |
|--------------|--------------|
| "Remind me to call mom tomorrow at 3pm" | Creates a reminder |
| "Show my reminders" | Lists all active reminders |
| "Delete the reminder about..." | Deletes a reminder |

### Tasks
| Example Input | What It Does |
|--------------|--------------|
| "Create a task to review the report" | Creates a new task |
| "Add a high priority task: fix the bug" | Creates a high priority task |
| "Show my tasks" | Lists all active tasks |
| "Complete the task about..." | Marks a task as done |

### Meetings
| Example Input | What It Does |
|--------------|--------------|
| "Schedule a meeting with John tomorrow at 2pm" | Schedules a meeting |
| "Show my meetings" | Lists upcoming meetings |
| "Cancel the meeting with..." | Cancels a meeting |

### General
| Command | What It Does |
|---------|--------------|
| `/start` | Welcome message and setup |
| `/help` | Show all available actions |
| `/summary` | Show overview of all items |
| `/reminders` | List all reminders |
| `/tasks` | List all tasks |
| `/meetings` | List all meetings |

## How It Works

1. **Input Processing**: Text or voice messages are received
2. **Audio Transcription**: Voice messages are converted to text using OpenAI Whisper
3. **Intent Recognition**: The semantic matcher uses embeddings to identify what you want to do
4. **Parameter Extraction**: The LLM extracts relevant details (dates, names, etc.)
5. **Clarification**: If confidence is low or info is missing, the bot asks for clarification
6. **Execution**: The appropriate service handles the request
7. **Response**: You get a confirmation with the result

## Development

### Code Style

```bash
# Format
black app/

# Lint
flake8 app/ --max-line-length=120

# Type check
mypy app/ --ignore-missing-imports
```

### Adding a New Action Type

1. Add the action to `ActionType` enum in `app/models/action.py`
2. Add action definition in `app/intelligence/semantic_matcher.py`
3. Add parameter schema in `app/intelligence/parameter_extractor.py`
4. Add handler in `app/services/assistant_service.py`

## Production Deployment

For AWS ECS Fargate deployment with GitOps CI/CD, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot doesn't start | Verify `TELEGRAM_BOT_TOKEN` is valid |
| Database connection fails | Check PostgreSQL is running and credentials are correct |
| Action not recognized | The bot will ask for clarification; try rephrasing |
| Audio not transcribed | Verify `OPENAI_API_KEY`, check file size (<25MB) |

## Technology Stack

- **Python 3.11** with asyncio
- **python-telegram-bot** for Telegram API
- **OpenAI API** (Whisper, Embeddings, GPT-4o-mini)
- **PostgreSQL 15** with asyncpg
- **Pydantic** for data validation
- **Docker** for containerization
- **Terraform** for AWS infrastructure
- **GitHub Actions** for CI/CD
