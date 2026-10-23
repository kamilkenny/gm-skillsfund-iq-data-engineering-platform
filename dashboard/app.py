"""GM SkillsFund IQ | Azure SQL-backed adult skills commissioning intelligence.

Independent portfolio demonstration. Published data only, not an official GMCA product.
App Service: gunicorn --chdir dashboard app:server --bind 0.0.0.0:8000 --workers 1 --timeout 180
"""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

from dash import Dash, Input, Output, State, dash_table, dcc, html
import plotly.graph_objects as go

import db
from logic import pounds, period_label, published_count, reconcile_funding

ASSETS = Path(__file__).parent / 'assets'
app = Dash(
    __name__, title='GM SkillsFund IQ | Skills Investment Intelligence',
    assets_folder=str(ASSETS), suppress_callback_exceptions=True,
    update_title='Reading published evidence…',
)
server = app.server
server.config['JSON_SORT_KEYS'] = False

INK = '#152d3e'
MUTED = '#657588'
TEAL = '#168f87'
OCHRE = '#d7943f'
LIGHT = '#edf3f5'
PLOTLY = dict(
    font=dict(family='Inter, Segoe UI, Arial, sans-serif', size=12, color=INK),
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=12, r=14, t=24, b=22),
    hoverlabel=dict(bgcolor=INK, font_color='#ffffff'),
    xaxis=dict(showgrid=False, zeroline=False, linecolor='#dbe5ea'),
    yaxis=dict(gridcolor='#e9eff2', zeroline=False, linecolor='#dbe5ea'),
    legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0, font=dict(size=11)),
)


def small_tag(label, class_name='tag'):
    return html.Span(label, className=class_name)


def kpi(label, number, desc, eyebrow='MEASURE', highlight=False):
    return html.Div([
        html.Div([html.Span(eyebrow), html.Span('↗', className='kpi-arrow')], className='kpi-top'),
        html.Div(number, className='kpi-value'),
        html.H3(label, className='kpi-title'),
        html.P(desc, className='kpi-description'),
    ], className='kpi' + (' kpi-highlight' if highlight else ''))


def section_intro(index, kicker, title, description, meta=None):
    return html.Div([
        html.Div([html.Span(index, className='section-index'), html.Span(kicker, className='section-kicker')], className='section-overline'),
        html.Div([
            html.Div([html.H2(title), html.P(description, className='section-description')]),
            small_tag(meta, 'meta-chip') if meta else None,
        ], className='section-title-row'),
    ], className='section-intro')


def chart_note(shows, matters, caution=None):
    return html.Div([
        html.Div([html.Span('READ THE VISUAL', className='note-caption'),
                  html.P([html.Strong('What this shows. '), shows])]),
        html.Div([html.Span('THE DECISION USE', className='note-caption'),
                  html.P([html.Strong('Why it matters. '), matters])]),
        html.P([html.Strong('Interpretation. '), caution], className='note-caution') if caution else None,
    ], className='chart-note')


def panel(title, intro, children, note=None, badge=None, extra_class='', note_first=False):
    # Table notes belong above the DataTable, never below its dynamic filter and row region.
    # Each panel remains a normal document-flow container rather than relying on overlays.
    header = html.Div([
        html.Div([html.H3(title), html.P(intro, className='panel-intro')]),
        small_tag(badge, 'panel-badge') if badge else None,
    ], className='panel-header')
    contents = [header]
    if note_first and note is not None:
        contents.append(note)
    contents.append(children)
    if not note_first and note is not None:
        contents.append(note)
    return html.Section(contents, className=('panel ' + extra_class).strip())


def empty_panel(title, detail):
    return html.Div([html.H3(title), html.P(detail)], className='empty-panel')


def table_widget(rows, page_size=12, filterable=False):
    if not rows:
        return empty_panel('No rows available', 'The reporting view returned no records for this selection.')
    return dash_table.DataTable(
        data=rows, columns=[{'name': col, 'id': col} for col in rows[0]],
        page_size=page_size, sort_action='native',
        filter_action='native' if filterable else 'none',
        style_table={'overflowX': 'auto', 'width': '100%', 'minWidth': '100%', 'maxWidth': '100%'},
        style_header={
            'backgroundColor': '#f0f5f6', 'fontWeight': '700',
            'color': INK, 'border': 'none', 'padding': '15px 14px',
            'fontSize': '11px', 'textTransform': 'uppercase', 'letterSpacing': '0.07em',
        },
        style_cell={
            'fontFamily': 'Inter, Segoe UI, sans-serif', 'fontSize': '12px',
            'padding': '14px', 'textAlign': 'left', 'minWidth': '100px',
            'maxWidth': '360px', 'whiteSpace': 'normal', 'height': 'auto',
            'border': 'none', 'borderBottom': '1px solid #e9eef0',
            'color': INK, 'backgroundColor': '#fff',
        },
        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#fbfcfc'}],
        css=[{'selector': '.dash-spreadsheet-container .dash-spreadsheet-inner',
              'rule': 'border: none !important;'}],
    )


def style_fig(fig, height=360, **kwargs):
    layout = {**PLOTLY, "height": height, **kwargs}
    fig.update_layout(**layout)
    return fig


def funding_page(rows):
    if not rows:
        return empty_panel('No funding allocations found', 'The SQL funding view currently has no published allocation records.')
    provider_count, total = reconcile_funding(rows)
    grant = sum((Decimal(str(r['grant_gbp'])) for r in rows), Decimal('0'))
    procured = sum((Decimal(str(r['procured_gbp'])) for r in rows), Decimal('0'))
    lines = sum(int(r['allocation_lines']) for r in rows)

    donut = go.Figure(go.Pie(
        labels=['Grant', 'Procured'], values=[float(grant), float(procured)],
        hole=.72, sort=False, direction='clockwise',
        marker=dict(colors=[TEAL, OCHRE], line=dict(color='#fff', width=4)),
        textinfo='percent', textposition='inside', insidetextorientation='horizontal',
        textfont=dict(color='#ffffff', size=13),
        customdata=[pounds(grant), pounds(procured)],
        hovertemplate='%{label}<br>%{customdata}<br>%{percent}<extra></extra>',
    ))
    style_fig(donut, 340, showlegend=False,
              margin=dict(l=18, r=18, t=12, b=18),
              annotations=[dict(text='<b>2 ROUTES</b><br><span style="font-size:11px">Published funding</span>',
                                x=.5, y=.5, showarrow=False, font=dict(size=19, color=INK))])

    top = sorted(rows, key=lambda r: Decimal(str(r['total_allocation_gbp'])), reverse=True)[:10]
    top_rev = list(reversed(top))
    ranked = go.Figure(go.Bar(
        orientation='h', y=[r['provider_name'] for r in top_rev],
        x=[float(r['total_allocation_gbp']) / 1_000_000 for r in top_rev],
        marker=dict(color=TEAL, line=dict(width=0)),
        customdata=[pounds(r['total_allocation_gbp']) for r in top_rev],
        hovertemplate='%{y}<br>%{customdata}<extra></extra>',
    ))
    style_fig(ranked, 450, xaxis_title='Approved allocation (£ million)',
              margin=dict(l=8, r=20, t=18, b=75),
              yaxis=dict(showgrid=False, automargin=True, tickfont=dict(size=10)),
              xaxis=dict(showgrid=True, gridcolor='#eef3f4', zeroline=False, ticksuffix='m'))

    funding_rows = [{
        'Provider': r['provider_name'], 'UKPRN': r['ukprn'],
        'Allocation lines': r['allocation_lines'],
        'Grant': pounds(r['grant_gbp']), 'Procured': pounds(r['procured_gbp']),
        'Total allocation': pounds(r['total_allocation_gbp']),
    } for r in rows]

    return html.Div([
        section_intro('01', 'FUNDING INTELLIGENCE', 'Follow the funding.',
                      'A reconciled view of Greater Manchester’s published 2026/27 Adult Skills Fund allocations. '
                      'Explore funding routes, provider concentration and individual allocation records.',
                      '2026 / 27 • PUBLISHED ALLOCATIONS'),
        html.Div([
            kpi('Approved allocation', pounds(total), 'Published grant and procured allocations combined.', highlight=True),
            kpi('Funded providers', f'{provider_count:,}', 'Unique providers identified by UKPRN.'),
            kpi('Allocation lines', f'{lines:,}', 'Individual published records, including separate procurement lots.'),
            kpi('Funding routes', '02', 'Grant funding and procured funding.'),
        ], className='kpi-row'),
        html.Div([
            panel('How funding is structured', 'Share of the approved allocation by route.',
                  html.Div(dcc.Graph(figure=donut, config={'displayModeBar': False},
                                     responsive=True, style={'height': '340px'}),
                           className='chart-stage chart-stage-donut'),
                  note=chart_note('The financial split between grant and procured routes.',
                                  'Makes the overall commissioning mix visible at a glance.',
                                  'Allocated amounts are not actual spend or audited delivery.'), badge='FINANCIAL MIX'),
            panel('Where allocations are concentrated', 'Ten largest provider allocations by published amount.',
                  html.Div(dcc.Graph(figure=ranked, config={'displayModeBar': False},
                                     responsive=True, style={'height': '450px'}),
                           className='chart-stage chart-stage-ranked'),
                  note=chart_note('The largest provider totals, aggregated from allocation records only.',
                                  'Helps reviewers spot concentration and decide which allocations may need closer scrutiny.',
                                  'Relative financial size is not a measure of value for money or provider performance.'), badge='TOP 10'),
        ], className='insights-grid'),
        panel('Funding allocation register', 'Search, sort and inspect every funded provider represented in the published workbook.',
              html.Div(table_widget(funding_rows, filterable=True), className='table-shell'),
              note=chart_note('Provider-level reconciled allocation amounts and line counts.',
                              'Provides a traceable basis for funding assurance and deeper provider review.',
                              'A provider may hold more than one procurement lot; rows are not deduplicated by UKPRN alone.'),
              badge=f'{provider_count} PROVIDERS', extra_class='panel-table', note_first=True),
    ])


def provider_page(rows, selected):
    if not selected:
        return html.Div([
            section_intro('02', 'PROVIDER EVIDENCE', 'Look beyond the allocation.',
                          'Select a funded provider above to review the available DfE statistical observations.'),
            empty_panel('Choose a provider', 'Select a funded provider to inspect its published participation and achievement evidence.'),
        ])
    if not rows:
        return html.Div([
            section_intro('02', 'PROVIDER EVIDENCE', 'Look beyond the allocation.',
                          'Explore published provider activity while keeping funding and learner outcomes distinct.'),
            empty_panel('No published evidence', 'The selected UKPRN has no matching activity in the SQL evidence view.'),
        ])

    periods = sorted({str(r['academic_period']) for r in rows})
    affected_rows = sum(1 for r in rows if r['participation_value'] is None or r['achievements_value'] is None)
    # Display individual source observations; overlapping category rows must NEVER be totalled.
    display_period = '202425' if '202425' in periods else periods[-1]
    samples = [r for r in rows if str(r['academic_period']) == display_period
               and r['participation_value'] is not None and r['achievements_value'] is not None]
    samples.sort(key=lambda r: int(r['participation_value']), reverse=True)
    samples = samples[:9]

    fig = go.Figure()
    if samples:
        labels = [f"{r['provision_type']} · {r['qualification_level']} · {r['regulated_status']}"
                  for r in reversed(samples)]
        for measure, colour, label in [
            ('participation_value', TEAL, 'Participation'),
            ('achievements_value', OCHRE, 'Learner achievements'),
        ]:
            fig.add_trace(go.Bar(
                orientation='h', y=labels,
                x=[float(r[measure]) for r in reversed(samples)],
                name=label, marker_color=colour,
                hovertemplate='%{y}<br>%{x:,.0f} reported observations<extra>%{fullData.name}</extra>',
            ))
        style_fig(fig, 455, barmode='group',
                  margin=dict(l=8, r=12, t=48, b=30),
                  xaxis_title='Published count',
                  xaxis=dict(showgrid=True, gridcolor='#eef3f4'),
                  yaxis=dict(showgrid=False, automargin=True, tickfont=dict(size=10)))

    table_rows = [{
        'Academic period': period_label(r['academic_period']),
        'Provision type': r['provision_type'],
        'Regulated status': r['regulated_status'],
        'Level': r['qualification_level'],
        'Participation': published_count(r['participation_raw'], r['participation_value']),
        'Achievements': published_count(r['achievements_raw'], r['achievements_value']),
    } for r in rows]
    return html.Div([
        section_intro('02', 'PROVIDER EVIDENCE', 'What does published activity tell us?',
                      'Examine the selected provider’s published DfE participation and achievement observations. '
                      'This is contextual evidence, not attribution of learners to GMCA-funded contracts.',
                      f'UKPRN {selected} • PUBLIC DfE DATA'),
        html.Div([
            kpi('Records displayed', f'{len(rows):,}', 'DfE breakdown records returned by the query (up to 500).', highlight=True),
            kpi('Academic periods', str(len(periods)), 'Periods represented in the provider evidence.'),
            kpi('Disclosure / missing rows', f'{affected_rows:,}', 'Rows where at least one measure is non-numeric.'),
        ], className='kpi-row'),
        html.Div([
            html.Span('IMPORTANT CONTEXT', className='warning-title'),
            html.P('These observations cover published provider-wide activity, not solely Greater Manchester-funded learners. '
                   'Overlapping category breakdowns must not be summed into provider-wide totals or used to calculate completion rates.'),
        ], className='guidance-strip'),
        panel(f'Provider activity snapshots · {period_label(display_period)}',
              'Up to nine individual published category rows with the highest numeric participation counts. '
              'This is an illustrative breakdown, not a provider total.',
              dcc.Graph(figure=fig, config={'displayModeBar': False}, responsive=True) if samples
              else empty_panel('No numeric breakdown rows', 'Disclosure restrictions prevent charting this period.'),
              note=chart_note('Participation and achievements reported for individual statistical category rows.',
                              'Supports targeted questions about the provider’s published provision mix.',
                              'Breakdowns may overlap. Do not sum bars or infer success rates. 2025/26 evidence may be provisional.'),
              badge='CATEGORY VIEW'),
        panel('Provider evidence register', 'Filter or sort the source-preserving records returned by the SQL query (up to 500).',
              table_widget(table_rows, filterable=True),
              note=chart_note('The original DfE counts alongside their provision, level and reporting period.',
                              'Allows users to examine individual observations without losing disclosure context.',
                              '“low” and other withheld values remain displayed as published, never treated as zero.'),
              badge=f'{len(rows):,} OBSERVATIONS'),
    ])


def borough_page(rows):
    if not rows:
        return empty_panel('Borough data unavailable', 'No borough learning observations were found in the SQL evidence view.')
    boroughs = sorted({str(r['borough_name']) for r in rows})
    periods = sorted({str(r['academic_period']) for r in rows})
    grouped = go.Figure()
    for period, colour in [(p, TEAL if i == 0 else OCHRE) for i, p in enumerate(periods)]:
        by_name = {r['borough_name']: r for r in rows if str(r['academic_period']) == period}
        grouped.add_trace(go.Bar(
            name=period_label(period) + (' · provisional' if period == '202526' else ''),
            x=boroughs, y=[by_name.get(b, {}).get('participation_value') for b in boroughs],
            marker_color=colour,
            customdata=[published_count(by_name.get(b, {}).get('participation_raw'),
                                        by_name.get(b, {}).get('participation_value')) for b in boroughs],
            hovertemplate='%{x}<br>Reported participation: %{customdata}<extra>%{fullData.name}</extra>',
        ))
    style_fig(grouped, 415, barmode='group',
              xaxis=dict(tickangle=-30, showgrid=False),
              yaxis=dict(gridcolor='#edf2f5', title='Reported participation'),
              margin=dict(l=24, r=12, t=42, b=75))

    reference_period = '202425' if '202425' in periods else periods[0]
    baseline_rows = [r for r in rows if str(r['academic_period']) == reference_period]
    baseline_rows.sort(key=lambda r: r['participation_value'] or 0)
    baseline = go.Figure()
    baseline.add_trace(go.Bar(
        orientation='h', y=[r['borough_name'] for r in baseline_rows],
        x=[r['participation_value'] for r in baseline_rows],
        name='Participation', marker_color=TEAL,
        hovertemplate='%{y}<br>Participation: %{x:,.0f}<extra></extra>',
    ))
    baseline.add_trace(go.Bar(
        orientation='h', y=[r['borough_name'] for r in baseline_rows],
        x=[r['achievements_value'] for r in baseline_rows],
        name='Achievements', marker_color=OCHRE,
        hovertemplate='%{y}<br>Achievements: %{x:,.0f}<extra></extra>',
    ))
    style_fig(baseline, 415, barmode='group',
              margin=dict(l=12, r=14, t=44, b=30),
              xaxis=dict(showgrid=True, gridcolor='#eef3f4', title='Published count'),
              yaxis=dict(showgrid=False, automargin=True))

    table_rows = [{
        'Borough': r['borough_name'], 'Academic year': period_label(r['academic_period']),
        'Participation': published_count(r['participation_raw'], r['participation_value']),
        'Achievements': published_count(r['achievements_raw'], r['achievements_value']),
        'Publication note': r.get('publication_warning', ''),
    } for r in rows]
    return html.Div([
        section_intro('03', 'PLACE-BASED LEARNING', 'The geography of opportunity.',
                      'Explore published tailored learning participation and achievements across the ten Greater Manchester boroughs.',
                      '10 BOROUGHS • TWO REPORTING PERIODS'),
        html.Div([
            kpi('Borough coverage', str(len(boroughs)), 'All ten Greater Manchester local authority districts.', highlight=True),
            kpi('Reporting periods', str(len(periods)), 'Academic year versions covered by the published tables.'),
            kpi('Borough observations', str(len(rows)), 'Published grand-total borough-period records.'),
        ], className='kpi-row'),
        html.Div([html.Span('PERIOD COMPARABILITY', className='warning-title'),
                  html.P('2025/26 may be provisional or partial. Adjacent bars are shown for context only, '
                         'not as valid year-on-year growth or decline comparisons.')], className='guidance-strip'),
        html.Div([
            panel('Learning participation by borough', 'Published participation for each available academic period.',
                  dcc.Graph(figure=grouped, config={'displayModeBar': False}, responsive=True),
                  note=chart_note('How reported tailored learning participation is distributed by place and period.',
                                  'Highlights geography that may warrant additional service-planning enquiries.',
                                  'Do not interpret the two periods as directly comparable full-year results.'),
                  badge='GEOGRAPHIC REACH'),
            panel(f'Participation and achievements · {period_label(reference_period)}',
                  'Within-period comparison for the complete reference period where available.',
                  dcc.Graph(figure=baseline, config={'displayModeBar': False}, responsive=True),
                  note=chart_note('Two distinct published count measures for each borough in one period.',
                                  'Shows the scale and distribution of observed learning activity.',
                                  'These are not matched-cohort outcomes; do not divide achievements by participation to infer success rates.'),
                  badge='REFERENCE PERIOD'),
        ], className='insights-grid'),
        panel('Borough evidence register', 'Inspect the published numerical and disclosure values by borough and period.',
              html.Div(table_widget(table_rows, filterable=True), className='table-shell'),
              note=chart_note('The recorded values and publication caveats at borough-period grain.',
                              'Supports transparent interpretation of area-based evidence.',
                              'Counts are rounded as published. Provisional periods require separate interpretation.'),
              badge=f'{len(rows)} RECORDS', extra_class='panel-table', note_first=True),
    ])


def ops_page(health, metrics, runs=None):
    health = health or []
    metrics = metrics or {}
    runs = runs or []
    data = [{
        'Dataset': r['dataset'], 'Rows loaded': f"{int(r['observation_rows']):,}",
        'Distinct entities': f"{int(r['distinct_entities']):,}",
        'Source version': r['source_version'],
    } for r in health]
    total_rows = sum(int(r['observation_rows']) for r in health)
    return html.Div([
        section_intro('04', 'ASSURANCE & LINEAGE', 'Trust starts with traceability.',
                      'Inspect which public sources underpin the visuals, how disclosure is preserved and which pipeline controls are in place.',
                      'PUBLISHED DATA • GOVERNED VIEWS'),
        html.Div([
            kpi('Source datasets', str(len(health)), 'GMCA allocations and two DfE statistical sources.', highlight=True),
            kpi('Stored observation rows', f'{total_rows:,}', 'Records across datasets; counts, not additive learner totals.'),
            kpi('Non-numeric measure rows', f"{int(metrics.get('provider_rows_with_nonnumeric_measures', 0)):,}",
                'Provider records with at least one suppressed or unavailable measure.'),
            kpi('Logged pipeline runs', f"{int(metrics.get('logged_runs', 0)):,}",
                'Operational log records; not a claim of scheduled automation.'),
        ], className='kpi-row'),
        html.Div([
            panel('Evidence sources and version fingerprints',
                  'The SQL source-health view records the loaded row counts, coverage and source hashes.',
                  html.Div(table_widget(data, page_size=8), className='table-shell'),
                  note=chart_note('The datasets and source versions currently stored in Azure SQL.',
                                  'Supports repeatable ingestion, lineage checks and audit questions.',
                                  'Hash-derived versions do not independently verify a publication date or source approval.'),
                  badge='LINEAGE REGISTER', extra_class='panel-table', note_first=True),
            panel('Data-to-decision architecture',
                  'How the published evidence is transformed into a read-only analytical experience.',
                  html.Div([
                      html.Div([html.Span('01', className='flow-number'), html.Div([
                          html.Strong('Official public data'), html.Small('GMCA allocations + DfE datasets')])], className='flow-step'),
                      html.Div('↓', className='flow-arrow'),
                      html.Div([html.Span('02', className='flow-number'), html.Div([
                          html.Strong('Python validation'), html.Small('Identity matching, data contracts, disclosure preservation')])], className='flow-step'),
                      html.Div('↓', className='flow-arrow'),
                      html.Div([html.Span('03', className='flow-number'), html.Div([
                          html.Strong('Azure SQL reporting'), html.Small('Core facts, reconciliations and governed views')])], className='flow-step'),
                      html.Div('↓', className='flow-arrow'),
                      html.Div([html.Span('04', className='flow-number'), html.Div([
                          html.Strong('Plotly Dash on Azure'), html.Small('Read-only, identity-based decision intelligence')])], className='flow-step'),
                  ], className='lineage-flow'),
                  note=chart_note('The architectural responsibilities at each processing stage.',
                                  'Makes it clear where ingestion, validation, modelling and presentation occur.',
                                  'The initial baseline was manually ingested. Scheduled SQL automation is shown separately in the audit history when active.'),
                  badge='ARCHITECTURE'),
        ], className='insights-grid'),
        panel('Scheduled pipeline execution history',
              'Recorded Azure Functions runs, their status and inserted rows. The schedule is not considered operational until a successful SQL run exists.',
              table_widget([{
                  'Started UTC': str(r['started_at_utc']),
                  'Finished UTC': str(r['finished_at_utc'] or ''),
                  'Status': r['status'], 'Inserted rows': r.get('rows_inserted') or 0,
                  'Details': r.get('message') or '',
              } for r in runs], page_size=10) if runs else
              empty_panel('No SQL pipeline runs yet',
                          'Source checking may be staged in Blob Storage, but no successful SQL-publishing run has been logged.'),
              note=chart_note('The most recent automated SQL ingestion jobs and their completion status.',
                              'Gives the assurance team an auditable trail of dataset refreshes.',
                              'A SUCCESS audit row documents completed SQL publishing; it does not certify source quality.'),
              badge='PIPELINE AUDIT'),
        html.Div([
            html.Div([html.Span('IN OPERATION', className='mini-status'),
                      html.H3('Published source integration'),
                      html.P('CSV ingestion, provider UKPRN matching, Azure SQL facts and versioned reporting views.')],
                     className='assurance-card'),
            html.Div([html.Span('PROTECTED', className='mini-status'),
                      html.H3('Disclosure-aware reporting'),
                      html.P('Suppressed and unavailable values remain non-numeric, not zero-filled.')],
                     className='assurance-card'),
            html.Div([html.Span('AUTOMATION AUDIT' if runs else 'NEXT DELIVERY PHASE', className='mini-status' if runs else 'mini-status pending'),
                      html.H3('Scheduled pipeline orchestration'),
                      html.P('Operational SQL pipeline runs are recorded and shown above.' if runs else
                             'Azure Functions SQL publishing has not yet been verified; no operational claim is made.')],
                     className='assurance-card'),
        ], className='assurance-grid'),
        html.Div([html.Strong('Disclosure and independence statement'),
                  html.P('This is an independent technical portfolio demonstration, not a product commissioned or approved by GMCA. '
                         'Public provider-wide statistics are contextual evidence and cannot be attributed to a GMCA allocation. '
                         'No individual participant records or synthetic learner outcomes are presented.')], className='governance-banner'),
    ])


def sql_error_panel():
    return html.Div([
        html.Span('DATA CONNECTION', className='warning-title'),
        html.H3('The Azure SQL reporting views are temporarily unavailable.'),
        html.P('No sample values or fabricated statistics have been substituted. '
               'The application remains online while the underlying read-only query is investigated.'),
        html.P('Maintainer checks: Microsoft Entra SQL access, Azure SQL network rules and service availability.'),
    ], className='error-panel')


app.layout = html.Div([
    dcc.Interval(id='refresh', interval=15 * 60 * 1000, n_intervals=0),
    html.Div([
        html.Div([
            html.Div('GM', className='brand-mark'),
            html.Div([html.Strong('SkillsFund IQ'), html.Span('EDUCATION DATA INTELLIGENCE')], className='brand-type'),
        ], className='brand'),
        html.Div([html.Span(className='status-dot'), 'Azure SQL-connected evidence'], className='header-status'),
    ], className='topbar'),
    html.Header([
        html.Div([
            html.Div([html.Span('GREATER MANCHESTER', className='hero-eyebrow'), html.Span(' / ADULT SKILLS INTELLIGENCE', className='hero-eyebrow muted')], className='hero-overline'),
            html.H1(['Clarity for ', html.Span('every funding decision.', className='hero-emphasis')]),
            html.P('GM SkillsFund IQ brings published Adult Skills Fund allocations, provider delivery evidence and borough learning patterns into a single, traceable analytical experience.', className='hero-subtitle'),
            html.Div([small_tag('GMCA FUNDING DATA', 'tech-chip'), small_tag('DfE OPEN STATISTICS', 'tech-chip'),
                      small_tag('PYTHON + AZURE SQL', 'tech-chip'), small_tag('PLOTLY DASH', 'tech-chip')], className='tech-chips'),
            html.Div([html.Span(className='author-line'), 'Designed and modelled by ', html.Strong('Kamil Ridwan')], className='author-credit'),
        ], className='hero-copy'),
        html.Aside([
            html.Div('THE INTELLIGENCE LENS', className='lens-eyebrow'),
            html.Div([html.Div([html.Span('PUBLIC', className='lens-small'), html.Strong('Evidence'),
                                html.Span('→ GOVERNED INSIGHT', className='lens-small')], className='lens-centre')], className='lens-orbit'),
            html.Div([html.Span('01 / FUNDING'), html.Span('02 / DELIVERY'), html.Span('03 / PLACE')], className='lens-footer'),
        ], className='hero-visual'),
    ], className='hero'),
    html.Div([
        html.Div([html.Span(className='signal-dot'), html.Strong('PURPOSE-BUILT FOR EVIDENCE REVIEW'),
                  html.Span('Trace allocations · Inspect provider context · Understand borough variation', className='purpose-detail')], className='purpose-bar'),
        html.Div([html.Span('EXPLORE THE PLATFORM', className='nav-overline'),
            dcc.Tabs(id='tabs', value='funding', parent_className='tabs-shell', className='tabs-list', children=[
                dcc.Tab(label='01   Funding assurance', value='funding', className='tab', selected_className='tab--selected'),
                dcc.Tab(label='02   Provider evidence', value='provider', className='tab', selected_className='tab--selected'),
                dcc.Tab(label='03   Borough learning', value='borough', className='tab', selected_className='tab--selected'),
                dcc.Tab(label='04   Data assurance', value='ops', className='tab', selected_className='tab--selected'),
            ])
        ], className='navigation-wrap'),
        html.Div([
            html.Div([html.Label('SELECT A FUNDED PROVIDER', htmlFor='provider-select'),
                      dcc.Dropdown(id='provider-select', placeholder='Choose a provider and UKPRN',
                                   options=[], clearable=False)], className='picker'),
            html.Span('Provider-wide DfE observations are contextual, not GMCA-funded outcomes.', className='selection-note'),
        ], id='provider-toolbar', className='provider-toolbar', style={'display': 'none'}),
        html.Main(html.Div(id='content', className='content'), className='main-content'),
    ], className='body-shell'),
    html.Footer([
        html.Div([html.Div([html.Strong('GM SkillsFund IQ'), html.P('Adult Skills Funding, Delivery Evidence & Assurance')], className='footer-brand'),
                  html.Div([html.Span('ENGINEERING STACK'), html.P('Python · T-SQL · Azure SQL · Managed Identity · Plotly Dash · Azure App Service')], className='footer-stack')], className='footer-columns'),
        html.Div([html.P('An independent portfolio demonstration using official GMCA and DfE published data. '
                         'Funding is not expenditure; statistical observations are not contract-attributed learner outcomes.'),
                  html.P(['Designed and modelled by ', html.Strong('Kamil Ridwan'), '   ·   ',
                          html.A('Project source & methodology ↗', href='https://github.com/kamilkenny/gm-skillsfund-iq-data-engineering-platform', target='_blank', rel='noopener noreferrer')])], className='footer-bottom'),
    ], className='site-footer'),
], className='site')


@app.callback(Output('provider-select', 'options'), Output('provider-select', 'value'),
              Input('refresh', 'n_intervals'), State('provider-select', 'value'))
def update_providers(_n, old_value):
    try:
        data = db.funding_summary()
        options = [{'label': f"{r['provider_name']} ({r['ukprn']})", 'value': str(r['ukprn'])}
                   for r in data]
        valid = {str(r['ukprn']) for r in data}
        return options, old_value if old_value in valid else (options[0]['value'] if options else None)
    except Exception:
        app.logger.exception('Failed to populate provider list')
        return [], None


@app.callback(Output('provider-toolbar', 'style'), Input('tabs', 'value'))
def provider_toolbar(tab):
    return {'display': 'flex'} if tab == 'provider' else {'display': 'none'}


@app.callback(Output('content', 'children'), Input('tabs', 'value'),
              Input('provider-select', 'value'), Input('refresh', 'n_intervals'))
def render_content(tab, selected, _n):
    try:
        if tab == 'funding':
            return funding_page(db.funding_summary())
        if tab == 'provider':
            return provider_page(db.provider_evidence(str(selected)) if selected else [], selected)
        if tab == 'borough':
            return borough_page(db.borough_evidence())
        if tab == 'ops':
            return ops_page(db.source_health(), db.quality_metrics(),
                            db.pipeline_runs() if hasattr(db, 'pipeline_runs') else [])
        return empty_panel('Unknown view', 'Choose one of the four intelligence sections above.')
    except Exception:
        app.logger.exception('SQL reporting query failed: %s', tab)
        return sql_error_panel()


@server.get('/health')
def health():
    # Liveness endpoint only; Azure SQL queries are verified separately in the interface.
    return {'service': 'gm-skillsfund-iq', 'status': 'running'}, 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8050')), debug=False)
