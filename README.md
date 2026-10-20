# Data Science Agent

A read-only analysis app for Cyber Operations device data. It is a separate
repository and a separate web app from the Data Fabric Agent.

Version 1 answers five questions: profile the fleet, compare two groups, show
the daily trend, explain a change, and find the risky vulnerability overlap.
It does not train models or change data.

## Run locally

From this folder, on a port other than the Data Fabric Agent:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:APP_ENV = "local"
$env:AGENT_NAME = "Data Science Agent"
$env:DATA_SOURCES_JSON = '[{"name":"cyber","kind":"kusto","endpoint":"https://<cluster>.<region>.kusto.windows.net","database":"<database>","description":"Cyber operations device views.","allowedTables":["deviceinfo_org_ago24h","deviceinfo_org_ago7d","DeviceInfo_DailySummary","v_SoftwareVulnerabilities_Daily"]}]'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8766
```

Open http://127.0.0.1:8766/. A chip fills the box. It does not send.

## Deploy

Package this folder, not a parent repository. The ZIP must contain `app/`,
`templates/`, `static/`, and `requirements.txt` at the top.

```powershell
Remove-Item app.zip -ErrorAction SilentlyContinue
tar -a -c -f app.zip --exclude=__pycache__ --exclude=.venv app templates static requirements.txt
tar -tf app.zip
az webapp deploy -g <group> -n <new-web-app> --src-path app.zip --type zip --clean true --restart true --track-status false --subscription <subscription>
```

Do not deploy this package onto the Data Fabric Agent web app.
