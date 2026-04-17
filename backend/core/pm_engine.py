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
import time
from typing import Optional

from core import config
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

        self._workflow = WorkflowEngine(self._event_queue)
        self._chat_history: list[ChatMessage] = []
        self._task_mgr = None   # lazily imported to avoid circular deps
        self._notifier = None
        self._webhook_dispatcher = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._start_time = time.time()

        await self._emit(EventType.PM_STARTED, None, "Heimdall PM started")
        await self._notify("Heimdall PM started and watching the task queue.")

        asyncio.create_task(self._run_loop())
        asyncio.create_task(self._fan_out_loop())

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
                await asyncio.sleep(poll_interval)
                continue

            await self._process_task(task)

        self._current_task_id = None

    async def _process_task(self, task: Task) -> None:
        mgr = self._get_task_mgr()
        self._current_task_id = task.id

        mgr.mark_in_progress(task.id)
        await self._emit(EventType.TASK_STARTED, task.id, f"Starting task: {task.title}")
        await self._notify(f"Starting task [{task.id}]: {task.title}")

        try:
            result = await self._workflow.execute_task(task)

            if result.status == "completed":
                mgr.mark_completed(task.id, result.output)
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

    async def chat(self, message: str, session_id: str = "default") -> str:
        """Process a chat message from the GUI or a messaging channel."""
        from core.llm_providers import call_llm, LLMError
        from core.vault import get_vault

        self._chat_history.append(ChatMessage(role="user", content=message))

        # Build context for the PM agent
        status = self.get_status()
        mgr = self._get_task_mgr()
        tasks = mgr.list_tasks()
        pending = [t for t in tasks if t.status == TaskStatus.PENDING]
        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]

        context = (
            f"Current status: {'running' if status.running else 'stopped'}. "
            f"Tasks — pending: {status.tasks_pending}, "
            f"completed: {status.tasks_completed}, "
            f"escalated: {status.tasks_escalated}.\n"
        )
        if self._current_task_id:
            context += f"Currently processing task: {self._current_task_id}.\n"

        agent_cfg = config.get("agents.orchestrator", {})
        vault = get_vault()
        provider = agent_cfg.get("provider", "lmstudio")
        model = agent_cfg.get("model", "gemma-3-12b-it")
        base_url = agent_cfg.get("base_url") or None
        api_key = vault.get("anthropic_key") if provider == "anthropic" else None

        system = agent_cfg.get("system_prompt", "") + f"\n\nSystem context:\n{context}"

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

        self._chat_history.append(ChatMessage(role="assistant", content=reply))
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
