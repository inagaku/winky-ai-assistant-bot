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
        "optional": ["datetime"],
        "schema": {
            "title": "Short description of the reminder (string, required)",
            "description": "Full info about the action to be done (string, required)",
            "datetime": "When to remind (ISO format or natural language like 'tomorrow at 3pm')",
        },
    },
    ActionType.CREATE_TASK: {
        "required": ["title", "description"],
        "optional": ["datetime", "priority", "tags"],
        "schema": {
            "title": "Short description of the task (string, required)",
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
            "title": "Short description of the meeting (string, required)",
            "description": "Full info about the meeting to be scheduled (string, required)",
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

    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini"):
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
                        "content": "You are a parameter extraction assistant. Extract parameters from user input and return them as JSON. Only include parameters that are explicitly mentioned or can be clearly inferred. Return an empty object {} if no parameters can be extracted.",
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

        return f"""Extract parameters from this user input for a {action_type.value} action.

User input: "{user_input}"

Expected parameters:
{schema_description}

Return a JSON object with the extracted parameters. Only include parameters that are explicitly mentioned or can be clearly inferred from the input. If a datetime is mentioned naturally (like "tomorrow" or "in 2 hours"), include it as-is.

Example outputs:
- For "remind me to call mom tomorrow at 3pm": {{"task": "call mom", "datetime": "tomorrow at 3pm"}}
- For "create task fix the bug": {{"task_name": "fix the bug"}}
- For "schedule meeting with John at 2pm": {{"title": "meeting with John", "participants": "John", "datetime_start": "2pm"}}
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
