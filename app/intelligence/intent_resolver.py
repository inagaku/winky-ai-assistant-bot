"""Intent resolver - main orchestrator for NLP processing."""

import logging
from typing import Optional, Tuple, Union

from app.models import (
    ActionIntent,
    ActionType,
    ActionStatus,
    ClarificationOption,
    ClarificationRequest,
    ClarificationType,
    ParsedAction,
)
from app.i18n import t

from .semantic_matcher import SemanticMatcher
from .parameter_extractor import ParameterExtractor
from .clarification_manager import ClarificationManager
from ..config import get_settings

logger = logging.getLogger(__name__)


class IntentResolver:
    """
    Main NLP orchestrator that resolves user input to executable actions.

    Flow:
    1. Match user input to action type using semantic embeddings
    2. Extract parameters using LLM
    3. Check if clarification is needed (low confidence or missing params)
    4. Return either a ready-to-execute ParsedAction or a ClarificationRequest
    """

    def __init__(self, openai_api_key: str):
        self.settings = get_settings()
        self.semantic_matcher = SemanticMatcher(openai_api_key)
        self.parameter_extractor = ParameterExtractor(openai_api_key)
        self.clarification_manager = ClarificationManager(self.parameter_extractor)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the resolver (pre-compute embeddings)."""
        if self._initialized:
            return
        await self.semantic_matcher.initialize()
        self._initialized = True

    async def resolve(
        self,
        user_input: str,
        user_id: int,
        chat_id: int,
        message_id: Optional[int] = None,
        skip_clarification: bool = False,
        locale: str = "en",
    ) -> Union[ParsedAction, ClarificationRequest]:
        """
        Resolve user input to an action or clarification request.

        Args:
            user_input: The user's message text
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message_id: Original message ID for replies
            skip_clarification: If True, skip clarification checks (for high-trust scenarios)
            locale: User's language preference for messages

        Returns:
            ParsedAction if ready to execute, ClarificationRequest if clarification needed
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"Resolving intent for: '{user_input[:100]}...'")

        # Step 1: Match to action type
        intent = await self.semantic_matcher.match(user_input, locale=locale)

        # Handle unknown/unmatched input
        if intent.action_type == ActionType.UNKNOWN or intent.confidence < self.settings.intention_low_confidence_threshold:
            return ClarificationRequest(
                type=ClarificationType.AMBIGUOUS_INPUT,
                message=t("clarify_ambiguous", locale=locale),
                options=[
                    ClarificationOption(
                        text=t("button_show_help", locale=locale),
                        callback_data="quick:help",
                    ),
                    ClarificationOption(
                        text=t("button_show_summary", locale=locale),
                        callback_data="quick:summary",
                    ),
                ],
            )

        # Step 2: Extract parameters
        parameters = await self.parameter_extractor.extract(user_input, intent.action_type)

        # Step 3: Create the action (we'll need it whether we clarify or not)
        action = ParsedAction(
            intent=intent,
            parameters=parameters,
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            status=ActionStatus.PENDING,
        )

        # Step 4: Check if clarification is needed (unless skipped)
        if not skip_clarification:
            # Get alternatives for potential clarification
            alternatives = await self.semantic_matcher.match_with_alternatives(user_input, top_n=3, locale=locale)

            clarification = await self.clarification_manager.check_and_clarify(
                intent, parameters, alternatives, locale=locale
            )

            if clarification is not None:
                # Attach the original action so it can be used when user confirms
                clarification.original_action = action
                return clarification

        logger.info(
            f"Resolved action: {action.action_type} with confidence {action.confidence:.2f}"
        )
        return action

    async def get_action_suggestions(self, partial_input: str) -> list:
        """
        Get action suggestions based on partial input.

        Useful for autocomplete or helping users.
        """
        if not self._initialized:
            await self.initialize()

        alternatives = await self.semantic_matcher.match_with_alternatives(
            partial_input, top_n=5
        )

        suggestions = []
        for action_type, score in alternatives:
            if score > 0.3:
                info = self.semantic_matcher.get_action_info(action_type)
                if info:
                    suggestions.append({
                        "action": action_type.value,
                        "description": info["description"],
                        "confidence": score,
                        "examples": info["examples"][:2],
                    })

        return suggestions
