"""Runtime settings. Empty optional values use the cloud-aware default."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from app.data_sources import DataSource, parse_data_sources

DEFAULT_AGENT_NAME = "Data Science Agent"
CLOUD_DEFAULTS = {
    "AzureUSGovernment": {
        "authority_host": "https://login.microsoftonline.us/",
        "openai_token_scope": "https://cognitiveservices.azure.us/.default",
        "api_style": "chat_completions",
    },
    "AzureCloud": {
        "authority_host": "https://login.microsoftonline.com/",
        "openai_token_scope": "https://cognitiveservices.azure.com/.default",
        "api_style": "responses",
    },
}


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable {name} is missing.")
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, "").strip() or default


def _positive_integer(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be a whole number.") from error
    if value < 1:
        raise ValueError(f"{name} must be greater than zero.")
    return value


def cloud_defaults() -> dict[str, str]:
    for name in ("AZURE_OPENAI_ENDPOINT", "AZURE_AUTHORITY_HOST"):
        host = urlparse(_optional(name)).hostname or ""
        if host.endswith(".us"):
            return CLOUD_DEFAULTS["AzureUSGovernment"]
    return CLOUD_DEFAULTS["AzureCloud"]


@dataclass(frozen=True)
class IdentitySettings:
    authority_host: str
    client_id: str
    openai_token_scope: str

    @classmethod
    def from_environment(cls) -> "IdentitySettings":
        defaults = cloud_defaults()
        return cls(
            authority_host=_optional("AZURE_AUTHORITY_HOST", defaults["authority_host"]),
            client_id=_optional("AZURE_CLIENT_ID"),
            openai_token_scope=_optional("AZURE_OPENAI_TOKEN_SCOPE", defaults["openai_token_scope"]),
        )


@dataclass(frozen=True)
class OpenAISettings:
    endpoint: str
    deployment: str
    api_style: str
    api_version: str

    @classmethod
    def from_environment(cls) -> "OpenAISettings":
        api_style = _optional("AZURE_OPENAI_API_STYLE", cloud_defaults()["api_style"]).lower()
        if api_style not in ("responses", "chat_completions"):
            raise ValueError("AZURE_OPENAI_API_STYLE must be 'responses' or 'chat_completions'.")
        default_version = "preview" if api_style == "responses" else "2024-10-21"
        return cls(
            endpoint=_required("AZURE_OPENAI_ENDPOINT"),
            deployment=_required("AZURE_OPENAI_DEPLOYMENT"),
            api_style=api_style,
            api_version=_optional("AZURE_OPENAI_API_VERSION", default_version),
        )


@dataclass(frozen=True)
class QuerySettings:
    maximum_rows: int
    timeout_seconds: int

    @classmethod
    def from_environment(cls) -> "QuerySettings":
        return cls(
            maximum_rows=_positive_integer("QUERY_MAX_ROWS", 100),
            timeout_seconds=_positive_integer("QUERY_TIMEOUT_SECONDS", 60),
        )


@dataclass(frozen=True)
class DataSourceSettings:
    sources: tuple[DataSource, ...]

    @classmethod
    def from_environment(cls) -> "DataSourceSettings":
        return cls(parse_data_sources(_required("DATA_SOURCES_JSON")))


@dataclass(frozen=True)
class AppSettings:
    app_env: str
    session_secret: str
    session_ttl_seconds: int
    local_user_id: str
    local_user_name: str
    agent_name: str = DEFAULT_AGENT_NAME
    version: str = "dev"

    @classmethod
    def from_environment(cls) -> "AppSettings":
        app_env = _optional("APP_ENV", "azure").lower()
        session_secret = _optional("SESSION_SECRET")
        if app_env != "local" and not session_secret:
            raise ValueError("SESSION_SECRET is required unless APP_ENV=local.")
        if app_env == "local" and not session_secret:
            session_secret = "LOCAL-DEVELOPMENT-ONLY-CHANGE-ME"
        agent_name = _optional("AGENT_NAME", DEFAULT_AGENT_NAME)
        if len(agent_name) > 60:
            raise ValueError("AGENT_NAME must be at most 60 characters.")
        return cls(
            app_env=app_env,
            session_secret=session_secret,
            session_ttl_seconds=_positive_integer("AGENT_SESSION_TTL_SECONDS", 1800),
            local_user_id=_optional("LOCAL_USER_ID", "local-developer"),
            local_user_name=_optional("LOCAL_USER_NAME", "Local Developer"),
            agent_name=agent_name,
            version=_optional("APP_VERSION", "dev"),
        )
