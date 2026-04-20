"""
WorkflowEngine — the core Qwen → Claude review loop.

Flow per task:
  1. Format task prompt and call Qwen (worker)
  2. Write Qwen's output to workspace/current/<task_id>/
  3. Send output to Claude (reviewer) for evaluation
  4. If approved → return TaskResult(completed)
  5. If rejected → write review file, send fix request to Qwen, go to step 3
  6. If max_review_iterations hit → return TaskResult(escalated)

Events are published to an asyncio.Queue so the PM engine and SSE
clients both receive real-time updates.
"""
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Optional

from core import config
from core.models import (
    EventType,
    PipelineEvent,
    ReviewIssue,
    ReviewResult,
    Task,
    TaskResult,
)
from core.restrictions import (
    RestrictionViolation,
    check_content,
    check_file_size,
    check_path_write,
    check_task_iterations,
)


class WorkflowEngine:
    def __init__(self, event_queue: asyncio.Queue, conversation_log: list | None = None):
        self._queue = event_queue
        self._log: list = conversation_log if conversation_log is not None else []

    # ── Public ────────────────────────────────────────────────────────────────

    async def execute_task(self, task: Task) -> TaskResult:
        """Run the full Qwen → review → fix loop for a single task."""
        start = time.time()
        workspace = self._prepare_workspace(task)

        await self._emit(EventType.TASK_SENT_TO_WORKER, task.id, f"Sending task to worker: {task.title}")

        worker_output = await self._call_worker(task, prior_review=None)
        await self._write_output(workspace, "output_v1.md", worker_output, task)

        iteration = 0
        while True:
            iteration += 1
            task.current_iteration = iteration

            # Guard: max iterations from restrictions engine
            try:
                check_task_iterations(task.id, iteration - 1)
            except RestrictionViolation as exc:
                await self._emit(EventType.TASK_ESCALATED, task.id, str(exc))
                return TaskResult(
                    task_id=task.id,
                    status="escalated",
                    output=worker_output,
                    iterations=iteration - 1,
                    reason=str(exc),
                    duration_seconds=round(time.time() - start, 2),
                )

            await self._emit(EventType.REVIEW_STARTED, task.id, f"Sending to reviewer (iteration {iteration})")
            review = await self._call_reviewer(task, worker_output, iteration)

            if review.approved:
                await self._emit(EventType.REVIEW_APPROVED, task.id, review.summary)
                return TaskResult(
                    task_id=task.id,
                    status="completed",
                    output=worker_output,
                    review=review,
                    iterations=iteration,
                    duration_seconds=round(time.time() - start, 2),
                )

            # Rejected — check iteration limit from task config
            await self._emit(
                EventType.REVIEW_REJECTED,
                task.id,
                f"Iteration {iteration}: {review.summary} ({len(review.issues)} issues)",
                {"issues": [i.model_dump() for i in review.issues]},
            )

            if iteration >= task.max_review_iterations:
                reason = (
                    f"Max review iterations ({task.max_review_iterations}) reached. "
                    f"Last review: {review.summary}"
                )
                await self._emit(EventType.TASK_ESCALATED, task.id, reason)
                return TaskResult(
                    task_id=task.id,
                    status="escalated",
                    output=worker_output,
                    review=review,
                    iterations=iteration,
                    reason=reason,
                    duration_seconds=round(time.time() - start, 2),
                )

            # Write review file for worker to read
            review_file = workspace / f"review_v{iteration}.md"
            self._write_review_file(review_file, review, iteration)

            await self._emit(EventType.FIX_REQUESTED, task.id, f"Requesting fixes (iteration {iteration + 1})")
            worker_output = await self._call_worker(task, prior_review=review)
            await self._write_output(workspace, f"output_v{iteration + 1}.md", worker_output, task)

    # ── Workspace ─────────────────────────────────────────────────────────────

    def _prepare_workspace(self, task: Task) -> Path:
        if task.output_path:
            workspace = Path(task.output_path)
        else:
            base = config.get("workspace.current_path", "workspace/current")
            workspace = Path(base) / task.id
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    async def _write_output(self, workspace: Path, filename: str, content: str, task: Task) -> None:
        try:
            check_path_write(str(workspace / filename), agent="worker")
            check_content(content, agent="worker")
            check_file_size(len(content.encode()), agent="worker")
        except RestrictionViolation as exc:
            await self._emit(EventType.ERROR, task.id, f"Restriction violation: {exc}")
            raise

        (workspace / filename).write_text(content, encoding="utf-8")

    def _write_review_file(self, path: Path, review: ReviewResult, iteration: int) -> None:
        lines = [
            f"# Review Feedback — Iteration {iteration}",
            "",
            f"**Decision:** {'APPROVED' if review.approved else 'CHANGES REQUIRED'}",
            f"**Summary:** {review.summary}",
            "",
        ]
        if review.issues:
            lines += ["## Issues to Fix", ""]
            for i, issue in enumerate(review.issues, 1):
                lines.append(f"{i}. **[{issue.severity.upper()}]** {issue.description}")
                if issue.location:
                    lines.append(f"   *Location:* `{issue.location}`")
                lines.append("")
        if review.feedback:
            lines += ["## Full Review Notes", "", review.feedback, ""]
        lines.append("---")
        lines.append("*Please address ALL issues above before resubmitting.*")
        path.write_text("\n".join(lines), encoding="utf-8")

    # ── LLM calls ─────────────────────────────────────────────────────────────

    async def _call_worker(self, task: Task, prior_review: Optional[ReviewResult]) -> str:
        from core.llm_providers import call_llm, LLMError
        from core.vault import get_vault

        agent_cfg = config.get("agents.worker", {})
        vault = get_vault()

        provider = agent_cfg.get("provider", "ollama")
        model = agent_cfg.get("model", "qwen2.5-coder:7b")
        base_url = agent_cfg.get("base_url") or None
        api_key = vault.get(f"{provider}_key") or vault.get("openai_key")

        iteration_num = task.current_iteration

        if prior_review is None:
            prompt = self._build_initial_prompt(task)
            self._record("pm", "PM → Worker (Qwen)", prompt, task.id, iteration_num, "prompt")
        else:
            prompt = self._build_fix_prompt(task, prior_review)
            self._record("pm", "PM → Worker (Qwen) [fix request]", prompt, task.id, iteration_num, "prompt")

        try:
            output = await call_llm(
                prompt=prompt,
                system=agent_cfg.get("system_prompt", ""),
                model=model,
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                temperature=agent_cfg.get("temperature", 0.3),
                max_tokens=agent_cfg.get("max_tokens", 8192),
            )
        except LLMError as exc:
            raise RuntimeError(f"Worker LLM failed: {exc}") from exc

        await self._emit(EventType.WORKER_OUTPUT_RECEIVED, task.id, f"Worker response received ({len(output)} chars)")
        self._record("worker", "Worker (Qwen)", output, task.id, iteration_num, "response")
        return output

    async def _call_reviewer(self, task: Task, worker_output: str, iteration: int) -> ReviewResult:
        from core.llm_providers import call_llm, LLMError
        from core.vault import get_vault

        agent_cfg = config.get("agents.reviewer", {})
        vault = get_vault()

        provider = agent_cfg.get("provider", "anthropic")
        model = agent_cfg.get("model", "claude-sonnet-4-6")
        base_url = agent_cfg.get("base_url") or None
        api_key = vault.get("anthropic_key")

        prompt = self._build_review_prompt(task, worker_output, iteration)
        self._record(
            "pm", f"PM → Reviewer (Claude) [review request, iteration {iteration}]",
            f"Reviewing Qwen's output for: {task.title}\n\nIteration {iteration}",
            task.id, iteration, "prompt",
        )

        try:
            raw = await call_llm(
                prompt=prompt,
                system=agent_cfg.get("system_prompt", ""),
                model=model,
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                temperature=agent_cfg.get("temperature", 0.1),
                max_tokens=agent_cfg.get("max_tokens", 4096),
            )
        except LLMError as exc:
            raise RuntimeError(f"Reviewer LLM failed: {exc}") from exc

        review = self._parse_review(raw, iteration)
        verdict = "APPROVED ✓" if review.approved else "CHANGES REQUIRED ✗"
        review_content = f"**{verdict}**\n\n{review.summary}"
        if review.issues:
            review_content += "\n\n**Issues:**\n" + "\n".join(
                f"- [{i.severity.upper()}] {i.description}" for i in review.issues
            )
        if review.feedback:
            review_content += f"\n\n**Notes:**\n{review.feedback}"
        self._record("reviewer", "Reviewer (Claude)", review_content, task.id, iteration, "response")
        return review

    # ── Prompt builders ───────────────────────────────────────────────────────

    def _build_initial_prompt(self, task: Task) -> str:
        return (
            f"# Task: {task.title}\n\n"
            f"{task.description.strip()}\n\n"
            f"Output all files to the directory: `{task.output_path or f'workspace/current/{task.id}'}`\n"
            f"Be thorough and complete. Include all required files."
        )

    def _build_fix_prompt(self, task: Task, review: ReviewResult) -> str:
        issues_text = "\n".join(
            f"- [{i.severity.upper()}] {i.description}" + (f" ({i.location})" if i.location else "")
            for i in review.issues
        )
        return (
            f"# Task: {task.title}\n\n"
            f"Your previous submission was reviewed and requires changes.\n\n"
            f"## Issues to Fix\n{issues_text}\n\n"
            f"## Reviewer Notes\n{review.feedback}\n\n"
            f"Please fix ALL issues above and resubmit the complete updated files.\n"
            f"Output to: `{task.output_path or f'workspace/current/{task.id}'}`"
        )

    def _build_review_prompt(self, task: Task, worker_output: str, iteration: int) -> str:
        return (
            f"# Review Request (iteration {iteration})\n\n"
            f"## Original Task\n{task.title}\n\n{task.description.strip()}\n\n"
            f"## Worker Submission\n\n{worker_output}\n\n"
            f"Review this submission against the task requirements and respond with JSON only."
        )

    # ── Review parser ─────────────────────────────────────────────────────────

    def _parse_review(self, raw: str, iteration: int) -> ReviewResult:
        # Strip markdown fences if present
        clean = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        clean = re.sub(r"\s*```$", "", clean.strip(), flags=re.MULTILINE)

        try:
            data = json.loads(clean)
            issues = [ReviewIssue(**i) for i in data.get("issues", [])]
            return ReviewResult(
                approved=bool(data.get("approved", False)),
                summary=data.get("summary", ""),
                issues=issues,
                feedback=data.get("feedback", ""),
                iteration=iteration,
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            # If the reviewer didn't return valid JSON, treat as rejection with raw feedback
            return ReviewResult(
                approved=False,
                summary="Reviewer returned non-JSON response",
                issues=[ReviewIssue(severity="major", description="Parse error in review response")],
                feedback=raw[:2000],
                iteration=iteration,
            )

    # ── Conversation log ──────────────────────────────────────────────────────

    def _record(
        self,
        agent: str,
        label: str,
        content: str,
        task_id: str,
        iteration: int = 0,
        entry_type: str = "response",
    ) -> None:
        self._log.append({
            "agent": agent,
            "label": label,
            "content": content,
            "task_id": task_id,
            "iteration": iteration,
            "type": entry_type,
            "timestamp": time.time(),
        })
        # Cap at 500 entries to prevent unbounded memory growth
        if len(self._log) > 500:
            self._log.pop(0)

    # ── Event helpers ─────────────────────────────────────────────────────────

    async def _emit(
        self,
        event_type: EventType,
        task_id: Optional[str],
        message: str,
        data: Optional[dict] = None,
    ) -> None:
        event = PipelineEvent(
            type=event_type,
            task_id=task_id,
            message=message,
            data=data or {},
        )
        await self._queue.put(event)
