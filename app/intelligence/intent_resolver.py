"""Intent resolver - main orchestrator for NLP processing."""

import logging
from typing import Optional, Tuple, Union

from app.models import (
    ActionIntent,
    ActionType,
    ActionStatus,
    ClarificationRequest,
    ParsedAction,
)

from .semantic_matcher import SemanticMatcher
from .parameter_extractor import ParameterExtractor
from .clarification_manager import ClarificationManager

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
    ) -> Union[ParsedAction, ClarificationRequest]:
        """
        Resolve user input to an action or clarification request.

        Args:
            user_input: The user's message text
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message_id: Original message ID for replies
            skip_clarification: If True, skip clarification checks (for high-trust scenarios)

        Returns:
            ParsedAction if ready to execute, ClarificationRequest if clarification needed
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"Resolving intent for: '{user_input[:100]}...'")

        # Step 1: Match to action type
        intent = await self.semantic_matcher.match(user_input)

        # Handle unknown/unmatched input
        if intent.action_type == ActionType.UNKNOWN or intent.confidence < 0.3:
            return ClarificationRequest(
                type="ambiguous_input",
                message="I'm not sure what you'd like me to do. Could you try rephrasing or use /help to see what I can do?",
                options=["Show help", "Show my summary"],
            )

        # Step 2: Extract parameters
        parameters = await self.parameter_extractor.extract(user_input, intent.action_type)

        # Step 3: Check if clarification is needed (unless skipped)
        if not skip_clarification:
            # Get alternatives for potential clarification
            alternatives = await self.semantic_matcher.match_with_alternatives(user_input, top_n=3)

            clarification = await self.clarification_manager.check_and_clarify(
                intent, parameters, alternatives
            )

            if clarification is not None:
                return clarification

        # Step 4: Create and return ParsedAction
        action = ParsedAction(
            intent=intent,
            parameters=parameters,
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            status=ActionStatus.PENDING,
        )

        logger.info(
            f"Resolved action: {action.action_type} with confidence {action.confidence:.2f}"
        )
        return action

    async def resolve_with_context(
        self,
        user_input: str,
        user_id: int,
        chat_id: int,
        message_id: Optional[int] = None,
        previous_clarification: Optional[ClarificationRequest] = None,
        clarification_response: Optional[str] = None,
    ) -> Union[ParsedAction, ClarificationRequest]:
        """
        Resolve with context from a previous clarification.

        Use this when the user is responding to a clarification request.
        """
        if previous_clarification and clarification_response:
            # Process the clarification response
            # For now, just re-resolve with the new input
            # In a more sophisticated implementation, we'd use the context
            return await self.resolve(
                user_input=clarification_response,
                user_id=user_id,
                chat_id=chat_id,
                message_id=message_id,
                skip_clarification=True,  # User already provided clarification
            )

        return await self.resolve(
            user_input=user_input,
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
        )

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
