"""Read-only Azure SQL access using Microsoft Entra identity tokens.

Deploy with a system-assigned managed identity with only db_datareader.
Never add a SQL password, SQL admin account, or token to source control.
"""
from __future__ import annotations

import os
import struct
from contextlib import closing


SERVER = os.getenv('SQL_SERVER', 'gmskillsfundiqsql.database.windows.net')
DATABASE = os.getenv('SQL_DATABASE', 'gm_skillsfund_iq')
SQL_ACCESS_TOKEN_OPT = 1256


def connection():
    try:
        import pyodbc
        from azure.identity import AzureCliCredential, ManagedIdentityCredential
    except ImportError as exc:
        raise RuntimeError('Database dependencies are not installed') from exc

    if os.environ.get('IDENTITY_ENDPOINT') or os.environ.get('MSI_ENDPOINT'):
        credential = ManagedIdentityCredential()
    else:
        credential = AzureCliCredential()
    token = credential.get_token('https://database.windows.net/.default').token
    token_bytes = token.encode('utf-16-le')
    token_struct = struct.pack('<I', len(token_bytes)) + token_bytes
    conn_str = (
        'DRIVER={ODBC Driver 18 for SQL Server};'
        f'SERVER=tcp:{SERVER},1433;'
        f'DATABASE={DATABASE};'
        'Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
    )
    return pyodbc.connect(conn_str, attrs_before={SQL_ACCESS_TOKEN_OPT: token_struct}, timeout=30)


def fetch_rows(sql: str, args=()):
    """SQL strings are application-owned constants; dynamic values are parameters."""
    with closing(connection()) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, *args)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, record)) for record in cursor.fetchall()]


def funding_summary():
    return fetch_rows('''
        SELECT ukprn, provider_name, allocation_lines, grant_gbp,
               procured_gbp, total_allocation_gbp
        FROM mart.funding_by_provider
        ORDER BY total_allocation_gbp DESC, provider_name
    ''')


def provider_evidence(ukprn: str):
    if not ukprn.isdecimal() or len(ukprn) != 8:
        return []
    return fetch_rows('''
        SELECT TOP (500) academic_period, provision_type, regulated_status,
               qualification_level, participation_raw, participation_value,
               achievements_raw, achievements_value
        FROM mart.funded_provider_activity_evidence
        WHERE ukprn = ?
        ORDER BY academic_period DESC, provision_type,
                 regulated_status, qualification_level
    ''', (ukprn,))


def borough_evidence():
    return fetch_rows('''
        SELECT borough_name, academic_period, participation_raw,
               participation_value, achievements_raw, achievements_value,
               publication_warning
        FROM mart.gm_borough_tailored_learning
        ORDER BY borough_name, academic_period
    ''')


def source_health():
    return fetch_rows('''
        SELECT dataset, observation_rows, distinct_entities, source_version
        FROM mart.source_health
        ORDER BY dataset
    ''')


def quality_metrics():
    return fetch_rows('''
        SELECT
          (SELECT COUNT_BIG(*) FROM ops.data_quality_exception) AS exception_rows,
          (SELECT COUNT_BIG(*) FROM ops.pipeline_run) AS logged_runs,
          (SELECT COUNT_BIG(*) FROM core.provider_activity
           WHERE participation_value IS NULL OR achievements_value IS NULL)
              AS provider_rows_with_nonnumeric_measures
    ''')[0]
