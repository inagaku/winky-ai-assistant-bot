"""
Data models for the Telegram AI Assistant Bot.
"""
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import yaml
from pydantic import BaseModel, Field


def _load_actions_config() -> Dict:
    """Load actions configuration from YAML file."""
    config_path = Path(__file__).parent / "config" / "actions.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Actions config not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config.get("actions", {})


def _create_action_type_enum() -> type:
    """Dynamically create ActionType enum from config."""
    actions_config = _load_actions_config()
    enum_values = {name.upper(): name for name in actions_config.keys()}
    return Enum("ActionType", enum_values, type=str)


# Create ActionType enum dynamically from config
ActionType = _create_action_type_enum()


class ActionStatus(str, Enum):
    """Status of an action in the processing pipeline."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UserInfo(BaseModel):
    """Telegram user information."""
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language_code: Optional[str] = None
    is_bot: bool = False


class Action(BaseModel):
    """
    Represents an action to be performed by the upstream service.
    This object is sent via queue to be processed.
    """
    # Tracking
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))

    # Action details
    action_type: str
    original_input: str
    parameters: Dict[str, Any]
    confidence: float = Field(gt=0, le=1.0)

    # User context
    user_id: int
    chat_id: int
    message_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    language_code: Optional[str] = "en"

    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source: str = "telegram"  # telegram, api, etc.
    embedding: Optional[List[float]] = None

    def validate_action_type(self) -> bool:
        """Validate that action_type is a valid configured action."""
        valid_types = {e.value for e in ActionType}
        return self.action_type in valid_types

    class Config:
        json_schema_extra = {
            "example": {
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                "action_type": "create_reminder",
                "original_input": "Remind me to buy milk tomorrow at 10:00",
                "parameters": {
                    "task": "buy milk",
                    "datetime": "tomorrow at 10:00"
                },
                "confidence": 0.95,
                "user_id": 123456,
                "chat_id": 123456,
                "message_id": 789,
                "username": "johndoe",
                "first_name": "John",
                "language_code": "en",
                "timestamp": "2025-12-08T10:30:00Z",
                "source": "telegram"
            }
        }


class ActionResponse(BaseModel):
    """
    Response from the consumer back to the bot.
    Contains the result of processing an action.
    """
    # Tracking - links back to original action
    correlation_id: str

    # Destination
    chat_id: int
    user_id: int
    reply_to_message_id: Optional[int] = None

    # Response details
    action_type: str
    status: ActionStatus = ActionStatus.COMPLETED
    message: str  # Human-readable response to send to user

    # Additional data (e.g., created reminder_id, meeting_id, etc.)
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    class Config:
        json_schema_extra = {
            "example": {
                "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
                "chat_id": 123456,
                "user_id": 123456,
                "reply_to_message_id": 789,
                "action_type": "create_reminder",
                "status": "completed",
                "message": "Got it! I'll remind you to buy milk tomorrow at 10:00 AM.",
                "data": {"reminder_id": "rem_12345"},
                "timestamp": "2025-12-08T10:30:01Z"
            }
        }


class PredefinedAction(BaseModel):
    """Schema for predefined actions that inputs are matched against."""
    action_type: str
    keywords: List[str]
    description: str
    required_parameters: List[str]
    example_inputs: List[str]


class Message(BaseModel):
    """Represents a user message."""
    user_id: int
    chat_id: int
    message_id: int
    text: Optional[str] = None
    audio_file_id: Optional[str] = None
    timestamp: str


# Queue names
QUEUE_ACTIONS = "actions"
QUEUE_RESPONSES = "responses"


def get_available_actions() -> List[str]:
    """Get list of available action types from config."""
    return [e.value for e in ActionType]


def load_predefined_actions() -> List[PredefinedAction]:
    """
    Load predefined actions from config file.

    Returns:
        List of PredefinedAction objects.
    """
    actions_config = _load_actions_config()
    predefined_actions = []

    for action_name, action_data in actions_config.items():
        predefined_actions.append(
            PredefinedAction(
                action_type=action_name,
                keywords=action_data.get("keywords", []),
                description=action_data.get("description", ""),
                required_parameters=action_data.get("required_parameters", []),
                example_inputs=action_data.get("example_inputs", [])
            )
        )

    return predefined_actions
