"""Data Science Agent website. Version 1 answers five Cyber Operations analysis jobs."""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from app.agent_service import AgentService, load_sources_for_greeting
from app.auth import require_user
from app.config import AppSettings, DataSourceSettings, IdentitySettings, OpenAISettings, QuerySettings
from app.prompts import PROMPTS

LOGGER = logging.getLogger(__name__)
BASE_DIRECTORY = Path(__file__).resolve().parent.parent


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    suggestions: list[dict[str, str | bool]]


def create_app(settings: AppSettings | None = None, agent_factory: Any = None) -> FastAPI:
    app_settings = settings or AppSettings.from_environment()
    application = FastAPI(title=app_settings.agent_name)
    application.add_middleware(
        SessionMiddleware,
        secret_key=app_settings.session_secret,
        same_site="lax",
        https_only=app_settings.app_env != "local",
        max_age=app_settings.session_ttl_seconds,
    )
    application.mount("/static", StaticFiles(directory=BASE_DIRECTORY / "static"), name="static")
    templates = Jinja2Templates(directory=BASE_DIRECTORY / "templates")

    def get_agent_service() -> AgentService:
        existing = getattr(application.state, "agent_service", None)
        if existing is None:
            existing = agent_factory() if agent_factory is not None else AgentService(
                app_settings,
                IdentitySettings.from_environment(),
                OpenAISettings.from_environment(),
                QuerySettings.from_environment(),
                DataSourceSettings.from_environment(),
            )
            application.state.agent_service = existing
        return existing

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "version": app_settings.version}

    @application.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        user = require_user(request, app_settings)
        sources = load_sources_for_greeting()
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "agent_name": app_settings.agent_name,
                "display_name": user.display_name,
                "welcome": {
                    "agentName": app_settings.agent_name,
                    "userName": user.display_name,
                    "databases": [source.database for source in sources],
                    "prompts": [prompt.as_dict() for prompt in PROMPTS],
                },
            },
        )

    @application.post("/api/chat", response_model=ChatResponse)
    async def chat(request: Request, chat_request: ChatRequest) -> ChatResponse | JSONResponse:
        user = require_user(request, app_settings)
        browser_id = request.session.get("browser_id")
        if not browser_id:
            browser_id = secrets.token_urlsafe(24)
            request.session["browser_id"] = browser_id
        try:
            reply = await get_agent_service().chat(f"{user.user_id}:{browser_id}", chat_request.message)
        except Exception as error:
            LOGGER.error("Chat request failed.", exc_info=error)
            return JSONResponse(status_code=500, content={"detail": "The analysis failed before a response was ready."})
        return ChatResponse(reply=reply, suggestions=[prompt.as_dict() for prompt in PROMPTS])

    return application


app = create_app()
