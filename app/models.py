"""
Data models for the Telegram AI Assistant Bot.
"""
import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class Parameter(BaseModel):
    """Represents a parameter required for an action."""
    name: str
    value: Any
    type: str = Field(default="string")
    required: bool = Field(default=True)


class Action(BaseModel):
    """
    Represents an action to be performed by the upstream service.
    This object is sent via queue to be processed.
    """
    action_type: str  # Using str instead of ActionType for flexibility
    user_id: int
    chat_id: int
    original_input: str
    parameters: Dict[str, Any]
    confidence: float = Field(gt=0, le=1.0)
    embedding: Optional[List[float]] = None
    timestamp: str
    message_id: Optional[int] = None

    def validate_action_type(self) -> bool:
        """Validate that action_type is a valid configured action."""
        valid_types = {e.value for e in ActionType}
        return self.action_type in valid_types

    class Config:
        json_schema_extra = {
            "example": {
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
                "timestamp": "2025-12-08T10:30:00Z",
                "message_id": 789
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
