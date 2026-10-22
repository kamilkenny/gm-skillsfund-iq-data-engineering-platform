# Plotly Dash, Azure App Service deployment plan

## Preconditions

1. Azure SQL `gm_skillsfund_iq` created and verified with `sql/005_dashboard_checks.sql`.
2. The physical database contains 32 funding allocation rows, 5,440 provider evidence observations and 20 borough grand-total rows for the current imported versions.
3. GitHub project commit pushed and working tree clean.
4. Read Azure App Service Linux Free F1 limits and inspect existing plan workloads before selecting or creating a dedicated F1 plan. **Never silently upgrade to Basic/Premium**.
5. Plan a limited inbound public dashboard with no sensitive data.

## App preparation

* Root `requirements.txt` includes `dashboard/requirements.txt` so App Service Oryx can resolve dependencies.
* Python runtime 3.12.
* Startup command:

```
gunicorn --chdir dashboard app:server --bind 0.0.0.0:8000 --workers 1 --timeout 180
```

* Environment variables: `SQL_SERVER=gmskillsfundiqsql.database.windows.net`, `SQL_DATABASE=gm_skillsfund_iq`.
* Authentication: enable a **system-assigned managed identity** on the web app. Do not use your SQL administrator account, SQL passwords or access tokens as app settings.
* In Azure SQL create an external contained user for the App Service managed identity (via its service principal), and grant `db_datareader` only. Microsoft Entra-only servers may require identity creation using `SID` / `TYPE = E` where name resolution is blocked. Confirm with the latest Microsoft documentation and make changes from a database administrator session.
* Configure the Azure SQL firewall to permit the web app's actual outbound addresses or the supported private networking architecture, not an unrestricted Azure services rule. App Service outbound IPs can change after reconfiguration, so document them.
* Verify `/health` returns HTTP 200; **that alone is not a database health check**. Confirm that the funding, borough and provider tabs each return actual SQL data.
* On App Service, confirm deployment build successfully installs ODBC Driver 18 availability and Python packages. Built-in Linux Python images normally include the Microsoft SQL ODBC driver; verify with an SSH console if it fails.

## Proposed CLI checks before provisioning a new plan

```bash
az appservice plan list --query '[].{Name:name,RG:resourceGroup,Tier:sku.tier,SKU:sku.name,Location:location}' -o table
az webapp list --query '[].{Name:name,RG:resourceGroup,Plan:appServicePlanId,State:state}' -o table
```

## Rollback and safety

* Push source code to GitHub before changing any Azure resource.
* Preserve database rows and older source versions; front end only reads.
* On failures, check App Service log stream and managed identity permissions, SQL firewall and pause state; do not relax global SQL firewall settings.
* Delete any temporary SQL Cloud Shell IP firewall rule once it is no longer required.
