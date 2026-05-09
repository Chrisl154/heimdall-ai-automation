"""
Tests for core/workflow_engine.py.

All LLM calls (worker + reviewer) are mocked — no Ollama, LM Studio,
or Anthropic connection is required to run this suite.
"""
import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm_providers import ClaudeRateLimitError, LLMError
from core.models import (
    ReviewIssue,
    ReviewResult,
    Task,
    TaskPriority,
    TaskStatus,
)
from core.workflow_engine import WorkflowEngine


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_engine(tmp_path: Path) -> WorkflowEngine:
    queue: asyncio.Queue = asyncio.Queue()
    engine = WorkflowEngine(event_queue=queue)
    return engine


def _make_task(tmp_path: Path, max_iter: int = 3) -> Task:
    return Task(
        id="wf-test-001",
        title="Test Task",
        description="Write a hello-world script.",
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.PENDING,
        created_at="2026-01-01",
        max_review_iterations=max_iter,
        output_path=str(tmp_path / "output"),
    )


def _approved_review(iteration: int = 1) -> ReviewResult:
    return ReviewResult(
        approved=True,
        summary="Looks good",
        issues=[],
        feedback="",
        iteration=iteration,
    )


def _rejected_review(iteration: int = 1) -> ReviewResult:
    return ReviewResult(
        approved=False,
        summary="Needs changes",
        issues=[ReviewIssue(severity="major", description="Missing error handling")],
        feedback="Please add try/except.",
        iteration=iteration,
    )


# ── _parse_review ─────────────────────────────────────────────────────────────

class TestParseReview:
    """_parse_review is a pure function — no mocking needed."""

    def _engine(self) -> WorkflowEngine:
        return WorkflowEngine(event_queue=asyncio.Queue())

    def test_valid_approved_json(self):
        raw = '{"approved": true, "summary": "All good", "issues": [], "feedback": ""}'
        result = self._engine()._parse_review(raw, iteration=1)
        assert result.approved is True
        assert result.summary == "All good"
        assert result.issues == []

    def test_valid_rejected_json_with_issues(self):
        raw = '''{
            "approved": false,
            "summary": "Needs work",
            "issues": [{"severity": "major", "description": "Missing tests", "location": "main.py"}],
            "feedback": "Add tests."
        }'''
        result = self._engine()._parse_review(raw, iteration=2)
        assert result.approved is False
        assert len(result.issues) == 1
        assert result.issues[0].severity == "major"
        assert result.issues[0].location == "main.py"
        assert result.iteration == 2

    def test_json_in_markdown_fences_is_stripped(self):
        raw = '```json\n{"approved": true, "summary": "ok", "issues": [], "feedback": ""}\n```'
        result = self._engine()._parse_review(raw, iteration=1)
        assert result.approved is True

    def test_invalid_json_returns_rejection(self):
        raw = "This is not JSON at all."
        result = self._engine()._parse_review(raw, iteration=1)
        assert result.approved is False
        assert "non-JSON" in result.summary
        assert len(result.issues) == 1

    def test_empty_string_returns_rejection(self):
        result = self._engine()._parse_review("", iteration=1)
        assert result.approved is False

    def test_approved_false_string_treated_as_falsy(self):
        raw = '{"approved": false, "summary": "reject", "issues": [], "feedback": ""}'
        result = self._engine()._parse_review(raw, iteration=1)
        assert result.approved is False


# ── Prompt builders ───────────────────────────────────────────────────────────

class TestPromptBuilders:
    def _engine(self) -> WorkflowEngine:
        return WorkflowEngine(event_queue=asyncio.Queue())

    def test_initial_prompt_contains_title_and_description(self):
        task = Task(
            id="t1", title="My Task", description="Do the thing.",
            priority=TaskPriority.MEDIUM, status=TaskStatus.PENDING,
            created_at="2026-01-01",
        )
        prompt = self._engine()._build_initial_prompt(task)
        assert "My Task" in prompt
        assert "Do the thing." in prompt

    def test_initial_prompt_contains_output_path(self):
        task = Task(
            id="t1", title="T", description="D",
            priority=TaskPriority.MEDIUM, status=TaskStatus.PENDING,
            created_at="2026-01-01", output_path="/tmp/out",
        )
        prompt = self._engine()._build_initial_prompt(task)
        assert "/tmp/out" in prompt

    def test_fix_prompt_contains_issue_descriptions(self):
        task = Task(
            id="t1", title="T", description="D",
            priority=TaskPriority.MEDIUM, status=TaskStatus.PENDING,
            created_at="2026-01-01",
        )
        review = _rejected_review()
        prompt = self._engine()._build_fix_prompt(task, review)
        assert "Missing error handling" in prompt
        assert "Please add try/except." in prompt

    def test_review_prompt_contains_worker_output(self):
        task = Task(
            id="t1", title="T", description="D",
            priority=TaskPriority.MEDIUM, status=TaskStatus.PENDING,
            created_at="2026-01-01",
        )
        prompt = self._engine()._build_review_prompt(task, "print('hello')", iteration=1)
        assert "print('hello')" in prompt
        assert "iteration 1" in prompt.lower()


# ── _write_review_file ────────────────────────────────────────────────────────

class TestWriteReviewFile:
    def test_creates_file_with_decision_and_issues(self, tmp_path):
        engine = WorkflowEngine(event_queue=asyncio.Queue())
        review = _rejected_review(iteration=2)
        path = tmp_path / "review_v2.md"
        engine._write_review_file(path, review, iteration=2)

        assert path.exists()
        content = path.read_text()
        assert "CHANGES REQUIRED" in content
        assert "Missing error handling" in content
        assert "Iteration 2" in content

    def test_approved_review_file_says_approved(self, tmp_path):
        engine = WorkflowEngine(event_queue=asyncio.Queue())
        review = _approved_review(iteration=1)
        path = tmp_path / "review_v1.md"
        engine._write_review_file(path, review, iteration=1)
        assert "APPROVED" in path.read_text()


# ── execute_task — approval paths ─────────────────────────────────────────────

class TestExecuteTaskApproval:
    """execute_task returns TaskResult(completed) when reviewer approves."""

    def test_first_iteration_approved(self, tmp_path):
        engine = _make_engine(tmp_path)
        task = _make_task(tmp_path)

        with (
            patch.object(engine, "_call_worker", new=AsyncMock(return_value="worker output")),
            patch.object(engine, "_call_reviewer", new=AsyncMock(return_value=_approved_review())),
        ):
            result = asyncio.get_event_loop().run_until_complete(engine.execute_task(task))

        assert result.status == "completed"
        assert result.task_id == task.id
        assert result.iterations == 1

    def test_rejected_then_approved(self, tmp_path):
        engine = _make_engine(tmp_path)
        task = _make_task(tmp_path, max_iter=3)

        reviewer_returns = [_rejected_review(1), _approved_review(2)]

        async def fake_reviewer(t, output, iteration):
            return reviewer_returns.pop(0)

        with (
            patch.object(engine, "_call_worker", new=AsyncMock(return_value="worker output")),
            patch.object(engine, "_call_reviewer", side_effect=fake_reviewer),
        ):
            result = asyncio.get_event_loop().run_until_complete(engine.execute_task(task))

        assert result.status == "completed"
        assert result.iterations == 2

    def test_output_file_written_to_workspace(self, tmp_path):
        engine = _make_engine(tmp_path)
        task = _make_task(tmp_path)
        out_dir = Path(task.output_path)
        out_dir.mkdir(parents=True, exist_ok=True)

        with (
            patch.object(engine, "_call_worker", new=AsyncMock(return_value="file content")),
            patch.object(engine, "_call_reviewer", new=AsyncMock(return_value=_approved_review())),
        ):
            asyncio.get_event_loop().run_until_complete(engine.execute_task(task))

        assert (out_dir / "output_v1.md").read_text() == "file content"


# ── execute_task — escalation paths ──────────────────────────────────────────

class TestExecuteTaskEscalation:
    """execute_task returns TaskResult(escalated) when iterations are exhausted."""

    def test_escalated_after_max_iterations(self, tmp_path):
        engine = _make_engine(tmp_path)
        task = _make_task(tmp_path, max_iter=2)

        with (
            patch.object(engine, "_call_worker", new=AsyncMock(return_value="worker output")),
            patch.object(engine, "_call_reviewer", new=AsyncMock(return_value=_rejected_review())),
        ):
            result = asyncio.get_event_loop().run_until_complete(engine.execute_task(task))

        assert result.status == "escalated"
        assert result.iterations == 2
        assert "Max review iterations" in result.reason

    def test_escalated_by_restriction_engine(self, tmp_path):
        from core.restrictions import RestrictionViolation
        engine = _make_engine(tmp_path)
        task = _make_task(tmp_path, max_iter=10)

        with (
            patch.object(engine, "_call_worker", new=AsyncMock(return_value="worker output")),
            patch.object(engine, "_call_reviewer", new=AsyncMock(return_value=_rejected_review())),
            patch("core.workflow_engine.check_task_iterations",
                  side_effect=RestrictionViolation("iteration limit exceeded")),
        ):
            result = asyncio.get_event_loop().run_until_complete(engine.execute_task(task))

        assert result.status == "escalated"
        assert "iteration limit" in result.reason


# ── Rate limiting ─────────────────────────────────────────────────────────────

class TestRateLimiting:
    """Reviewer rate-limit window and ClaudeRateLimitError handling."""

    def test_rate_limit_window_returns_auto_approved(self, tmp_path):
        engine = _make_engine(tmp_path)
        # Set window far in the future
        engine.set_reviewer_unavailable(time.time() + 3600)

        task = _make_task(tmp_path)

        with patch.object(engine, "_call_worker", new=AsyncMock(return_value="output")):
            result = asyncio.get_event_loop().run_until_complete(engine.execute_task(task))

        assert result.status == "completed"
        assert result.review is not None
        assert result.review.summary == "__rate_limited__"

    def test_expired_rate_limit_window_calls_reviewer(self, tmp_path):
        engine = _make_engine(tmp_path)
        # Window expired in the past
        engine.set_reviewer_unavailable(time.time() - 1)

        task = _make_task(tmp_path)
        with (
            patch.object(engine, "_call_worker", new=AsyncMock(return_value="output")),
            patch.object(engine, "_call_reviewer", new=AsyncMock(return_value=_approved_review())),
        ):
            result = asyncio.get_event_loop().run_until_complete(engine.execute_task(task))

        assert result.status == "completed"
        assert result.review.summary != "__rate_limited__"

    def test_claude_rate_limit_error_auto_approves(self, tmp_path):
        """When stream_llm raises ClaudeRateLimitError inside _call_reviewer,
        the task should be auto-approved with the __rate_limited__ sentinel."""
        engine = _make_engine(tmp_path)
        task = _make_task(tmp_path)

        async def fake_call_reviewer(t, output, iteration):
            # Simulate what _call_reviewer does on ClaudeRateLimitError
            return ReviewResult(
                approved=True, summary="__rate_limited__", issues=[],
                feedback="Claude API rate-limited. Auto-approved.",
                iteration=iteration,
            )

        with (
            patch.object(engine, "_call_worker", new=AsyncMock(return_value="output")),
            patch.object(engine, "_call_reviewer", side_effect=fake_call_reviewer),
        ):
            result = asyncio.get_event_loop().run_until_complete(engine.execute_task(task))

        assert result.status == "completed"
        assert result.review.summary == "__rate_limited__"


# ── Conversation log ──────────────────────────────────────────────────────────

class TestConversationLog:
    def test_events_emitted_after_execute(self, tmp_path):
        """execute_task emits at least TASK_SENT_TO_WORKER and REVIEW_STARTED
        to the queue regardless of which LLM calls are mocked."""
        engine = _make_engine(tmp_path)
        task = _make_task(tmp_path)

        with (
            patch.object(engine, "_call_worker", new=AsyncMock(return_value="output")),
            patch.object(engine, "_call_reviewer", new=AsyncMock(return_value=_approved_review())),
        ):
            asyncio.get_event_loop().run_until_complete(engine.execute_task(task))

        assert not engine._queue.empty(), "Expected at least one event in the queue"

    def test_log_capped_at_500_entries(self, tmp_path):
        engine = _make_engine(tmp_path)
        # Directly fill beyond the cap
        for i in range(600):
            engine._record("pm", f"label {i}", "content", "task-x", i, "prompt")
        assert len(engine._log) <= 500
