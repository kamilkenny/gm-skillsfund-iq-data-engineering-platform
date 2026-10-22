"""GM SkillsFund IQ Dash prototype, published evidence, read-only Azure SQL.

Run locally: python dashboard/app.py
App Service startup: gunicorn --chdir dashboard app:server --bind 0.0.0.0:8000 --workers 1 --timeout 180
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
app = Dash(__name__, title='GM SkillsFund IQ | Published evidence',
           assets_folder=str(ASSETS), suppress_callback_exceptions=True,
           update_title='Loading published evidence...')
server = app.server
server.config['JSON_SORT_KEYS'] = False


def message(text, cls='notice'):
    return html.Div(text, className=cls)


def pill(label, value):
    return html.Div([html.Div(label, className='kpi-title'),
                     html.Div(value, className='kpi-value')], className='kpi')


def sql_error_panel():
    return html.Div([
        html.H3('Live data connection unavailable'),
        html.P('The platform could not retrieve the current Azure SQL reporting views. '
               'No statistics are being substituted with sample or synthetic data.'),
        html.P('For the maintainer: check managed identity SQL reader access, '
               'Azure SQL networking, and database availability. See the deployment runbook.'),
    ], className='error-panel')


def funding_page(rows):
    if not rows:
        return message('No published allocation data is available in the SQL reporting view.')
    count, total = reconcile_funding(rows)
    grant_total = sum(Decimal(str(r['grant_gbp'])) for r in rows)
    proc_total = sum(Decimal(str(r['procured_gbp'])) for r in rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=['Grant', 'Procured'],
                         y=[float(grant_total), float(proc_total)],
                         text=[pounds(grant_total), pounds(proc_total)],
                         textposition='outside', marker_color=['#176b91', '#3d8f77']))
    fig.update_layout(margin=dict(l=20, r=15, t=35, b=20),
                      yaxis_title='Approved allocation (£)',
                      paper_bgcolor='white', plot_bgcolor='white', height=320)
    top = [dict(Provider=r['provider_name'], UKPRN=r['ukprn'],
                **{'Allocation lines': r['allocation_lines'],
                   'Grant': pounds(r['grant_gbp']),
                   'Procured': pounds(r['procured_gbp']),
                   'Total allocation': pounds(r['total_allocation_gbp'])})
           for r in rows]
    return html.Div([
        html.Div([pill('Approved allocation', pounds(total)),
                  pill('Funded providers', str(count)),
                  pill('Published allocation lines', str(sum(r['allocation_lines'] for r in rows)))],
                 className='kpi-row'),
        html.Div([
            html.Div([html.H3('Grant and procured funding'), dcc.Graph(figure=fig)],
                     className='panel'),
            html.Div([html.H3('Appropriate interpretation'),
                      html.P('These are published 2026/27 allocations, not expenditure or audited provider performance.'),
                      html.P('A provider can hold multiple procurement lots. Funding is aggregated from allocation facts only, not joined to detailed DfE observations.'),
                      message('Independent analytical engineering prototype, not an official GMCA product.')],
                     className='panel')
        ], className='two-column'),
        html.Div([html.H3('Provider funding allocation register'),
                  dash_table.DataTable(
                      data=top, columns=[{'name': k, 'id': k} for k in top[0]],
                      page_size=12, sort_action='native', filter_action='native',
                      style_table={'overflowX': 'auto'},
                      style_cell={'fontFamily': 'Arial, sans-serif', 'fontSize': 13,
                                  'padding': '10px', 'textAlign': 'left', 'minWidth': '115px'},
                      style_header={'fontWeight': 'bold', 'backgroundColor': '#eaf1f5'})],
                 className='panel')
    ])


def borough_page(rows):
    if not rows:
        return message('No borough evidence is currently available.')
    boroughs = sorted(set(row['borough_name'] for row in rows))
    fig = go.Figure()
    for period in sorted(set(row['academic_period'] for row in rows)):
        by_name = {r['borough_name']: r for r in rows if r['academic_period'] == period}
        fig.add_trace(go.Bar(
            name=period_label(period) + (' (provisional)' if period == '202526' else ''),
            x=boroughs,
            y=[by_name.get(b, {}).get('participation_value') for b in boroughs],
            customdata=[by_name.get(b, {}).get('participation_raw') for b in boroughs],
            hovertemplate='%{x}<br>Reported participation: %{customdata}<extra>%{fullData.name}</extra>'
        ))
    fig.update_layout(barmode='group', height=450, margin=dict(l=20,r=20,t=25,b=90),
                      paper_bgcolor='white', plot_bgcolor='white',
                      xaxis_tickangle=-35, yaxis_title='Reported participation')
    table_rows = [
        {'Borough': r['borough_name'], 'Academic period': period_label(r['academic_period']),
         'Participation': published_count(r['participation_raw'], r['participation_value']),
         'Achievements': published_count(r['achievements_raw'], r['achievements_value'])}
        for r in rows
    ]
    return html.Div([
        html.Div([pill('Greater Manchester boroughs', str(len(boroughs))),
                  pill('Published borough observations', str(len(rows)))], className='kpi-row'),
        message('2025/26 is provisional or partial. These are not like-for-like full academic year comparisons. '
                'Do not interpret differences as annual performance growth or decline.'),
        html.Div([html.H3('Published tailored learning participation'), dcc.Graph(figure=fig)], className='panel'),
        html.Div([html.H3('Borough reporting register'),
                  dash_table.DataTable(data=table_rows,
                     columns=[{'name':k,'id':k} for k in table_rows[0]],
                     page_size=12, sort_action='native', style_table={'overflowX':'auto'},
                     style_cell={'fontFamily':'Arial, sans-serif','fontSize':13,'padding':'10px','textAlign':'left'})],
                 className='panel')
    ])


def provider_page(rows, selected):
    if not selected:
        return message('Select a funded provider to review its published DfE observations.')
    if not rows:
        return message('No DfE published observations available for this provider.')
    periods = sorted({row['academic_period'] for row in rows})
    suppressed = sum(1 for row in rows if row['participation_value'] is None or row['achievements_value'] is None)
    table = [{
        'Academic year': period_label(r['academic_period']),
        'Provision type': r['provision_type'], 'Regulated status': r['regulated_status'],
        'Level': r['qualification_level'],
        'Participation': published_count(r['participation_raw'], r['participation_value']),
        'Achievements': published_count(r['achievements_raw'], r['achievements_value'])
    } for r in rows]
    return html.Div([
        html.Div([pill('Published observation rows', str(len(rows))),
                  pill('Academic periods', str(len(periods))),
                  pill('Rows with suppressed / unavailable values', str(suppressed))],
                 className='kpi-row'),
        message('Provider-wide DfE activity is not evidence that all learners were GMCA-funded. '
                'Do not sum overlapping provision or qualification breakdowns or calculate cohort success rates from these rows.'),
        html.Div([html.H3('Provider participation and achievement observations'),
                  dash_table.DataTable(data=table, columns=[{'name':k,'id':k} for k in table[0]],
                     page_size=12, filter_action='native', sort_action='native',
                     style_table={'overflowX':'auto'},
                     style_cell={'fontFamily':'Arial, sans-serif','fontSize':13,'padding':'10px','textAlign':'left'})],
                 className='panel')
    ])


def ops_page(health, metrics):
    data = [
        {'Dataset': row['dataset'], 'Observations': int(row['observation_rows']),
         'Entities': int(row['distinct_entities']), 'Source version': row['source_version']}
        for row in health
    ]
    return html.Div([
        html.Div([pill('Datasets registered', str(len(health))),
                  pill('Rows with non-numeric provider measures', str(metrics['provider_rows_with_nonnumeric_measures'])),
                  pill('Logged pipeline runs', str(metrics['logged_runs']))], className='kpi-row'),
        message('Initial data was loaded manually through Azure SQL scripts. The scheduled Azure Functions pipeline '
                'is not yet deployed. Empty run logs must not be interpreted as completed scheduled runs.'),
        html.Div([html.H3('Source observation counts and version identifiers'),
                  dash_table.DataTable(data=data,
                     columns=[{'name':k,'id':k} for k in data[0]],
                     page_size=10, style_table={'overflowX':'auto'},
                     style_cell={'fontFamily':'Arial, sans-serif','fontSize':13,'padding':'10px','textAlign':'left'})],
                 className='panel'),
        html.Div([html.H3('Operational limitations'),
                  html.P('Source version hashes demonstrate reproducibility, but do not by themselves establish publication date or business approval.'),
                  html.P('Pipeline-run and exception tables are ready for scheduled automation; a complete monitoring history begins only after it is configured.'),
                  html.P('Suppressed statistical measures remain NULL numerically, with their published disclosure codes retained.')],
                 className='panel')
    ])


app.layout = html.Div([
    html.Header([
        html.Div('GM / DATA INTELLIGENCE', className='eyebrow'),
        html.H1('GM SkillsFund IQ'),
        html.P('Adult Skills Funding, Delivery Evidence & Assurance'),
        html.Div('Independent technical portfolio demonstration using official published data',
                 className='site-note')
    ], className='masthead'),
    html.Main([
        dcc.Interval(id='refresh', interval=15*60*1000, n_intervals=0),
        html.Div([
            html.Div([html.Label('Funded provider', htmlFor='provider-select'),
                      dcc.Dropdown(id='provider-select', placeholder='Choose provider',
                                   options=[], clearable=False)], className='picker'),
            html.Div('Evidence is read from read-only Azure SQL views', className='data-label')
        ], className='toolbar'),
        dcc.Tabs(id='tabs', value='funding', children=[
            dcc.Tab(label='Funding assurance', value='funding'),
            dcc.Tab(label='Provider evidence', value='provider'),
            dcc.Tab(label='Borough learning', value='borough'),
            dcc.Tab(label='Data assurance', value='ops')
        ]),
        html.Div(id='content', className='content')
    ]),
    html.Footer('Source: GMCA Core ASF 2026/27 and DfE published statistical releases. '
                'Provisional periods and disclosure codes must be interpreted with care.')
], className='site')


@app.callback(Output('provider-select', 'options'),
              Output('provider-select', 'value'),
              Input('refresh', 'n_intervals'),
              State('provider-select', 'value'))
def update_providers(_n, old_value):
    try:
        data = db.funding_summary()
        options = [{'label': f"{r['provider_name']} ({r['ukprn']})", 'value': r['ukprn']}
                   for r in data]
        valid = {r['ukprn'] for r in data}
        return options, old_value if old_value in valid else (options[0]['value'] if options else None)
    except Exception:
        app.logger.exception('Failed to populate provider list')
        return [], None


@app.callback(Output('content','children'),
              Input('tabs','value'), Input('provider-select','value'),
              Input('refresh','n_intervals'))
def render_content(tab, selected, _n):
    try:
        if tab == 'funding':
            return funding_page(db.funding_summary())
        if tab == 'borough':
            return borough_page(db.borough_evidence())
        if tab == 'provider':
            return provider_page(db.provider_evidence(selected) if selected else [], selected)
        if tab == 'ops':
            return ops_page(db.source_health(), db.quality_metrics())
        return message('Unknown section')
    except Exception:
        app.logger.exception('SQL reporting query failed for %s', tab)
        return sql_error_panel()


@server.get('/health')
def health():
    # This is an application liveness check, not evidence of current SQL connectivity.
    return {'service': 'gm-skillsfund-iq', 'status': 'running'}, 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8050')), debug=False)
