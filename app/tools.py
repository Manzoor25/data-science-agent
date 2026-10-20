"""The only operations the model may ask for. Python runs them and enforces the allowlist."""

from __future__ import annotations

import json
import logging
import re
from typing import Annotated, Any, Callable

from agent_framework import tool
from pydantic import Field

from app.errors import QueryRejectedError
from app.kusto_source import KustoSource
from app.progress import report_progress

LOGGER = logging.getLogger(__name__)
MAX_FOUND_OBJECTS = 40


def run_logged_tool(tool_name: str, arguments: dict[str, Any], run: Callable[[], Any]) -> str:
    LOGGER.info("Tool call: %s %s", tool_name, json.dumps(arguments))
    report_progress("tool", f"Running {tool_name}.", tool=tool_name)
    try:
        result = run()
    except QueryRejectedError as error:
        LOGGER.info("Tool result: %s rejected: %s", tool_name, error)
        return json.dumps({"error": str(error)})
    except Exception as error:
        LOGGER.exception("Tool %s failed before returning a result.", tool_name)
        raise
    LOGGER.info("Tool result: %s returned %s", tool_name, result.get("rowCount", "") if isinstance(result, dict) else "")
    return json.dumps(result, default=str)


class DataTools:
    def __init__(self, sources: dict[str, KustoSource]) -> None:
        self.sources = sources

    def _source(self, name: str) -> KustoSource:
        source = self.sources.get(name.strip().lower())
        if source is None:
            raise QueryRejectedError(f"Unknown data source '{name}'. Known: {', '.join(self.sources)}.")
        return source

    def list_data_sources(self) -> list[dict[str, str]]:
        return [{"name": item.source.name, "kind": "kusto", "database": item.source.database, "description": item.source.description}
                for item in self.sources.values()]

    def find_objects(self, source_name: str, keywords: str) -> dict[str, Any]:
        catalog = self._source(source_name).list_objects()
        words = [word.casefold() for word in re.split(r"[\s,;]+", keywords) if word]
        matches = catalog
        if words:
            matches = [item for item in catalog if any(word in f"{item['object']} {item['description']}".casefold() for word in words)]
        return {"source": source_name, "totalObjects": len(catalog), "matches": matches[:MAX_FOUND_OBJECTS]}

    def describe_object(self, source_name: str, object_name: str) -> dict[str, Any]:
        return self._source(source_name).describe_object(object_name)

    def run_kql(self, source_name: str, query: str) -> dict[str, Any]:
        return self._source(source_name).run_guarded(query)


def build_agent_tools(data: DataTools) -> list[Callable[..., Any]]:
    @tool(approval_mode="never_require")
    def list_data_sources() -> str:
        """List the Azure Data Explorer sources you can query."""
        return run_logged_tool("list_data_sources", {}, data.list_data_sources)

    @tool(approval_mode="never_require")
    def find_objects(
        source: Annotated[str, Field(description="Data source name from list_data_sources.")],
        keywords: Annotated[str, Field(description="Words to match against object names. Empty lists the allowed objects.")],
    ) -> str:
        """Find allowed tables or materialized views."""
        return run_logged_tool("find_objects", {"source": source, "keywords": keywords}, lambda: data.find_objects(source, keywords))

    @tool(approval_mode="never_require")
    def describe_object(
        source: Annotated[str, Field(description="Data source name.")],
        object_name: Annotated[str, Field(description="Exact table or materialized-view name.")],
    ) -> str:
        """Show the columns of one allowed object before writing a query."""
        return run_logged_tool("describe_object", {"source": source, "object": object_name}, lambda: data.describe_object(source, object_name))

    @tool(approval_mode="never_require")
    def run_kql(
        source: Annotated[str, Field(description="Data source name.")],
        query: Annotated[str, Field(description="One read-only KQL query against an allowed object.")],
    ) -> str:
        """Run one read-only KQL query. Results are capped. Prefer summarize over listing devices."""
        return run_logged_tool("run_kql", {"source": source, "query": query}, lambda: data.run_kql(source, query))

    return [list_data_sources, find_objects, describe_object, run_kql]
