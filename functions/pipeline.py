"""Scheduled, source-versioned DfE ingestion for GM SkillsFund IQ.

A downloaded extract is archived before any SQL changes. SQL publishing is
separately gated by SQL_WRITE_ENABLED so restricted firewall access stays intact.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.etl import BOROUGHS, main as extract_dfe, sha256_file
from src.load_dfe_sql import integer_or_null  # source disclosure validation

LOG = logging.getLogger(__name__)
RUN_PREFIX = 'runs'
DATA_SPECS = {
    'provider_activity': {
        'file': 'funded_provider_activity.csv', 'version_prefix': 'DFE_PROVIDER_',
        'table': 'core.provider_activity',
    },
    'borough_learning': {
        'file': 'gm_borough_learning_totals.csv', 'version_prefix': 'DFE_BOROUGH_',
        'table': 'core.borough_learning',
    },
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f'CSV has no header: {path}')
        rows = list(reader)
        if not rows:
            raise ValueError(f'CSV is empty: {path}')
        return rows


def validate_borough_coverage(rows):
    """Allow future published periods, but require all ten boroughs per period."""
    periods = {}
    for row in rows:
        borough = row['lad_name'].strip()
        period = row['time_period'].strip()
        if not re.fullmatch(r'\d{6}', period) or borough not in BOROUGHS:
            raise ValueError(f'Invalid borough-period record: {borough}, {period}')
        if row['geographic_level'].strip().casefold() != 'local authority district':
            raise ValueError('Borough evidence must be LAD level')
        for key in ('sex', 'ethnicity_major', 'family_learning', 'tailored_learning_purpose'):
            if row[key].strip() != 'Total':
                raise ValueError(f'Unexpected borough subgroup: {key}')
        period_boroughs = periods.setdefault(period, set())
        if borough in period_boroughs:
            raise ValueError(f'Duplicate borough and period: {borough}, {period}')
        period_boroughs.add(borough)
        for measure in ('participation', 'learner_achievements'):
            validate_measure(row[measure])
    if len(periods) < 2:
        raise ValueError('Expected at least two reporting periods in borough source')
    for period, names in periods.items():
        if names != BOROUGHS:
            raise ValueError(f'Incomplete borough coverage for {period}: {len(names)}/10')
    return sorted(periods)


def validate_measure(raw):
    """Preserve disclosure values as NULL; reject unfamiliar measure formats."""
    # The existing, tested loader treats a known disclosure marker as NULL.
    value = integer_or_null(raw)
    return None if value == 'NULL' else int(value)


def prepare_rows(processed: Path):
    """Validate extracts against known funded provider identities and CSV contracts."""
    from src.etl import load_allocations
    funded_ukprns = {r['ukprn'] for r in load_allocations()}
    providers = read_csv(processed / DATA_SPECS['provider_activity']['file'])
    boroughs = read_csv(processed / DATA_SPECS['borough_learning']['file'])
    seen_versions = set()
    for r in providers:
        ukprn = r['provider_ukprn'].strip()
        period = r['time_period'].strip()
        if ukprn not in funded_ukprns or not re.fullmatch(r'\d{8}', ukprn):
            raise ValueError(f'Provider UKPRN outside funded cohort: {ukprn}')
        if not re.fullmatch(r'\d{6}', period):
            raise ValueError(f'Invalid provider period: {period}')
        for field in ('participation', 'learner_achievements'):
            validate_measure(r[field])
        seen_versions.add(ukprn)
    if not seen_versions:
        raise ValueError('No funded providers in published extract')
    periods = validate_borough_coverage(boroughs)
    return providers, boroughs, periods


def token_credential():
    """User-assigned managed identity in Azure, Azure CLI during local development."""
    from azure.identity import AzureCliCredential, ManagedIdentityCredential
    client_id = os.getenv('AZURE_CLIENT_ID', '').strip()
    if os.getenv('IDENTITY_ENDPOINT') or os.getenv('MSI_ENDPOINT'):
        return ManagedIdentityCredential(client_id=client_id or None)
    return AzureCliCredential()


def blob_container():
    from azure.storage.blob import BlobServiceClient
    url = os.environ['ARCHIVE_STORAGE_URL']
    name = os.getenv('ARCHIVE_CONTAINER', 'gm-skillsfund-iq-archive')
    client = BlobServiceClient(account_url=url, credential=token_credential())
    container = client.get_container_client(name)
    try:
        container.create_container()
    except Exception as exc:
        from azure.core.exceptions import ResourceExistsError
        if not isinstance(exc, ResourceExistsError):
            raise
    return container


def archive_extracts(container, processed, manifest, versions, run_id):
    """Content-addressed, non-overwriting filtered snapshots plus per-run manifest."""
    snapshots = {}
    for name, spec in DATA_SPECS.items():
        path = processed / spec['file']
        digest = sha256_file(path)
        if digest != manifest['sha256'][spec['file']]:
            raise ValueError(f'Extract changed during processing: {path.name}')
        blob_name = f'snapshots/{name}/{digest}.csv'
        from azure.core.exceptions import ResourceExistsError
        try:
            with path.open('rb') as handle:
                container.upload_blob(name=blob_name, data=handle, overwrite=False,
                                      content_settings=_csv_content_settings())
        except ResourceExistsError:
            pass  # identical, immutable extract already archived
        snapshots[name] = {'blob': blob_name, 'sha256': digest, 'version': versions[name]}
    run_blob = f'{RUN_PREFIX}/{datetime.now(timezone.utc):%Y/%m/%d}/{run_id}/manifest.json'
    full_manifest = {**manifest, 'run_id': run_id, 'snapshots': snapshots,
                     'archive_kind': 'filtered DfE extracts, NOT full source publisher files'}
    container.upload_blob(name=run_blob,
                          data=json.dumps(full_manifest, indent=2).encode('utf-8'),
                          overwrite=False)
    return run_blob


def _csv_content_settings():
    from azure.storage.blob import ContentSettings
    return ContentSettings(content_type='text/csv; charset=utf-8')


def publish_run_status(container, run_id, status, details):
    """A current append-by-ID operational record, even if SQL is unavailable."""
    log = {'run_id': run_id, 'status': status, 'recorded_utc': utc_now(), **details}
    blob_name = f'{RUN_PREFIX}/status/{run_id}.json'
    container.upload_blob(blob_name, json.dumps(log, indent=2, default=str).encode('utf-8'),
                          overwrite=True)


def sql_connection():
    """Microsoft SQL's Python driver avoids reliance on OS-level ODBC packages."""
    import mssql_python
    conn_string = (
        f"Server=tcp:{os.environ['SQL_SERVER']},1433;"
        f"Database={os.environ['SQL_DATABASE']};Encrypt=yes;"
    )
    return mssql_python.connect(conn_string, token_provider=token_credential())


def _current_version(cursor, name):
    cursor.execute('SELECT active_version FROM ops.source_state WHERE source_name = ?', (name,))
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f'Missing ops.source_state row for {name}; run SQL 006 migration')
    return row[0]


def _build_provider_insert(rows, version):
    result = []
    for i, r in enumerate(rows, 1):
        result.append((version, i, r['provider_ukprn'].strip(), r['time_period'].strip(),
                       r['provision_type'][:100], r['regulated_status'][:60], r['level'][:60],
                       r['participation'][:24], validate_measure(r['participation']),
                       r['learner_achievements'][:24], validate_measure(r['learner_achievements'])))
    return result


def _build_borough_insert(rows, version):
    result = []
    for i, r in enumerate(rows, 1):
        result.append((version, i, r['lad_code'][:12], r['lad_name'].strip(),
                       r['time_period'].strip(), r['participation'][:24],
                       validate_measure(r['participation']), r['learner_achievements'][:24],
                       validate_measure(r['learner_achievements'])))
    return result


def _write_run_start(run_id):
    with sql_connection() as conn:
        cur = conn.cursor()
        cur.execute('''INSERT INTO ops.pipeline_run (run_id, status, message)
                       VALUES (?, 'RUNNING', 'Scheduled DfE source review started')''', (run_id,))
        conn.commit()


def _write_run_result(run_id, status, rows, message, exception=None):
    with sql_connection() as conn:
        cur = conn.cursor()
        cur.execute('''UPDATE ops.pipeline_run
                       SET status=?, finished_at_utc=SYSUTCDATETIME(), rows_inserted=?, message=?
                       WHERE run_id=?''', (status, rows, message[:1900], run_id))
        if exception:
            cur.execute('''INSERT INTO ops.data_quality_exception
                           (run_id, source_name, rule_code, record_reference, exception_details)
                           VALUES (?, ?, ?, ?, ?)''',
                        (run_id, 'DfE sources', 'PIPELINE_FAILURE', None, str(exception)[:1900]))
        conn.commit()


def load_sql(providers, boroughs, manifest, versions):
    """One SQL transaction per full published snapshot; pointer flips only after validation.

    New versions are additive and become visible to Dash atomically. No deletes of
    historical snapshots, no table truncation, no writes to funding allocations.
    """
    rows_by_name = {'provider_activity': providers, 'borough_learning': boroughs}
    insert_sql = {
        'provider_activity': '''INSERT INTO core.provider_activity
              (source_version,source_row,ukprn,academic_period,provision_type,
               regulated_status,qualification_level,participation_raw,participation_value,
               achievements_raw,achievements_value)
              VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        'borough_learning': '''INSERT INTO core.borough_learning
              (source_version,source_row,lad_code,borough_name,academic_period,
               participation_raw,participation_value,achievements_raw,achievements_value)
              VALUES (?,?,?,?,?,?,?,?,?)''',
    }
    builders = {'provider_activity': _build_provider_insert,
                'borough_learning': _build_borough_insert}
    written = 0
    changed = []
    # First compute payloads so validation fails before a SQL transaction starts.
    values = {name: builders[name](rows_by_name[name], versions[name]) for name in DATA_SPECS}
    if any(len(values[name]) != len(rows_by_name[name]) for name in DATA_SPECS):
        raise ValueError('Inconsistent row counts after conversion')
    with sql_connection() as conn:
        try:
            cur = conn.cursor()
            for name, spec in DATA_SPECS.items():
                version = versions[name]
                current = _current_version(cur, name)
                if current != version:
                    cur.execute(f'SELECT COUNT_BIG(*) FROM {spec["table"]} WHERE source_version=?', (version,))
                    existing_count = int(cur.fetchone()[0])
                    if existing_count not in (0, len(values[name])):
                        raise ValueError(f'Partial prior source version found for {name}; review required')
                    if existing_count == 0:
                        # Use one short parameterised INSERT per row to avoid driver-specific
                        # executemany inference errors with mixed NULL/Unicode source values.
                        for item in values[name]:
                            cur.execute(insert_sql[name], item)
                        written += len(values[name])
                    cur.execute(f'SELECT COUNT_BIG(*) FROM {spec["table"]} WHERE source_version=?', (version,))
                    count = int(cur.fetchone()[0])
                    if count != len(values[name]):
                        raise ValueError(f'{name}: SQL count {count} != source {len(values[name])}')
                    changed.append(name)
                cur.execute('''UPDATE ops.source_state
                       SET active_version=?, sha256=?, row_count=?, source_url=?,
                           last_checked_at_utc=SYSUTCDATETIME(),
                           last_changed_at_utc=CASE WHEN active_version<>? THEN SYSUTCDATETIME()
                                                    ELSE last_changed_at_utc END
                       WHERE source_name=?''',
                    (version, manifest['sha256'][spec['file']], len(rows_by_name[name]),
                     manifest['source_urls'][name], version, name))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return written, changed


def run_once(run_id=None):
    run_id = run_id or str(uuid.uuid4())
    stage = 'DOWNLOADING'
    container = None
    sql_enabled = os.getenv('SQL_WRITE_ENABLED', 'false').strip().casefold() == 'true'
    sql_run_created = False
    processed_dir = None
    try:
        container = blob_container()
        if sql_enabled:
            _write_run_start(run_id)
            sql_run_created = True
        with tempfile.TemporaryDirectory(prefix='skillsfund-') as temp:
            processed_dir = Path(temp)
            # Existing source adapter has already been used for real public DfE data.
            extract_dfe(processed_dir)
            manifest = json.loads((processed_dir / 'source_manifest.json').read_text())
            providers, boroughs, periods = prepare_rows(processed_dir)
            if len(providers) != manifest['provider_rows_extracted'] or len(boroughs) != manifest['gm_borough_grand_total_rows_extracted']:
                raise ValueError('Manifest row counts do not match validated CSV')
            versions = {name: spec['version_prefix'] + manifest['sha256'][spec['file']][:16]
                        for name, spec in DATA_SPECS.items()}
            stage = 'ARCHIVING'
            run_blob = archive_extracts(container, processed_dir, manifest, versions, run_id)
            stage = 'SQL_PUBLISHING' if sql_enabled else 'STAGED_ONLY'
            inserted, changed = (load_sql(providers, boroughs, manifest, versions)
                                  if sql_enabled else (0, []))
            suppression = Counter(str(r[f]).strip().casefold()
                                  for coll in (providers, boroughs) for r in coll
                                  for f in ('participation', 'learner_achievements')
                                  if not str(r[f]).strip().isdecimal())
            status = 'SUCCESS' if sql_enabled else 'STAGED'
            details = {'rows_inserted': inserted, 'source_changed': changed,
                       'provider_rows': len(providers), 'borough_rows': len(boroughs),
                       'periods': periods, 'versions': versions, 'suppression_markers': dict(suppression),
                       'manifest_blob': run_blob, 'sql_published': sql_enabled}
            if sql_run_created:
                _write_run_result(run_id, 'SUCCESS', inserted,
                                  f'DfE checked; changed={changed}; inserted={inserted}')
            publish_run_status(container, run_id, status, details)
            LOG.info('Pipeline %s: %s %s', run_id, status, details)
            return {'run_id': run_id, 'status': status, **details}
    except Exception as exc:
        LOG.exception('Pipeline failed, run=%s stage=%s', run_id, stage)
        if sql_run_created:
            try:
                _write_run_result(run_id, 'FAILED', 0, f'{stage}: {exc}', exception=exc)
            except Exception:
                LOG.exception('Unable to write SQL failure audit for %s', run_id)
        if container:
            try:
                publish_run_status(container, run_id, 'FAILED',
                                   {'stage': stage, 'error': str(exc)[:500], 'sql_published': False})
            except Exception:
                LOG.exception('Unable to write Blob failure audit for %s', run_id)
        raise
