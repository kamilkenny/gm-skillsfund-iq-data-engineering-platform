# Live GM SkillsFund IQ Dash interface

A read-only application for inspecting verified Azure SQL views and published evidence. This is an independent demonstration, **not a GMCA official service**.

## Scope
* Funding assurance uses `mart.funding_by_provider` (one row per provider), never a direct join to detailed participation.
* Provider evidence uses `mart.funded_provider_activity_evidence`, filtered by a single UKPRN, preserving disclosure values such as `low`.
* Borough learning uses `mart.gm_borough_tailored_learning`, with provisional-period warnings.
* Data assurance reads `mart.source_health` and selected aggregate monitoring counts. An empty pipeline-run table is not presented as successful automation.

## Local preparation

```bash
python -m pip install -r requirements.txt
az login  # only if needed outside Azure Cloud Shell
python dashboard/app.py
```

Visit `http://localhost:8050`. On Azure Cloud Shell, use its Web preview if you have a persistent session; do not use `localhost` from your normal browser.

## Deployment

See `docs/dash_deployment.md`. App Service must have a **system-assigned managed identity**, Azure SQL `db_datareader` only, and a narrow Azure SQL firewall allowance for its documented outbound IP addresses. The web application exposes only predetermined SQL views, no arbitrary SQL queries and no database credentials.

## Operational caveats

* Azure SQL serverless may need time to resume and can pause after exhausting the free allowance.
* DfE data is published periodically; displayed versions are not live participant records.
* Provider-level activity includes provision beyond GMCA funding. No provider return-on-investment claims are supported.
* Reported 2025/26 data may be partial. Differences from full 2024/25 are not year-on-year performance changes.
* This web app is a read-only viewer. Scheduled ingestion via Azure Functions is a subsequent deployment task.
