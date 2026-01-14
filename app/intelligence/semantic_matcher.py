"""Semantic matcher using OpenAI embeddings."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from openai import AsyncOpenAI

from app.models import ActionType, ActionIntent

logger = logging.getLogger(__name__)

# Supported languages for action definitions
SUPPORTED_LANGUAGES = ["en", "ru"]

# Directory containing action definition files
ACTION_DEFINITIONS_DIR = Path(__file__).parent / "action_definitions"


def load_action_definitions(language: str) -> Dict[str, Dict]:
    """Load action definitions for a specific language."""
    file_path = ACTION_DEFINITIONS_DIR / f"{language}.json"
    if not file_path.exists():
        logger.warning(f"Action definitions not found for language: {language}")
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_action_definitions() -> Dict[str, Dict[str, Dict]]:
    """Load action definitions for all supported languages."""
    definitions = {}
    for lang in SUPPORTED_LANGUAGES:
        definitions[lang] = load_action_definitions(lang)
    return definitions


class SemanticMatcher:
    """Match user input to actions using semantic embeddings."""

    def __init__(self, openai_api_key: str, model: str = "text-embedding-3-small"):
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.model = model
        # Embeddings stored per language: {lang: {ActionType: embedding}}
        self._action_embeddings: Dict[str, Dict[ActionType, List[float]]] = {}
        # Action definitions per language
        self._action_definitions: Dict[str, Dict[str, Dict]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Pre-compute embeddings for all action definitions in all languages."""
        if self._initialized:
            return

        logger.info("Loading action definitions and computing embeddings...")
        self._action_definitions = load_all_action_definitions()

        for lang, definitions in self._action_definitions.items():
            self._action_embeddings[lang] = {}

            for action_name, definition in definitions.items():
                try:
                    action_type = ActionType(action_name.lower())
                except ValueError:
                    logger.warning(f"Unknown action type: {action_name}")
                    continue

                # Combine keywords, description, and examples for rich embedding
                text_parts = [
                    definition.get("description", ""),
                    " ".join(definition.get("keywords", [])),
                    " ".join(definition.get("examples", [])),
                ]
                combined_text = " | ".join(text_parts)
                embedding = await self._get_embedding(combined_text)
                self._action_embeddings[lang][action_type] = embedding

            logger.info(f"Computed {len(self._action_embeddings[lang])} embeddings for language: {lang}")

        self._initialized = True
        total = sum(len(emb) for emb in self._action_embeddings.values())
        logger.info(f"Computed total of {total} action embeddings across {len(SUPPORTED_LANGUAGES)} languages")

    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using OpenAI API."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a_np = np.array(a)
        b_np = np.array(b)
        return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))

    async def match(self, user_input: str, locale: str = "en") -> ActionIntent:
        """Match user input to the best action type for the given locale."""
        if not self._initialized:
            await self.initialize()

        # Get embedding for user input
        input_embedding = await self._get_embedding(user_input)

        # Use the specified locale, fall back to English if not available
        embeddings = self._action_embeddings.get(locale) or self._action_embeddings.get("en", {})

        # Find best matching action
        best_action = ActionType.UNKNOWN
        best_score = 0.0

        for action_type, action_embedding in embeddings.items():
            similarity = self._cosine_similarity(input_embedding, action_embedding)
            if similarity > best_score:
                best_score = similarity
                best_action = action_type

        logger.info(f"Matched '{user_input[:50]}...' to {best_action} (confidence: {best_score:.2f}, locale: {locale})")

        return ActionIntent(
            action_type=best_action,
            confidence=best_score,
            original_input=user_input,
            embedding=input_embedding,
        )

    async def match_with_alternatives(
        self, user_input: str, top_n: int = 3, locale: str = "en"
    ) -> List[Tuple[ActionType, float]]:
        """Match user input and return top N alternatives with scores for the given locale."""
        if not self._initialized:
            await self.initialize()

        input_embedding = await self._get_embedding(user_input)

        # Use the specified locale, fall back to English if not available
        embeddings = self._action_embeddings.get(locale) or self._action_embeddings.get("en", {})

        scores = []
        for action_type, action_embedding in embeddings.items():
            similarity = self._cosine_similarity(input_embedding, action_embedding)
            scores.append((action_type, similarity))

        # Sort by score descending and return top N
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]

    def get_action_info(self, action_type: ActionType, language: str = "en") -> Optional[Dict]:
        """Get information about an action type for a specific language."""
        lang_definitions = self._action_definitions.get(language, {})
        return lang_definitions.get(action_type.value.upper())
