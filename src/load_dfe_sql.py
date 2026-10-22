"""Generate repeatable Azure SQL loads for verified DfE CSV extracts.

Requires existing `python3 -m src.etl --output-dir data/processed` and the
001_schema.sql / 002_load_gmca_funding.sql already applied to the database.
Uses only Python standard library, no SQL credentials.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_COLUMNS = (
    "time_period", "provider_name", "provider_ukprn", "provision_type",
    "regulated_status", "level", "participation", "learner_achievements",
)
BOROUGH_COLUMNS = (
    "time_period", "geographic_level", "lad_code", "lad_name", "sex",
    "ethnicity_major", "family_learning", "tailored_learning_purpose",
    "participation", "learner_achievements",
)
VALID_BOROUGHS = {
    "Bolton", "Bury", "Manchester", "Oldham", "Rochdale",
    "Salford", "Stockport", "Tameside", "Trafford", "Wigan",
}

def literal(value: str) -> str:
    return "N'" + str(value).replace("'", "''") + "'"

def integer_or_null(raw: str) -> str:
    raw = str(raw).strip()
    if raw.isdecimal():
        return str(int(raw))
    if raw.casefold() in {"low", "c", "x", "z", "", "~", "u", "-"}:
        return "NULL"
    raise ValueError(f"Unexpected DfE measure: {raw!r}")

def read_rows(path: Path, required: tuple[str, ...]):
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or not set(required).issubset(r.fieldnames):
            raise ValueError(f"Unexpected columns in {path}: {r.fieldnames}")
        rows = list(r)
    if not rows:
        raise ValueError(f"No rows in {path}")
    return rows

def version(prefix: str, path: Path) -> str:
    return prefix + hashlib.sha256(path.read_bytes()).hexdigest()[:16]

def validate_and_convert_provider(rows, funded_ukprns):
    out = []
    for i, r in enumerate(rows, 1):
        ukprn = r["provider_ukprn"].strip()
        period = r["time_period"].strip()
        if ukprn not in funded_ukprns or not re.fullmatch(r"\d{8}", ukprn):
            raise ValueError(f"Provider row {i} contains unexpected UKPRN: {ukprn}")
        if not re.fullmatch(r"\d{6}", period):
            raise ValueError(f"Provider row {i} contains invalid period: {period}")
        parts = [
            str(i), literal(ukprn), literal(period),
            literal(r["provision_type"][:100]), literal(r["regulated_status"][:60]),
            literal(r["level"][:60]), literal(r["participation"][:24]),
            integer_or_null(r["participation"]), literal(r["learner_achievements"][:24]),
            integer_or_null(r["learner_achievements"]),
        ]
        out.append("(" + ",".join(parts) + ")")
    return out

def validate_and_convert_borough(rows):
    out = []
    seen = set()
    for i, r in enumerate(rows, 1):
        b = r["lad_name"].strip()
        period = r["time_period"].strip()
        if b not in VALID_BOROUGHS:
            raise ValueError(f"Unexpected borough: {b}")
        if not re.fullmatch(r"\d{6}", period):
            raise ValueError(f"Invalid borough period: {period}")
        if r["geographic_level"].strip().casefold() != "local authority district":
            raise ValueError(f"Unexpected geographic level for {b}")
        if not all(r[k] == "Total" for k in ("sex", "ethnicity_major", "family_learning", "tailored_learning_purpose")):
            raise ValueError(f"Non-total subgroup row for {b}")
        key = (b, period)
        if key in seen:
            raise ValueError(f"Duplicate borough grand-total row: {key}")
        seen.add(key)
        parts = [
            str(i), literal(r["lad_code"][:12]), literal(b), literal(period),
            literal(r["participation"][:24]), integer_or_null(r["participation"]),
            literal(r["learner_achievements"][:24]), integer_or_null(r["learner_achievements"]),
        ]
        out.append("(" + ",".join(parts) + ")")
    if seen != {(b, p) for b in VALID_BOROUGHS for p in ("202425", "202526")}:
        raise ValueError(f"Expected exactly ten GM boroughs for both periods; found {len(seen)}")
    return out

def batches(values, n=120):
    for start in range(0, len(values), n):
        yield values[start:start + n]

def write_sql(providers, boroughs, p_version, b_version, destination: Path):
    sql = ["-- Generated from real downloaded DfE CSVs, DO NOT EDIT BY HAND.",
           "-- Rows have explicit source version + row identity; reruns do not duplicate.",
           "SET XACT_ABORT ON;", "BEGIN TRY", "BEGIN TRANSACTION;", ""]
    for data, target, vers, columns, source_cols in [
        (providers, "core.provider_activity", p_version,
         "source_version,source_row,ukprn,academic_period,provision_type,regulated_status,qualification_level,participation_raw,participation_value,achievements_raw,achievements_value",
         "source_row,ukprn,academic_period,provision_type,regulated_status,qualification_level,participation_raw,participation_value,achievements_raw,achievements_value"),
        (boroughs, "core.borough_learning", b_version,
         "source_version,source_row,lad_code,borough_name,academic_period,participation_raw,participation_value,achievements_raw,achievements_value",
         "source_row,lad_code,borough_name,academic_period,participation_raw,participation_value,achievements_raw,achievements_value"),
    ]:
        col_list = source_cols.split(',')
        for batch in batches(data):
            sql.append(f"INSERT INTO {target} ({columns})")
            sql.append(f"SELECT '{vers}', s.*")
            sql.append("FROM (VALUES\n  " + ",\n  ".join(batch) + ") AS s(" + source_cols + ")")
            sql.append(f"WHERE NOT EXISTS (SELECT 1 FROM {target} d WHERE d.source_version='{vers}' AND d.source_row=s.source_row);")
        sql.append(f"IF (SELECT COUNT_BIG(*) FROM {target} WHERE source_version='{vers}') <> {len(data)}")
        sql.append(f"    THROW 51041, 'DfE source reconciliation count failed for {target}', 1;")
        sql.append("")
    sql += ["COMMIT TRANSACTION;", "END TRY", "BEGIN CATCH", "IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;", "THROW;", "END CATCH;", "GO",
            f"SELECT 'Provider activity' AS dataset, COUNT(*) AS rows_loaded, COUNT(DISTINCT ukprn) AS entities FROM core.provider_activity WHERE source_version='{p_version}';",
            f"SELECT 'Borough learning' AS dataset, COUNT(*) AS rows_loaded, COUNT(DISTINCT borough_name) AS entities FROM core.borough_learning WHERE source_version='{b_version}';", "GO"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(sql) + "\n", encoding="utf-8")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", default="data/processed")
    p.add_argument("--output", default="sql/003_load_dfe_evidence.sql")
    args = p.parse_args()
    datadir = Path(args.input_dir)
    manifest = json.loads((datadir / "source_manifest.json").read_text(encoding="utf-8"))
    ppath = datadir / "funded_provider_activity.csv"
    bpath = datadir / "gm_borough_learning_totals.csv"
    import sys
    sys.path.insert(0, str(ROOT))
    from src.etl import load_allocations
    funded_ukprns = {r['ukprn'] for r in load_allocations()}
    p_rows = read_rows(ppath, PROVIDER_COLUMNS)
    b_rows = read_rows(bpath, BOROUGH_COLUMNS)
    ps = validate_and_convert_provider(p_rows, funded_ukprns)
    bs = validate_and_convert_borough(b_rows)
    if len(ps) != manifest["provider_rows_extracted"] or len(bs) != manifest["gm_borough_grand_total_rows_extracted"]:
        raise ValueError("Manifest record count does not match source CSV")
    from src.etl import sha256_file
    for file in (ppath, bpath):
        if sha256_file(file) != manifest["sha256"][file.name]:
            raise ValueError(f"SHA256 mismatch for {file}")
    p_version = version('DFE_PROVIDER_', ppath)
    b_version = version('DFE_BOROUGH_', bpath)
    write_sql(ps, bs, p_version, b_version, Path(args.output))
    print(f"Generated {args.output}; provider observations={len(ps)}, unique funded providers={len({r['provider_ukprn'] for r in p_rows})}, borough observations={len(bs)}")
    print(f"Source versions: {p_version}; {b_version}")
    suppression = Counter(v.strip().casefold() for rows in (p_rows,b_rows) for r in rows for v in (r['participation'],r['learner_achievements']) if not v.strip().isdecimal())
    print('Non-numeric disclosure values preserved:', dict(suppression))
    print('CAUTION: Provider-wide activity must not be interpreted as GMCA-funded learner outcomes.')

if __name__ == '__main__':
    main()
