import dash
from dash import dcc, html, Input, Output, State, callback, callback_context, no_update
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta
from utils import db_connection, build_base_query, apply_minimalist_style, render_info_tooltip, create_user_status_widget, get_supervisor_counts
from fpdf import FPDF

dash.register_page(__name__, path='/')

layout = dbc.Container([
    dcc.Store(id='drilldown-store'),
    dcc.Download(id="download-dataframe-csv"),
    dcc.Download(id="download-dataframe-pdf"),
    dcc.Store(id='interaction-store', data={}), 

    # Header uses Red (text-primary) by default via CSS
    html.H3([html.I(className="fa-solid fa-users me-2"), "Attendance Analytics"], className="mb-4 text-primary fw-bold"),

    # --- 1. MINI STATUS WIDGET ---
    html.Div(id='att-status-widget'),

    # --- 2. CONTROLS ROW (Date + Supervisor KPI) ---
    dbc.Row([
        # Date Picker
        dbc.Col([
            html.Label([html.I(className="fa-regular fa-calendar me-2"), "Select Anchor Date"], className="fw-bold small"),
            dcc.DatePickerSingle(
                id='att-date',
                min_date_allowed=date(2020, 1, 1),
                max_date_allowed=date(2030, 12, 31),
                date=date(2025, 11, 30), # Default Date
                display_format='Y-MM-DD',
                className="d-block w-100 shadow-sm"
            )
        ], width=4),

        # NEW: Supervisor Employee Count Widget
        dbc.Col([
             dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            # --- CHANGED LABEL HERE ---
                            html.H6("Employees Present", className="card-subtitle text-muted mb-1 small text-uppercase"),
                            html.H4(id="kpi-supervisor-count", children="0 / 0", className="card-title text-primary fw-bold mb-0")
                        ], width=8),
                        dbc.Col([
                            html.I(className="fa-solid fa-people-group fa-2x text-black-50")
                        ], width=4, className="d-flex align-items-center justify-content-end")
                    ])
                ], className="p-2")
             ], className="shadow-sm border-0 h-100")
        ], width=4),

        # Reset Button
        dbc.Col([
            dbc.Button([html.I(className="fa-solid fa-rotate-left"), " Reset View"], id="btn-clear-filter", color="danger", outline=True, size="sm", className="mt-4 w-100")
        ], width=2)
    ], className="mb-4 align-items-end"),

    # 3. ROW 1: WEEKLY + DEPARTMENT
    dbc.Row([
        dbc.Col(dbc.Card([
            # Changed text-info to text-primary (Red)
            dbc.CardHeader([
                html.I(className="fa-solid fa-chart-area me-2 text-primary"), "Weekly Trend",
                render_info_tooltip("tt-weekly", "Daily headcount trend.")
            ], className="fw-bold border-bottom d-flex align-items-center"),
            dbc.CardBody(dcc.Loading(
                html.Div(
                    html.Div(dcc.Graph(id='weekly-attendance-graph', config={'displayModeBar': False}), style={'minWidth': '1000px'}),
                    style={'height': '350px', 'overflowX': 'auto', 'overflowY': 'hidden'}
                )
            ))
        ], className="shadow-sm border-0 h-100"), width=6), 
        
        dbc.Col(dbc.Card([
            dbc.CardHeader([
                html.I(className="fa-solid fa-sitemap me-2 text-primary"), "Department Breakdown",
                render_info_tooltip("tt-dept", "Actual vs Required headcount by Department.")
            ], className="fw-bold border-bottom d-flex align-items-center"),
            dbc.CardBody(dcc.Loading(
                html.Div(
                    html.Div(dcc.Graph(id='department-bar-graph', config={'displayModeBar': False}), style={'minWidth': '550px'}),
                    style={'maxHeight': '350px', 'overflow': 'auto'} 
                )
            ))
        ], className="shadow-sm border-0 h-100"), width=6),
    ], className="mb-4"),

    # 4. ROW 2: GENDER, SKILLS, SHIFT
    dbc.Row([
        # Gender
        dbc.Col(dbc.Card([
            dbc.CardHeader([html.I(className="fa-solid fa-venus-mars me-2 text-primary"), "By Gender"], className="fw-bold small border-bottom"),
            dbc.CardBody(dcc.Loading(html.Div(html.Div(dcc.Graph(id='gender-bar-graph', config={'displayModeBar': False}), style={'minWidth': '300px'}), style={'height': '300px', 'overflowX': 'auto', 'overflowY': 'hidden'})), className="p-0")
        ], className="shadow-sm border-0 h-100"), width=4),

        # Skills
        dbc.Col(dbc.Card([
            dbc.CardHeader([html.I(className="fa-solid fa-award me-2 text-primary"), "By Skills"], className="fw-bold small border-bottom"),
            dbc.CardBody(dcc.Loading(html.Div(html.Div(dcc.Graph(id='skills-bar-graph', config={'displayModeBar': False}), style={'minWidth': '400px'}), style={'height': '300px', 'overflowX': 'auto', 'overflowY': 'hidden'})), className="p-0")
        ], className="shadow-sm border-0 h-100"), width=4),

        # Shift
        dbc.Col(dbc.Card([
            dbc.CardHeader([html.I(className="fa-regular fa-clock me-2 text-primary"), "By Shift"], className="fw-bold small border-bottom"),
            dbc.CardBody(dcc.Loading(html.Div(html.Div(dcc.Graph(id='shift-bar-graph', config={'displayModeBar': False}), style={'minWidth': '350px'}), style={'height': '300px', 'overflowX': 'auto', 'overflowY': 'hidden'})), className="p-0")
        ], className="shadow-sm border-0 h-100"), width=4),
    ], className="mb-5"),

    # DRILL DOWN SIDEBAR
    dbc.Offcanvas(
        id="details-offcanvas", title="Drill-Down Details", is_open=False, placement="end", style={"width": "50%"},
        children=[
            dbc.Row([
                dbc.Col(dbc.Button([html.I(className="fa-solid fa-file-csv me-2"), "Export CSV"], id="btn-download", color="success", size="sm", className="w-100"), width=6),
                dbc.Col(dbc.Button([html.I(className="fa-solid fa-file-pdf me-2"), "Export PDF"], id="btn-download-pdf", color="danger", size="sm", className="w-100"), width=6),
            ], className="mb-3"),
            html.Div(id='table-container')
        ]
    )
], fluid=True)

# ---------------------------------------------------------
# CALLBACKS
# ---------------------------------------------------------

# 1. WIDGET UPDATE
@callback(
    Output('att-status-widget', 'children'), 
    [Input('user-context-store', 'data'), 
     Input('att-date', 'date')]
)
def update_attendance_widget(user_data, selected_date):
    # --- GUARD CLAUSE ---
    if user_data is None: 
        return dash.no_update
    # --------------------
    
    emp_name = user_data.get('emp_name', 'Unknown') 
    contractor = user_data.get('contractor_name', None)
    
    return create_user_status_widget(emp_name, contractor, selected_date)

# --- NEW: SUPERVISOR KPI WIDGET (Using Utils) ---
@callback(Output('kpi-supervisor-count', 'children'), 
          [Input('att-date', 'date'), Input('user-context-store', 'data')])
def update_supervisor_kpi(selected_date, user_data):
    # --- GUARD CLAUSE ---
    if user_data is None: 
        return "0 / 0"
    # --------------------

    if not selected_date: return "0 / 0"
    
    supervisor_id = user_data.get('empid') 
    
    # Use helper function instead of repeating SQL
    return get_supervisor_counts(supervisor_id, selected_date)

# 2. COORDINATOR
@callback(
    Output('interaction-store', 'data'),
    [Input('department-bar-graph', 'clickData'), Input('gender-bar-graph', 'clickData'),
     Input('skills-bar-graph', 'clickData'), Input('shift-bar-graph', 'clickData'),
     Input('btn-clear-filter', 'n_clicks')]
)
def update_interaction_store(dept_click, gender_click, skills_click, shift_click, clear_click):
    ctx = callback_context
    if not ctx.triggered: return {}
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger_id == 'btn-clear-filter': return {}
    
    if trigger_id == 'department-bar-graph' and dept_click: return {'col': 'd.name', 'val': dept_click['points'][0]['y'], 'source': trigger_id}
    if trigger_id == 'gender-bar-graph' and gender_click: return {'col': "COALESCE(e.gender, 'Unknown')", 'val': gender_click['points'][0]['x'], 'source': trigger_id}
    if trigger_id == 'skills-bar-graph' and skills_click: return {'col': "COALESCE(e.skills_status, 'Unknown')", 'val': skills_click['points'][0]['x'], 'source': trigger_id}
    if trigger_id == 'shift-bar-graph' and shift_click: return {'col': 's.name', 'val': shift_click['points'][0]['x'], 'source': trigger_id}
    return {}

def get_colors(df, category_col, filter_data, default_color, grey_color='#adb5bd'):
    if not filter_data or filter_data.get('col') is None: return [default_color] * len(df)
    selected_val = filter_data['val']
    return [default_color if val == selected_val else grey_color for val in df[category_col]]

# --- GRAPH CALLBACKS ---

@callback(Output('weekly-attendance-graph', 'figure'), 
          [Input('att-date', 'date'), Input('user-context-store', 'data')])
def update_weekly_graph(selected_date, user_data):
    # --- GUARD CLAUSE ---
    if user_data is None:
        return dash.no_update
    # --------------------

    if not selected_date: return go.Figure().update_layout(title="Select a date")
    
    plant_id = user_data.get('plant_id') 
    company_id = user_data.get('company_id') 
    contractor_id = user_data.get('contractor_id') 
    supervisor_id = user_data.get('empid') # Logged in user is supervisor

    sel_dt = pd.to_datetime(selected_date).date()
    start_current_week = sel_dt - timedelta(days=sel_dt.weekday()) 
    end_current_week = start_current_week + timedelta(days=6)
    start_prev_week = start_current_week - timedelta(days=7)
    
    q_start = start_prev_week 
    q_end = end_current_week

    joins, where_clause = build_base_query(plant_id, company_id, None, contractor_id)
    
    # FILTER: Add Supervisor Scope
    if supervisor_id:
        where_clause += f" AND e.parent_id = {supervisor_id}"

    date_condition = f"AND DATE(a.check_in) >= '{q_start}' AND DATE(a.check_in) <= '{q_end}'"
    final_where = (where_clause + " " + date_condition) if where_clause else (f" WHERE {date_condition[4:]}" if date_condition else "")
    
    try:
        df = pd.read_sql(f"SELECT a.check_in, a.employee_id FROM hr_attendance a {joins} {final_where}", db_connection)
    except Exception as e: return go.Figure().update_layout(title=f"Error: {e}")

    if df.empty: 
        df_final = pd.DataFrame({'date': [sel_dt], 'count': [0]})
    else:
        df['check_in'] = pd.to_datetime(df['check_in'], errors='coerce')
        df_grouped = df.dropna(subset=['check_in']).copy()
        df_grouped['date'] = df_grouped['check_in'].dt.date
        df_final = df_grouped.groupby('date')['employee_id'].nunique().reset_index(name='count').sort_values('date')
    
    colors = ['#d32f2f' if d == sel_dt else '#adb5bd' for d in df_final['date']]
    sizes = [14 if d == sel_dt else 8 for d in df_final['date']]
    
    fig = go.Figure(go.Scatter(
        x=df_final['date'], 
        y=df_final['count'], 
        mode='lines+markers+text', 
        text=df_final['count'],    
        textposition="top center",
        fill='tozeroy', 
        line=dict(color='#d32f2f', width=2, shape='spline'), 
        marker=dict(size=sizes, color=colors, line=dict(width=1, color='white'))
    ))
    
    apply_minimalist_style(fig, height=350)

    range_start = q_start - timedelta(days=1)
    range_end = q_end + timedelta(days=1)

    fig.update_xaxes(
        showgrid=False, 
        type='date', 
        tickformat='%d-%b',
        dtick=86400000.0, 
        range=[range_start, range_end], 
        fixedrange=True
    )
    
    fig.update_layout(
        margin=dict(l=60, r=60, t=30, b=40),
        minreducedwidth=1000 
    )
    
    return fig

@callback(Output('department-bar-graph', 'figure'), 
          [Input('weekly-attendance-graph', 'clickData'), 
           Input('att-date', 'date'), 
           Input('interaction-store', 'data'), 
           Input('user-context-store', 'data')])
def update_department_figure(clickData, date_picker_val, filter_data, user_data):
    # --- GUARD CLAUSE ---
    if user_data is None:
        return dash.no_update
    # --------------------

    ctx = callback_context
    clicked_date = date_picker_val 
    
    if ctx.triggered:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if trigger_id == 'weekly-attendance-graph' and clickData:
            clicked_date = clickData['points'][0]['x']
    
    if not clicked_date: return go.Figure()

    plant_id = user_data.get('plant_id') 
    company_id = user_data.get('company_id') 
    contractor_id = user_data.get('contractor_id') 
    supervisor_id = user_data.get('empid') # Logged in user is supervisor
    
    conditions = ["e.active = true"]
    if company_id: conditions.append(f"e.company_id = {company_id}")
    if plant_id: conditions.append(f"e.plant_id = {plant_id}")
    if contractor_id: conditions.append(f"e.contractor_id = {contractor_id}")
    
    # FILTER: Add Supervisor Scope
    if supervisor_id: conditions.append(f"e.parent_id = {supervisor_id}")

    if filter_data and filter_data.get('source') != 'department-bar-graph': conditions.append(f"{filter_data['col']} = '{filter_data['val']}'")
    
    where_sql = (" AND " + " AND ".join(conditions)) if conditions else ""

    query = f"""
    SELECT d.name as dept_name, COUNT(DISTINCT a.employee_id) as present_count,
        MAX(d.requirement_a_shift) as req_a, MAX(d.requirement_b_shift) as req_b
    FROM hr_department d
    LEFT JOIN hr_employee e ON d.id = e.department_id 
    LEFT JOIN resource_calendar s ON e.resource_calendar_id = s.id
    LEFT JOIN plant_contractor c ON e.contractor_id = c.id
    LEFT JOIN hr_attendance a ON e.id = a.employee_id AND DATE(a.check_in) = '{clicked_date}'
    WHERE 1=1 {where_sql} GROUP BY d.name ORDER BY present_count ASC
    """
    try:
        df = pd.read_sql(query, db_connection)
        if df.empty: return go.Figure().update_layout(title="No Data")
        
        is_self = (filter_data and filter_data.get('source') == 'department-bar-graph')
        present_colors = get_colors(df, 'dept_name', filter_data if is_self else None, '#d32f2f')

        fig = go.Figure()
        fig.add_trace(go.Bar(y=df['dept_name'], x=df['req_a'], name='Req A', orientation='h', marker=dict(color='#1976d2'), text=df['req_a'], textposition='auto'))
        fig.add_trace(go.Bar(y=df['dept_name'], x=df['req_b'], name='Req B', orientation='h', marker=dict(color='#0288d1'), text=df['req_b'], textposition='auto'))
        fig.add_trace(go.Bar(y=df['dept_name'], x=df['present_count'], name='Present', orientation='h', marker=dict(color=present_colors), text=df['present_count'], textposition='auto'))

        h = max(350, len(df) * 35)
        apply_minimalist_style(fig, height=h)
        fig.update_xaxes(showgrid=True, gridcolor='rgba(128,128,128,0.2)')
        fig.update_yaxes(showgrid=False)
        fig.update_layout(margin=dict(l=150, r=20, t=10, b=20), barmode='group')
        return fig
    except: return go.Figure()

@callback([Output('gender-bar-graph', 'figure'), Output('skills-bar-graph', 'figure')],
    [Input('weekly-attendance-graph', 'clickData'), 
     Input('att-date', 'date'), 
     Input('interaction-store', 'data'), 
     Input('user-context-store', 'data')])
def update_gender_skills_figures(clickData, date_picker_val, filter_data, user_data):
    # --- GUARD CLAUSE ---
    if user_data is None:
        return go.Figure(), go.Figure()
    # --------------------

    ctx = callback_context
    clicked_date = date_picker_val
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'].startswith('weekly-attendance-graph') and clickData:
            clicked_date = clickData['points'][0]['x']
            
    if not clicked_date: return go.Figure(), go.Figure()

    plant_id = user_data.get('plant_id') 
    company_id = user_data.get('company_id') 
    contractor_id = user_data.get('contractor_id') 
    supervisor_id = user_data.get('empid')
    
    base_conds = ["e.active = true"]
    if company_id: base_conds.append(f"e.company_id = {company_id}")
    if plant_id: base_conds.append(f"e.plant_id = {plant_id}")
    if contractor_id: base_conds.append(f"e.contractor_id = {contractor_id}")
    
    # FILTER: Add Supervisor Scope
    if supervisor_id: base_conds.append(f"e.parent_id = {supervisor_id}")

    g_conds, s_conds = base_conds.copy(), base_conds.copy()
    if filter_data:
        if filter_data.get('source') != 'gender-bar-graph': g_conds.append(f"{filter_data['col']} = '{filter_data['val']}'")
        if filter_data.get('source') != 'skills-bar-graph': s_conds.append(f"{filter_data['col']} = '{filter_data['val']}'")

    def get_query(select, conds):
        where = f"WHERE DATE(a.check_in) = '{clicked_date}'"
        if conds: where += " AND " + " AND ".join(conds)
        return f" {select} FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id LEFT JOIN hr_department d ON e.department_id = d.id LEFT JOIN resource_calendar s ON e.resource_calendar_id = s.id LEFT JOIN plant_contractor c ON e.contractor_id = c.id {where} GROUP BY 1"

    try:
        df_g = pd.read_sql(get_query("SELECT COALESCE(e.gender, 'Unknown') as label, COUNT(DISTINCT a.employee_id) as val", g_conds), db_connection)
        df_s = pd.read_sql(get_query("SELECT COALESCE(e.skills_status, 'Unknown') as label, COUNT(DISTINCT a.employee_id) as val", s_conds), db_connection)
        
        c_g = get_colors(df_g, 'label', filter_data if filter_data and filter_data.get('source') == 'gender-bar-graph' else None, '#d32f2f')
        c_s = get_colors(df_s, 'label', filter_data if filter_data and filter_data.get('source') == 'skills-bar-graph' else None, '#d32f2f')

        fig_g = go.Figure(go.Bar(x=df_g['label'], y=df_g['val'], marker=dict(color=c_g), text=df_g['val'], textposition='auto'))
        apply_minimalist_style(fig_g, height=300)
        fig_g.update_xaxes(showgrid=False)
        fig_g.update_layout(margin=dict(l=40, r=20, t=10, b=40))

        fig_s = go.Figure(go.Bar(x=df_s['label'], y=df_s['val'], marker=dict(color=c_s), text=df_s['val'], textposition='auto'))
        apply_minimalist_style(fig_s, height=300)
        fig_s.update_xaxes(showgrid=False)
        fig_s.update_layout(margin=dict(l=40, r=20, t=10, b=40))
        return fig_g, fig_s
    except: return go.Figure(), go.Figure()

@callback(Output('shift-bar-graph', 'figure'), 
          [Input('weekly-attendance-graph', 'clickData'), 
           Input('att-date', 'date'), 
           Input('interaction-store', 'data'), 
           Input('user-context-store', 'data')])
def update_shift_figure(clickData, date_picker_val, filter_data, user_data):
    # --- GUARD CLAUSE ---
    if user_data is None:
        return go.Figure()
    # --------------------

    ctx = callback_context
    clicked_date = date_picker_val
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'].startswith('weekly-attendance-graph') and clickData:
            clicked_date = clickData['points'][0]['x']

    if not clicked_date: return go.Figure()
    
    plant_id = user_data.get('plant_id')
    company_id = user_data.get('company_id') 
    contractor_id = user_data.get('contractor_id') 
    supervisor_id = user_data.get('empid')
    
    conds = ["s.active = True", "e.active = true"]
    if company_id: conds.append(f"s.company_id = {company_id}")
    if plant_id: conds.append(f"e.plant_id = {plant_id}")
    if contractor_id: conds.append(f"e.contractor_id = {contractor_id}")
    
    # FILTER: Add Supervisor Scope
    if supervisor_id: conds.append(f"e.parent_id = {supervisor_id}")

    if filter_data and filter_data.get('source') != 'shift-bar-graph': conds.append(f"{filter_data['col']} = '{filter_data['val']}'")
    where_sql = "WHERE " + " AND ".join(conds)

    query = f"""
    SELECT s.name as label, COUNT(DISTINCT a.employee_id) as val
    FROM resource_calendar s
    LEFT JOIN hr_employee e ON s.id = e.resource_calendar_id 
    LEFT JOIN hr_department d ON e.department_id = d.id
    LEFT JOIN plant_contractor c ON e.contractor_id = c.id
    LEFT JOIN hr_attendance a ON e.id = a.employee_id AND DATE(a.check_in) = '{clicked_date}'
    {where_sql} GROUP BY s.name
    """
    try:
        df = pd.read_sql(query, db_connection)
        is_self = (filter_data and filter_data.get('source') == 'shift-bar-graph')
        colors = get_colors(df, 'label', filter_data if is_self else None, '#d32f2f')
        fig = go.Figure(go.Bar(x=df['label'], y=df['val'], marker=dict(color=colors), text=df['val'], textposition='auto'))
        h = max(300, len(df) * 35)
        apply_minimalist_style(fig, height=h)
        fig.update_xaxes(showgrid=False)
        fig.update_layout(margin=dict(l=40, r=20, t=10, b=40))
        return fig
    except: return go.Figure()

# 7. DRILL DOWN (Updated with Employee Code)
@callback(
    [Output("details-offcanvas", "is_open"), Output("table-container", "children"), Output("details-offcanvas", "title"), Output("drilldown-store", "data")],
    [Input("weekly-attendance-graph", "clickData"), 
     Input('att-date', 'date'), 
     Input('interaction-store', 'data'), 
     Input('user-context-store', 'data')]
)
def unified_drilldown(weekly_click, date_picker_val, filter_data, user_data):
    # --- GUARD CLAUSE ---
    if user_data is None:
        return False, dash.no_update, dash.no_update, dash.no_update
    # --------------------

    ctx = callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    clicked_date = date_picker_val
    if weekly_click: clicked_date = weekly_click['points'][0]['x']

    if trigger_id == 'att-date':
        return False, dash.no_update, dash.no_update, dash.no_update

    if not weekly_click: return False, dash.no_update, dash.no_update, dash.no_update
    
    plant_id = user_data.get('plant_id') 
    company_id = user_data.get('company_id') 
    contractor_id = user_data.get('contractor_id') 
    supervisor_id = user_data.get('empid')
    
    _, where_clause = build_base_query(plant_id, company_id, None, contractor_id)
    
    # FILTER: Add Supervisor Scope
    if supervisor_id:
        if where_clause: where_clause += f" AND e.parent_id = {supervisor_id}"
        else: where_clause = f" WHERE e.parent_id = {supervisor_id}"
    
    extra_conditions = f" AND DATE(a.check_in) = '{clicked_date}'"
    header_text = f"Drill-Down: {clicked_date}"
    if filter_data:
        extra_conditions += f" AND {filter_data['col']} = '{filter_data['val']}'"
        header_text += f" ({filter_data['val']})"
    full_where = (where_clause + extra_conditions) if where_clause else f" WHERE 1=1 {extra_conditions}"

    query = f"""
    SELECT DISTINCT 
        e.employee_code as "Code",
        e.name as "Name", 
        d.name as "Department", 
        s.name as "Shift", 
        a.check_in as "Check In", 
        a.check_out as "Check Out"
    FROM hr_attendance a 
    LEFT JOIN hr_employee e ON a.employee_id = e.id 
    LEFT JOIN hr_department d ON e.department_id = d.id 
    LEFT JOIN hr_job j ON e.job_id = j.id 
    LEFT JOIN resource_calendar s ON e.resource_calendar_id = s.id 
    LEFT JOIN plant_contractor c ON e.contractor_id = c.id
    {full_where} 
    ORDER BY "Check In" DESC 
    LIMIT 500
    """
    
    try:
        df_drill = pd.read_sql(query, db_connection)
        if df_drill.empty: return True, dbc.Alert("No data found.", color="warning"), header_text, []
        
        if 'Check In' in df_drill.columns: df_drill['Check In'] = pd.to_datetime(df_drill['Check In'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')
        if 'Check Out' in df_drill.columns: df_drill['Check Out'] = pd.to_datetime(df_drill['Check Out'], errors='coerce').dt.strftime('%H:%M')
        
        df_drill = df_drill.astype(object).fillna("N/A")
        
        table = dbc.Table.from_dataframe(df_drill, striped=True, bordered=True, hover=True, responsive=True) 
        store_data = df_drill.to_dict('records')
        return True, table, header_text, store_data
        
    except Exception as e: return True, dbc.Alert(f"Error: {e}", color="danger"), "Error", []

# 8. EXPORT
@callback(Output("download-dataframe-pdf", "data"), Input("btn-download-pdf", "n_clicks"), State("drilldown-store", "data"), prevent_initial_call=True)
def download_pdf(n_clicks, data):
    if not n_clicks or not data: return dash.no_update
    df_export = pd.DataFrame(data)
    df_export.insert(0, "S.No", range(1, 1 + len(df_export)))
    df_export = df_export.astype(str)
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="Attendance Report", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", size=8)
    cols = df_export.columns.tolist()
    col_w = [10, 60, 50, 40, 40, 40]
    for i, col in enumerate(cols):
        w = col_w[i] if i < len(col_w) else 30
        pdf.cell(w, 10, col[:15], border=1, align='C')
    pdf.ln()
    for index, row in df_export.iterrows():
        for i, item in enumerate(row):
            w = col_w[i] if i < len(col_w) else 30
            pdf.cell(w, 8, item[:20], border=1, align='C')
        pdf.ln()
    def to_output(file_obj): pdf_string = pdf.output(dest='S'); file_obj.write(pdf_string.encode('latin-1'))
    return dcc.send_bytes(to_output, "attendance_report.pdf")

@callback(Output("download-dataframe-csv", "data"), Input("btn-download", "n_clicks"), State("drilldown-store", "data"), prevent_initial_call=True)
def download_csv(n_clicks, data):
    if not n_clicks or not data: return dash.no_update
    df_export = pd.DataFrame(data)
    df_export.insert(0, "S.No", range(1, 1 + len(df_export)))
    return dcc.send_data_frame(df_export.to_csv, filename="attendance_drilldown.csv", index=False)

