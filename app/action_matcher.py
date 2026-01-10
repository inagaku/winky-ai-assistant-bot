"""
Embedding and action matching module.
Uses OpenAI embeddings to match user input to predefined actions.
"""
import json
import logging
import os
from typing import List, Optional, Tuple

import numpy as np
from openai import OpenAI

from models import PredefinedAction, load_predefined_actions

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
        self.predefined_actions = load_predefined_actions()
        self.action_embeddings = {}
        self._compute_action_embeddings()

        logger.info(f"Loaded {len(self.predefined_actions)} actions from config: "
                    f"{[a.action_type for a in self.predefined_actions]}")

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

    async def match_action(self, user_input: str) -> Tuple[str, float, List[float]]:
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

    def get_predefined_action(self, action_type: str) -> Optional[PredefinedAction]:
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

    def extract_parameters(self, user_input: str, action_type: str) -> dict:
        """
        Extract parameters from user input for a specific action using LLM.

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
            logger.warning(f"No schema found for action type: {action_type}")
            return {}

        parameters = {}

        try:
            extraction_prompt = f"""
Extract parameters from the user input for a {action_type} action.
Required parameters: {', '.join(action_schema.required_parameters)}
User input: "{user_input}"

Return a JSON object with the extracted parameters.
If a parameter is not found, use null or reasonable defaults.
Only return valid JSON, no explanation.
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

            response_text = response.choices[0].message.content.strip()

            # Try to parse JSON from response
            try:
                # Handle potential markdown code blocks
                if response_text.startswith("```"):
                    response_text = response_text.split("```")[1]
                    if response_text.startswith("json"):
                        response_text = response_text[4:]
                    response_text = response_text.strip()

                parameters = json.loads(response_text)
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON response: {response_text}")
                parameters = {}

        except Exception as e:
            logger.error(f"Error extracting parameters: {e}")
            parameters = {}

        logger.info(f"Extracted parameters: {parameters}")
        return parameters

    def reload_actions(self):
        """Reload actions from config file (useful for hot-reloading)."""
        logger.info("Reloading actions from config...")
        self.predefined_actions = load_predefined_actions()
        self.action_embeddings = {}
        self._compute_action_embeddings()
        logger.info(f"Reloaded {len(self.predefined_actions)} actions")
