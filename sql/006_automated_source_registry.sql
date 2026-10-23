/* GM SkillsFund IQ automation migration, safe on the existing database.
   Apply once before enabling SQL_WRITE_ENABLED. Leaves every existing data row intact.
   Never SUM provider category activity into funding outcomes.
*/
SET XACT_ABORT ON;
BEGIN TRANSACTION;
IF OBJECT_ID(N'ops.source_state', N'U') IS NULL
BEGIN
    CREATE TABLE ops.source_state (
        source_name VARCHAR(40) NOT NULL PRIMARY KEY,
        active_version VARCHAR(64) NULL,
        sha256 CHAR(64) NULL,
        row_count INT NULL,
        source_url NVARCHAR(700) NULL,
        last_checked_at_utc DATETIME2 NULL,
        last_changed_at_utc DATETIME2 NULL
    );
END;

IF NOT EXISTS (SELECT 1 FROM ops.source_state WHERE source_name='provider_activity')
BEGIN
    INSERT INTO ops.source_state (source_name, active_version, row_count, last_changed_at_utc)
    SELECT 'provider_activity',
           (SELECT TOP(1) source_version FROM core.provider_activity
            GROUP BY source_version ORDER BY COUNT_BIG(*) DESC, source_version DESC),
           (SELECT COUNT(*) FROM core.provider_activity WHERE source_version =
               (SELECT TOP(1) source_version FROM core.provider_activity
                GROUP BY source_version ORDER BY COUNT_BIG(*) DESC, source_version DESC)),
           SYSUTCDATETIME();
END;
IF NOT EXISTS (SELECT 1 FROM ops.source_state WHERE source_name='borough_learning')
BEGIN
    INSERT INTO ops.source_state (source_name, active_version, row_count, last_changed_at_utc)
    SELECT 'borough_learning',
           (SELECT TOP(1) source_version FROM core.borough_learning
            GROUP BY source_version ORDER BY COUNT_BIG(*) DESC, source_version DESC),
           (SELECT COUNT(*) FROM core.borough_learning WHERE source_version =
               (SELECT TOP(1) source_version FROM core.borough_learning
                GROUP BY source_version ORDER BY COUNT_BIG(*) DESC, source_version DESC)),
           SYSUTCDATETIME();
END;
COMMIT TRANSACTION;
GO

/* Existing downstream columns unchanged; only current-source selection is improved. */
CREATE OR ALTER VIEW mart.funded_provider_activity_evidence AS
SELECT p.ukprn,p.provider_name,a.academic_period,a.provision_type,a.regulated_status,
       a.qualification_level,a.participation_raw,a.participation_value,
       a.achievements_raw,a.achievements_value,a.source_version
FROM core.provider_activity AS a
JOIN core.provider AS p ON p.ukprn=a.ukprn
WHERE a.source_version=(SELECT active_version FROM ops.source_state WHERE source_name='provider_activity');
GO
CREATE OR ALTER VIEW mart.gm_borough_tailored_learning AS
SELECT borough_name,lad_code,academic_period,
       participation_raw,participation_value,achievements_raw,achievements_value,
       CASE WHEN academic_period='202526' THEN 'Provisional or partial release'
            ELSE 'Check published period metadata' END AS publication_warning,
       source_version
FROM core.borough_learning
WHERE source_version=(SELECT active_version FROM ops.source_state WHERE source_name='borough_learning');
GO
CREATE OR ALTER VIEW mart.source_health AS
SELECT 'Funding allocations' AS dataset, COUNT_BIG(*) AS observation_rows,
       COUNT_BIG(DISTINCT ukprn) AS distinct_entities,
       MAX(CAST(source_version AS NVARCHAR(64))) AS source_version
FROM core.funding_allocation
WHERE source_version=(SELECT MAX(source_version) FROM core.funding_allocation)
UNION ALL
SELECT 'DfE funded provider observations', COUNT_BIG(*), COUNT_BIG(DISTINCT ukprn),
       MAX(CAST(source_version AS NVARCHAR(64)))
FROM core.provider_activity
WHERE source_version=(SELECT active_version FROM ops.source_state WHERE source_name='provider_activity')
UNION ALL
SELECT 'DfE GM borough grand totals', COUNT_BIG(*), COUNT_BIG(DISTINCT borough_name),
       MAX(CAST(source_version AS NVARCHAR(64)))
FROM core.borough_learning
WHERE source_version=(SELECT active_version FROM ops.source_state WHERE source_name='borough_learning');
GO
CREATE OR ALTER VIEW mart.pipeline_health AS
SELECT TOP (20) run_id,started_at_utc,finished_at_utc,status,
       rows_inserted,rows_rejected,message
FROM ops.pipeline_run
ORDER BY started_at_utc DESC;
GO
SELECT source_name,active_version,row_count,last_checked_at_utc
FROM ops.source_state ORDER BY source_name;
SELECT dataset,observation_rows,distinct_entities,source_version
FROM mart.source_health ORDER BY dataset;
GO
