# GM SkillsFund IQ — Backend automation starter

This package intentionally omits `dashboard/app.py` and `dashboard/db.py`, so it will NOT overwrite the layout-fix v3 work or current dashboard code. The Data Assurance UI can be updated separately after the pipeline succeeds.

## Restore after Cloud Shell restart

```bash
cd ~/gm-skillsfund-iq-data-engineering-platform
unzip -o ~/gm-skillsfundiq-automation-backend-v1.zip -d .
python3 -m unittest discover -s tests -v
python3 -m compileall -q functions
bash azure/build-functions-package.sh
```

## Verify SQL before deploying

The Azure SQL server firewall may need a new narrowly scoped Cloud Shell IP after every Cloud Shell restart. Use `az sql server firewall-rule list` and SQL server error messages; do not enable the unrestricted Azure-services exception.

```bash
bash azure/sql_apply.sh sql/006_automated_source_registry.sql
```

Expect **5,440 funded-provider observations**, **20 GM borough period records**, and **32 GMCA funding allocation records**.

## Provision a new B1 Function App (no SQL writes)

```bash
bash azure/create-b1-functions.sh
```

This creates `gm-skillsfundiq-jobs-kamil-898341` on the existing Linux B1 plan. It enables Always On and initially sets `SQL_WRITE_ENABLED=false`.

Only after verification:

```bash
bash azure/sql_apply.sh sql/007_function_sql_grants.sql
bash azure/build-functions-package.sh
```

Read `docs/automation_runbook.md` for deployment, protected manual-run endpoint, Blob staging, SQL publishing verification and clean-up. **The runbook's final step that updates dashboard/app.py is not applicable to this backend-only package.** It should happen as a separate layout-preserving update.

Never copy function keys, connection tokens or storage-account keys to GitHub.
