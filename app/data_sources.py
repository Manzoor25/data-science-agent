"""The plug-in list of Azure Data Explorer databases this agent may read."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

_SOURCE_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_KUSTO_URI = re.compile(r"^https://[A-Za-z0-9.-]{3,253}/?$")
_DATABASE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$")
_IDENTIFIER = re.compile(r"^(\*|[A-Za-z_][A-Za-z0-9_]{0,127})$")


@dataclass(frozen=True)
class DataSource:
    name: str
    endpoint: str
    database: str
    description: str
    allowed_tables: tuple[str, ...] = ()

    def allows_kusto_table(self, table: str) -> bool:
        tables = {value.casefold() for value in self.allowed_tables}
        return "*" in tables or table.casefold() in tables


def parse_data_sources(raw_json: str) -> tuple[DataSource, ...]:
    try:
        entries = json.loads(raw_json)
    except json.JSONDecodeError as error:
        raise ValueError("DATA_SOURCES_JSON is not valid JSON.") from error
    if not isinstance(entries, list) or not entries:
        raise ValueError("DATA_SOURCES_JSON must be a non-empty list of data sources.")

    sources: list[DataSource] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each data source must be a JSON object.")
        name = str(entry.get("name", ""))
        if not _SOURCE_NAME.fullmatch(name):
            raise ValueError(f"Data source name '{name}' must be lowercase letters, digits, '-' or '_'.")
        if str(entry.get("kind", "kusto")).lower() != "kusto":
            raise ValueError(f"Data source '{name}': this agent only accepts kind 'kusto'.")
        endpoint = str(entry.get("endpoint", "")).strip()
        if not _KUSTO_URI.fullmatch(endpoint):
            raise ValueError(f"Data source '{name}': endpoint must be an https:// cluster URI.")
        database = str(entry.get("database", ""))
        if not _DATABASE_NAME.fullmatch(database):
            raise ValueError(f"Data source '{name}': database name '{database}' contains unsupported characters.")
        tables = entry.get("allowedTables", [])
        if not isinstance(tables, list) or not tables or not all(isinstance(item, str) and _IDENTIFIER.fullmatch(item) for item in tables):
            raise ValueError(f"Data source '{name}': allowedTables must be a list of table names.")
        description = str(entry.get("description", "")).strip()
        sources.append(DataSource(name, endpoint.rstrip("/"), database, description, tuple(tables)))
    return tuple(sources)
