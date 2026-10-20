"""Builds the analysis agent and keeps one conversation per browser."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.identity.aio import get_bearer_token_provider

from app.config import AppSettings, DataSourceSettings, IdentitySettings, OpenAISettings, QuerySettings
from app.data_sources import DataSource
from app.kusto_source import KustoSource
from app.progress import ProgressReporter, progress_reporter, report_progress
from app.tools import DataTools, build_agent_tools

INSTRUCTIONS = """You are {agent_name}, a read-only data science assistant for Cyber Operations device data.

You only analyze the allowed Azure Data Explorer objects. You do not train models, run Python, or change data.

Version-1 jobs:
- Profile deviceinfo_org_ago24h.
- Compare two machine groups or ECH values in deviceinfo_org_ago24h.
- Show the daily trend in DeviceInfo_DailySummary.
- Explain the change between the latest two report dates in DeviceInfo_DailySummary.
- Find high-exposure devices in deviceinfo_org_ago24h that also have an exploitable critical finding in v_SoftwareVulnerabilities_Daily.

Rules:
- If the message still contains a square-bracket placeholder, ask the user to replace it. Do not query.
- Use MachineGroup or ECH, whichever column exists. Do not use SiteCode.
- If a named column or object is missing, say so. Do not invent values.
- Call describe_object before the first query against an object. If describe_object fails, still run the analysis query.
- Prefer summarize. Do not list individual devices unless the user asks for one named device.
- Results are capped at {maximum_rows} rows.
- When asked for the query, show the KQL in a code block.

Dashboard replies:
- Return one fenced dashboard block containing strict JSON with this shape:
  {{"title":"...","subtitle":"...","kpis":[{{"label":"...","value":"...","detail":"...","tone":"neutral|good|warning|critical"}}],"charts":[{{"title":"...","items":[{{"label":"...","value":123}}]}}]}}
- Include at most 6 KPI cards, 4 charts, and 8 items per chart. Chart values must be non-negative numbers.
- Put no prose inside the JSON. After the block, add no more than three short observations.

Data sources:
{source_summary}
"""


def final_reply(result: Any) -> str:
    for message in reversed(getattr(result, "messages", None) or []):
        if getattr(message, "text", "").strip():
            return message.text
    return str(result)


def build_openai_token_provider(credential: Any, token_scope: str) -> Callable[[], Awaitable[str]]:
    return get_bearer_token_provider(credential, token_scope)


@dataclass
class TimedAgentSession:
    session: Any
    last_used_at: float
    run_lock: asyncio.Lock


class AgentService:
    def __init__(
        self,
        app_settings: AppSettings,
        identity: IdentitySettings,
        openai: OpenAISettings,
        query: QuerySettings,
        data: DataSourceSettings,
    ) -> None:
        self.app_settings = app_settings
        self._sessions: dict[str, TimedAgentSession] = {}
        self._sessions_lock = asyncio.Lock()
        client_id = identity.client_id or None
        self._async_credential = AsyncDefaultAzureCredential(
            authority=identity.authority_host,
            managed_identity_client_id=client_id,
        )
        credential = DefaultAzureCredential(authority=identity.authority_host, managed_identity_client_id=client_id)
        sources = {
            source.name: KustoSource(source, credential, query)
            for source in data.sources
        }
        client_class = OpenAIChatClient if openai.api_style == "responses" else OpenAIChatCompletionClient
        chat_client = client_class(
            model=openai.deployment,
            azure_endpoint=openai.endpoint,
            api_version=openai.api_version,
            credential=build_openai_token_provider(self._async_credential, identity.openai_token_scope),
        )
        summary = "\n".join(f"- {source.name}: {source.database}. {source.description}" for source in data.sources)
        self.agent = Agent(
            client=chat_client,
            name="DataScienceAgent",
            instructions=INSTRUCTIONS.format(
                agent_name=app_settings.agent_name,
                maximum_rows=query.maximum_rows,
                source_summary=summary or "- none configured",
            ),
            tools=build_agent_tools(DataTools(sources)),
        )

    async def _session_for(self, session_key: str) -> TimedAgentSession:
        now = time.monotonic()
        async with self._sessions_lock:
            expired = [key for key, value in self._sessions.items() if now - value.last_used_at > self.app_settings.session_ttl_seconds]
            for key in expired:
                del self._sessions[key]
            timed = self._sessions.get(session_key)
            if timed is None:
                timed = TimedAgentSession(self.agent.create_session(), now, asyncio.Lock())
                self._sessions[session_key] = timed
            else:
                timed.last_used_at = now
            return timed

    async def chat(self, session_key: str, message: str, progress: ProgressReporter | None = None) -> str:
        with progress_reporter(progress):
            report_progress("agent", "Loading the conversation.")
            timed = await self._session_for(session_key)
            async with timed.run_lock:
                report_progress("agent", "Agent is analyzing the request.")
                result = await self.agent.run(message, session=timed.session)
                report_progress("response", "Agent finished.")
                return final_reply(result)

    async def close(self) -> None:
        await self._async_credential.close()


def load_sources_for_greeting() -> tuple[DataSource, ...]:
    try:
        return DataSourceSettings.from_environment().sources
    except ValueError:
        return ()
