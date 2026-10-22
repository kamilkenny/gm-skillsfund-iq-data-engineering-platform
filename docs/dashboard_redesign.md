# GM SkillsFund IQ: Editorial Intelligence Interface, v2

## Purpose

The redesign turns the functioning Azure SQL-backed technical dashboard into a portfolio-ready decision-support application. It does **not** change database authentication, the existing reporting views, ingestion logic, the original source data or the application's `/health` endpoint.

## Four navigable analytical views

1. **Funding assurance:** Reconciled financial KPIs, route share (grant and procured), ranked provider allocations and searchable provider register.
2. **Provider evidence:** Funded-provider selector, disclosure-aware observation counts, category-specific chart and searchable source-preserving observation table. Category records can overlap and are **not summed** or converted into achievement rates.
3. **Borough learning:** Two-period participation chart, within-reference-period participation/achievement breakdown, borough table and explicit provisional-release caveat.
4. **Data assurance:** SQL source registry, source fingerprints, operational readiness, architecture/lineage stages and disclosure limitations. No claim of automated scheduled ingestion until Azure Functions is deployed.

## Design principles

- A navy/sea-glass/ochre visual identity that does not copy the GM Transport application.
- Clear product identity, purpose text, project architecture and attribution to **Kamil Ridwan** in header and footer.
- Each chart includes **what the chart shows**, **why it matters** and **interpretation** guidance.
- Fully responsive desktop, tablet and mobile layouts.
- Read-only Azure SQL queries using the application's existing managed identity. No mocked figures or synthetic records.
- Visualisations are exploratory, not official funding recommendations.

## Technical change

Replace only:

- `dashboard/app.py`
- `dashboard/assets/style.css`

All original backend and dependency files stay in place.

## Local smoke checks

```bash
python3 -m compileall -q dashboard
python3 -m unittest discover -s tests -v
```

The updated `dashboard/app.py` is compatible with the previously configured startup command:

```bash
gunicorn --chdir dashboard app:server --bind 0.0.0.0:8000 --workers 1 --timeout 180
```

## Live deployment

The Azure B1 site is `gm-skillsfundiq-b1-kamil-898341` (the old F1 site is not the deployment target). Commit source updates to GitHub, ZIP `dashboard/` with root `requirements.txt`, and publish to the B1 Kudu endpoint using the Microsoft Entra / ARM token method that previously returned HTTP 200.

After redeployment, verify `/health` and the homepage return HTTP 200; open all four sections and confirm that data and caveats render correctly. If an issue occurs, use the existing deployment package from the previous Git commit to roll back the UI change. Remote operations and status cannot be verified from this document.
