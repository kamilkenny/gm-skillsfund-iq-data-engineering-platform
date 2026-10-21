# Proposed architecture and data boundaries

Official GMCA workbook and DfE CSVs → Azure Functions Python validation and extraction → Azure Blob Storage raw source versions → Azure SQL Database staging, conformed dimensions, distinct allocation/provider/geography fact tables → SQL reporting views → Azure App Service Plotly Dash → Power BI in the subsequent phase.

Use GitHub for source control and documentation, not as the production ingestion scheduler. Use an Azure Functions Timer trigger after identity and storage configuration is verified. The Function App has been created but no code is deployed as of the starter baseline.

**Source grain**
* Funding: one source allocation line, provider UKPRN, funding route and procurement lot, 2026/27.
* Provider participation: one published provider/year/provision type/regulated status/qualification level breakdown. The provider report is NOT restricted to GMCA-funded learners.
* Borough learning: one local-authority/year/demographic/learning purpose breakdown; filter all demographic and purpose dimensions to `Total` for displayed borough totals.

**Access**: the public dashboard should display only published aggregate records. Production Azure SQL access should use a read-only identity where possible, and source connection credentials must never be committed.
