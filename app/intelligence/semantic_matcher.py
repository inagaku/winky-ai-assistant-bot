"""Semantic matcher using OpenAI embeddings."""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from openai import AsyncOpenAI

from app.models import ActionType, ActionIntent

logger = logging.getLogger(__name__)


# Action definitions with keywords and example phrases
ACTION_DEFINITIONS: Dict[ActionType, Dict] = {
    ActionType.CREATE_REMINDER: {
        "keywords": ["remind", "reminder", "remember", "don't forget", "alert me", "notify me"],
        "description": "Create a reminder for a task or event",
        "examples": [
            "remind me to call mom",
            "set a reminder for the meeting",
            "remember to buy groceries",
            "don't forget to submit the report",
        ],
    },
    ActionType.LIST_REMINDERS: {
        "keywords": ["show reminders", "list reminders", "my reminders", "what reminders"],
        "description": "Show all active reminders",
        "examples": [
            "show my reminders",
            "what reminders do I have",
            "list my reminders",
        ],
    },
    ActionType.DELETE_REMINDER: {
        "keywords": ["delete reminder", "remove reminder", "cancel reminder"],
        "description": "Delete a reminder",
        "examples": [
            "delete my reminder",
            "remove the reminder about",
            "cancel the reminder",
        ],
    },
    ActionType.CREATE_TASK: {
        "keywords": ["task", "todo", "to-do", "create task", "add task", "new task"],
        "description": "Create a new task or todo item",
        "examples": [
            "create a task to fix the bug",
            "add task review the code",
            "new task prepare presentation",
            "todo write documentation",
        ],
    },
    ActionType.LIST_TASKS: {
        "keywords": ["show tasks", "list tasks", "my tasks", "what tasks", "todos"],
        "description": "Show all active tasks",
        "examples": [
            "show my tasks",
            "what tasks do I have",
            "list my todos",
        ],
    },
    ActionType.COMPLETE_TASK: {
        "keywords": ["complete task", "done task", "finish task", "mark done", "mark complete"],
        "description": "Mark a task as completed",
        "examples": [
            "mark task as done",
            "complete the task",
            "I finished the task",
        ],
    },
    ActionType.DELETE_TASK: {
        "keywords": ["delete task", "remove task", "cancel task"],
        "description": "Delete a task",
        "examples": [
            "delete the task",
            "remove task",
            "cancel that task",
        ],
    },
    ActionType.SCHEDULE_MEETING: {
        "keywords": ["meeting", "schedule", "appointment", "book", "set up meeting"],
        "description": "Schedule a meeting with participants",
        "examples": [
            "schedule a meeting with John",
            "book an appointment for tomorrow",
            "set up a meeting at 2pm",
        ],
    },
    ActionType.LIST_MEETINGS: {
        "keywords": ["show meetings", "list meetings", "my meetings", "calendar", "agenda"],
        "description": "Show upcoming meetings",
        "examples": [
            "show my meetings",
            "what meetings do I have",
            "show my calendar",
            "what's on my agenda",
        ],
    },
    ActionType.CANCEL_MEETING: {
        "keywords": ["cancel meeting", "delete meeting", "remove meeting"],
        "description": "Cancel a scheduled meeting",
        "examples": [
            "cancel the meeting",
            "delete meeting with John",
        ],
    },
    ActionType.SHOW_SUMMARY: {
        "keywords": ["summary", "overview", "what's up", "status", "dashboard"],
        "description": "Show a summary of all items",
        "examples": [
            "show my summary",
            "give me an overview",
            "what's on my plate",
            "show my dashboard",
        ],
    },
    ActionType.HELP: {
        "keywords": ["help", "how to", "what can you do", "commands"],
        "description": "Show help information",
        "examples": [
            "help",
            "what can you do",
            "show commands",
        ],
    },
}


class SemanticMatcher:
    """Match user input to actions using semantic embeddings."""

    def __init__(self, openai_api_key: str, model: str = "text-embedding-3-small"):
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.model = model
        self._action_embeddings: Dict[ActionType, List[float]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Pre-compute embeddings for all action definitions."""
        if self._initialized:
            return

        logger.info("Computing action embeddings...")
        for action_type, definition in ACTION_DEFINITIONS.items():
            # Combine keywords, description, and examples for rich embedding
            text_parts = [
                definition["description"],
                " ".join(definition["keywords"]),
                " ".join(definition["examples"]),
            ]
            combined_text = " | ".join(text_parts)
            embedding = await self._get_embedding(combined_text)
            self._action_embeddings[action_type] = embedding

        self._initialized = True
        logger.info(f"Computed embeddings for {len(self._action_embeddings)} actions")

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

    async def match(self, user_input: str) -> ActionIntent:
        """Match user input to the best action type."""
        if not self._initialized:
            await self.initialize()

        # Get embedding for user input
        input_embedding = await self._get_embedding(user_input)

        # Find best matching action
        best_action = ActionType.UNKNOWN
        best_score = 0.0

        for action_type, action_embedding in self._action_embeddings.items():
            similarity = self._cosine_similarity(input_embedding, action_embedding)
            if similarity > best_score:
                best_score = similarity
                best_action = action_type

        logger.info(f"Matched '{user_input[:50]}...' to {best_action} (confidence: {best_score:.2f})")

        return ActionIntent(
            action_type=best_action,
            confidence=best_score,
            original_input=user_input,
            embedding=input_embedding,
        )

    async def match_with_alternatives(
        self, user_input: str, top_n: int = 3
    ) -> List[Tuple[ActionType, float]]:
        """Match user input and return top N alternatives with scores."""
        if not self._initialized:
            await self.initialize()

        input_embedding = await self._get_embedding(user_input)

        scores = []
        for action_type, action_embedding in self._action_embeddings.items():
            similarity = self._cosine_similarity(input_embedding, action_embedding)
            scores.append((action_type, similarity))

        # Sort by score descending and return top N
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]

    def get_action_info(self, action_type: ActionType) -> Optional[Dict]:
        """Get information about an action type."""
        return ACTION_DEFINITIONS.get(action_type)
