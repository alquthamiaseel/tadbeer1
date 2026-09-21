from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import dev as dev_routes
from app.api.auth import router as auth_router
from app.api.routes import router as api_router
from app.config import settings
from app.integrations import slack

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("pmfyp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("pm-fyp backend starting (model=%s)", settings.llm_model)

    slack_task: asyncio.Task | None = None
    if slack.app is not None:
        slack_task = asyncio.create_task(slack.start_socket_mode())
        log.info("Slack listener starting in the background")
    else:
        log.info("SLACK_BOT_TOKEN/SLACK_APP_TOKEN not set; Slack listener is disabled")

    yield

    if slack_task is not None:
        slack_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await slack_task
    log.info("pm-fyp backend stopping")


app = FastAPI(
    title="pm-fyp",
    description="Agentic AI project manager: Slack conversation to plan, WBS, design, prototype",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(api_router)
app.include_router(dev_routes.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
