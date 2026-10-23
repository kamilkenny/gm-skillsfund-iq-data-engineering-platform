#!/usr/bin/env bash
# Provisions a SEPARATE Function App on the existing B1 plan without modifying the flood app.
# SQL writes are intentionally disabled until the migration, identity grants and verification pass.
set -euo pipefail
RG=GMSkillsFundIQ_group
FN=gm-skillsfundiq-jobs-kamil-898341
STORAGE=gmskillsfundiqgroup9fce
PLAN_RG=rg-gm-flood-monitoring
PLAN=asp-gm-flood-dashboard
UAMI=GMSkillsFundIQ-uami

PLAN_ID=$(az appservice plan show -g "$PLAN_RG" -n "$PLAN" --query id -o tsv)
UAMI_ID=$(az identity show -g "$RG" -n "$UAMI" --query id -o tsv)
UAMI_CLIENT=$(az identity show -g "$RG" -n "$UAMI" --query clientId -o tsv)
UAMI_PRINCIPAL=$(az identity show -g "$RG" -n "$UAMI" --query principalId -o tsv)
STORAGE_ID=$(az storage account show -g "$RG" -n "$STORAGE" --query id -o tsv)

if ! az functionapp show -g "$RG" -n "$FN" --output none >/dev/null 2>&1; then
  az functionapp create --resource-group "$RG" --name "$FN" \
    --plan "$PLAN_ID" --storage-account "$STORAGE" \
    --runtime python --runtime-version 3.12 --functions-version 4 \
    --os-type Linux --https-only true --output none
fi
az functionapp identity assign -g "$RG" -n "$FN" --identities "$UAMI_ID" --output none
az functionapp config set -g "$RG" -n "$FN" --always-on true --output none
az functionapp config appsettings set -g "$RG" -n "$FN" --settings \
  "AZURE_CLIENT_ID=$UAMI_CLIENT" \
  "ARCHIVE_STORAGE_URL=https://${STORAGE}.blob.core.windows.net" \
  ARCHIVE_CONTAINER=gm-skillsfund-iq-archive \
  SQL_SERVER=gmskillsfundiqsql.database.windows.net SQL_DATABASE=gm_skillsfund_iq \
  "GM_IQ_SCHEDULE=0 0 6 * * 1" \
  SQL_WRITE_ENABLED=false \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true ENABLE_ORYX_BUILD=true \
  --output none

# Scope Blob Data Contributor to the single existing project storage account.
ASSIGNMENT_COUNT=$(az role assignment list --assignee "$UAMI_PRINCIPAL" \
  --scope "$STORAGE_ID" --role 'Storage Blob Data Contributor' --query 'length(@)' -o tsv)
if [[ "$ASSIGNMENT_COUNT" == '0' ]]; then
  az role assignment create --assignee-object-id "$UAMI_PRINCIPAL" \
    --assignee-principal-type ServicePrincipal --role 'Storage Blob Data Contributor' \
    --scope "$STORAGE_ID" --output none
fi
az functionapp show -g "$RG" -n "$FN" \
  --query '{Name:name,State:state,Runtime:siteConfig.linuxFxVersion,Plan:serverFarmId}' -o table
az functionapp config show -g "$RG" -n "$FN" \
  --query '{AlwaysOn:alwaysOn}' -o table
printf '\nNOTE: SQL_WRITE_ENABLED=false; do not enable until SQL setup and runtime validation succeed.\n'
