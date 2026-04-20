"""
Heimdall AI Automation — FastAPI application entry point.
"""
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

# Ensure the backend directory is on sys.path so `core.*` imports work
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("heimdall")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    logger.info("Heimdall starting up…")

    # Wire up messaging manager → PM engine
    from core.messaging.manager import MessagingManager
    from core.notification_router import NotificationRouter
    from core.webhook_dispatcher import WebhookDispatcher
    from core.pm_engine import get_pm
    from core.routes.messaging import set_manager
    from core import config

    cfg = config.load_config()

    messaging = MessagingManager(data_dir=os.getenv("HEIMDALL_DATA_DIR", "data"))
    notifier = NotificationRouter(messaging)
    notifier.configure(cfg)

    webhooks_dispatcher = WebhookDispatcher(cfg)

    pm = get_pm()
    pm.set_notifier(notifier)
    pm.set_webhook_dispatcher(webhooks_dispatcher)

    messaging.set_pm_callback(pm.chat)
    set_manager(messaging)

    await messaging.start_all()
    logger.info("Messaging adapters started.")

    # Start scheduler
    from scheduler import TaskScheduler, set_scheduler
    from core.task_manager import TaskManager
    scheduler = TaskScheduler(TaskManager())
    set_scheduler(scheduler)
    scheduler.start()
    logger.info("Scheduler started.")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    logger.info("Heimdall shutting down…")
    scheduler.stop()
    await messaging.stop_all()
    if get_pm()._running:
        await get_pm().stop()


app = FastAPI(
    title="Heimdall AI Automation",
    version="1.0.0",
    description="Multi-AI orchestration platform with Gemma PM, Qwen worker, and Claude reviewer.",
    lifespan=lifespan,
)

# CORS — allow the Next.js dev server and any configured origins
_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
from core.routes import pm, tasks, vault, settings, restrictions, messaging, git, workspace, webhooks, analytics, templates     # noqa: E402
from scheduler import router as schedule_router     # noqa: E402
from core.auth import require_token     # noqa: E402
from core.routes.config import router as config_router     # noqa: E402
from core.routes.setup import router as setup_router     # noqa: E402
from core.routes.models import router as models_router     # noqa: E402
from core.routes.project import router as project_router     # noqa: E402

app.include_router(pm.router, dependencies=[Depends(require_token)])
app.include_router(tasks.router, dependencies=[Depends(require_token)])
app.include_router(vault.router, dependencies=[Depends(require_token)])
app.include_router(settings.router, dependencies=[Depends(require_token)])
app.include_router(restrictions.router, dependencies=[Depends(require_token)])
app.include_router(messaging.router, dependencies=[Depends(require_token)])
app.include_router(git.router, dependencies=[Depends(require_token)])
app.include_router(workspace.router, dependencies=[Depends(require_token)])
app.include_router(webhooks.router, dependencies=[Depends(require_token)])
app.include_router(analytics.router, dependencies=[Depends(require_token)])
app.include_router(templates.router, dependencies=[Depends(require_token)])
app.include_router(schedule_router)
app.include_router(config_router, dependencies=[Depends(require_token)])
app.include_router(models_router, dependencies=[Depends(require_token)])
app.include_router(project_router, dependencies=[Depends(require_token)])
app.include_router(setup_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "heimdall"}


# ── Serve Next.js static build (production) ───────────────────────────────────
_frontend_out = Path(__file__).parent.parent / "frontend" / "out"
if _frontend_out.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_out), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HEIMDALL_HOST", "0.0.0.0"),
        port=int(os.getenv("HEIMDALL_PORT", "8000")),
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
    )
