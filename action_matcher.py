"""
Embedding and action matching module.
Uses OpenAI embeddings to match user input to predefined actions.
"""
import logging
import os
from typing import List, Optional, Tuple
import numpy as np
from openai import OpenAI

from models import ActionType, Action, PredefinedAction, Parameter

logger = logging.getLogger(__name__)


class ActionMatcher:
    """Matches user input to predefined actions using embeddings."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the ActionMatcher.

        Args:
            api_key: OpenAI API key. If not provided, will use OPENAI_API_KEY env var.
        """
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.predefined_actions = self._load_predefined_actions()
        self.action_embeddings = {}
        self._compute_action_embeddings()

    def _load_predefined_actions(self) -> List[PredefinedAction]:
        """
        Load predefined actions that inputs will be matched against.

        Returns:
            List of predefined actions.
        """
        return [
            PredefinedAction(
                action_type=ActionType.SEND_MESSAGE,
                keywords=["send", "message", "tell", "message to"],
                description="Send a message to a recipient",
                required_parameters=["recipient", "message"],
                example_inputs=[
                    "Send a message to John saying hello",
                    "Tell Sarah that I'll be late"
                ]
            ),
            PredefinedAction(
                action_type=ActionType.SCHEDULE_MEETING,
                keywords=["schedule", "meeting", "appointment", "calendar", "book"],
                description="Schedule a meeting with participants",
                required_parameters=["attendee", "date", "time"],
                example_inputs=[
                    "Schedule a meeting with John tomorrow at 2 PM",
                    "Book an appointment with the team next Monday at 10 AM"
                ]
            ),
            PredefinedAction(
                action_type=ActionType.CREATE_REMINDER,
                keywords=["remind", "reminder", "remember", "set alarm"],
                description="Create a reminder for a task",
                required_parameters=["task", "time"],
                example_inputs=[
                    "Remind me to call the dentist tomorrow",
                    "Set a reminder for the meeting in 30 minutes"
                ]
            ),
            PredefinedAction(
                action_type=ActionType.GET_WEATHER,
                keywords=["weather", "temperature", "rain", "forecast", "sunny"],
                description="Get weather information",
                required_parameters=["location"],
                example_inputs=[
                    "What's the weather in New York?",
                    "Tell me the forecast for tomorrow in London"
                ]
            ),
            PredefinedAction(
                action_type=ActionType.SEARCH_INFORMATION,
                keywords=["search", "find", "look up", "google", "information"],
                description="Search for information",
                required_parameters=["query"],
                example_inputs=[
                    "Search for Python documentation",
                    "Find information about artificial intelligence"
                ]
            ),
            PredefinedAction(
                action_type=ActionType.SEND_EMAIL,
                keywords=["email", "mail", "send email", "compose email"],
                description="Send an email",
                required_parameters=["recipient", "subject", "body"],
                example_inputs=[
                    "Send an email to john@example.com about the project",
                    "Email the team with the meeting notes"
                ]
            ),
            PredefinedAction(
                action_type=ActionType.CREATE_TASK,
                keywords=["task", "todo", "create task", "add task"],
                description="Create a new task",
                required_parameters=["task_name"],
                example_inputs=[
                    "Create a task to fix the bug",
                    "Add a task for code review"
                ]
            ),
            PredefinedAction(
                action_type=ActionType.UPDATE_CALENDAR,
                keywords=["calendar", "schedule", "block time", "update calendar"],
                description="Update calendar with event",
                required_parameters=["event_name", "date", "time"],
                example_inputs=[
                    "Block 2 hours on my calendar for the presentation",
                    "Update calendar with lunch plans on Friday"
                ]
            ),
        ]

    def _compute_action_embeddings(self):
        """Compute embeddings for predefined action descriptions."""
        logger.info("Computing embeddings for predefined actions...")

        for action in self.predefined_actions:
            try:
                # Combine keywords and description for better embedding
                text = f"{action.description} {' '.join(action.keywords)}"
                embedding = self._get_embedding(text)
                self.action_embeddings[action.action_type] = embedding
            except Exception as e:
                logger.error(f"Error computing embedding for {action.action_type}: {e}")

        logger.info(f"Computed embeddings for {len(self.action_embeddings)} actions")

    def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for a text using OpenAI.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector.
        """
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            raise

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector.
            vec2: Second vector.

        Returns:
            Cosine similarity score (0-1).
        """
        vec1_array = np.array(vec1)
        vec2_array = np.array(vec2)

        dot_product = np.dot(vec1_array, vec2_array)
        norm1 = np.linalg.norm(vec1_array)
        norm2 = np.linalg.norm(vec2_array)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    async def match_action(self, user_input: str) -> Tuple[ActionType, float, List[float]]:
        """
        Match user input to a predefined action using embeddings.

        Args:
            user_input: User's input text.

        Returns:
            Tuple of (matched_action_type, confidence_score, input_embedding).

        Raises:
            Exception: If matching fails.
        """
        try:
            logger.info(f"Matching action for input: {user_input[:100]}...")

            # Get embedding for user input
            input_embedding = self._get_embedding(user_input)

            # Compute similarity with all action embeddings
            similarities = {}
            for action_type, action_embedding in self.action_embeddings.items():
                similarity = self._cosine_similarity(input_embedding, action_embedding)
                similarities[action_type] = similarity

            # Find best match
            best_match = max(similarities, key=similarities.get)
            confidence = similarities[best_match]

            logger.info(f"Matched action: {best_match} (confidence: {confidence:.2f})")

            return best_match, confidence, input_embedding

        except Exception as e:
            logger.error(f"Error matching action: {e}")
            raise

    def get_predefined_action(self, action_type: ActionType) -> Optional[PredefinedAction]:
        """
        Get predefined action schema by type.

        Args:
            action_type: Action type to retrieve.

        Returns:
            Predefined action schema or None.
        """
        for action in self.predefined_actions:
            if action.action_type == action_type:
                return action
        return None

    def extract_parameters(self, user_input: str, action_type: ActionType) -> dict:
        """
        Extract parameters from user input for a specific action.
        This is a simple implementation - can be enhanced with LLM.

        Args:
            user_input: User's input text.
            action_type: Type of action.

        Returns:
            Dictionary of extracted parameters.
        """
        logger.info(f"Extracting parameters for {action_type}...")

        # Get the predefined action schema
        action_schema = self.get_predefined_action(action_type)
        if not action_schema:
            return {}

        # Simple parameter extraction - can be enhanced with LLM
        parameters = {}

        # This is a basic implementation. For production, use an LLM like GPT to extract parameters
        # Here's an example of how you might use LLM for parameter extraction:
        try:
            extraction_prompt = f"""
            Extract parameters from the user input for a {action_type} action.
            Required parameters: {', '.join(action_schema.required_parameters)}
            User input: "{user_input}"
            
            Return a JSON object with the extracted parameters.
            If a parameter is not found, use null or reasonable defaults.
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a parameter extraction assistant. Return valid JSON only."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )

            import json
            response_text = response.choices[0].message.content.strip()

            # Try to parse JSON from response
            try:
                parameters = json.loads(response_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract from text
                logger.warning(f"Could not parse JSON response: {response_text}")
                parameters = {}

        except Exception as e:
            logger.error(f"Error extracting parameters: {e}")
            parameters = {}

        logger.info(f"Extracted parameters: {parameters}")
        return parameters

