# GM SkillsFund IQ | Scheduled ingestion and operational monitoring

This is an independent portfolio platform, **not** an official GMCA product. The only automatic publisher downloads are the two **official DfE CSV URLs** already used in the initial ETL. The GMCA 2026/27 funding baseline is retained as an approved, manually controlled reference; a new GMCA allocation publication requires explicit review and a new funding import.

## Architecture

```text
Official DfE provider + LAD CSV
        |   weekly Monday 06:00 UTC, or authenticated POST
        v
Azure Functions Python v2, Dedicated B1 plan, Always On
        |--> validate schema, funded UKPRNs, borough/period coverage, suppressed values
        |--> Blob Storage: content-addressed CSV extracts + dated manifests + run status JSON
        |--> Azure SQL: parameterised transactional inserts only when source hash changes
                              |
                              +--> ops.source_state (active pointer, checked/changed dates)
                              +--> ops.pipeline_run / ops.data_quality_exception
                              +--> mart current-version views, finance unchanged
                                         |
                                         v
                              Azure B1 Plotly Dash (read-only managed identity)
```

The scheduled Function App is hosted on the **existing Basic B1 Linux App Service plan**, not the problematic Free F1 app. This is important because the new B1 Function App can use the same outbound network infrastructure already restricted in the Azure SQL firewall. Creating a **Function App** does not create a second paid plan. B1 resources are shared with the flood dashboard and the SkillsFund dashboard, so watch CPU and memory; avoid heavy concurrent work. The previously created **Flex Consumption** Function App remains untouched until this new workload is proven.

## Safety and correctness

- `SQL_WRITE_ENABLED=false` is the initial setting; this enables source extraction and Blob archive **only**. It must be changed to true **after** schema migration, SQL identity grants and connectivity checks succeed.
- Azure Storage and Azure SQL both use a **user-assigned managed identity** (`GMSkillsFundIQ-uami`) without SQL passwords. RBAC: `Storage Blob Data Contributor` on this project's existing storage account. SQL object permissions grant SELECT/INSERT only on provider/borough evidence, limited pipeline logging and source-state updates. No funding-allocation write access.
- Blob archives hold **filtered DfE extracts** (not the entire publisher file), identified by SHA-256 and source URL. Paths use the digest, and existing paths are not overwritten. This is not an Azure immutability retention policy.
- Source versions are SHA-derived. SQL `ops.source_state` decides which *validated, fully loaded* version the dashboard reads. Old versions remain in database for lineage but do not inflate active reporting counts.
- Loads use parameterised SQL, explicit row reconciliation, and a transaction for both source datasets and the active-version switch. An incomplete/invalid extract or interrupted load cannot publish a partial new snapshot. A rerun of the same version is idempotent.
- Published `low` and other disclosure values remain raw text plus `NULL` numeric values, never zero. Provider-level statistics are **not** GMCA-funded learner outcomes. Funding amounts are allocations, not expenditure.
- Audit records: SQL `ops.pipeline_run` and `ops.data_quality_exception`; separate Blob status JSON is retained even when SQL publishing is switched off or SQL is unavailable. `mart.pipeline_health` is the read view. `SUCCESS` means SQL publishing completed, not that a publisher certified quality.
- The scheduler uses `0 0 6 * * 1` (Mondays at 06:00 UTC), with `run_on_startup=False` and schedule monitor. For this Dedicated plan, **Always On** must be true for timer functions to fire reliably.
- A manual `POST /api/run-now` requires an Azure Function key. Treat function keys as secrets and do not put them in GitHub, pasted logs or browser URLs.
- DfE changes may require schema adjustments. Unsupported source fields, new disclosure markers or incomplete borough coverage fail closed and generate audit evidence instead of silently altering results.

## Order of operations

### 1. In Cloud Shell, unzip the automation overlay into repo

```bash
cd ~/gm-skillsfund-iq-data-engineering-platform
unzip -o ~/gm-skillsfundiq-automation-v1.zip -d .
python3 -m unittest discover -s tests -v
python3 -m compileall -q functions dashboard
bash azure/build-functions-package.sh
```

### 2. Apply schema migration and verify baseline still displays

```bash
bash azure/sql_apply.sh sql/006_automated_source_registry.sql
```

Expect provider state version `DFE_PROVIDER_e73122bfe7518375`, borough state version `DFE_BOROUGH_1327c32297d07afb`, 5,440 and 20 active observations respectively, subject to previous version imports. **Stop** if SQL reports errors or if these don't match your existing baseline.

### 3. Create B1 Function App with SQL writes DISABLED

```bash
bash azure/create-b1-functions.sh
```

New app: `gm-skillsfundiq-jobs-kamil-898341`. Existing B1 plan: `asp-gm-flood-dashboard`, Germany West Central. This action **creates another site resource on the existing billable B1 plan** and assigns the existing UAMI Blob role. No paid tier upgrade.

### 4. Grant Functions UAMI least-privilege SQL access

```bash
bash azure/sql_apply.sh sql/007_function_sql_grants.sql
```

Be sure to run this after `create-b1-functions.sh`, which assigns `GMSkillsFundIQ-uami` to the new site. The SQL script grants no access to the GMCA funding allocation table.

### 5. Verify outbound IP coverage

```bash
az functionapp show -g GMSkillsFundIQ_group -n gm-skillsfundiq-jobs-kamil-898341 \
  --query '{State:state,Outbounds:outboundIpAddresses}' -o json
```

The Function App shares B1 networking, but check its actual outbound addresses against the existing `GMFundIQB1WebNN` SQL firewall rules. Do **not** enable the broad 'Allow Azure services' exception; if specific additional IPs appear, whitelist them individually. If SQL connectivity is uncertain, leave `SQL_WRITE_ENABLED=false` and test the Blob-only stage first.

### 6. Deploy the Functions package

```bash
bash azure/build-functions-package.sh
az functionapp deployment source config-zip -g GMSkillsFundIQ_group \
  -n gm-skillsfundiq-jobs-kamil-898341 \
  --src /tmp/gm-skillsfundiq-functions.zip --build-remote true
```

If Cloud Shell repeats `Timeout waiting for token from portal`, the **B1-only** fallback is the same direct Kudu deployment that succeeded for Dash:

```bash
FN=gm-skillsfundiq-jobs-kamil-898341
TOKEN=$(az account get-access-token --resource https://management.azure.com/ --query accessToken -o tsv)
curl --fail-with-body --show-error --connect-timeout 30 --max-time 300 -i \
  -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/zip' \
  --data-binary @/tmp/gm-skillsfundiq-functions.zip \
  "https://${FN}.scm.azurewebsites.net/api/publish?type=zip"
unset TOKEN
```

A successful publish response is **not** proof that Functions loaded correctly. Verify discovery:

```bash
az functionapp function list -g GMSkillsFundIQ_group \
  -n gm-skillsfundiq-jobs-kamil-898341 --query '[].name' -o table
```

You should see `SkillsFundScheduledReview` and `SkillsFundRunNow`. If either is missing, inspect the Functions runtime and remote build logs before proceeding.

### 7. Run one *staging* job (no SQL writes)

```bash
FN=gm-skillsfundiq-jobs-kamil-898341
KEY=$(az functionapp function keys list -g GMSkillsFundIQ_group \
  -n "$FN" --function-name SkillsFundRunNow --query default -o tsv)
curl --fail-with-body --show-error --max-time 220 -X POST \
  -H "x-functions-key: $KEY" "https://${FN}.azurewebsites.net/api/run-now"
unset KEY
```

Expect a JSON response with `"status":"STAGED"`, `"sql_published":false`, 5,440 provider observations and 20 borough observations (assuming publisher sources unchanged). Check storage `gm-skillsfund-iq-archive` via `az storage blob list --account-name gmskillsfundiqgroup9fce --container-name gm-skillsfund-iq-archive --auth-mode login` if your CLI user has Blob Data Reader; otherwise check via Portal or grant yourself reader rights. Do not assume app success from HTTP 200 alone; inspect Blob run status.

### 8. Enable SQL publishing only after staging success

```bash
az functionapp config appsettings set -g GMSkillsFundIQ_group \
  -n gm-skillsfundiq-jobs-kamil-898341 \
  --settings SQL_WRITE_ENABLED=true --output none
```

Run the same authenticated manual POST again. Expect `"status":"SUCCESS"`, a new `ops.pipeline_run` SQL SUCCESS record. Since baseline source versions are present, `rows_inserted` should be zero **if the published sources haven't changed**. A later publisher update results in a new source version and changes the active view pointers atomically.

Check SQL with:

```bash
bash azure/sql_apply.sh sql/008_pipeline_verify.sql
```

### 9. Update the B1 Dash Data Assurance section to display the SQL run history

These files are included in this overlay: `dashboard/app.py` and `dashboard/db.py`. They show a neutral "no SQL pipeline runs yet" message before activation, then display actual run status/timestamps.

```bash
zip -q -r /tmp/gm-skillsfundiq-automated-dash.zip dashboard requirements.txt -x '*/__pycache__/*' '*.pyc'
APP=gm-skillsfundiq-b1-kamil-898341
TOKEN=$(az account get-access-token --resource https://management.azure.com/ --query accessToken -o tsv)
curl --fail-with-body -sS -i -X POST \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/zip' \
  --data-binary @/tmp/gm-skillsfundiq-automated-dash.zip \
  "https://${APP}.scm.azurewebsites.net/api/publish?type=zip"
unset TOKEN
```

Check `/health` and Data Assurance in the browser. A SQL 40613 or other transient timeout may require retrying after database serverless resume.

### 10. Commit everything

```bash
git add functions/ azure/ sql/006_automated_source_registry.sql \
  sql/007_function_sql_grants.sql sql/008_pipeline_verify.sql \
  tests/test_pipeline_automation.py docs/automation_runbook.md \
  dashboard/app.py dashboard/db.py

git commit -m "feat: schedule DfE ingestion, versioned SQL loads and pipeline monitoring"
git push origin main
```

## Known operational limitations

- The source is a mutable CSV export URL. A SHA over a **filtered extract** is sufficient for internal change detection of the selected rows but not a fingerprint of the publisher's entire underlying dataset. Publication timestamps and authoritative approval remain separate metadata.
- DfE releases can be provisional or contain rounding and disclosure controls. Do not present numeric differences as outcomes or causal effects.
- Functions can fail if publisher endpoints become unavailable, Blob RBAC takes time to propagate, the shared B1 worker is resource constrained, SQL serverless is resuming, or the SQL native driver is missing OS-level libraries. Check the Blob audit and the Functions runtime logs.
- The public dashboard remains **read-only**. The Function App has separate least-privilege SQL rights. B1 outbound-IP rules are not a substitute for authentication.
- No external email or SMS alerts are configured here; on-screen SQL run history and Blob run status are the initial monitoring mechanisms. A later Azure Monitor alert rule can be added subject to cost.
- Because the existing B1 plan hosts multiple applications, monitor CPU and memory and do not delete the flood project unless you explicitly want to retire it.
