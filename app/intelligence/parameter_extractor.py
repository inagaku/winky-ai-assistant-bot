"""Parameter extractor using LLM."""

import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.models import ActionType

logger = logging.getLogger(__name__)


# Required parameters for each action type
ACTION_PARAMETERS: Dict[ActionType, Dict[str, Any]] = {
    ActionType.CREATE_REMINDER: {
        "required": ["title", "description"],
        "optional": ["remind_at_explicit", "event_time", "lead_time"],
        "schema": {
            "title": "Short, imperative summary of the reminder suitable as a notification title (string, required). Example: 'Call John', 'Submit tax form'",
            "description": "Full natural-language description of what needs to be done, including context or details not suitable for the title (string, required)",
            "remind_at_explicit": "When the user specifies WHEN they want to receive the notification,either as an absolute time (`at 4pm`, `tomorrow morning`) or a relative time (`in 30 minutes','after 2 hours`),and the time is not tied to an event.",
            "event_time": "When the actual event or action occurs (not the notification). Use if the user describes something happening at a time (e.g., 'the meeting is at 3pm', 'my flight departs tomorrow at 9', 'I need to do it by the end of month'). Natural language time.",
            "lead_time": "Relative offset before event_time indicating when to notify. Use only if the user specifies a relative time (e.g., '30 minutes before', '2 hours earlier', 'the day before'). Store as a duration string or normalized minutes. If lead_time is set, event_time MUST also be set. Do not infer event_time.",
        },
    },
    ActionType.CREATE_TASK: {
        "required": ["title", "description"],
        "optional": ["datetime", "priority", "tags"],
        "schema": {
            "title": "Short, imperative summary of the reminder suitable as a notification title (string, required). Example: 'Call John', 'Submit tax form'",
            "description": "Full info about the task to be done (string, required)",
            "datetime": "Due date (ISO format or natural language)",
            "priority": "Priority level: low, medium, high, urgent",
            "tags": "Comma-separated tags",
        },
    },
    ActionType.SCHEDULE_MEETING: {
        "required": ["title", "description"],
        "optional": ["datetime_start", "datetime_end", "participants", "location"],
        "schema": {
            "title": "Short, imperative summary of the reminder suitable as a notification title (string, required). Example: 'Call with John', 'Vacation discussion'",
            "description": "Full natural-language description of what needs to be done, including context or details not suitable for the title (string, required)",
            "datetime_start": "Start time (ISO format or natural language)",
            "datetime_end": "End time (ISO format or natural language)",
            "participants": "Comma-separated list of attendees",
            "location": "Meeting location or 'online'",
        },
    },
    ActionType.DELETE_REMINDER: {
        "required": [],
        "optional": ["reminder_id", "title"],
        "schema": {
            "reminder_id": "ID of the reminder to delete",
            "title": "Title of the reminder to identify it",
        },
    },
    ActionType.DELETE_TASK: {
        "required": [],
        "optional": ["task_id", "title"],
        "schema": {
            "task_id": "ID of the task to delete",
            "title": "Title of the task to identify it",
        },
    },
    ActionType.COMPLETE_TASK: {
        "required": [],
        "optional": ["task_id", "title"],
        "schema": {
            "task_id": "ID of the task to complete",
            "title": "Title of the task to identify it",
        },
    },
    ActionType.CANCEL_MEETING: {
        "required": [],
        "optional": ["meeting_id", "title"],
        "schema": {
            "meeting_id": "ID of the meeting to cancel",
            "title": "Title of the meeting to identify it",
        },
    },
}


class ParameterExtractor:
    """Extract parameters from user input using LLM."""

    def __init__(self, openai_api_key: str, model: str = "gpt-4.1-mini"):
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.model = model

    async def extract(
        self,
        user_input: str,
        action_type: ActionType,
    ) -> Dict[str, Any]:
        """Extract parameters for the given action type from user input."""
        params_config = ACTION_PARAMETERS.get(action_type)
        if not params_config:
            return {}

        schema = params_config.get("schema", {})
        if not schema:
            return {}

        prompt = self._build_extraction_prompt(user_input, action_type, schema)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract only the predefined parameters from the user input and return them as a valid JSON object.\n"
                            "Include ONLY fields that are explicitly mentioned or clearly implied.\n"
                            "Do NOT invent values, do NOT guess times, and do NOT include null fields.\n"
                            "Return JSON only, with no extra text."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if content:
                params = json.loads(content)
                logger.info(f"Extracted parameters: {params}")
                return params

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse parameters JSON: {e}")
        except Exception as e:
            logger.error(f"Error extracting parameters: {e}")

        return {}

    def _build_extraction_prompt(
        self,
        user_input: str,
        action_type: ActionType,
        schema: Dict[str, str],
    ) -> str:
        """Build the prompt for parameter extraction."""
        schema_description = "\n".join(
            f"- {key}: {description}" for key, description in schema.items()
        )

        return f"""Extract parameters from this user input according to the schema.

User input: "{user_input}"

Expected parameters:
{schema_description}

Return a JSON object with the extracted parameters. Only include parameters that are explicitly mentioned or can be clearly inferred from the input. If a datetime is mentioned naturally (like "tomorrow" or "in 2 hours"), include it as-is.

IMPORTANT for reminders - distinguish between:
1. remind_at_explicit: When user says "remind me AT <time>" - this is when they want to RECEIVE the notification
2. event_time: When user says something "is at <time>" or "happens at <time>" - this is when the EVENT occurs
3. lead_time: When user says "notify X before" or "remind X before" - this is the advance notice time

Example outputs:
- For "remind me at 4pm to buy milk": {{"title": "buy milk", "description": "buy milk", "remind_at_explicit": "4pm"}}
- For "remind me about the meeting at 4pm": {{"title": "meeting", "description": "meeting at 4pm", "event_time": "4pm"}}
- For "remind me about doctor at 4pm, notify 1 hour before": {{"title": "doctor", "description": "doctor appointment", "event_time": "4pm", "lead_time": "1 hour"}}
- For "remind me tomorrow morning to call mom": {{"title": "call mom", "description": "call mom", "remind_at_explicit": "tomorrow morning"}}
- For "don't let me forget the presentation tomorrow at 2pm": {{"title": "presentation", "description": "presentation", "event_time": "tomorrow at 2pm"}}
- For "create task fix the bug": {{"title": "fix the bug", "description": "fix the bug"}}
- For "schedule meeting with John at 2pm": {{"title": "meeting with John", "description": "meeting with John", "participants": "John", "datetime_start": "2pm"}}
"""

    def get_missing_parameters(
        self,
        action_type: ActionType,
        extracted_params: Dict[str, Any],
    ) -> List[str]:
        """Get list of required parameters that are missing."""
        params_config = ACTION_PARAMETERS.get(action_type)
        if not params_config:
            return []

        required = params_config.get("required", [])
        return [param for param in required if param not in extracted_params]

    def get_parameter_schema(self, action_type: ActionType) -> Dict[str, str]:
        """Get the parameter schema for an action type."""
        params_config = ACTION_PARAMETERS.get(action_type)
        if not params_config:
            return {}
        return params_config.get("schema", {})
