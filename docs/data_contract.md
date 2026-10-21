# Data contract v0.1

## Allocations
Columns: `source_row`, `ukprn` (8-digit string), `provider_name`, `funding_route` (`Grant`/`Procured`), `allocation_gbp` (decimal), `academic_year` (`2026/27`).

Validation: 32 source lines, 29 distinct UKPRNs and baseline sum 97002960.34 GBP. **These are baseline checks, not permanent rules**: alert and review if future publications differ. Procurement lot suffixes are retained; repeated UKPRNs are legitimate.

## DfE provider participation
`time_period`, `time_identifier`, `geographic_level`, `country_code`, `country_name`, `provider_name`, `provider_ukprn`, `provision_type`, `regulated_status`, `level`, `participation`, `learner_achievements`.

Filter *only* for UKPRNs found in the funding source when preparing the initial funded-provider evidence extract. Keep individual published breakdown rows. Do not aggregate across overlapping categories without checking official methodology.

## DfE geography
`time_period`, `time_identifier`, `geographic_level`, `country_code`, `country_name`, `region_code`, `region_name`, `lad_code`, `lad_name`, `sex`, `ethnicity_major`, `family_learning`, `tailored_learning_purpose`, `participation`, `learner_achievements`.

Initial borough reporting chooses the ten Greater Manchester local authorities and only rows where all four categorical columns equal `Total`. No unpublished individual participant records.

## Suppression
Retain the textual source value. Numeric parser accepts only integer strings, otherwise NULL plus suppression marker (`low`, `c`, `x`, `z`, or `other`). Do not convert `low` into 0.
