# Operational runbook, starter

## Run the baseline tests
`python3 -m unittest discover -s tests -v`

## Run extraction
`python3 -m src.etl --output-dir data/processed`

## Expected outputs
* `funding_allocations.csv`
* `funded_provider_activity.csv`
* `gm_borough_learning_totals.csv`
* `source_manifest.json`

## On schema change or HTTP failure
Do not overwrite last known good published data. Preserve the HTTP status, error and source URL. Review changes to CSV headers before modifying the data contract. Re-run the pipeline after an approved patch.

## On unexpected funding totals
Inspect new publication version, source worksheet heading, categories and duplicate UKPRNs. UKPRN repetition across procurement lots is expected, not by itself a quality failure.

## On missing geographic rows
Check the official publication period, `geographic_level` values and whether the four total filters remain valid. Avoid filling missing borough counts with zero.

## Cloud Shell persistence
Azure Cloud Shell is currently ephemeral because Azure Files failed to mount. Commit and push files to GitHub after each verified change; do not store credentials or confidential information in the repository.
