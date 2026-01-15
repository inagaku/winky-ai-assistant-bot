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
from app.i18n import t

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
        locale: str = "en",
    ) -> Union[ParsedAction, ClarificationRequest]:
        """
        Check if clarification is needed and return either a ready action or clarification request.

        Returns:
            ParsedAction if ready to execute, or ClarificationRequest if clarification needed.
        """
        # Case 1: Very low confidence - we're not sure what the user wants
        if intent.confidence < self.LOW_CONFIDENCE_THRESHOLD:
            return self._request_action_confirmation(intent, alternatives, locale)

        # Case 2: Medium confidence - ask for confirmation
        if intent.confidence < self.HIGH_CONFIDENCE_THRESHOLD:
            return self._request_action_confirmation(intent, alternatives, locale)

        # Case 3: High confidence but missing required parameters
        missing_params = self.parameter_extractor.get_missing_parameters(
            intent.action_type, parameters
        )
        if missing_params:
            return self._request_missing_parameter(intent, parameters, missing_params[0], locale)

        # Case 4: Ready to execute - return as ParsedAction placeholder
        # The actual ParsedAction will be created by IntentResolver
        return None  # Signal that no clarification is needed

    def _request_action_confirmation(
        self,
        intent: ActionIntent,
        alternatives: Optional[List[Tuple[ActionType, float]]] = None,
        locale: str = "en",
    ) -> ClarificationRequest:
        """Request confirmation for the detected action."""
        # Map action types to translation keys
        action_translation_keys = {
            ActionType.CREATE_REMINDER: "action_create_reminder",
            ActionType.LIST_REMINDERS: "action_list_reminders",
            ActionType.DELETE_REMINDER: "action_delete_reminder",
            ActionType.CREATE_TASK: "action_create_task",
            ActionType.LIST_TASKS: "action_list_tasks",
            ActionType.COMPLETE_TASK: "action_complete_task",
            ActionType.DELETE_TASK: "action_delete_task",
            ActionType.SCHEDULE_MEETING: "action_schedule_meeting",
            ActionType.LIST_MEETINGS: "action_list_meetings",
            ActionType.CANCEL_MEETING: "action_cancel_meeting",
            ActionType.SHOW_SUMMARY: "action_show_summary",
            ActionType.HELP: "action_help",
        }

        action_key = action_translation_keys.get(intent.action_type)
        primary_action = t(action_key, locale=locale) if action_key else str(intent.action_type.value)

        # Build options from alternatives
        yes_text = t("btn_yes", locale=locale)
        options = [f"{yes_text}, {primary_action}"]
        if alternatives:
            for alt_action, score in alternatives[1:3]:  # Top 2 alternatives
                if score > 0.4:  # Only show reasonable alternatives
                    alt_key = action_translation_keys.get(alt_action)
                    alt_desc = t(alt_key, locale=locale) if alt_key else str(alt_action.value)
                    no_text = t("btn_cancel", locale=locale)
                    options.append(f"{no_text}, {alt_desc}")

        options.append(t("btn_something_else", locale=locale))

        confidence_pct = int(intent.confidence * 100)
        message = t("clarify_confirm", locale=locale, confidence_pct=confidence_pct, action=primary_action)

        return ClarificationRequest(
            type=ClarificationType.CONFIRM_ACTION,
            message=message,
            options=options,
            original_action=None,  # Will be set by caller if needed
            alternatives=alternatives,  # Store alternatives for callback handling
        )

    def _request_missing_parameter(
        self,
        intent: ActionIntent,
        current_params: dict,
        missing_param: str,
        locale: str = "en",
    ) -> ClarificationRequest:
        """Request a missing required parameter."""
        # User-friendly parameter prompts (translation keys)
        param_prompt_keys = {
            "title": "param_prompt_title",
            "description": "param_prompt_description",
            "datetime": "param_prompt_datetime",
            "datetime_start": "param_prompt_datetime_start",
            "datetime_end": "param_prompt_datetime_end",
            "participants": "param_prompt_participants",
        }

        prompt_key = param_prompt_keys.get(missing_param)
        if prompt_key:
            message = t(prompt_key, locale=locale)
        else:
            message = t("param_prompt_generic", locale=locale, param=missing_param)

        # Provide helpful time options for datetime parameters
        options = []
        if "datetime" in missing_param.lower():
            options = [
                t("time_option_1hour", locale=locale),
                t("time_option_tomorrow_morning", locale=locale),
                t("time_option_tomorrow_afternoon", locale=locale),
                t("time_option_next_week", locale=locale),
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
