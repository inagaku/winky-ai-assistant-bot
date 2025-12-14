# Telegram AI Assistant Bot

A sophisticated Telegram bot that accepts text and audio inputs, converts audio to text, analyzes input using AI embeddings to match predefined actions, and sends action objects to an upstream service via a message queue.

## Architecture Overview

```
┌─────────────────────────┐
│   Telegram Users        │
│  (Text/Audio Input)     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│   Telegram Bot Handler                  │
│  - Receives messages & audio            │
│  - Downloads audio files                │
└────────────┬────────────────────────────┘
             │
             ├──────────────┬──────────────┐
             ▼              ▼              ▼
       ┌─────────┐   ┌──────────────┐  ┌──────────────┐
       │  Text   │   │Audio          │  │  Processed  │
       │Input    │   │Processor      │  │  Text       │
       └─────────┘   └──────────────┘  └──────────────┘
                          │
                          ▼
       ┌──────────────────────────────────────┐
       │  Action Matcher (Embeddings)         │
       │  - Compute text embedding            │
       │  - Match to predefined actions       │
       │  - Extract parameters                │
       └────────────┬─────────────────────────┘
                    │
                    ▼
       ┌──────────────────────────────────────┐
       │  Action Object Creation              │
       │  {                                   │
       │    action_type,                      │
       │    user_id,                          │
       │    parameters,                       │
       │    confidence,                       │
       │    embedding                         │
       │  }                                   │
       └────────────┬─────────────────────────┘
                    │
                    ▼
       ┌──────────────────────────────────────┐
       │  Queue Manager                       │
       │  (Redis or RabbitMQ)                 │
       └────────────┬─────────────────────────┘
                    │
                    ▼
       ┌──────────────────────────────────────┐
       │  Message Queue                       │
       │  (Redis/RabbitMQ)                    │
       └────────────┬─────────────────────────┘
                    │
                    ▼
       ┌──────────────────────────────────────┐
       │  Upstream Service                    │
       │  (Queue Consumer)                    │
       │  - Process actions                   │
       │  - Execute business logic            │
       └──────────────────────────────────────┘
```

## Features

### 1. **Text Input Support**
- Accept text messages from Telegram users
- Process text directly for action matching

### 2. **Audio Input Support**
- Accept voice messages and audio files
- Convert audio to text using OpenAI Whisper API
- Support for multiple audio formats (MP3, OGG, WAV, etc.)

### 3. **AI-Powered Action Matching**
- Use OpenAI embeddings to match user input to predefined actions
- Confidence scoring for matched actions
- Support for 8+ predefined action types

### 4. **Predefined Actions**
- `send_message` - Send a message to a recipient
- `schedule_meeting` - Schedule a meeting with attendees
- `create_reminder` - Create a reminder for a task
- `get_weather` - Get weather information
- `search_information` - Search for information
- `send_email` - Send an email
- `create_task` - Create a new task
- `update_calendar` - Update calendar with events

### 5. **Smart Parameter Extraction**
- Automatically extract required parameters from user input
- Use LLM for intelligent parameter extraction
- Support for multiple parameter types

### 6. **Queue Integration**
- Support for both Redis and RabbitMQ backends
- Reliable message delivery
- Durable message storage
- Easy configuration switching

### 7. **Action Object**
- Structured representation of actions
- Includes user context, confidence scores, and embeddings
- Ready for upstream service processing

## Installation

### Prerequisites
- Python 3.9+
- pip (Python package manager)
- Redis or RabbitMQ (for message queue)
- Telegram Bot Token (from BotFather)
- OpenAI API Key

### Setup

1. **Clone or navigate to the project directory:**
```bash
cd /Users/nagaku/Projects/n8n/naga-ai-assistant-bot-2
```

2. **Create a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

**Required environment variables:**
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
QUEUE_TYPE=redis  # or 'rabbitmq'

# For Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# For RabbitMQ
# RABBITMQ_HOST=localhost
# RABBITMQ_PORT=5672
# RABBITMQ_USERNAME=guest
# RABBITMQ_PASSWORD=guest
```

## Usage

### Start the Telegram Bot

```bash
python telegram_bot.py
```

The bot will:
1. Connect to Telegram
2. Connect to the message queue
3. Start listening for messages

### Start the Queue Consumer (Upstream Service)

```bash
python queue_consumer.py
```

The consumer will:
1. Connect to the message queue
2. Listen for action messages
3. Process actions and execute business logic

## Configuration

### Queue Backend Selection

**Using Redis (Default):**
```bash
export QUEUE_TYPE=redis
export REDIS_HOST=localhost
export REDIS_PORT=6379
```

**Using RabbitMQ:**
```bash
export QUEUE_TYPE=rabbitmq
export RABBITMQ_HOST=localhost
export RABBITMQ_PORT=5672
export RABBITMQ_USERNAME=guest
export RABBITMQ_PASSWORD=guest
```

### Adding Custom Actions

To add custom actions, edit the `_load_predefined_actions()` method in `action_matcher.py`:

```python
PredefinedAction(
    action_type=ActionType.YOUR_ACTION,  # Add to ActionType enum first
    keywords=["keyword1", "keyword2"],
    description="Description of your action",
    required_parameters=["param1", "param2"],
    example_inputs=[
        "Example user input 1",
        "Example user input 2"
    ]
)
```

## API & Data Models

### Action Model

```python
{
    "action_type": "schedule_meeting",  # Type of action
    "user_id": 123456,                  # Telegram user ID
    "chat_id": 123456,                  # Telegram chat ID
    "original_input": "Schedule a meeting with John tomorrow at 2 PM",
    "parameters": {
        "attendee": "John",
        "date": "2025-12-09",
        "time": "14:00"
    },
    "confidence": 0.95,                 # Confidence score (0-1)
    "embedding": [...],                 # Text embedding vector
    "timestamp": "2025-12-08T10:30:00Z",
    "message_id": 789                   # Telegram message ID
}
```

### Message Model

```python
{
    "user_id": 123456,
    "chat_id": 123456,
    "message_id": 789,
    "text": "Schedule a meeting...",      # For text messages
    "audio_file_id": "AgAC...",         # For audio messages
    "timestamp": "2025-12-08T10:30:00Z"
}
```

## Module Description

### `models.py`
- **Purpose**: Define data models using Pydantic
- **Key Classes**:
  - `Action` - Action object sent to upstream service
  - `PredefinedAction` - Schema for predefined actions
  - `ActionType` - Enum of available actions
  - `Message` - User message representation

### `audio_processor.py`
- **Purpose**: Handle audio-to-text conversion
- **Key Class**: `AudioProcessor`
- **Features**:
  - Transcribe audio using OpenAI Whisper API
  - Support for local files and URLs
  - Error handling and logging

### `action_matcher.py`
- **Purpose**: Match user input to actions using embeddings
- **Key Class**: `ActionMatcher`
- **Features**:
  - Load predefined actions
  - Compute embeddings for actions
  - Match user input to best action
  - Extract parameters from input

### `queue_manager.py`
- **Purpose**: Manage message queue operations
- **Key Classes**:
  - `QueueManager` - Main manager
  - `RedisBackend` - Redis implementation
  - `RabbitMQBackend` - RabbitMQ implementation
- **Features**:
  - Pluggable queue backends
  - Connection management
  - Message publishing

### `telegram_bot.py`
- **Purpose**: Main Telegram bot application
- **Key Class**: `TelegramAIBot`
- **Features**:
  - Handle text and audio messages
  - Integrate all components
  - Send feedback to users
  - Command handling

### `queue_consumer.py`
- **Purpose**: Consume and process actions from queue
- **Key Classes**:
  - `QueueConsumer` - Main consumer
  - `ActionProcessor` - Action processing logic
- **Features**:
  - Connect to queue backend
  - Process actions
  - Execute business logic
  - Error handling

## Workflow Example

1. **User sends message to bot:**
   ```
   User: "Schedule a meeting with John tomorrow at 2 PM"
   ```

2. **Bot processes the message:**
   - Receives text input
   - Computes embedding for input
   - Matches to `schedule_meeting` action (confidence: 0.95)
   - Extracts parameters: `{attendee: "John", date: "2025-12-09", time: "14:00"}`

3. **Action object created:**
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

4. **Action published to queue:**
   - Sent to Redis or RabbitMQ

5. **Upstream service processes:**
   - Consumer receives message
   - Calls appropriate handler
   - Executes business logic (creates calendar event, etc.)
   - Returns confirmation

## Error Handling

The bot implements comprehensive error handling:

- **Audio Processing Errors**: Falls back gracefully with error messages
- **API Errors**: Retries with exponential backoff
- **Queue Errors**: Logs and notifies user
- **Invalid Input**: Provides helpful error messages

## Logging

Logs are output to console with the format:
```
2025-12-08 10:30:00,123 - telegram_bot - INFO - User 123456 started the bot
```

Configure log level via environment:
```bash
export LOG_LEVEL=DEBUG
```

## Performance Considerations

### Optimization Tips

1. **Caching Embeddings**: Pre-compute embeddings for predefined actions
2. **Async Processing**: All I/O operations are async
3. **Connection Pooling**: Queue connections are reused
4. **Rate Limiting**: Consider adding rate limiting for API calls

### Scaling

- **Horizontal Scaling**: Run multiple bot instances with shared queue
- **Queue Partitioning**: Distribute actions across queue partitions
- **Load Balancing**: Use load balancer for multiple consumer instances

## Security Considerations

1. **API Keys**: Store in environment variables, never in code
2. **Message Queue**: Use authentication (RabbitMQ credentials, Redis password)
3. **SSL/TLS**: Use encrypted connections to queue services
4. **Input Validation**: All inputs are validated with Pydantic models
5. **Logging**: Sensitive data is not logged

## Troubleshooting

### Bot doesn't start
- Check `TELEGRAM_BOT_TOKEN` is valid
- Verify internet connection
- Check logs for detailed error messages

### Audio transcription fails
- Ensure `OPENAI_API_KEY` is valid
- Check audio file format is supported
- Verify file size is under OpenAI limits (25MB)

### Queue connection fails
- Verify Redis/RabbitMQ is running
- Check host and port configuration
- Verify authentication credentials
- Check network connectivity

### Action not matched correctly
- Check confidence threshold
- Review predefined actions and keywords
- Consider adding more training examples

## Examples

### Send a message
```
User: "Send a message to Sarah saying I'll be there in 10 minutes"
Bot: ✅ Got it! I understood you want to: send_message
     Confidence: 92%
```

### Create a reminder
```
User: 🎙️ *[audio message]*
Bot: 📝 Transcribed text: "Remind me to call the dentist on Friday"
     ✅ Understood! I will: create_reminder
     Confidence: 88%
```

### Search information
```
User: "Search for information about machine learning"
Bot: ✅ Got it! I understood you want to: search_information
     Confidence: 96%
```

## Development

### Adding New Features

1. **New Action Type**:
   - Add to `ActionType` enum in `models.py`
   - Add to predefined actions in `action_matcher.py`
   - Add handler in `queue_consumer.py`

2. **New Queue Backend**:
   - Create new class inheriting from `QueueBackend`
   - Implement `connect()`, `disconnect()`, `publish()`
   - Register in `QueueManager`

3. **Improved Parameter Extraction**:
   - Enhance LLM prompt in `ActionMatcher.extract_parameters()`
   - Add validation logic
   - Test with various inputs

## License

[Add your license here]

## Support

For issues or questions, please create an issue in the repository or contact the development team.

## Changelog

### v1.0.0 (2025-12-08)
- Initial release
- Text and audio input support
- 8 predefined actions
- Redis and RabbitMQ support
- Queue consumer service

