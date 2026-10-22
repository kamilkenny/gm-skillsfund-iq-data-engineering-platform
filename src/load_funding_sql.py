"""Build an idempotent, versioned SQL load of the published GMCA funding CSV."""
import csv
import hashlib
import re
from decimal import Decimal
from pathlib import Path

source = Path('data/reference/gmca_allocations_2026_27.csv')
rows = list(csv.DictReader(source.open(encoding='utf-8-sig', newline='')))
assert len(rows) == 32, f'Unexpected record count: {len(rows)}'
assert len({r['ukprn'] for r in rows}) == 29, 'Unexpected unique provider count'
assert len({r['source_row'] for r in rows}) == 32, 'Duplicate source rows'
amounts = [Decimal(r['allocation_gbp']) for r in rows]
assert sum(amounts) == Decimal('97002960.34'), 'Funding total mismatch'
assert all(len(r['ukprn']) == 8 and r['ukprn'].isdigit() for r in rows)
assert all(r['funding_route'] in ('Grant', 'Procured') for r in rows)

version = 'GMCA_CORE_ASF_2026_27_' + hashlib.sha256(source.read_bytes()).hexdigest()[:12]
def esc(value):
    return value.replace("'", "''")

values = []
for r, amount in zip(rows, amounts):
    match = re.search(r' - LOT (\d+)$', r['provider_name'], re.I)
    lot = match.group(1) if match else 'NULL'
    provider = re.sub(r' - LOT \d+$', '', r['provider_name'], flags=re.I)
    if r['funding_route'] == 'Grant' and match:
        raise ValueError('Unexpected grant lot')
    values.append('    (' + ', '.join([
        str(int(r['source_row'])),
        "'" + r['ukprn'] + "'",
        "N'" + esc(provider) + "'",
        "N'" + esc(r['provider_name']) + "'",
        "'" + r['funding_route'] + "'",
        lot,
        f'{amount:.2f}',
    ]) + ')')

sql = f"""-- Versioned baseline import, generated from the public GMCA allocation CSV.
SET XACT_ABORT ON;
BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @src TABLE (
      source_row INT PRIMARY KEY, ukprn VARCHAR(8), provider_clean NVARCHAR(255),
      provider_published NVARCHAR(255), funding_route VARCHAR(16),
      procurement_lot SMALLINT NULL, amount DECIMAL(18,2)
    );
    INSERT INTO @src
      (source_row, ukprn, provider_clean, provider_published, funding_route, procurement_lot, amount)
    VALUES
{',\n'.join(values)};

    INSERT INTO core.provider (ukprn, provider_name)
    SELECT s.ukprn, MIN(s.provider_clean)
    FROM @src AS s
    WHERE NOT EXISTS (SELECT 1 FROM core.provider AS p WHERE p.ukprn = s.ukprn)
    GROUP BY s.ukprn;

    INSERT INTO core.funding_allocation
      (source_version, source_row, ukprn, provider_name_as_published,
       funding_route, academic_year, procurement_lot, allocation_gbp)
    SELECT '{version}', s.source_row, s.ukprn, s.provider_published,
           s.funding_route, '2026/27', s.procurement_lot, s.amount
    FROM @src AS s
    WHERE NOT EXISTS (
      SELECT 1 FROM core.funding_allocation AS a
      WHERE a.source_version = '{version}' AND a.source_row = s.source_row
    );

    IF (SELECT COUNT(*) FROM core.funding_allocation WHERE source_version = '{version}') <> 32
       OR (SELECT SUM(allocation_gbp) FROM core.funding_allocation WHERE source_version = '{version}') <> 97002960.34
       THROW 51000, 'Funding allocation reconciliation failed', 1;
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
SELECT source_version, COUNT(*) AS allocation_rows,
       COUNT(DISTINCT ukprn) AS providers,
       SUM(allocation_gbp) AS total_gbp
FROM core.funding_allocation
WHERE source_version = '{version}'
GROUP BY source_version;
GO
"""
out = Path('sql/002_load_gmca_funding.sql')
out.write_text(sql, encoding='utf-8')
print('Created', out, 'with', len(rows), 'records; total £', sum(amounts), '; version', version)
