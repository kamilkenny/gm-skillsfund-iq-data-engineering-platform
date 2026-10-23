SELECT source_name,active_version,row_count,sha256,
       last_checked_at_utc,last_changed_at_utc
FROM ops.source_state ORDER BY source_name;
GO
SELECT TOP (10) started_at_utc,finished_at_utc,status,
       rows_inserted,message
FROM ops.pipeline_run ORDER BY started_at_utc DESC;
GO
SELECT dataset,observation_rows,distinct_entities,source_version
FROM mart.source_health ORDER BY dataset;
GO
SELECT TOP(10) source_name,rule_code,exception_details,created_at_utc
FROM ops.data_quality_exception ORDER BY created_at_utc DESC;
GO
