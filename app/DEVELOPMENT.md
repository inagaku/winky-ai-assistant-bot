# Development Guide

This guide covers development setup, testing, and extending the Telegram AI Assistant Bot.

## Development Setup

### Prerequisites
- Python 3.9+
- Git
- Docker & Docker Compose (optional, for local services)
- IDE (VS Code, PyCharm, etc.)

### Local Development Environment

1. **Clone the repository:**
```bash
cd /Users/nagaku/Projects/n8n/winky-ai-assistant-bot-2
```

2. **Create and activate virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies with dev extras:**
```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-mock black flake8 mypy
```

4. **Setup pre-commit hooks (optional):**
```bash
pip install pre-commit
pre-commit install
```

5. **Create `.env.local` for development:**
```bash
cp .env.example .env.local
# Edit with your test credentials
```

### Running Local Services

Using Docker Compose (recommended):

```bash
# Start only Redis
docker-compose up -d redis

# Or start only RabbitMQ
docker-compose up -d rabbitmq

# Or start all services
docker-compose up -d
```

Alternatively, install locally:

**Redis:**
```bash
# macOS
brew install redis
redis-server

# Ubuntu/Debian
sudo apt-get install redis-server
redis-server
```

**RabbitMQ:**
```bash
# macOS
brew install rabbitmq
brew services start rabbitmq

# Ubuntu/Debian
sudo apt-get install rabbitmq-server
sudo service rabbitmq-server start
```

## Project Structure

```
winky-ai-assistant-bot-2/
├── models.py                 # Data models
├── audio_processor.py        # Audio to text conversion
├── action_matcher.py         # Action matching & parameter extraction
├── queue_manager.py          # Queue integration
├── telegram_bot.py           # Main bot application
├── queue_consumer.py         # Action consumer service
├── requirements.txt          # Python dependencies
├── .env.example             # Environment variables template
├── Dockerfile               # Docker image definition
├── docker-compose.yml       # Multi-container setup
├── README.md                # User documentation
└── DEVELOPMENT.md           # This file
```

## Code Style

### Formatting

Using Black:
```bash
black *.py
```

### Linting

Using flake8:
```bash
flake8 *.py --max-line-length=120
```

### Type Checking

Using mypy:
```bash
mypy *.py --ignore-missing-imports
```

## Testing

### Running Tests

```bash
pytest -v
```

### Running Specific Test File

```bash
pytest tests/test_action_matcher.py -v
```

### Running with Coverage

```bash
pytest --cov=. --cov-report=html
```

### Example Test Cases

Create `test_models.py`:

```python
import pytest
from app.models import Action, ActionType
from datetime import datetime


def test_action_model_creation():
    action = Action(
        action_type=ActionType.SEND_MESSAGE,
        user_id=123,
        chat_id=123,
        original_input="Send a message",
        parameters={"recipient": "John"},
        confidence=0.95,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    assert action.action_type == ActionType.SEND_MESSAGE
    assert action.confidence == 0.95
```

## Common Development Tasks

### Add a New Action Type

1. **Update `models.py`:**
```python
class ActionType(str, Enum):
    # ... existing actions ...
    MY_NEW_ACTION = "my_new_action"
```

2. **Update `action_matcher.py`:**
```python
def _load_predefined_actions(self) -> List[PredefinedAction]:
    return [
        # ... existing actions ...
        PredefinedAction(
            action_type=ActionType.MY_NEW_ACTION,
            keywords=["keyword1", "keyword2"],
            description="Description of my new action",
            required_parameters=["param1", "param2"],
            example_inputs=[
                "Example input 1",
                "Example input 2"
            ]
        )
    ]
```

3. **Add handler in `queue_consumer.py`:**
```python
async def _handle_my_new_action(self, action: Action):
    logger.info(f"Executing MY_NEW_ACTION with parameters: {action.parameters}")
    # TODO: Implement your business logic
    pass

def _register_handlers(self) -> dict:
    return {
        # ... existing handlers ...
        ActionType.MY_NEW_ACTION: self._handle_my_new_action,
    }
```

### Improve Parameter Extraction

The parameter extraction in `action_matcher.py` uses an LLM-based approach. To improve it:

```python
def extract_parameters(self, user_input: str, action_type: ActionType) -> dict:
    action_schema = self.get_predefined_action(action_type)
    
    # Enhanced extraction with better prompt engineering
    extraction_prompt = f"""
    Extract parameters from the user input for a {action_type} action.
    Required parameters: {', '.join(action_schema.required_parameters)}
    
    Examples:
    {chr(10).join(action_schema.example_inputs)}
    
    User input: "{user_input}"
    
    Return a JSON object with extracted parameters.
    Ensure all required parameters are present.
    """
    
    # ... rest of implementation
```

### Add Logging

```python
import logging

logger = logging.getLogger(__name__)

# In your function
logger.info("Processing message...")
logger.warning("Potential issue detected")
logger.error("An error occurred", exc_info=True)
logger.debug("Debug information")
```

### Database Integration (Optional)

To add database support for storing actions:

1. **Install database driver:**
```bash
pip install sqlalchemy asyncpg  # For PostgreSQL
# or
pip install motor  # For MongoDB
```

2. **Create models:**
```python
# models.py additions
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ActionRecord(Base):
    __tablename__ = "actions"
    
    id = Column(Integer, primary_key=True)
    action_type = Column(String)
    user_id = Column(Integer)
    parameters = Column(String)  # JSON
    confidence = Column(Float)
    created_at = Column(DateTime)
```

3. **Create database service:**
```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

class Database:
    def __init__(self, url: str):
        self.engine = create_async_engine(url)
    
    async def save_action(self, action: Action):
        # Implementation
        pass
```

## Debugging

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
python telegram_bot.py
```

### Using Python Debugger

```python
import pdb

# In your code
pdb.set_trace()  # Execution will pause here
```

### Using IDE Debugger

Most IDEs support Python debugging. Set breakpoints and use Run → Debug.

## Performance Profiling

### CPU Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
# ...

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Memory Profiling

```bash
pip install memory-profiler

python -m memory_profiler telegram_bot.py
```

## CI/CD Integration

### GitHub Actions Example

Create `.github/workflows/test.yml`:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt pytest pytest-asyncio
      - run: pytest -v
```

## Deployment

### Development Deployment

```bash
# Using Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f telegram-bot

# Stop services
docker-compose down
```

### Production Deployment

1. **Use environment-specific configs:**
```bash
export TELEGRAM_BOT_TOKEN=prod_token
export OPENAI_API_KEY=prod_key
export QUEUE_TYPE=rabbitmq
```

2. **Enable SSL/TLS for queue connections**

3. **Use proper logging aggregation** (ELK, Splunk, etc.)

4. **Monitor bot health:**
```python
# Add health check endpoint
async def health_check():
    # Verify queue connection
    # Verify API connectivity
    return {"status": "healthy"}
```

## Troubleshooting Development Issues

### Module Import Errors

```bash
# Ensure you're in the project directory
cd /Users/nagaku/Projects/n8n/winky-ai-assistant-bot-2

# Verify Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Queue Connection Issues

```bash
# Test Redis connection
redis-cli ping

# Test RabbitMQ connection
sudo rabbitmq-diagnostics ping
```

### API Rate Limiting

```python
# Add exponential backoff retry logic
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def call_api():
    # Your API call
    pass
```

## Best Practices

1. **Always use async/await for I/O operations**
2. **Validate all inputs using Pydantic models**
3. **Use environment variables for configuration**
4. **Log important operations and errors**
5. **Handle exceptions gracefully**
6. **Write tests for new features**
7. **Document your code with docstrings**
8. **Use type hints for better code clarity**

## Resources

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Python Asyncio](https://docs.python.org/3/library/asyncio.html)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Redis Documentation](https://redis.io/documentation)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)

## Getting Help

- Check existing issues and documentation
- Enable debug logging for troubleshooting
- Review error messages and stack traces carefully
- Test with smaller components first

