"""
Data models for the Telegram AI Assistant Bot.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ActionType(str, Enum):
    """Predefined list of possible actions."""
    SEND_MESSAGE = "send_message"
    SCHEDULE_MEETING = "schedule_meeting"
    CREATE_REMINDER = "create_reminder"
    GET_WEATHER = "get_weather"
    SEARCH_INFORMATION = "search_information"
    SEND_EMAIL = "send_email"
    CREATE_TASK = "create_task"
    UPDATE_CALENDAR = "update_calendar"


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
    action_type: ActionType
    user_id: int
    chat_id: int
    original_input: str
    parameters: Dict[str, Any]
    confidence: float = Field(gt=0, le=1.0)
    embedding: Optional[List[float]] = None
    timestamp: str
    message_id: Optional[int] = None

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
    action_type: ActionType
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

