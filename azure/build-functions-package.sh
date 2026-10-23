#!/usr/bin/env bash
set -euo pipefail
# Run from repository root. Requires zip, python3.
ROOT=$(pwd)
for path in functions/function_app.py functions/pipeline.py src/etl.py src/load_dfe_sql.py data/reference/gmca_allocations_2026_27.csv; do
  [[ -f "$ROOT/$path" ]] || { echo "Missing: $path" >&2; exit 1; }
done
BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
cp functions/function_app.py functions/pipeline.py functions/host.json functions/requirements.txt "$BUILD/"
mkdir -p "$BUILD/src" "$BUILD/data/reference"
cp src/__init__.py src/etl.py src/load_dfe_sql.py "$BUILD/src/"
cp data/reference/gmca_allocations_2026_27.csv "$BUILD/data/reference/"
python3 -m compileall -q "$BUILD/function_app.py" "$BUILD/pipeline.py" "$BUILD/src"
OUT="${1:-/tmp/gm-skillsfundiq-functions.zip}"
mkdir -p "$(dirname "$OUT")"
OUT=$(realpath "$OUT")
(cd "$BUILD" && zip -q -r "$OUT" . -x '*/__pycache__/*' '*.pyc')
unzip -t "$OUT" | tail -1
printf 'Ready for Azure Functions Python remote build: %s\n' "$OUT"
