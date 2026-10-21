"""Initial real-data extraction and validation; standard-library-only."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import shutil
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNDING_FILE = ROOT / "data/reference/gmca_allocations_2026_27.csv"
SOURCES = {
    "provider_activity": "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/3281ce98-6e10-43a8-b17e-a7178cefb248/csv",
    "borough_learning": "https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/5e47f27f-6673-45a6-bbd6-28e6534c8bf1/csv",
}
BOROUGHS = {"Bolton", "Bury", "Manchester", "Oldham", "Rochdale", "Salford", "Stockport", "Tameside", "Trafford", "Wigan"}
TOTAL_FIELDS = ("sex", "ethnicity_major", "family_learning", "tailored_learning_purpose")
PROVIDER_FIELDS = ("time_period","time_identifier","geographic_level","country_code","country_name","provider_name","provider_ukprn","provision_type","regulated_status","level","participation","learner_achievements")
BOROUGH_FIELDS = ("time_period","time_identifier","geographic_level","country_code","country_name","region_code","region_name","lad_code","lad_name","sex","ethnicity_major","family_learning","tailored_learning_purpose","participation","learner_achievements")


def parse_published_count(text: str):
    """Return (value or None, disclosure marker or None). Never treat 'low' as 0."""
    value = str(text or "").strip()
    if value.isdecimal():
        return int(value), None
    return None, value.lower() if value else "missing"


def load_allocations(path=FUNDING_FILE):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    required = {"source_row", "ukprn", "provider_name", "funding_route", "allocation_gbp", "academic_year"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("Unexpected funding source schema")
    for row in rows:
        if not row["ukprn"].isdigit():
            raise ValueError("Invalid UKPRN")
        if row["funding_route"] not in ("Grant", "Procured"):
            raise ValueError("Unexpected route")
        try:
            if Decimal(row["allocation_gbp"]) <= 0:
                raise ValueError("Non-positive allocation")
        except InvalidOperation:
            raise ValueError("Invalid allocation amount")
    return rows


def provider_filter(row, ukprns):
    return row["provider_ukprn"].strip() in ukprns


def borough_filter(row):
    return (row["lad_name"].strip() in BOROUGHS
            and row["geographic_level"].strip().casefold() == "local authority district"
            and all(row[col].strip() == "Total" for col in TOTAL_FIELDS))


def fetch_filtered_csv(url, expected_fields, predicate, output):
    req = urllib.request.Request(url, headers={"User-Agent": "GM-SkillsFundIQ/0.1 (public-data research)", "Accept-Encoding": "identity"})
    count = 0
    with urllib.request.urlopen(req, timeout=120) as response:
        if "text/csv" not in (response.headers.get("Content-Type") or "").lower():
            raise ValueError("Expected text/csv from DfE, refusing non-CSV payload")
        text = io.TextIOWrapper(response, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(text)
        if not reader.fieldnames or not set(expected_fields).issubset(reader.fieldnames):
            raise ValueError("DfE schema changed: " + str(reader.fieldnames))
        with Path(output).open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader:
                if predicate(row):
                    writer.writerow(row)
                    count += 1
    return count


def sha256_file(path):
    hash_ = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hash_.update(chunk)
    return hash_.hexdigest()


def main(output_dir):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    funding = load_allocations()
    ukprns = {r["ukprn"] for r in funding}
    funding_out = out / "funding_allocations.csv"
    shutil.copy2(FUNDING_FILE, funding_out)
    provider_out = out / "funded_provider_activity.csv"
    borough_out = out / "gm_borough_learning_totals.csv"
    provider_n = fetch_filtered_csv(SOURCES["provider_activity"], PROVIDER_FIELDS,
                                    lambda row: provider_filter(row, ukprns), provider_out)
    borough_n = fetch_filtered_csv(SOURCES["borough_learning"], BOROUGH_FIELDS,
                                   borough_filter, borough_out)
    total = sum(Decimal(r["allocation_gbp"]) for r in funding)
    manifest = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "funding_source": "GMCA Core ASF Allocations 2026/27 official workbook, copied in normalised CSV form",
        "funding_records": len(funding),
        "funded_ukprns": len(ukprns),
        "funding_total_gbp": str(total),
        "funding_routes": dict(Counter(r["funding_route"] for r in funding)),
        "provider_rows_extracted": provider_n,
        "gm_borough_grand_total_rows_extracted": borough_n,
        "source_urls": SOURCES,
        "sha256": {p.name: sha256_file(p) for p in (funding_out, provider_out, borough_out)},
        "warnings": ["Do not attribute provider-wide activity to GMCA-funded learners", "2025/26 may be provisional or partial", "Suppressed counts must remain non-numeric"],
    }
    (out / "source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", default=str(ROOT / "data/processed"))
    main(p.parse_args().output_dir)
