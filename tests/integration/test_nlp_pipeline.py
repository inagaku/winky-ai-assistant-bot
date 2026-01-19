"""Integration tests for NLP pipeline (semantic matcher + parameter extractor).

This test suite connects to the real OpenAI API to test intent matching
and parameter extraction with various user messages.

Run with: python -m pytest tests/integration/test_nlp_pipeline.py -v -s
Or standalone: python tests/integration/test_nlp_pipeline.py
"""

import asyncio
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.models import ActionType
from app.intelligence.semantic_matcher import SemanticMatcher
from app.intelligence.parameter_extractor import ParameterExtractor


@dataclass
class TestCase:
    """A test case for the NLP pipeline."""
    message: str
    locale: str
    expected_intent: ActionType
    expected_params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    # Acceptable alternative intents (for ambiguous cases)
    acceptable_intents: List[ActionType] = field(default_factory=list)


@dataclass
class TestResult:
    """Result of a single test case."""
    test_case: TestCase
    matched_intent: ActionType
    confidence: float
    extracted_params: Dict[str, Any]
    intent_correct: bool
    params_correct: bool
    duration_ms: float


# =============================================================================
# TEST CASES
# =============================================================================

TEST_CASES: List[TestCase] = [
    # -------------------------------------------------------------------------
    # REMINDERS - English
    # -------------------------------------------------------------------------
    TestCase(
        message="Remind me to buy milk tomorrow",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "buy milk", "event_time": "tomorrow"},
        description="Simple reminder with relative date",
    ),
    TestCase(
        message="Remind me about the doctor appointment at 4pm on Monday",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "doctor appointment", "event_time": "4pm on Monday"},
        description="Reminder with EVENT time (appointment IS at 4pm)",
    ),
    TestCase(
        message="Set a reminder for 3pm to call mom",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "call mom", "remind_at_explicit": "3pm"},
        description="Reminder with EXPLICIT notification time (remind me AT 3pm)",
    ),
    TestCase(
        message="Remind me in 30 minutes to check the oven",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "check the oven", "remind_at_explicit": "in 30 minutes"},
        description="Reminder with relative notification time",
    ),
    TestCase(
        message="Don't let me forget to submit the report by Friday",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "submit the report", "event_time": "Friday"},
        description="Implicit reminder - deadline/event based",
    ),
    TestCase(
        message="Remind me today at 16:00 that I need to buy a milk",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "buy a milk", "remind_at_explicit": "today at 16:00"},
        description="Reminder with EXPLICIT notification time (remind AT 16:00)",
    ),
    TestCase(
        message="Remind me that I have a doctor appointment at 16:30 on Monday. Notify me 1.5 hours before",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "doctor appointment", "event_time": "16:30 on Monday", "lead_time": "1.5 hours"},
        description="Reminder with EVENT time AND lead time",
    ),
    TestCase(
        message="Remind me at 4pm to buy milk",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "buy milk", "remind_at_explicit": "4pm"},
        description="EXPLICIT reminder time - 'remind AT 4pm'",
    ),
    TestCase(
        message="Meeting at 4pm, remind me 30 minutes before",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "meeting", "event_time": "4pm", "lead_time": "30 minutes"},
        description="EVENT time with explicit lead time",
    ),
    TestCase(
        message="Show my reminders",
        locale="en",
        expected_intent=ActionType.LIST_REMINDERS,
        description="List reminders",
    ),
    TestCase(
        message="What reminders do I have?",
        locale="en",
        expected_intent=ActionType.LIST_REMINDERS,
        description="List reminders - question form",
    ),
    TestCase(
        message="Delete the reminder about milk",
        locale="en",
        expected_intent=ActionType.DELETE_REMINDER,
        expected_params={"title": "milk"},
        description="Delete reminder by title",
    ),

    # -------------------------------------------------------------------------
    # REMINDERS - Russian
    # -------------------------------------------------------------------------
    TestCase(
        message="Напомни мне купить молоко завтра",
        locale="ru",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "купить молоко", "event_time": "завтра"},
        description="Simple reminder in Russian - explicit time",
    ),
    TestCase(
        message="Напомни о встрече с врачом в понедельник в 16:30",
        locale="ru",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "встреча с врачом", "event_time": "понедельник в 16:30"},
        description="Reminder about event in Russian",
    ),
    TestCase(
        message="Напомни мне сегодня в 16:00, что нужно купить молоко",
        locale="ru",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "купить молоко", "remind_at_explicit": "сегодня в 16:00"},
        description="Reminder with explicit notification time in Russian",
    ),
    TestCase(
        message="Встреча в 15:00, напомни за час",
        locale="ru",
        expected_intent=ActionType.CREATE_REMINDER,
        expected_params={"title": "встреча", "event_time": "15:00", "lead_time": "час"},
        description="Event with lead time in Russian",
    ),
    TestCase(
        message="Покажи мои напоминания",
        locale="ru",
        expected_intent=ActionType.LIST_REMINDERS,
        description="List reminders in Russian",
    ),
    #
    # # -------------------------------------------------------------------------
    # # TASKS - English
    # # -------------------------------------------------------------------------
    # TestCase(
    #     message="Create a task to fix the login bug",
    #     locale="en",
    #     expected_intent=ActionType.CREATE_TASK,
    #     expected_params={"title": "fix the login bug"},
    #     description="Simple task creation",
    # ),
    # TestCase(
    #     message="Add task: review pull request #123",
    #     locale="en",
    #     expected_intent=ActionType.CREATE_TASK,
    #     expected_params={"title": "review pull request #123"},
    #     description="Task with colon format",
    # ),
    # TestCase(
    #     message="I need to finish the presentation by tomorrow",
    #     locale="en",
    #     expected_intent=ActionType.CREATE_TASK,
    #     expected_params={"title": "finish the presentation", "datetime": "tomorrow"},
    #     acceptable_intents=[ActionType.CREATE_REMINDER],
    #     description="Implicit task with deadline",
    # ),
    # TestCase(
    #     message="Add urgent task to deploy hotfix",
    #     locale="en",
    #     expected_intent=ActionType.CREATE_TASK,
    #     expected_params={"title": "deploy hotfix", "priority": "urgent"},
    #     description="Task with priority",
    # ),
    # TestCase(
    #     message="Show my tasks",
    #     locale="en",
    #     expected_intent=ActionType.LIST_TASKS,
    #     description="List tasks",
    # ),
    # TestCase(
    #     message="What's on my todo list?",
    #     locale="en",
    #     expected_intent=ActionType.LIST_TASKS,
    #     description="List tasks - informal",
    # ),
    # TestCase(
    #     message="Mark the bug fix task as done",
    #     locale="en",
    #     expected_intent=ActionType.COMPLETE_TASK,
    #     expected_params={"title": "bug fix"},
    #     description="Complete task",
    # ),
    # TestCase(
    #     message="Complete task review PR",
    #     locale="en",
    #     expected_intent=ActionType.COMPLETE_TASK,
    #     expected_params={"title": "review PR"},
    #     description="Complete task - direct",
    # ),
    #
    # # -------------------------------------------------------------------------
    # # TASKS - Russian
    # # -------------------------------------------------------------------------
    # TestCase(
    #     message="Создай задачу исправить баг",
    #     locale="ru",
    #     expected_intent=ActionType.CREATE_TASK,
    #     expected_params={"title": "исправить баг"},
    #     description="Create task in Russian",
    # ),
    # TestCase(
    #     message="Покажи мои задачи",
    #     locale="ru",
    #     expected_intent=ActionType.LIST_TASKS,
    #     description="List tasks in Russian",
    # ),
    # TestCase(
    #     message="Выполнить задачу с отчетом",
    #     locale="ru",
    #     expected_intent=ActionType.COMPLETE_TASK,
    #     expected_params={"title": "отчет"},
    #     description="Complete task in Russian",
    # ),
    #
    # # -------------------------------------------------------------------------
    # # MEETINGS - English
    # # -------------------------------------------------------------------------
    # TestCase(
    #     message="Schedule a meeting with John tomorrow at 2pm",
    #     locale="en",
    #     expected_intent=ActionType.SCHEDULE_MEETING,
    #     expected_params={"title": "meeting with John", "participants": "John", "datetime_start": "tomorrow at 2pm"},
    #     description="Meeting with participant and time",
    # ),
    # TestCase(
    #     message="Set up a call with the team on Friday at 10am",
    #     locale="en",
    #     expected_intent=ActionType.SCHEDULE_MEETING,
    #     expected_params={"title": "call with the team", "datetime_start": "Friday at 10am"},
    #     description="Meeting as call",
    # ),
    # TestCase(
    #     message="Book a meeting room for project review next Monday",
    #     locale="en",
    #     expected_intent=ActionType.SCHEDULE_MEETING,
    #     expected_params={"title": "project review", "datetime_start": "next Monday"},
    #     description="Meeting with location context",
    # ),
    # TestCase(
    #     message="Show my meetings",
    #     locale="en",
    #     expected_intent=ActionType.LIST_MEETINGS,
    #     description="List meetings",
    # ),
    # TestCase(
    #     message="What meetings do I have this week?",
    #     locale="en",
    #     expected_intent=ActionType.LIST_MEETINGS,
    #     description="List meetings - question form",
    # ),
    # TestCase(
    #     message="Cancel the meeting with John",
    #     locale="en",
    #     expected_intent=ActionType.CANCEL_MEETING,
    #     expected_params={"title": "meeting with John"},
    #     description="Cancel meeting",
    # ),
    #
    # # -------------------------------------------------------------------------
    # # MEETINGS - Russian
    # # -------------------------------------------------------------------------
    # TestCase(
    #     message="Запланируй встречу с Иваном завтра в 14:00",
    #     locale="ru",
    #     expected_intent=ActionType.SCHEDULE_MEETING,
    #     expected_params={"title": "встреча с Иваном", "participants": "Иван"},
    #     description="Schedule meeting in Russian",
    # ),
    # TestCase(
    #     message="Покажи мои встречи",
    #     locale="ru",
    #     expected_intent=ActionType.LIST_MEETINGS,
    #     description="List meetings in Russian",
    # ),

    # -------------------------------------------------------------------------
    # GENERAL - English
    # -------------------------------------------------------------------------
    TestCase(
        message="Show me my summary",
        locale="en",
        expected_intent=ActionType.SHOW_SUMMARY,
        description="Show summary",
    ),
    TestCase(
        message="What do I have planned?",
        locale="en",
        expected_intent=ActionType.SHOW_SUMMARY,
        description="Summary - question form",
    ),
    TestCase(
        message="Help",
        locale="en",
        expected_intent=ActionType.HELP,
        description="Help command",
    ),
    TestCase(
        message="What can you do?",
        locale="en",
        expected_intent=ActionType.HELP,
        description="Help - question form",
    ),

    # -------------------------------------------------------------------------
    # GENERAL - Russian
    # -------------------------------------------------------------------------
    TestCase(
        message="Покажи сводку",
        locale="ru",
        expected_intent=ActionType.SHOW_SUMMARY,
        description="Show summary in Russian",
    ),
    TestCase(
        message="Помощь",
        locale="ru",
        expected_intent=ActionType.HELP,
        description="Help in Russian",
    ),

    # -------------------------------------------------------------------------
    # EDGE CASES / AMBIGUOUS
    # -------------------------------------------------------------------------
    TestCase(
        message="Meeting tomorrow",
        locale="en",
        expected_intent=ActionType.SCHEDULE_MEETING,
        acceptable_intents=[ActionType.CREATE_REMINDER, ActionType.LIST_MEETINGS],
        description="Ambiguous - could be schedule or reminder",
    ),
    TestCase(
        message="Call mom",
        locale="en",
        expected_intent=ActionType.CREATE_REMINDER,
        acceptable_intents=[ActionType.CREATE_TASK],
        description="Short reminder/task",
    ),
]


class NLPPipelineTest:
    """Test runner for NLP pipeline integration tests."""

    def __init__(self, openai_api_key: str):
        self.semantic_matcher = SemanticMatcher(openai_api_key)
        self.parameter_extractor = ParameterExtractor(openai_api_key)
        self.results: List[TestResult] = []

    async def initialize(self):
        """Initialize the semantic matcher."""
        print("Initializing semantic matcher (computing embeddings)...")
        await self.semantic_matcher.initialize()
        print("Initialization complete.\n")

    async def run_test(self, test_case: TestCase) -> TestResult:
        """Run a single test case."""
        start_time = datetime.now()

        # Match intent
        intent = await self.semantic_matcher.match(test_case.message, locale=test_case.locale)

        # Extract parameters
        params = await self.parameter_extractor.extract(test_case.message, intent.action_type)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Check if intent is correct (including acceptable alternatives)
        intent_correct = (
            intent.action_type == test_case.expected_intent or
            intent.action_type in test_case.acceptable_intents
        )

        # Check if key expected params are present (flexible matching)
        params_correct = self._check_params(test_case.expected_params, params)

        return TestResult(
            test_case=test_case,
            matched_intent=intent.action_type,
            confidence=intent.confidence,
            extracted_params=params,
            intent_correct=intent_correct,
            params_correct=params_correct,
            duration_ms=duration_ms,
        )

    def _check_params(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
        """Check if expected parameters are present in actual (flexible matching)."""
        if not expected:
            return True  # No expected params to check

        for key, expected_value in expected.items():
            if key not in actual:
                # Check alternative keys
                alt_keys = {
                    "title": ["title", "task", "task_name", "name", "what", "description"],
                    "datetime": ["datetime", "when", "time", "datetime_start", "date", "remind_at_explicit", "event_time"],
                    "remind_at_explicit": ["remind_at_explicit", "datetime", "when", "time"],
                    "event_time": ["event_time", "datetime", "when", "time", "datetime_start"],
                    "lead_time": ["lead_time", "lead_time_minutes", "before"],
                    "participants": ["participants", "attendees", "with"],
                }
                found = False
                for alt_key in alt_keys.get(key, [key]):
                    if alt_key in actual:
                        found = True
                        break
                if not found:
                    return False
        return True

    async def run_all_tests(self, test_cases: List[TestCase] = None) -> None:
        """Run all test cases and collect results."""
        cases = test_cases or TEST_CASES
        total = len(cases)

        print(f"Running {total} test cases...\n")
        print("=" * 80)

        for i, test_case in enumerate(cases, 1):
            result = await self.run_test(test_case)
            self.results.append(result)

            # Print result
            status = "PASS" if (result.intent_correct and result.params_correct) else "FAIL"
            intent_status = "OK" if result.intent_correct else "WRONG"
            params_status = "OK" if result.params_correct else "MISSING"

            print(f"[{i}/{total}] {status} | {test_case.locale.upper()} | {test_case.description}")
            print(f"  Input: \"{test_case.message}\"")
            print(f"  Intent: {result.matched_intent.value} (expected: {test_case.expected_intent.value}) [{intent_status}] conf={result.confidence:.2f}")
            print(f"  Params: {result.extracted_params} [{params_status}]")
            if test_case.expected_params:
                print(f"  Expected: {test_case.expected_params}")
            print(f"  Duration: {result.duration_ms:.0f}ms")
            print("-" * 80)

        print("\n")
        self.print_statistics()

    def print_statistics(self) -> None:
        """Print test statistics."""
        total = len(self.results)
        if total == 0:
            print("No results to report.")
            return

        intent_correct = sum(1 for r in self.results if r.intent_correct)
        params_correct = sum(1 for r in self.results if r.params_correct)
        both_correct = sum(1 for r in self.results if r.intent_correct and r.params_correct)

        avg_confidence = sum(r.confidence for r in self.results) / total
        avg_duration = sum(r.duration_ms for r in self.results) / total

        # Group by locale
        locales = {}
        for r in self.results:
            locale = r.test_case.locale
            if locale not in locales:
                locales[locale] = {"total": 0, "intent_ok": 0, "params_ok": 0}
            locales[locale]["total"] += 1
            if r.intent_correct:
                locales[locale]["intent_ok"] += 1
            if r.params_correct:
                locales[locale]["params_ok"] += 1

        # Group by intent type
        intents = {}
        for r in self.results:
            intent = r.test_case.expected_intent.value
            if intent not in intents:
                intents[intent] = {"total": 0, "correct": 0}
            intents[intent]["total"] += 1
            if r.intent_correct:
                intents[intent]["correct"] += 1

        print("=" * 80)
        print("STATISTICS")
        print("=" * 80)
        print(f"\nOVERALL:")
        print(f"  Total tests:        {total}")
        print(f"  Intent accuracy:    {intent_correct}/{total} ({100*intent_correct/total:.1f}%)")
        print(f"  Params accuracy:    {params_correct}/{total} ({100*params_correct/total:.1f}%)")
        print(f"  Full accuracy:      {both_correct}/{total} ({100*both_correct/total:.1f}%)")
        print(f"  Avg confidence:     {avg_confidence:.2f}")
        print(f"  Avg duration:       {avg_duration:.0f}ms")

        print(f"\nBY LOCALE:")
        for locale, stats in sorted(locales.items()):
            t = stats["total"]
            i = stats["intent_ok"]
            p = stats["params_ok"]
            print(f"  {locale.upper()}: {t} tests, intent={100*i/t:.0f}%, params={100*p/t:.0f}%")

        print(f"\nBY INTENT TYPE:")
        for intent, stats in sorted(intents.items()):
            t = stats["total"]
            c = stats["correct"]
            print(f"  {intent}: {c}/{t} ({100*c/t:.0f}%)")

        # List failures
        failures = [r for r in self.results if not (r.intent_correct and r.params_correct)]
        if failures:
            print(f"\nFAILURES ({len(failures)}):")
            for r in failures:
                print(f"  - [{r.test_case.locale}] \"{r.test_case.message[:50]}...\"")
                if not r.intent_correct:
                    print(f"    Intent: got {r.matched_intent.value}, expected {r.test_case.expected_intent.value}")
                if not r.params_correct:
                    print(f"    Params: got {r.extracted_params}, expected {r.test_case.expected_params}")

        print("\n" + "=" * 80)


async def main():
    """Main entry point for running tests."""
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # Try loading from .env file
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("OPENAI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"\'')
                        break

    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment or .env file")
        sys.exit(1)

    print("=" * 80)
    print("NLP PIPELINE INTEGRATION TEST")
    print("=" * 80)
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Test cases: {len(TEST_CASES)}")
    print("=" * 80 + "\n")

    tester = NLPPipelineTest(api_key)
    await tester.initialize()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
else:
    # Pytest integration - only import when running via pytest
    try:
        import pytest

        @pytest.fixture
        async def nlp_tester():
            """Pytest fixture for NLP tester."""
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                pytest.skip("OPENAI_API_KEY not set")
            tester = NLPPipelineTest(api_key)
            await tester.initialize()
            return tester

        @pytest.mark.asyncio
        async def test_nlp_pipeline(nlp_tester):
            """Run all NLP pipeline tests via pytest."""
            await nlp_tester.run_all_tests()

            # Assert overall accuracy thresholds
            total = len(nlp_tester.results)
            intent_correct = sum(1 for r in nlp_tester.results if r.intent_correct)

            # Expect at least 80% intent accuracy
            assert intent_correct / total >= 0.8, f"Intent accuracy below 80%: {100*intent_correct/total:.1f}%"
    except ImportError:
        pass  # pytest not installed, skip pytest integration
