# DfE data integration step, real published sources

Run from the GitHub repository root:

```bash
python3 -m src.etl --output-dir data/processed
python3 src/load_dfe_sql.py
python3 -m unittest discover -s tests -v
```

The extraction streams the actual DfE CSVs (no fabricated learning data), retaining source-matched funded provider UKPRNs and the 10 borough grand totals for both 2024/25 and 2025/26. Outputs `data/processed` must remain out of Git unless separately reviewed for licensing and size; the baseline CSV is public source information.

The generated `sql/003_load_dfe_evidence.sql` uses source hashes and source-row identifiers for rerun-safe loading. It intentionally keeps DfE suppression tokens (`low`, `c`, `x`, `z`) in raw columns with NULL numeric values. The 2025/26 figures are provisional or partial, so don't compare with full prior years as equivalent periods.

Apply `003` using ODBC sqlcmd and a short-lived Microsoft Entra token, then `004_evidence_views.sql`. Do not multiply funding rows through direct joins to observation facts. The starter mart view uses string MAX on source version: replace with timestamp-ranked snapshots before a production deployment.

After loading, query:
```sql
SELECT COUNT(*) AS activity_rows, COUNT(DISTINCT ukprn) AS funded_providers FROM core.provider_activity;
SELECT academic_period, COUNT(*) AS boroughs, SUM(participation_value) AS published_gm_grand_totals_sum FROM mart.gm_borough_tailored_learning GROUP BY academic_period ORDER BY academic_period;
SELECT * FROM mart.source_health;
```

The borough sum above is a sum across 10 **disjoint borough grand totals only**, but is subject to rounding and publication comparability limits; it must not be described as unique individual learner journeys or a definitive estimate of funding effectiveness.
