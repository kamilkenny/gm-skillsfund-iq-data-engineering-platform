/* Run AFTER assigning the user-assigned identity GMSkillsFundIQ-uami to the Function App.
   This identity is NOT the read-only B1 dashboard identity.
*/
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name=N'GMSkillsFundIQ-uami')
    CREATE USER [GMSkillsFundIQ-uami] FROM EXTERNAL PROVIDER;
GO
GRANT SELECT ON OBJECT::core.provider TO [GMSkillsFundIQ-uami];
GRANT SELECT, INSERT ON OBJECT::core.provider_activity TO [GMSkillsFundIQ-uami];
GRANT SELECT, INSERT ON OBJECT::core.borough_learning TO [GMSkillsFundIQ-uami];
GRANT SELECT, UPDATE ON OBJECT::ops.source_state TO [GMSkillsFundIQ-uami];
GRANT SELECT, INSERT, UPDATE ON OBJECT::ops.pipeline_run TO [GMSkillsFundIQ-uami];
GRANT INSERT ON OBJECT::ops.data_quality_exception TO [GMSkillsFundIQ-uami];
GO
SELECT name,type_desc FROM sys.database_principals WHERE name=N'GMSkillsFundIQ-uami';
GO
