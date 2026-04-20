"""
PMEngine — the top-level orchestrator.

Responsibilities:
  - Poll the task backlog and feed tasks to WorkflowEngine
  - Respond to chat messages from the GUI / messaging channels
  - Broadcast PipelineEvents to all SSE subscribers
  - Trigger notifications after task state transitions
  - Coordinate git commits on task completion
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from core import config

_CHAT_LOG_PATH = Path("logs/chat_history.json")
from core.models import (
    ChatMessage,
    EventType,
    PipelineEvent,
    PMStatusResponse,
    Task,
    TaskStatus,
)
from core.workflow_engine import WorkflowEngine


class PMEngine:
    def __init__(self):
        self._running = False
        self._start_time: Optional[float] = None
        self._current_task_id: Optional[str] = None

        # Central event queue — WorkflowEngine pushes, PMEngine fans out
        self._event_queue: asyncio.Queue[PipelineEvent] = asyncio.Queue()

        # SSE subscriber queues — each connected browser tab gets its own
        self._subscribers: list[asyncio.Queue[PipelineEvent]] = []

        # Wakes the poll loop immediately when a task is added
        self._work_event: asyncio.Event = asyncio.Event()

        # Shared conversation log — WorkflowEngine appends, exposed via API
        self._conversation_log: list[dict] = []

        self._workflow = WorkflowEngine(self._event_queue, self._conversation_log)
        self._chat_history: list[ChatMessage] = self._load_chat_history()
        self._claude_unavailable_until: float = 0.0
        self._task_mgr = None   # lazily imported to avoid circular deps
        self._notifier = None
        self._webhook_dispatcher = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._start_time = time.time()

        # Start loops first — notifications must never block the pipeline
        asyncio.create_task(self._run_loop())
        asyncio.create_task(self._fan_out_loop())

        await self._emit(EventType.PM_STARTED, None, "Heimdall PM started")
        await self._notify("Heimdall PM started and watching the task queue.")

    async def stop(self) -> None:
        self._running = False
        await self._emit(EventType.PM_STOPPED, None, "Heimdall PM stopped")
        await self._notify("Heimdall PM stopped.")

    # ── Main task loop ────────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        poll_interval = config.get("pm.poll_interval", 15)

        while self._running:
            mgr = self._get_task_mgr()
            task = mgr.get_next_task()

            if task is None:
                self._work_event.clear()
                try:
                    await asyncio.wait_for(self._work_event.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass
                continue

            await self._process_task(task)

        self._current_task_id = None

    async def _process_task(self, task: Task) -> None:
        mgr = self._get_task_mgr()
        self._current_task_id = task.id

        # Sync current rate-limit window to WorkflowEngine before each task
        self._workflow.set_reviewer_unavailable(self._claude_unavailable_until)

        mgr.mark_in_progress(task.id)
        await self._emit(EventType.TASK_STARTED, task.id, f"Starting task: {task.title}")
        await self._notify(f"Starting task [{task.id}]: {task.title}")

        try:
            result = await self._workflow.execute_task(task)

            if result.status == "completed":
                mgr.mark_completed(task.id, result.output)
                rate_limited = result.review and result.review.summary == "__rate_limited__"
                if rate_limited:
                    self._claude_unavailable_until = time.time() + 1800
                    self._workflow.set_reviewer_unavailable(self._claude_unavailable_until)
                    await self._emit(
                        EventType.TASK_COMPLETED, task.id,
                        f"Task auto-approved (Claude rate-limited). Review pending — Claude paused for 30 min."
                    )
                    await self._notify(
                        f"[RATE LIMITED] Task [{task.id}] *{task.title}* auto-approved — Claude quota exhausted. "
                        f"Manual review recommended. Claude paused for 30 min.",
                        urgent=True,
                    )
                else:
                    await self._emit(EventType.TASK_COMPLETED, task.id, f"Task completed after {result.iterations} iteration(s)")
                    await self._notify(
                        f"Task [{task.id}] *{task.title}* completed in {result.iterations} review cycle(s)."
                    )
                await self._maybe_commit(task, result.output)

            elif result.status == "escalated":
                mgr.mark_escalated(task.id, result.reason)
                await self._emit(EventType.TASK_ESCALATED, task.id, result.reason)
                await self._notify(
                    f"ESCALATION — Task [{task.id}] *{task.title}* needs human input.\n"
                    f"Reason: {result.reason}",
                    urgent=True,
                )

        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            mgr.mark_failed(task.id, str(exc))
            await self._emit(EventType.TASK_FAILED, task.id, f"Task failed: {exc}")
            await self._notify(f"ERROR in task [{task.id}]: {exc}", urgent=True)
            print(f"[PM] Task {task.id} failed:\n{tb}", flush=True)

        finally:
            self._current_task_id = None

    # ── Chat interface ────────────────────────────────────────────────────────

    _TASK_CMD_INSTRUCTIONS = (
        "\n\n## Task Management Commands\n"
        "You can create or modify tasks by including a JSON block wrapped in <heimdall-action> tags.\n"
        "The block will be executed automatically. Do NOT describe what you're doing — just include it.\n\n"
        "**Create a task:**\n"
        "<heimdall-action>{\"action\":\"create_task\",\"title\":\"Task title\",\"description\":\"What Qwen should build\","
        "\"priority\":\"high\",\"tags\":[\"backend\"],\"stream\":\"qwen\"}</heimdall-action>\n\n"
        "**Update a task status:**\n"
        "<heimdall-action>{\"action\":\"update_task\",\"task_id\":\"qwen-001\",\"status\":\"pending\"}</heimdall-action>\n\n"
        "**Delete a task:**\n"
        "<heimdall-action>{\"action\":\"delete_task\",\"task_id\":\"qwen-001\"}</heimdall-action>\n\n"
        "Priority values: low | medium | high | critical. Stream: qwen (default) or claude.\n"
        "After the block, continue your normal response text."
    )

    async def _execute_task_commands(self, reply: str) -> tuple[str, list[str]]:
        """Parse and execute <heimdall-action> blocks in the LLM reply.
        Returns (cleaned_reply, list_of_action_results)."""
        import re
        import uuid
        from datetime import datetime, timezone

        pattern = re.compile(r"<heimdall-action>(.*?)</heimdall-action>", re.DOTALL)
        results: list[str] = []
        mgr = self._get_task_mgr()

        for match in pattern.finditer(reply):
            raw = match.group(1).strip()
            try:
                cmd = json.loads(raw)
                action = cmd.get("action", "")

                if action == "create_task":
                    task_id = f"task-{uuid.uuid4().hex[:8]}"
                    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    task = Task(
                        id=task_id,
                        title=cmd.get("title", "Untitled"),
                        description=cmd.get("description", ""),
                        priority=cmd.get("priority", "medium"),
                        status=TaskStatus.PENDING,
                        created_at=now,
                        tags=cmd.get("tags", []),
                        stream=cmd.get("stream", "qwen"),
                        output_path=cmd.get("output_path", f"workspace/current/{task_id}"),
                        max_review_iterations=cmd.get("max_review_iterations", 3),
                    )
                    mgr.add_task(task)
                    self._work_event.set()
                    results.append(f"✓ Task created: [{task_id}] {task.title}")
                    await self._emit(EventType.TASK_STARTED, task_id, f"PM created task: {task.title}")

                elif action == "update_task":
                    task_id = cmd.get("task_id", "")
                    task = mgr.get_task(task_id)
                    if not task:
                        results.append(f"✗ Task not found: {task_id}")
                        continue
                    updates = {k: v for k, v in cmd.items() if k not in ("action", "task_id")}
                    if "status" in updates:
                        status_val = updates.pop("status")
                        mgr.update_task(task_id, status=TaskStatus(status_val))
                    if updates:
                        mgr.update_task(task_id, **updates)
                    results.append(f"✓ Task updated: {task_id}")

                elif action == "delete_task":
                    task_id = cmd.get("task_id", "")
                    if mgr.delete_task(task_id):
                        results.append(f"✓ Task deleted: {task_id}")
                    else:
                        results.append(f"✗ Task not found: {task_id}")

                else:
                    results.append(f"✗ Unknown action: {action}")

            except (json.JSONDecodeError, Exception) as exc:
                results.append(f"✗ Command error: {exc}")

        cleaned = pattern.sub("", reply).strip()
        return cleaned, results

    async def chat(self, message: str, session_id: str = "default") -> str:
        """Process a chat message from the GUI or a messaging channel."""
        from core.llm_providers import call_llm, LLMError
        from core.vault import get_vault

        self._chat_history.append(ChatMessage(role="user", content=message))

        status = self.get_status()
        mgr = self._get_task_mgr()
        tasks = mgr.list_tasks()

        task_list = "\n".join(
            f"  [{t.id}] {t.status.value} — {t.title}"
            for t in tasks[:20]
        )
        context = (
            f"Current status: {'running' if status.running else 'stopped'}. "
            f"Tasks — pending: {status.tasks_pending}, "
            f"active: {sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)}, "
            f"completed: {status.tasks_completed}, "
            f"escalated: {status.tasks_escalated}.\n"
            f"Task list:\n{task_list or '  (none)'}\n"
        )
        if self._current_task_id:
            context += f"Currently processing: {self._current_task_id}.\n"

        agent_cfg = config.get("agents.orchestrator", {})
        vault = get_vault()
        provider = agent_cfg.get("provider", "lmstudio")
        model = agent_cfg.get("model", "gemma-3-12b-it")
        base_url = agent_cfg.get("base_url") or None
        api_key = vault.get("anthropic_key") if provider == "anthropic" else None

        system = (
            agent_cfg.get("system_prompt", "")
            + self._TASK_CMD_INSTRUCTIONS
            + f"\n\nSystem context:\n{context}"
        )

        history = [
            {"role": m.role, "content": m.content}
            for m in self._chat_history[-20:]
        ]

        try:
            reply = await call_llm(
                prompt=message,
                system=system,
                model=model,
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                temperature=agent_cfg.get("temperature", 0.2),
                max_tokens=agent_cfg.get("max_tokens", 2048),
                history=history[:-1],
            )
        except LLMError as exc:
            reply = f"PM agent error: {exc}"

        # Execute any task commands embedded in the reply
        reply, action_results = await self._execute_task_commands(reply)
        if action_results:
            reply = reply + "\n\n" + "\n".join(action_results) if reply else "\n".join(action_results)

        self._chat_history.append(ChatMessage(role="assistant", content=reply))
        self._save_chat_history()
        await self._emit(EventType.PM_CHAT_RESPONSE, None, reply)
        return reply

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> PMStatusResponse:
        mgr = self._get_task_mgr()
        tasks = mgr.list_tasks()
        return PMStatusResponse(
            running=self._running,
            current_task_id=self._current_task_id,
            tasks_pending=sum(1 for t in tasks if t.status == TaskStatus.PENDING),
            tasks_completed=sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
            tasks_failed=sum(1 for t in tasks if t.status == TaskStatus.FAILED),
            tasks_escalated=sum(1 for t in tasks if t.status == TaskStatus.ESCALATED),
            uptime_seconds=round(time.time() - self._start_time, 2) if self._start_time else 0.0,
        )

    # ── SSE subscriptions ─────────────────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        """Register a new SSE client. Returns its event queue."""
        q: asyncio.Queue[PipelineEvent] = asyncio.Queue(maxsize=512)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    async def _fan_out_loop(self) -> None:
        """Forward events from the central queue to all SSE subscribers."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    dead.append(q)

            for q in dead:
                self.unsubscribe(q)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _emit(self, event_type: EventType, task_id: Optional[str], message: str, data: Optional[dict] = None) -> None:
        event = PipelineEvent(type=event_type, task_id=task_id, message=message, data=data or {})
        await self._event_queue.put(event)
        await self._dispatch_webhook(event)

    async def _notify(self, message: str, urgent: bool = False) -> None:
        if self._notifier:
            await self._notifier.broadcast(message, urgent=urgent)

    async def _dispatch_webhook(self, event: PipelineEvent) -> None:
        if self._webhook_dispatcher:
            await self._webhook_dispatcher.handle_event(event)

    async def _maybe_commit(self, task: Task, output: str) -> None:
        if not config.get("pm.auto_commit", True):
            return
        if not config.get("git.enabled", True):
            return
        try:
            from core.git_integration import GitManager, GitError
            git = GitManager()
            prefix = config.get("git.commit_prefix", "[Heimdall]")
            sha = git.commit_task_output(
                task_id=task.id,
                output_path=task.output_path or f"workspace/current/{task.id}",
                message=f"{prefix} Complete task {task.id}: {task.title}",
            )
            if sha:
                await self._emit(EventType.TASK_COMPLETED, task.id, f"Committed output: {sha[:8]}")
        except Exception as exc:
            print(f"[PM] Git commit failed (non-fatal): {exc}", flush=True)

    def _get_task_mgr(self):
        if self._task_mgr is None:
            from core.task_manager import TaskManager
            self._task_mgr = TaskManager()
        return self._task_mgr

    # ── Chat history persistence ───────────────────────────────────────────────

    def _load_chat_history(self) -> list[ChatMessage]:
        try:
            if _CHAT_LOG_PATH.exists():
                data = json.loads(_CHAT_LOG_PATH.read_text(encoding="utf-8"))
                return [ChatMessage(**m) for m in data]
        except Exception as exc:
            print(f"[PM] Could not load chat history: {exc}", flush=True)
        return []

    def _save_chat_history(self) -> None:
        try:
            _CHAT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            _CHAT_LOG_PATH.write_text(
                json.dumps([m.model_dump() for m in self._chat_history[-500:]], ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[PM] Could not save chat history: {exc}", flush=True)

    def get_chat_history(self) -> list[dict]:
        """Return persisted user-PM chat history."""
        return [m.model_dump() for m in self._chat_history]

    def get_conversation(self, limit: int = 100) -> list[dict]:
        """Return the agent-to-agent conversation log (newest last)."""
        return self._conversation_log[-limit:]

    async def notify_task_added(self) -> None:
        """Wake the poll loop and auto-start PM if it was idle."""
        if not self._running:
            await self.start()
        self._work_event.set()

    def set_notifier(self, notifier) -> None:
        self._notifier = notifier

    def set_webhook_dispatcher(self, dispatcher) -> None:
        self._webhook_dispatcher = dispatcher


# Module-level singleton
_pm: Optional[PMEngine] = None


def get_pm() -> PMEngine:
    global _pm
    if _pm is None:
        _pm = PMEngine()
    return _pm
