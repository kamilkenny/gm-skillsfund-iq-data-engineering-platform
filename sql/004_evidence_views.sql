/* Non-aggregating evidence views deliberately preserve published statistical grain. */
CREATE OR ALTER VIEW mart.funded_provider_activity_evidence AS
SELECT
  p.ukprn, p.provider_name,
  a.academic_period, a.provision_type, a.regulated_status,
  a.qualification_level,
  a.participation_raw, a.participation_value,
  a.achievements_raw, a.achievements_value,
  a.source_version
FROM core.provider_activity AS a
JOIN core.provider AS p ON p.ukprn=a.ukprn
WHERE a.source_version=(
    SELECT MAX(source_version) FROM core.provider_activity
);
GO
CREATE OR ALTER VIEW mart.gm_borough_tailored_learning AS
SELECT borough_name, lad_code, academic_period,
       participation_raw, participation_value,
       achievements_raw, achievements_value,
       CASE WHEN academic_period='202526' THEN 'Provisional or partial release' ELSE 'Check published period metadata' END AS publication_warning,
       source_version
FROM core.borough_learning
WHERE source_version=(SELECT MAX(source_version) FROM core.borough_learning);
GO
/* Health view counts only: never sum measures across overlapping categories. */
CREATE OR ALTER VIEW mart.source_health AS
SELECT 'Funding allocations' AS dataset, COUNT_BIG(*) AS observation_rows,
       COUNT_BIG(DISTINCT ukprn) AS distinct_entities,
       MAX(CAST(source_version AS NVARCHAR(64))) AS source_version
FROM core.funding_allocation
UNION ALL
SELECT 'DfE funded provider observations', COUNT_BIG(*), COUNT_BIG(DISTINCT ukprn), MAX(CAST(source_version AS NVARCHAR(64)))
FROM core.provider_activity
UNION ALL
SELECT 'DfE GM borough grand totals', COUNT_BIG(*), COUNT_BIG(DISTINCT borough_name), MAX(CAST(source_version AS NVARCHAR(64)))
FROM core.borough_learning;
GO
