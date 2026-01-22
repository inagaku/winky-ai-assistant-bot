"""Parameter extractor using LLM."""

import json
import logging
import textwrap
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from app.models import ActionType

logger = logging.getLogger(__name__)


# Required parameters for each action type
ACTION_PARAMETERS: Dict[ActionType, Dict[str, Any]] = {
    ActionType.CREATE_REMINDER: {
        "required": ["title", "description", "remind_at_explicit or event_time"],
        "optional": ["remind_at_explicit", "event_time", "lead_time"],
        "semantic": {
            "title": "Short, imperative summary of the reminder suitable as a notification title (string, required). Example: 'Call John', 'Submit tax form'",
            "description": "Full natural-language description of what needs to be done, including context or details not suitable for the title (string, required)",
            "remind_at_explicit": "When the user specifies WHEN they want to receive the notification, either as an absolute time (`at 4pm`, `tomorrow morning`, 'for 3pm') or a relative time (`in 30 minutes','after 2 hours`), and the time is not tied to an event.",
            "event_time": "When the actual event or action occurs (not the notification). Use if the user describes something happening at a time (e.g., 'the meeting is at 3pm', 'my flight departs tomorrow at 9', 'I need to do it by the end of month', 'to do something tomorrow`). Natural language time.",
            "lead_time": "Relative offset before event_time indicating when to notify. Use only if the user specifies a relative time (e.g., '30 minutes before', '2 hours earlier', 'the day before'). Store as a duration string or normalized minutes. If lead_time is set, event_time MUST also be set. Do not infer event_time.",
        },
        "time_interpretation_rules": textwrap.dedent("""\
            - At least one of remind_at_explicit and event_time parameters HAVE TO BE populated.
            - If a relative time (e.g., "in 30 minutes") is mentioned and NO event_time exists, it MUST be interpreted as remind_at_explicit.
            - lead_time MUST NOT be set unless event_time is present."""),
        "precedence_rules": textwrap.dedent("""\
            - If a relative time (e.g., "in 30 minutes") is mentioned and NO event_time exists, it MUST be interpreted as remind_at_explicit.
            - lead_time MUST NOT be set unless event_time is present."""),

    },
    ActionType.CREATE_TASK: {
        "required": ["title", "description"],
        "optional": ["datetime", "priority", "tags"],
        "semantic": {
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
        "semantic": {
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
        "semantic": {
            "reminder_id": "ID of the reminder to delete",
            "title": "Title of the reminder to identify it",
        },
    },
    ActionType.DELETE_TASK: {
        "required": [],
        "optional": ["task_id", "title"],
        "semantic": {
            "task_id": "ID of the task to delete",
            "title": "Title of the task to identify it",
        },
    },
    ActionType.COMPLETE_TASK: {
        "required": [],
        "optional": ["task_id", "title"],
        "semantic": {
            "task_id": "ID of the task to complete",
            "title": "Title of the task to identify it",
        },
    },
    ActionType.CANCEL_MEETING: {
        "required": [],
        "optional": ["meeting_id", "title"],
        "semantic": {
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

        if not ACTION_PARAMETERS.get(action_type):
            return {}

        system_prompt = self._build_system_prompt(action_type)

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ])

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

    def _build_system_prompt(
        self,
        action_type: ActionType,
    ) -> str:
        """Build the system prompt for parameter extraction."""

        params_config = ACTION_PARAMETERS.get(action_type)
        required_fields_block = "\n".join(f"- {f}" for f in params_config.get("required"))
        optional_fields_block = "\n".join(f"- {f}" for f in params_config.get("optional"))
        params_semantic_block = "\n".join(f"- {name}: {desc}" for name, desc in params_config.get("semantic").items())
        time_interpretation_rules = params_config.get("time_interpretation_rules", "No rules.")
        precedence_rules = params_config.get("precedence_rules", "No rules.")

        return f"""\
You are a parameter extraction assistant.

Extract parameters from user input and return a valid JSON object.
Include ONLY fields that are explicitly mentioned or clearly implied.
Do NOT invent values, do NOT guess times, and do NOT include null fields.

Required fields:
{required_fields_block}

Optional fields:
{optional_fields_block}

Field semantics:
{params_semantic_block}

Time interpretation rules:
{time_interpretation_rules}

Precedence rules:
{precedence_rules}

Output rules:
- Return JSON only, with no extra text.
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
