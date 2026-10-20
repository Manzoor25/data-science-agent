"""Read-only Azure Data Explorer access for one configured database."""

from __future__ import annotations

import datetime
import json
import logging
import re
import time
from typing import Any

from azure.core.credentials import TokenCredential
from azure.kusto.data import ClientRequestProperties, KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoServiceError

from app.config import QuerySettings
from app.data_sources import DataSource
from app.errors import QueryRejectedError

LOGGER = logging.getLogger(__name__)
CATALOG_CACHE_SECONDS = 600
_MANAGEMENT_COMMAND = re.compile(r"(^|;)\s*\.", re.MULTILINE)
_SET_STATEMENT = re.compile(r"(^|;)\s*set\s", re.IGNORECASE | re.MULTILINE)
_BLOCKED_FUNCTIONS = re.compile(r"\b(cluster|database|externaldata|external_table)\s*\(", re.IGNORECASE)
_TRAILING_RENDER = re.compile(r"\|\s*render\b[^|]*$", re.IGNORECASE)
_LINE_COMMENT = re.compile(r"//[^\n]*")


def validate_read_only_kql(query: str, source: DataSource, maximum_rows: int, known_tables: list[str]) -> str:
    text = query.strip()
    if not text:
        raise QueryRejectedError("The KQL query is empty.")
    if len(text) > 20_000:
        raise QueryRejectedError("The KQL query is too long.")
    checked = _LINE_COMMENT.sub("", text)
    if _MANAGEMENT_COMMAND.search(checked):
        raise QueryRejectedError("Management commands (starting with '.') are not allowed; write a query instead.")
    if _SET_STATEMENT.search(checked):
        raise QueryRejectedError("'set' statements are not allowed.")
    if _BLOCKED_FUNCTIONS.search(checked):
        raise QueryRejectedError("cluster(), database(), externaldata and external_table() are not allowed.")
    if "*" not in source.allowed_tables:
        for table in known_tables:
            if re.search(rf"\b{re.escape(table)}\b", checked) and not source.allows_kusto_table(table):
                raise QueryRejectedError(f"Table {table} is not in the allowed list for '{source.name}'.")
    body = _TRAILING_RENDER.sub("", text.rstrip().rstrip(";").rstrip()).rstrip()
    return f"{body}\n| take {maximum_rows + 1}"


class KustoSource:
    def __init__(self, source: DataSource, credential: TokenCredential, settings: QuerySettings) -> None:
        self.source = source
        self.settings = settings
        connection = KustoConnectionStringBuilder.with_azure_token_credential(source.endpoint, credential)
        self.client = KustoClient(connection)
        self._catalog: list[dict[str, str]] | None = None
        self._catalog_loaded_at = 0.0

    def _request_properties(self) -> ClientRequestProperties:
        properties = ClientRequestProperties()
        properties.set_option("servertimeout", datetime.timedelta(seconds=self.settings.timeout_seconds))
        properties.set_option("request_readonly", True)
        properties.set_option("request_callout_disabled", True)
        properties.set_option("request_external_data_disabled", True)
        properties.set_option("request_remote_entities_disabled", True)
        properties.set_option("request_sandboxed_execution_disabled", True)
        return properties

    def _management(self, command: str):
        LOGGER.info("KQL command to %s: %s", self.source.name, command)
        return self.client.execute_mgmt(self.source.database, command).primary_results[0]

    def list_objects(self) -> list[dict[str, str]]:
        if self._catalog is not None and time.monotonic() - self._catalog_loaded_at < CATALOG_CACHE_SECONDS:
            return self._catalog
        tables = [
            {"object": row["TableName"], "type": "table", "description": row["DocString"] or ""}
            for row in self._management(".show tables details | project TableName, DocString")
            if self.source.allows_kusto_table(row["TableName"])
        ]
        views = []
        try:
            view_rows = list(self._management(".show materialized-views | project Name, DocString"))
        except Exception as error:
            LOGGER.warning("Materialized views are not visible on %s: %s", self.source.name, error)
            view_rows = []
        for row in view_rows:
            name = row["Name"]
            if name and self.source.allows_kusto_table(name):
                views.append({"object": name, "type": "materialized-view", "description": row["DocString"] or ""})
        self._catalog = views + tables
        self._catalog_loaded_at = time.monotonic()
        return self._catalog

    def _known_names(self) -> list[str]:
        if "*" in self.source.allowed_tables:
            return []
        names = [row["TableName"] for row in self._management(".show tables | project TableName")]
        try:
            names.extend(row["Name"] for row in self._management(".show materialized-views | project Name") if row["Name"])
        except Exception:
            pass
        return names

    def describe_object(self, object_name: str) -> dict[str, Any]:
        match = next((item for item in self.list_objects() if item["object"].casefold() == object_name.strip().casefold()), None)
        if match is None:
            raise QueryRejectedError(f"'{object_name}' is not an allowed object in '{self.source.name}'. Use find_objects first.")
        kind = "materialized-view" if match["type"] == "materialized-view" else "table"
        schema_json = self._management(f".show {kind} ['{match['object']}'] schema as json")[0]["Schema"]
        columns = json.loads(schema_json)["OrderedColumns"]
        return {
            "object": match["object"],
            "type": match["type"],
            "columns": [{"name": column["Name"], "type": column["CslType"]} for column in columns],
        }

    def run_guarded(self, proposed_query: str) -> dict[str, Any]:
        safe_query = validate_read_only_kql(proposed_query, self.source, self.settings.maximum_rows, self._known_names())
        LOGGER.info("KQL to %s: %s", self.source.name, safe_query)
        try:
            table = self.client.execute_query(self.source.database, safe_query, self._request_properties()).primary_results[0]
        except KustoServiceError as error:
            raise QueryRejectedError(f"ADX rejected the query: {error}") from error
        columns = [column.column_name for column in table.columns]
        rows = [row.to_dict() for row in table]
        truncated = len(rows) > self.settings.maximum_rows
        shown = rows[: self.settings.maximum_rows]
        return {
            "source": self.source.name,
            "executedQuery": safe_query,
            "columns": columns,
            "rows": shown,
            "rowCount": len(shown),
            "truncated": truncated,
        }
