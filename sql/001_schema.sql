/* GM SkillsFund IQ, starter Azure SQL schema. Run on a NEW project database only. */
IF SCHEMA_ID('core') IS NULL EXEC('CREATE SCHEMA core');
IF SCHEMA_ID('ops') IS NULL EXEC('CREATE SCHEMA ops');
IF SCHEMA_ID('mart') IS NULL EXEC('CREATE SCHEMA mart');
GO
CREATE TABLE core.provider (
    ukprn VARCHAR(8) NOT NULL PRIMARY KEY,
    provider_name NVARCHAR(255) NOT NULL,
    created_at_utc DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE TABLE core.funding_allocation (
    allocation_id INT IDENTITY(1,1) PRIMARY KEY,
    source_version VARCHAR(64) NOT NULL,
    source_row INT NOT NULL,
    ukprn VARCHAR(8) NOT NULL,
    provider_name_as_published NVARCHAR(255) NOT NULL,
    funding_route VARCHAR(16) NOT NULL,
    academic_year CHAR(7) NOT NULL,
    procurement_lot SMALLINT NULL,
    allocation_gbp DECIMAL(18,2) NOT NULL,
    CONSTRAINT fk_funding_provider FOREIGN KEY (ukprn) REFERENCES core.provider(ukprn),
    CONSTRAINT ck_funding_route CHECK (funding_route IN ('Grant','Procured')),
    CONSTRAINT ck_allocation_positive CHECK (allocation_gbp > 0),
    CONSTRAINT uq_funding_version_source_row UNIQUE (source_version, source_row)
);
GO
CREATE TABLE core.provider_activity (
    activity_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    source_version VARCHAR(64) NOT NULL,
    source_row INT NOT NULL,
    ukprn VARCHAR(8) NOT NULL,
    academic_period CHAR(6) NOT NULL,
    provision_type NVARCHAR(100) NULL,
    regulated_status NVARCHAR(60) NULL,
    qualification_level NVARCHAR(60) NULL,
    participation_raw VARCHAR(24) NOT NULL,
    participation_value INT NULL,
    achievements_raw VARCHAR(24) NOT NULL,
    achievements_value INT NULL,
    CONSTRAINT fk_activity_provider FOREIGN KEY (ukprn) REFERENCES core.provider(ukprn),
    CONSTRAINT uq_activity_version_source_row UNIQUE (source_version, source_row)
);
GO
CREATE TABLE core.borough_learning (
    borough_learning_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    source_version VARCHAR(64) NOT NULL,
    source_row INT NOT NULL,
    lad_code VARCHAR(12) NULL,
    borough_name NVARCHAR(90) NOT NULL,
    academic_period CHAR(6) NOT NULL,
    participation_raw VARCHAR(24) NOT NULL,
    participation_value INT NULL,
    achievements_raw VARCHAR(24) NOT NULL,
    achievements_value INT NULL,
    CONSTRAINT uq_borough_version_source_row UNIQUE (source_version, source_row)
);
GO
CREATE TABLE ops.pipeline_run (
    run_id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
    started_at_utc DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    finished_at_utc DATETIME2 NULL,
    status VARCHAR(15) NOT NULL,
    rows_inserted INT NULL,
    rows_rejected INT NULL,
    message NVARCHAR(2000) NULL,
    CONSTRAINT ck_pipeline_status CHECK (status IN ('RUNNING','SUCCESS','FAILED'))
);
GO
CREATE TABLE ops.data_quality_exception (
    exception_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    run_id UNIQUEIDENTIFIER NULL,
    source_name VARCHAR(60) NOT NULL,
    rule_code VARCHAR(60) NOT NULL,
    record_reference NVARCHAR(255) NULL,
    exception_details NVARCHAR(2000) NULL,
    created_at_utc DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE OR ALTER VIEW mart.funding_by_provider AS
SELECT p.ukprn, p.provider_name,
       COUNT(*) allocation_lines,
       SUM(CASE WHEN a.funding_route='Grant' THEN a.allocation_gbp ELSE 0 END) grant_gbp,
       SUM(CASE WHEN a.funding_route='Procured' THEN a.allocation_gbp ELSE 0 END) procured_gbp,
       SUM(a.allocation_gbp) total_allocation_gbp
FROM core.provider p
JOIN core.funding_allocation a ON p.ukprn=a.ukprn
WHERE a.source_version = (SELECT MAX(source_version) FROM core.funding_allocation)
GROUP BY p.ukprn, p.provider_name;
GO
/* Caution: lexical MAX(source_version) is a temporary starter convention.
   Production should use publication timestamps and approved snapshot IDs. */
