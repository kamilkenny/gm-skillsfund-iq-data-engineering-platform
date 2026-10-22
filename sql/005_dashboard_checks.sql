/* Read-only predeployment checks for GM SkillsFund IQ Dash.
   Run only against gm_skillsfund_iq. No data is modified. */
SELECT DB_NAME() AS database_name, COUNT_BIG(*) AS physical_tables FROM sys.tables;
SELECT COUNT_BIG(*) AS funding_allocation_rows,
       COUNT(DISTINCT ukprn) AS funded_providers,
       SUM(allocation_gbp) AS allocation_total_gbp
FROM core.funding_allocation
WHERE source_version=(SELECT MAX(source_version) FROM core.funding_allocation);
SELECT COUNT_BIG(*) AS provider_evidence_rows,
       COUNT(DISTINCT ukprn) AS represented_providers
FROM mart.funded_provider_activity_evidence;
SELECT COUNT_BIG(*) AS borough_evidence_rows,
       COUNT(DISTINCT borough_name) AS represented_boroughs
FROM mart.gm_borough_tailored_learning;
SELECT dataset, observation_rows, distinct_entities, source_version FROM mart.source_health;
SELECT COUNT_BIG(*) AS recorded_pipeline_runs FROM ops.pipeline_run;
GO
