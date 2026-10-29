# GM SkillsFund IQ
# live intelligence dashboard - https://gm-skillsfundiq-b1-kamil-898341.azurewebsites.net/
**Adult Skills Funding, Delivery Evidence and Data Assurance**, a portfolio engineering prototype using official published data for Greater Manchester. Independent demonstration, **not an official GMCA product**.

## The decision problem
Provide a repeatable evidence base to help analysts reconcile published Adult Skills Fund allocations, inspect provider-reported participation, examine borough learning activity and identify gaps requiring investigation before a commissioning briefing.

The system **does not** measure actual expenditure, contract performance, unique learner journeys or the impact of GMCA funding. DfE provider-level results can cover learners outside Greater Manchester and funding from other sources. The 2025/26 figures may be provisional or partial.

## Data sources
1. GMCA Core Adult Skills Fund Allocations 2026/27, official published workbook: https://www.greatermanchester-ca.gov.uk/what-we-do/education-work-and-skills/adult-skills-fund/supporting-documents/
2. DfE provider participation and achievements: https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/3281ce98-6e10-43a8-b17e-a7178cefb248/csv
3. DfE tailored learning by geography: https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/5e47f27f-6673-45a6-bbd6-28e6534c8bf1/csv

## Verified baseline
The supplied GMCA workbook contains **32 allocation records**, **29 unique UKPRNs**, **16 grant** and **16 procured allocation lines**, totalling **£97,002,960.34**. The worksheet name mentions 2425, but the published heading specifies **2026/27**; retain this source metadata discrepancy as an audit note. Three UKPRNs have multiple procurement lots. The CSV in `data/reference/` is a normalised transcription of the user-provided official workbook, not synthetic data.

## Local preparation

```bash
python3 -m unittest discover -s tests -v
python3 -m src.etl --output-dir data/processed
```

The ETL command downloads the DfE CSVs through their official public endpoints, retains only reported rows matching funded provider UKPRNs and Greater Manchester borough totals, and produces a manifest with source metadata. It **does not** yet load Azure SQL or publish the dashboard. These are deliberate next milestones.

## Roadmap
1. Verify source data and record contracts, done for the three inputs listed above.
2. Connect Azure Blob Storage, Azure SQL staging and audit tables, and complete identity-based Azure Functions scheduling.
3. Build a Plotly Dash app reading **verified SQL reporting views** and deploy it to Azure App Service.
4. Add Power BI semantic modelling after the live application is tested.

## Responsible interpretation
- Never use a provider's published national activity as proof of GMCA-funded delivery.
- The `low`, `c`, `x` and `z` disclosures are not numeric zero. Preserve the literal raw field and a separate parsed nullable value.
- Avoid summing across overlapping qualification or demographic breakdowns.
- Do not directly join provider allocation fact rows to detailed participation fact rows before their grain is specified.
- This repository does not contain or simulate GMIT participant records.

## Architecture and operational docs
See `docs/architecture.md`, `docs/data_contract.md`, `docs/runbook.md` and `sql/001_schema.sql`.
