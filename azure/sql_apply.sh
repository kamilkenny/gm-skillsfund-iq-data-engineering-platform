#!/usr/bin/env bash
# Execute an existing repo SQL script with your Azure CLI Microsoft Entra login.
set -euo pipefail
if [[ $# -lt 1 ]]; then echo 'Usage: bash azure/sql_apply.sh sql/<file>.sql [...]' >&2; exit 2; fi
export PATH="/opt/mssql-tools18/bin:$PATH"
command -v sqlcmd >/dev/null || { echo 'Missing /opt/mssql-tools18/bin/sqlcmd' >&2; exit 1; }
TOKEN_FILE=$(mktemp)
trap 'rm -f "$TOKEN_FILE"' EXIT
chmod 600 "$TOKEN_FILE"
az account get-access-token --resource https://database.windows.net/ --query accessToken -o tsv \
  | tr -d '\n' | iconv -f UTF-8 -t UTF-16LE > "$TOKEN_FILE"
for file in "$@"; do
  [[ -f "$file" ]] || { echo "Missing SQL file: $file" >&2; exit 2; }
  echo "Executing ${file} against gm_skillsfund_iq..."
  sqlcmd -S tcp:gmskillsfundiqsql.database.windows.net,1433 \
    -d gm_skillsfund_iq -G -P "$TOKEN_FILE" -b -l 90 -i "$file"
done
