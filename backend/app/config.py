"""Application settings, loaded from the repository-root .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/app -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Gemini ----------------------------------------------------------
    gemini_api_key: str = ""
    # Free tier. Flash is the workhorse; flash-lite handles cheap classification.
    llm_model: str = "gemini-3.6-flash"
    llm_fast_model: str = "gemini-3.5-flash-lite"
    # low | medium | high — mapped to Gemini's thinking level.
    llm_effort: str = "high"
    # Free-tier quota is per minute, so a six-stage run can trip it. Retries
    # back off rather than failing the run.
    llm_max_retries: int = 5

    # --- Slack -----------------------------------------------------------
    slack_bot_token: str = ""
    slack_app_token: str = ""

    # --- Asana -----------------------------------------------------------
    asana_access_token: str = ""
    asana_workspace_gid: str = ""
    # Set false to build the work breakdown without publishing it to Asana.
    # The task graph, dependencies and constraints are still produced and shown
    # in the dashboard; only the push to Asana is skipped. This is the fallback
    # for a workspace that is not available yet, or a free tier that cannot link
    # dependencies — it is opt-out rather than automatic, so a missing token is
    # still reported as the misconfiguration it usually is.
    asana_enabled: bool = True

    # --- GitHub ----------------------------------------------------------
    github_token: str = ""
    github_owner: str = ""

    # --- Vercel ----------------------------------------------------------
    vercel_token: str = ""
    vercel_team_id: str = ""

    # --- Application -----------------------------------------------------
    database_url: str = "postgresql+asyncpg://pmfyp:pmfyp@localhost:5433/pmfyp"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # Off by default: the API listens on localhost, where a login would only be
    # a password to lose. Turn it on before putting the dashboard on a domain.
    dashboard_auth: bool = False
    # Signs session tokens issued at login. Must be set to a real secret before
    # DASHBOARD_AUTH is turned on in anything but a local, single-user setup.
    session_secret: str = "changeme-session-secret"
    log_level: str = "INFO"

    @property
    def sync_database_url(self) -> str:
        """Alembic runs synchronously; strip the asyncpg driver suffix."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
