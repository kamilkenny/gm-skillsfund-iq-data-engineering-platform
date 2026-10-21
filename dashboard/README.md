# Live Azure Dash application

Not yet deployed. The first version will query verified Azure SQL reporting views through a read-only connection. We deliberately do not expose a static dashboard as if it were already connected to production data.

The initial public pages will be:
1. Funding assurance and allocation summaries.
2. Provider and borough evidence, with period and statistical suppression warnings.
3. Pipeline freshness and data quality exception monitoring.

A locally generated snapshot can be used for UI testing, but public release is gated on completed SQL ingestion and row-level reconciliation.
