import pytest

from app.data_sources import DataSource
from app.errors import QueryRejectedError
from app.kusto_source import validate_read_only_kql

SOURCE = DataSource(
    "cyber",
    "https://adx.example.kusto.windows.net",
    "SecurityLab",
    "Cyber operations",
    ("deviceinfo_org_ago24h", "DeviceInfo_DailySummary", "v_SoftwareVulnerabilities_Daily"),
)


def test_a_summary_query_is_capped() -> None:
    safe = validate_read_only_kql("deviceinfo_org_ago24h | count", SOURCE, 100, ["deviceinfo_org_ago24h"])
    assert safe.endswith("| take 101")


def test_management_commands_are_rejected() -> None:
    with pytest.raises(QueryRejectedError, match="Management commands"):
        validate_read_only_kql(".drop table deviceinfo_org_ago24h", SOURCE, 100, [])


def test_cross_cluster_calls_are_rejected() -> None:
    with pytest.raises(QueryRejectedError, match="cluster"):
        validate_read_only_kql('cluster("other").database("x").table', SOURCE, 100, [])


def test_an_unlisted_table_is_rejected() -> None:
    with pytest.raises(QueryRejectedError, match="not in the allowed list"):
        validate_read_only_kql("SecretTable | count", SOURCE, 100, ["SecretTable", "deviceinfo_org_ago24h"])
