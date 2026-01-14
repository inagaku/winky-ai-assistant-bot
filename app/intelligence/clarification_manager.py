"""Clarification manager for handling low confidence and missing parameters."""

import logging
from typing import List, Optional, Tuple, Union

from app.models import (
    ActionIntent,
    ActionType,
    ClarificationRequest,
    ClarificationType,
    ParsedAction,
)

from .parameter_extractor import ParameterExtractor

logger = logging.getLogger(__name__)


class ClarificationManager:
    """Manage clarification requests for ambiguous or incomplete inputs."""

    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.7
    LOW_CONFIDENCE_THRESHOLD = 0.4

    def __init__(self, parameter_extractor: ParameterExtractor):
        self.parameter_extractor = parameter_extractor

    async def check_and_clarify(
        self,
        intent: ActionIntent,
        parameters: dict,
        alternatives: Optional[List[Tuple[ActionType, float]]] = None,
    ) -> Union[ParsedAction, ClarificationRequest]:
        """
        Check if clarification is needed and return either a ready action or clarification request.

        Returns:
            ParsedAction if ready to execute, or ClarificationRequest if clarification needed.
        """
        # Case 1: Very low confidence - we're not sure what the user wants
        if intent.confidence < self.LOW_CONFIDENCE_THRESHOLD:
            return self._request_action_confirmation(intent, alternatives)

        # Case 2: Medium confidence - ask for confirmation
        if intent.confidence < self.HIGH_CONFIDENCE_THRESHOLD:
            return self._request_action_confirmation(intent, alternatives)

        # Case 3: High confidence but missing required parameters
        missing_params = self.parameter_extractor.get_missing_parameters(
            intent.action_type, parameters
        )
        if missing_params:
            return self._request_missing_parameter(intent, parameters, missing_params[0])

        # Case 4: Ready to execute - return as ParsedAction placeholder
        # The actual ParsedAction will be created by IntentResolver
        return None  # Signal that no clarification is needed

    def _request_action_confirmation(
        self,
        intent: ActionIntent,
        alternatives: Optional[List[Tuple[ActionType, float]]] = None,
    ) -> ClarificationRequest:
        """Request confirmation for the detected action."""
        action_descriptions = {
            ActionType.CREATE_REMINDER: "create a reminder",
            ActionType.LIST_REMINDERS: "show your reminders",
            ActionType.DELETE_REMINDER: "delete a reminder",
            ActionType.CREATE_TASK: "create a task",
            ActionType.LIST_TASKS: "show your tasks",
            ActionType.COMPLETE_TASK: "complete a task",
            ActionType.DELETE_TASK: "delete a task",
            ActionType.SCHEDULE_MEETING: "schedule a meeting",
            ActionType.LIST_MEETINGS: "show your meetings",
            ActionType.CANCEL_MEETING: "cancel a meeting",
            ActionType.SHOW_SUMMARY: "show your summary",
            ActionType.HELP: "show help",
        }

        primary_action = action_descriptions.get(
            intent.action_type, str(intent.action_type.value)
        )

        # Build options from alternatives
        options = [f"Yes, {primary_action}"]
        if alternatives:
            for alt_action, score in alternatives[1:3]:  # Top 2 alternatives
                if score > 0.4:  # Only show reasonable alternatives
                    alt_desc = action_descriptions.get(alt_action, str(alt_action.value))
                    options.append(f"No, {alt_desc}")

        options.append("Something else")

        confidence_pct = int(intent.confidence * 100)
        message = f"I'm {confidence_pct}% sure you want to {primary_action}. Is that correct?"

        return ClarificationRequest(
            type=ClarificationType.CONFIRM_ACTION,
            message=message,
            options=options,
            original_action=None,  # Will be set by caller if needed
        )

    def _request_missing_parameter(
        self,
        intent: ActionIntent,
        current_params: dict,
        missing_param: str,
    ) -> ClarificationRequest:
        """Request a missing required parameter."""
        # User-friendly parameter prompts
        param_prompts = {
            "title": "What's the title?",
            "description": "What should I do?",
            "datetime": "When should this be?",
            "datetime_start": "When should this start?",
            "datetime_end": "When should this end?",
            "participants": "Who should attend?",
        }

        message = param_prompts.get(
            missing_param, f"What should the {missing_param} be?"
        )

        # Provide helpful time options for datetime parameters
        options = []
        if "datetime" in missing_param.lower():
            options = [
                "In 1 hour",
                "Tomorrow morning",
                "Tomorrow afternoon",
                "Next week",
            ]

        return ClarificationRequest(
            type=ClarificationType.MISSING_PARAMETER,
            message=message,
            parameter=missing_param,
            options=options,
            original_action=None,
        )

    def process_clarification_response(
        self,
        original_intent: ActionIntent,
        original_params: dict,
        clarification: ClarificationRequest,
        user_response: str,
    ) -> Tuple[ActionIntent, dict]:
        """
        Process user's response to a clarification request.

        Returns updated intent and parameters.
        """
        if clarification.type == ClarificationType.CONFIRM_ACTION:
            # User confirmed or selected an alternative
            response_lower = user_response.lower()
            if response_lower.startswith("yes"):
                return original_intent, original_params
            elif "something else" in response_lower:
                # User wants to try again - return unknown action to trigger re-processing
                return ActionIntent(
                    action_type=ActionType.UNKNOWN,
                    confidence=0.0,
                    original_input=original_intent.original_input,
                ), {}
            else:
                # User selected an alternative - would need to parse which one
                # For now, treat as re-process
                return original_intent, original_params

        elif clarification.type == ClarificationType.MISSING_PARAMETER:
            # User provided the missing parameter
            updated_params = original_params.copy()
            updated_params[clarification.parameter] = user_response
            return original_intent, updated_params

        return original_intent, original_params

    def needs_clarification(
        self,
        intent: ActionIntent,
        parameters: dict,
    ) -> bool:
        """Quick check if clarification would be needed."""
        if intent.confidence < self.HIGH_CONFIDENCE_THRESHOLD:
            return True

        missing = self.parameter_extractor.get_missing_parameters(
            intent.action_type, parameters
        )
        return len(missing) > 0
