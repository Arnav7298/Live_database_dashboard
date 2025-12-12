import dash
from dash import dcc, html, Input, Output, State, callback, callback_context, no_update
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from datetime import date
from utils import db_connection, get_company_options, get_plant_options, get_emp_type_options, build_base_query
from fpdf import FPDF

dash.register_page(__name__, path='/')

# ---------------------------------------------------------
# LAYOUT
# ---------------------------------------------------------
layout = dbc.Container([
    dcc.Store(id='drilldown-store'),
    dcc.Download(id="download-dataframe-csv"),
    dcc.Download(id="download-dataframe-pdf"),
    dcc.Store(id='interaction-store', data={}), 

    # --- 1. HEADER ROW (FILTERS) ---
    dbc.Row([
        dbc.Col([
            dbc.Row([
                dbc.Col([html.Label("Date Range"), dcc.DatePickerRange(id='att-date', min_date_allowed=date(2020, 1, 1), max_date_allowed=date(2030, 12, 31), start_date=date(2025, 11, 15), end_date=date(2025, 11, 30), display_format='Y-MM-DD', className="d-block")], width=3),
                dbc.Col([html.Label("Company"), dcc.Dropdown(id='att-comp', options=get_company_options(), value=None, placeholder="All", clearable=True)], width=3),
                dbc.Col([html.Label("Plant"), dcc.Dropdown(id='att-plant', options=get_plant_options(), value=None, placeholder="All", clearable=True)], width=3),
                dbc.Col([html.Label("Type"), dcc.Dropdown(id='att-type', options=get_emp_type_options(), value=None, placeholder="All", clearable=True)], width=3),
            ])
        ], width=10, className="align-self-center"),
        dbc.Col([
            dbc.Button("Clear Selection", id="btn-clear-filter", color="secondary", outline=True, className="mt-4 w-100")
        ], width=2)
    ]),

    html.Hr(),

    # --- 2. ROW 1: WEEKLY + DEPARTMENT (Side by Side) ---
    dbc.Row([
        # Weekly Graph
        dbc.Col([
            html.H5("Weekly Trend", className="card-title"),
            html.Small("👉 Click on any data point to begin analysis", className="text-primary fw-bold"),
            dcc.Graph(
                id='weekly-attendance-graph', 
                config={'displayModeBar': False},
                style={'height': '300px'}
            )
        ], width=6),
        
        # Department Graph
        dbc.Col([
            html.H5("Department Breakdown", className="card-title"),
            html.Small("👉 Click a bar to filter dashboard by Department", className="text-muted"),
            dcc.Loading(dcc.Graph(id='department-bar-graph', config={'displayModeBar': False}))
        ], width=6),
    ], className="mb-4"),

    # --- 3. ROW 2: GENDER, SKILLS, SHIFT, CONTRACTOR (All in one row) ---
    dbc.Row([
        # Gender
        dbc.Col([
            html.H6("By Gender", className="mb-1"),
            html.Small("Click to filter", className="text-muted"),
            dcc.Loading(dcc.Graph(id='gender-bar-graph', config={'displayModeBar': False}, style={'height': '300px'}))
        ], width=3),

        # Skills
        dbc.Col([
            html.H6("By Skills", className="mb-1"),
            html.Small("Click to filter", className="text-muted"),
            dcc.Loading(dcc.Graph(id='skills-bar-graph', config={'displayModeBar': False}, style={'height': '300px'}))
        ], width=3),

        # Shift
        dbc.Col([
            html.H6("By Shift", className="mb-1"),
            html.Small("Click to filter", className="text-muted"),
            dcc.Loading(dcc.Graph(id='shift-bar-graph', config={'displayModeBar': False}, style={'height': '300px'}))
        ], width=3),

        # Contractor
        dbc.Col([
            html.H6("Contractors", className="mb-1"),
            html.Small("Click to filter", className="text-muted"),
            dcc.Loading(dcc.Graph(id='contractor-bar-graph', config={'displayModeBar': False}, style={'height': '300px'}))
        ], width=3),
    ]),

    # --- 4. NEW DRILL DOWN (SLIDE-OUT SIDEBAR) ---
    dbc.Offcanvas(
        children=[
            dbc.Row([
                dbc.Col(dbc.Button("Export CSV", id="btn-download", color="success", size="sm", className="w-100"), width=6),
                dbc.Col(dbc.Button("Export PDF", id="btn-download-pdf", color="danger", size="sm", className="w-100"), width=6),
            ], className="mb-3"),
            html.Div(id='table-container')
        ],
        id="details-offcanvas",
        title="Drill-Down Details",
        is_open=False,
        placement="end",
        style={"width": "50%"} 
    )

], fluid=True)

# ---------------------------------------------------------
# CALLBACKS
# ---------------------------------------------------------

# 1. LOGIN / CONTEXT LOCKING (Updates visual dropdowns only)
@callback(
    [Output('att-comp', 'value'), Output('att-comp', 'disabled'),
     Output('att-plant', 'value'), Output('att-plant', 'disabled')],
    Input('user-context-store', 'data')
)
def load_context(data):
    if data and data.get('locked'):
        return data['company_id'], True, data['plant_id'], True
    return None, False, None, False

# 2. COORDINATOR CALLBACK (No changes needed)
@callback(
    Output('interaction-store', 'data'),
    [Input('department-bar-graph', 'clickData'),
     Input('gender-bar-graph', 'clickData'),
     Input('skills-bar-graph', 'clickData'),
     Input('shift-bar-graph', 'clickData'),
     Input('contractor-bar-graph', 'clickData'),
     Input('btn-clear-filter', 'n_clicks')]
)
def update_interaction_store(dept_click, gender_click, skills_click, shift_click, contractor_click, clear_click):
    ctx = callback_context
    if not ctx.triggered: return {}
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'btn-clear-filter': return {}
    
    if trigger_id == 'department-bar-graph' and dept_click:
        return {'col': 'd.name', 'val': dept_click['points'][0]['y'], 'source': trigger_id}
    if trigger_id == 'gender-bar-graph' and gender_click:
        return {'col': "COALESCE(e.gender, 'Unknown')", 'val': gender_click['points'][0]['x'], 'source': trigger_id}
    if trigger_id == 'skills-bar-graph' and skills_click:
        return {'col': "COALESCE(e.skills_status, 'Unknown')", 'val': skills_click['points'][0]['x'], 'source': trigger_id}
    if trigger_id == 'shift-bar-graph' and shift_click:
        return {'col': 's.name', 'val': shift_click['points'][0]['x'], 'source': trigger_id}
    if trigger_id == 'contractor-bar-graph' and contractor_click:
        return {'col': 'c.contractor_name', 'val': contractor_click['points'][0]['y'], 'source': trigger_id}
    return {}

# 3. HELPER: GREY OUT LOGIC
def get_colors(df, category_col, filter_data, default_color, grey_color='#d3d3d3'):
    if not filter_data or filter_data.get('col') is None:
        return [default_color] * len(df)
    selected_val = filter_data['val']
    return [default_color if val == selected_val else grey_color for val in df[category_col]]


# --- GRAPH CALLBACKS (ALL UPDATED WITH SECURITY LOGIC) ---

# 1. WEEKLY GRAPH
@callback(
    Output('weekly-attendance-graph', 'figure'),
    [Input('att-date', 'start_date'), Input('att-date', 'end_date'),
     Input('att-plant', 'value'), Input('att-comp', 'value'), Input('att-type', 'value')],
    [State('user-context-store', 'data')] # <--- [SECURITY UPDATE] Add State
)
def update_weekly_graph(start_date, end_date, plant_id, company_id, emp_type, user_data):
    # [SECURITY UPDATE] Extract hidden contractor ID
    contractor_id = None
    if user_data and user_data.get('contractor_id'):
        contractor_id = user_data['contractor_id']

    # [SECURITY UPDATE] Pass contractor_id to build_base_query
    joins, where_clause = build_base_query(plant_id, company_id, emp_type, contractor_id)
    
    date_condition = ""
    if start_date and end_date:
        date_condition = f"AND DATE(a.check_in) >= '{start_date}' AND DATE(a.check_in) <= '{end_date}'"
    
    final_where = (where_clause + " " + date_condition) if where_clause else (f" WHERE {date_condition[4:]}" if date_condition else "")
    
    try:
        df = pd.read_sql(f"SELECT a.check_in, a.employee_id FROM hr_attendance a {joins} {final_where}", db_connection)
    except Exception as e: return go.Figure().update_layout(title=f"Error: {e}")

    if df.empty: return go.Figure().update_layout(title="No data found")
    
    df['check_in'] = pd.to_datetime(df['check_in'], errors='coerce')
    df_grouped = df.dropna(subset=['check_in']).copy()
    df_grouped['date'] = df_grouped['check_in'].dt.date
    df_final = df_grouped.groupby('date')['employee_id'].nunique().reset_index(name='count').sort_values('date')
    
    fig = go.Figure(go.Scatter(
        x=df_final['date'], 
        y=df_final['count'], 
        mode='lines+markers+text',
        text=df_final['count'],
        textposition='top center',
        fill='tozeroy', 
        line=dict(color='#0d6efd', width=3)
    ))

    fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=300, autosize=False, hovermode="x unified", yaxis=dict(fixedrange=True))
    return fig


# 2. DEPARTMENT GRAPH
@callback(
    Output('department-bar-graph', 'figure'),
    [Input('weekly-attendance-graph', 'clickData'), Input('att-plant', 'value'),
     Input('att-comp', 'value'), Input('att-type', 'value'), Input('interaction-store', 'data')],
    [State('user-context-store', 'data')] # <--- [SECURITY UPDATE] Add State
)
def update_department_figure(clickData, plant_id, company_id, emp_type, filter_data, user_data):
    if not clickData: return go.Figure().update_layout(title="Waiting...", xaxis={'visible':False}, yaxis={'visible':False})
    clicked_date = clickData['points'][0]['x']
    
    conditions = []
    if company_id: conditions.append(f"e.company_id = {company_id}")
    if plant_id: conditions.append(f"e.plant_id = {plant_id}")
    if emp_type: conditions.append(f"e.employee_type = '{emp_type}'")
    
    # [SECURITY UPDATE] Manually add Contractor Restriction
    if user_data and user_data.get('contractor_id'):
        conditions.append(f"e.contractor_id = {user_data['contractor_id']}")

    if filter_data and filter_data.get('source') != 'department-bar-graph':
        conditions.append(f"{filter_data['col']} = '{filter_data['val']}'")
    
    where_sql = (" AND " + " AND ".join(conditions)) if conditions else ""

    query = f"""
    SELECT d.name as dept_name, COUNT(DISTINCT a.employee_id) as present_count
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
        colors = get_colors(df, 'dept_name', filter_data if is_self else None, '#0d6efd')

        fig = go.Figure(go.Bar(
            y=df['dept_name'], 
            x=df['present_count'], 
            orientation='h', 
            marker=dict(color=colors),
            text=df['present_count'],
            textposition='auto'
        ))
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300) 
        return fig
    except Exception as e: return go.Figure().update_layout(title=f"Error: {e}")


# 3. GENDER & SKILLS
@callback(
    [Output('gender-bar-graph', 'figure'), Output('skills-bar-graph', 'figure')],
    [Input('weekly-attendance-graph', 'clickData'), Input('att-plant', 'value'),
     Input('att-comp', 'value'), Input('att-type', 'value'), Input('interaction-store', 'data')],
    [State('user-context-store', 'data')] # <--- [SECURITY UPDATE] Add State
)
def update_gender_skills_figures(clickData, plant_id, company_id, emp_type, filter_data, user_data):
    if not clickData: 
        empty = go.Figure().update_layout(title="Waiting...", xaxis={'visible':False}, yaxis={'visible':False})
        return empty, empty
    clicked_date = clickData['points'][0]['x']
    
    base_conds = []
    if company_id: base_conds.append(f"e.company_id = {company_id}")
    if plant_id: base_conds.append(f"e.plant_id = {plant_id}")
    if emp_type: base_conds.append(f"e.employee_type = '{emp_type}'")

    # [SECURITY UPDATE] Add Contractor Restriction
    if user_data and user_data.get('contractor_id'):
        base_conds.append(f"e.contractor_id = {user_data['contractor_id']}")

    g_conds, s_conds = base_conds.copy(), base_conds.copy()
    if filter_data:
        if filter_data.get('source') != 'gender-bar-graph': g_conds.append(f"{filter_data['col']} = '{filter_data['val']}'")
        if filter_data.get('source') != 'skills-bar-graph': s_conds.append(f"{filter_data['col']} = '{filter_data['val']}'")

    def get_query(select, conds):
        where = f"WHERE DATE(a.check_in) = '{clicked_date}'"
        if conds: where += " AND " + " AND ".join(conds)
        return f"""
        {select} FROM hr_attendance a 
        LEFT JOIN hr_employee e ON a.employee_id = e.id
        LEFT JOIN hr_department d ON e.department_id = d.id
        LEFT JOIN resource_calendar s ON e.resource_calendar_id = s.id
        LEFT JOIN plant_contractor c ON e.contractor_id = c.id
        {where} GROUP BY 1
        """

    try:
        df_g = pd.read_sql(get_query("SELECT COALESCE(e.gender, 'Unknown') as label, COUNT(DISTINCT a.employee_id) as val", g_conds), db_connection)
        df_s = pd.read_sql(get_query("SELECT COALESCE(e.skills_status, 'Unknown') as label, COUNT(DISTINCT a.employee_id) as val", s_conds), db_connection)
        
        c_g = get_colors(df_g, 'label', filter_data if filter_data and filter_data.get('source') == 'gender-bar-graph' else None, '#6610f2')
        c_s = get_colors(df_s, 'label', filter_data if filter_data and filter_data.get('source') == 'skills-bar-graph' else None, '#fd7e14')

        fig_g = go.Figure(go.Bar(
            x=df_g['label'], 
            y=df_g['val'], 
            marker=dict(color=c_g),
            text=df_g['val'],
            textposition='auto'
        ))
        fig_g.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=250)

        fig_s = go.Figure(go.Bar(
            x=df_s['label'], 
            y=df_s['val'], 
            marker=dict(color=c_s),
            text=df_s['val'],
            textposition='auto'
        ))
        fig_s.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=250)

        return fig_g, fig_s
    except: return go.Figure(), go.Figure()


# 4. SHIFT GRAPH
@callback(
    Output('shift-bar-graph', 'figure'),
    [Input('weekly-attendance-graph', 'clickData'), Input('att-plant', 'value'),
     Input('att-comp', 'value'), Input('att-type', 'value'), Input('interaction-store', 'data')],
    [State('user-context-store', 'data')] # <--- [SECURITY UPDATE] Add State
)
def update_shift_figure(clickData, plant_id, company_id, emp_type, filter_data, user_data):
    if not clickData: return go.Figure().update_layout(title="Waiting...", xaxis={'visible':False}, yaxis={'visible':False})
    clicked_date = clickData['points'][0]['x']
    
    conds = ["s.active = True"]
    if company_id: conds.append(f"s.company_id = {company_id}")
    if plant_id: conds.append(f"e.plant_id = {plant_id}")
    if emp_type: conds.append(f"e.employee_type = '{emp_type}'")

    # [SECURITY UPDATE] Add Contractor Restriction
    if user_data and user_data.get('contractor_id'):
        conds.append(f"e.contractor_id = {user_data['contractor_id']}")

    if filter_data and filter_data.get('source') != 'shift-bar-graph':
        conds.append(f"{filter_data['col']} = '{filter_data['val']}'")
    
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
        colors = get_colors(df, 'label', filter_data if is_self else None, '#0d6efd')
        
        fig = go.Figure(go.Bar(
            x=df['label'], 
            y=df['val'], 
            marker=dict(color=colors),
            text=df['val'],
            textposition='auto'
        ))
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=250)
        return fig
    except: return go.Figure()


# 5. CONTRACTOR GRAPH
@callback(
    Output('contractor-bar-graph', 'figure'),
    [Input('weekly-attendance-graph', 'clickData'), Input('att-plant', 'value'),
     Input('att-comp', 'value'), Input('att-type', 'value'), Input('interaction-store', 'data')],
    [State('user-context-store', 'data')] # <--- [SECURITY UPDATE] Add State
)
def update_contractor_figure(clickData, plant_id, company_id, emp_type, filter_data, user_data):
    if not clickData: return go.Figure().update_layout(title="Waiting...", xaxis={'visible':False}, yaxis={'visible':False})
    clicked_date = clickData['points'][0]['x']
    
    conds = []
    if company_id: conds.append(f"e.company_id = {company_id}")
    if plant_id: conds.append(f"e.plant_id = {plant_id}")
    if emp_type: conds.append(f"e.employee_type = '{emp_type}'")
    
    # [SECURITY UPDATE] Add Contractor Restriction
    if user_data and user_data.get('contractor_id'):
        conds.append(f"e.contractor_id = {user_data['contractor_id']}")

    if filter_data and filter_data.get('source') != 'contractor-bar-graph':
        conds.append(f"{filter_data['col']} = '{filter_data['val']}'")
    
    where_sql = (" WHERE " + " AND ".join(conds)) if conds else " WHERE 1=1 "

    query = f"""
    SELECT c.contractor_name as label, COUNT(DISTINCT a.employee_id) as val
    FROM plant_contractor c
    LEFT JOIN hr_employee e ON c.id = e.contractor_id 
    LEFT JOIN hr_department d ON e.department_id = d.id
    LEFT JOIN resource_calendar s ON e.resource_calendar_id = s.id
    LEFT JOIN hr_attendance a ON e.id = a.employee_id AND DATE(a.check_in) = '{clicked_date}'
    {where_sql} GROUP BY c.contractor_name
    """
    try:
        df = pd.read_sql(query, db_connection)
        if df.empty: return go.Figure().update_layout(title="No Data")
        is_self = (filter_data and filter_data.get('source') == 'contractor-bar-graph')
        colors = get_colors(df, 'label', filter_data if is_self else None, '#198754')
        
        fig = go.Figure(go.Bar(
            y=df['label'], 
            x=df['val'], 
            orientation='h', 
            marker=dict(color=colors),
            text=df['val'],
            textposition='auto'
        ))
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=250)
        return fig
    except: return go.Figure()

# --- DRILL DOWN: UPDATED TO FIX WARNINGS ---
@callback(
    [Output("details-offcanvas", "is_open"), 
     Output("table-container", "children"), 
     Output("details-offcanvas", "title"),
     Output("drilldown-store", "data")],
     
    [Input("weekly-attendance-graph", "clickData"),
     Input('interaction-store', 'data'),
     Input('att-plant', 'value'), 
     Input('att-comp', 'value'), 
     Input('att-type', 'value')],
    [State('user-context-store', 'data')]
)
def unified_drilldown(weekly_click, filter_data, plant_id, company_id, emp_type, user_data):
    
    if not weekly_click:
        return False, dash.no_update, dash.no_update, dash.no_update

    clicked_date = weekly_click['points'][0]['x']
    
    # Security: Extract contractor_id
    contractor_id = None
    if user_data and user_data.get('contractor_id'):
        contractor_id = user_data['contractor_id']
        
    _, where_clause = build_base_query(plant_id, company_id, emp_type, contractor_id)
    
    extra_conditions = f" AND DATE(a.check_in) = '{clicked_date}'"
    header_text = f"Drill-Down: {clicked_date}"

    if filter_data:
        extra_conditions += f" AND {filter_data['col']} = '{filter_data['val']}'"
        header_text += f" ({filter_data['val']})"

    if where_clause: full_where = where_clause + extra_conditions
    else: full_where = f" WHERE 1=1 {extra_conditions}"

    query = f"""
    SELECT DISTINCT 
        e.name as "Name", d.name as "Department", s.name as "Shift",
        a.check_in as "Check In", a.check_out as "Check Out"
    FROM hr_attendance a
    LEFT JOIN hr_employee e ON a.employee_id = e.id
    LEFT JOIN hr_department d ON e.department_id = d.id
    LEFT JOIN hr_job j ON e.job_id = j.id
    LEFT JOIN resource_calendar s ON e.resource_calendar_id = s.id
    LEFT JOIN plant_contractor c ON e.contractor_id = c.id
    {full_where}
    ORDER BY "Check In" DESC LIMIT 500
    """

    try:
        df_drill = pd.read_sql(query, db_connection)
        
        if df_drill.empty:
            return True, dbc.Alert("No data found.", color="warning"), header_text, []

        # --- FIX START: PROCESS DATES BEFORE FILLING "N/A" ---
        
        # 1. Handle "Check In" Format
        if 'Check In' in df_drill.columns:
            # Using errors='coerce' to turn bad data into NaT (Not a Time)
            # This runs on the raw data BEFORE we add any "N/A" strings
            df_drill['Check In'] = pd.to_datetime(df_drill['Check In'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')

        # 2. Handle "Check Out" Format
        if 'Check Out' in df_drill.columns:
            df_drill['Check Out'] = pd.to_datetime(df_drill['Check Out'], errors='coerce').dt.strftime('%H:%M')

        # 3. Now Convert to Object (Text) so we can add "N/A" safely
        df_drill = df_drill.astype(object)

        # 4. Fill Empty Spots (This catches the original Nulls AND the failed dates from step 1 & 2)
        # assign the result back to df_drill to avoid the "inplace" warning
        df_drill = df_drill.fillna("N/A")
        
        # --- FIX END ---
        
        table = dbc.Table.from_dataframe(df_drill, striped=True, bordered=True, hover=True, responsive=True)
        store_data = df_drill.to_dict('records')
        return True, table, header_text, store_data

    except Exception as e:
        return True, dbc.Alert(f"Error: {e}", color="danger"), "Error", []

# PDF/CSV EXPORT CALLBACKS REMAIN UNCHANGED

# --- 9. EXPORT PDF (Unchanged) ---
@callback(
    Output("download-dataframe-pdf", "data"),
    Input("btn-download-pdf", "n_clicks"),
    State("drilldown-store", "data"),
    prevent_initial_call=True
)
def download_pdf(n_clicks, data):
    if not n_clicks or not data: return dash.no_update
    df_export = pd.DataFrame(data)
    df_export.insert(0, "S.No", range(1, 1 + len(df_export)))
    df_export = df_export.astype(str)
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=8)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="Attendance Drill-Down Report", ln=True, align='C')
    pdf.ln(5)
    col_widths = [10, 15, 40, 30, 30, 25, 25, 25, 20] # Simplified
    pdf.set_font("Arial", 'B', 9)
    pdf.set_fill_color(200, 220, 255) 
    cols = df_export.columns.tolist()
    for i, col_name in enumerate(cols):
        w = col_widths[i] if i < len(col_widths) else 25
        text = (col_name[:15] + '..') if len(col_name) > 18 else col_name
        pdf.cell(w, 10, text, border=1, align='C', fill=True)
    pdf.ln()
    pdf.set_font("Arial", size=8)
    pdf.set_fill_color(255, 255, 255) 
    for index, row in df_export.iterrows():
        for i, item in enumerate(row):
            w = col_widths[i] if i < len(col_widths) else 25
            text = (item[:20] + '..') if len(item) > 22 else item
            pdf.cell(w, 8, text, border=1, align='C')
        pdf.ln()
    def to_output(file_obj):
        pdf_string = pdf.output(dest='S')
        file_obj.write(pdf_string.encode('latin-1'))
    return dcc.send_bytes(to_output, "attendance_report.pdf")

# --- 10. EXPORT CSV (Unchanged) ---
@callback(
    Output("download-dataframe-csv", "data"),
    Input("btn-download", "n_clicks"),
    State("drilldown-store", "data"),
    prevent_initial_call=True
)
def download_csv(n_clicks, data):
    if not n_clicks or not data: return dash.no_update
    df_export = pd.DataFrame(data)
    df_export.insert(0, "S.No", range(1, 1 + len(df_export)))
    return dcc.send_data_frame(df_export.to_csv, filename="attendance_drilldown.csv", index=False)
