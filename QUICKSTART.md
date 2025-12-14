# Quick Start Guide

Get the Telegram AI Assistant Bot up and running in 5 minutes.

## Prerequisites

- Python 3.9+
- Telegram Bot Token (from BotFather)
- OpenAI API Key (from OpenAI Dashboard)
- Redis or RabbitMQ running

## Step-by-Step Setup

### 1. Setup Environment (2 minutes)

```bash
# Navigate to project directory
cd /Users/nagaku/Projects/n8n/naga-ai-assistant-bot-2

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables (1 minute)

```bash
# Copy example config
cp .env.example .env

# Edit .env with your credentials
# Required:
# - TELEGRAM_BOT_TOKEN
# - OPENAI_API_KEY
```

### 3. Start Message Queue (1 minute)

**Option A: Using Docker (Recommended)**
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine
```

**Option B: Using Homebrew (macOS)**
```bash
# Start Redis
brew install redis
redis-server
```

**Option C: Using Package Manager (Linux)**
```bash
sudo apt-get install redis-server
redis-server
```

### 4. Start the Bot (1 minute)

**Terminal 1 - Start Telegram Bot:**
```bash
source venv/bin/activate
python telegram_bot.py
```

**Terminal 2 - Start Queue Consumer:**
```bash
source venv/bin/activate
python queue_consumer.py
```

**That's it!** The bot is now running and waiting for messages.

## Testing the Bot

### Via Telegram Mobile App

1. Open Telegram
2. Find your bot (@YourBotName)
3. Send a message:
   ```
   Schedule a meeting with John tomorrow at 2 PM
   ```
4. The bot will respond with the action it understood

### Via curl (for testing)

```bash
# Test if Redis is running
redis-cli ping
# Expected output: PONG
```

## Common Actions to Try

### 1. Send Message
```
Send a message to Sarah saying I'll be there soon
```

### 2. Schedule Meeting
```
Schedule a meeting with the team tomorrow at 10 AM
```

### 3. Create Reminder
```
Remind me to call John in 30 minutes
```

### 4. Get Weather
```
What's the weather in New York?
```

### 5. Send Email
```
Send an email to john@example.com about the project
```

### 6. Voice Message
```
🎙️ Send voice message saying "Schedule a meeting with John tomorrow at 2 PM"
```

## Using Docker Compose

### Start Everything at Once

```bash
# Create .env file first
cp .env.example .env
# Edit .env with your credentials

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f telegram-bot

# Stop all services
docker-compose down
```

### Services Started:
- Redis (port 6379)
- Telegram Bot (reads from environment)
- Queue Consumer (processes actions)

## Troubleshooting Quick Fixes

### Bot doesn't start
```bash
# Check if token is correct
echo $TELEGRAM_BOT_TOKEN

# Check Python version
python3 --version  # Should be 3.9+

# Check dependencies
pip list | grep telegram
```

### Queue connection error
```bash
# Check if Redis is running
redis-cli ping

# If using Docker
docker ps | grep redis
```

### API key error
```bash
# Verify OpenAI API key
echo $OPENAI_API_KEY

# Test API connection
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

## Next Steps

1. **Customize Actions**: See [DEVELOPMENT.md](DEVELOPMENT.md) for adding new actions
2. **Deploy**: See deployment section in [README.md](README.md)
3. **Integrate**: Connect to your upstream service via queue
4. **Monitor**: Set up logging and monitoring

## Useful Commands

```bash
# Activate virtual environment
source venv/bin/activate

# View logs in real-time
docker-compose logs -f

# Check queue status
redis-cli
> LLEN actions

# Stop everything
docker-compose down

# Rebuild Docker images
docker-compose build --no-cache

# Run in detached mode
docker-compose up -d
```

## Environment Variables Reference

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# OpenAI
OPENAI_API_KEY=your_api_key

# Queue (redis or rabbitmq)
QUEUE_TYPE=redis

# Redis Config
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# RabbitMQ Config (if using)
# RABBITMQ_HOST=localhost
# RABBITMQ_PORT=5672
# RABBITMQ_USERNAME=guest
# RABBITMQ_PASSWORD=guest
```

## Architecture Overview

```
User's Telegram Message
          ↓
    [Telegram Bot]
    - Accepts text/audio
    - Transcribes audio
          ↓
   [Action Matcher]
    - Matches action type
    - Extracts parameters
          ↓
     [Redis/RabbitMQ]
    - Stores action message
          ↓
   [Queue Consumer]
    - Processes actions
    - Executes business logic
          ↓
   Your Upstream Service
```

## Getting Help

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Verify environment variables: `cat .env`
3. Test Redis: `redis-cli ping`
4. Test OpenAI: Call the API directly
5. Review [README.md](README.md) or [DEVELOPMENT.md](DEVELOPMENT.md)

## What's Next?

After the bot is running:

- [ ] Test with voice messages
- [ ] Customize predefined actions
- [ ] Connect upstream service
- [ ] Set up monitoring
- [ ] Deploy to production

Good luck! 🚀

