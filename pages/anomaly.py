import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import date
from utils import db_connection, create_user_status_widget, get_supervisor_counts

dash.register_page(__name__, path='/anomaly')

layout = dbc.Container([
    dcc.Store(id='anomaly-data-store'),

    # Header
    html.H3([html.I(className="fa-solid fa-triangle-exclamation me-2"), "Data Quality & Anomaly Tracking"], className="mb-4 text-danger fw-bold"),

    html.Div(id='anomaly-status-widget'),

    # --- 2. CONTROLS ROW ---
    dbc.Row([
        dbc.Col([
            html.Label([html.I(className="fa-regular fa-calendar me-2"), "Select Date"], className="fw-bold small"),
            dcc.DatePickerSingle(
                id='anomaly-date', 
                date=date(2025, 11, 15), # Default fallback
                min_date_allowed=date(2020, 1, 1),
                max_date_allowed=date(2030, 12, 31),
                display_format='Y-MM-DD',
                className="d-block w-100 shadow-sm"
            )
        ], width=4),

        dbc.Col([
             dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H6("Employees Present", className="card-subtitle text-muted mb-1 small text-uppercase"),
                            html.H4(id="anomaly-kpi-supervisor-count", children="0 / 0", className="card-title text-primary fw-bold mb-0")
                        ], width=8),
                        dbc.Col([html.I(className="fa-solid fa-people-group fa-2x text-black-50")], width=4, className="d-flex align-items-center justify-content-end")
                    ])
                ], className="p-2")
             ], className="shadow-sm border-0 h-100")
        ], width=4),

        dbc.Col(width=4),

    ], className="mb-4 align-items-end"),

    html.Hr(), 

    # --- 3. ATTENDANCE ANOMALY TABLES ---
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader(
                [html.I(className="fa-solid fa-user-slash me-2 text-danger"), "Missed Check-Out Details"], 
                id="hdr-missed", className="fw-bold border-bottom d-flex align-items-center justify-content-between"
            ), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-missed', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader(
                [html.I(className="fa-solid fa-clock me-2 text-warning"), "Multiple Check-In Details"], 
                id="hdr-multi", className="fw-bold border-bottom d-flex align-items-center justify-content-between"
            ), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-multi', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
    ], className="mb-4"),

    # --- 4. MASTER DATA ANOMALY TABLES ---
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Skills", id="hdr-skills", className="fw-bold border-bottom d-flex align-items-center justify-content-between"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-skills', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Contractor ID", id="hdr-contractor", className="fw-bold border-bottom d-flex align-items-center justify-content-between"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-contractor', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Salary Category", id="hdr-desig", className="fw-bold border-bottom d-flex align-items-center justify-content-between"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-desig', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
        
        dbc.Col(dbc.Card([
            dbc.CardHeader("Employees without Department", id="hdr-dept", className="fw-bold border-bottom d-flex align-items-center justify-content-between"), 
            dbc.CardBody(dcc.Loading(html.Div(id='tbl-dept', style={'maxHeight': '300px', 'overflowY': 'auto'})))
        ], className="shadow-sm border-0 h-100"), width=6),
    ], className="mb-5"),

], fluid=True)

# ---------------------------------------------------------
# CALLBACKS
# ---------------------------------------------------------

# --- DATE PERSISTENCE LOGIC ---

# 1. Sync LOCAL DatePicker -> GLOBAL Store
@callback(
    Output('global-date-store', 'data', allow_duplicate=True),
    Input('anomaly-date', 'date'),
    prevent_initial_call=True
)
def sync_date_to_store(local_date):
    if not local_date: return dash.no_update
    return local_date

# 2. Sync GLOBAL Store -> LOCAL DatePicker
@callback(
    Output('anomaly-date', 'date'),
    Input('global-date-store', 'data')
)
def load_date_from_store(stored_date):
    if not stored_date: return dash.no_update
    return stored_date

# --- EXISTING CALLBACKS ---

@callback(
    Output('anomaly-status-widget', 'children'), 
    [Input('user-context-store', 'data'), Input('anomaly-date', 'date')]
)
def update_anomaly_widget(user_data, selected_date):
    if user_data is None: return dash.no_update
    emp_name = user_data.get('emp_name', 'Unknown')
    contractor = user_data.get('contractor_name', None)
    date_display = str(selected_date) if selected_date else "Select Date"
    return create_user_status_widget(emp_name, contractor, date_display)

# --- SUPERVISOR KPI CALLBACK ---
@callback(
    Output('anomaly-kpi-supervisor-count', 'children'), 
    [Input('anomaly-date', 'date'), Input('user-context-store', 'data')]
)
def update_md_supervisor_kpi(selected_date, user_data):
    if user_data is None: return "0 / 0"
    
    supervisor_id = user_data.get('empid')
    plant_id = user_data.get('plant_id')
    company_id = user_data.get('company_id')
    contractor_id = user_data.get('contractor_id')

    return get_supervisor_counts(supervisor_id, selected_date, company_id, plant_id, contractor_id)

@callback(
    [Output('tbl-missed', 'children'), Output('hdr-missed', 'children'),
     Output('tbl-multi', 'children'), Output('hdr-multi', 'children')],
    [Input('anomaly-date', 'date'), Input('user-context-store', 'data')]
)
def update_attendance_tables(selected_date, user_data):
    def loading_state(title, icon_cls):
        header = html.Div([
            html.Span([html.I(className=f"{icon_cls} me-2"), title]),
            dbc.Badge("...", color="secondary", className="ms-2")
        ], className="d-flex align-items-center w-100 justify-content-between")
        return html.Div("Loading..."), header

    if user_data is None: 
        m = loading_state("Missed Check-Out", "fa-solid fa-user-slash")
        mu = loading_state("Multiple Check-In", "fa-solid fa-clock")
        return m[0], m[1], mu[0], mu[1]

    plant_id = user_data.get('plant_id')
    company_id = user_data.get('company_id')
    contractor_id = user_data.get('contractor_id')
    supervisor_id = user_data.get('empid') 
    
    conditions = ["e.active = true"]
    if company_id: conditions.append(f"e.company_id = {company_id}")
    if plant_id: conditions.append(f"e.plant_id = {plant_id}")
    if contractor_id: conditions.append(f"e.contractor_id = {contractor_id}")
    if supervisor_id: conditions.append(f"e.parent_id = {supervisor_id}")
    
    date_cond = f"AND DATE(a.check_in) = '{selected_date}'" if selected_date else "AND 1=0"
    join_sql = f"AND {' AND '.join(conditions)}"

    q_missed = f"""
        SELECT DATE(a.check_in) as "Date", e.name as "Name", e.employee_code as "Employee Code" 
        FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id 
        WHERE a.check_out IS NULL {date_cond} {join_sql}
        ORDER BY a.check_in DESC LIMIT 50
    """
    q_multi = f"""
        SELECT DATE(a.check_in) as "Date", e.name as "Name", e.employee_code as "Employee Code", COUNT(*) as "Count"
        FROM hr_attendance a LEFT JOIN hr_employee e ON a.employee_id = e.id 
        WHERE 1=1 {date_cond} {join_sql} 
        GROUP BY a.employee_id, DATE(a.check_in), e.name, e.employee_code
        HAVING COUNT(*) > 1
        ORDER BY "Date" DESC LIMIT 50
    """

    def process_data(query, title_text, icon_class, color_class):
        try:
            df = pd.read_sql(query, db_connection)
            count = len(df)
            header_content = html.Div([
                html.Span([html.I(className=f"{icon_class} me-2 {color_class}"), title_text]),
                dbc.Badge(f"{count}", color="secondary" if count == 0 else "danger", pill=True, className="ms-2")
            ], className="d-flex align-items-center w-100 justify-content-between")
            if df.empty: table_content = dbc.Alert("No anomalies found.", color="success", className="mb-0")
            else: table_content = dbc.Table.from_dataframe(df, striped=True, bordered=True, hover=True, size='sm') 
            return table_content, header_content
        except Exception as e: 
            err_header = html.Div([html.Span(title_text), dbc.Badge("!", color="dark")])
            return dbc.Alert(f"Error: {e}", color="danger"), err_header

    tbl_missed, hdr_missed = process_data(q_missed, "Missed Check-Out Details", "fa-solid fa-user-slash", "text-danger")
    tbl_multi, hdr_multi = process_data(q_multi, "Multiple Check-In Details", "fa-solid fa-clock", "text-warning")
    return tbl_missed, hdr_missed, tbl_multi, hdr_multi

@callback(
    [Output('tbl-skills', 'children'), Output('hdr-skills', 'children'),
     Output('tbl-contractor', 'children'), Output('hdr-contractor', 'children'),
     Output('tbl-desig', 'children'), Output('hdr-desig', 'children'),
     Output('tbl-dept', 'children'), Output('hdr-dept', 'children')],
    [Input('user-context-store', 'data')]
)
def update_master_tables(user_data):
    def loading_state(title):
        header = html.Div([html.Span(title), dbc.Badge("...", color="secondary")], className="d-flex justify-content-between")
        return html.Div("Loading..."), header
    if user_data is None: return (loading_state("Skills") + loading_state("Contractor") + loading_state("Salary Category") + loading_state("Department"))

    plant_id = user_data.get('plant_id')
    company_id = user_data.get('company_id')
    contractor_id = user_data.get('contractor_id')
    supervisor_id = user_data.get('empid') 
    
    conditions = ["active = true"] 
    if company_id: conditions.append(f"company_id = {company_id}")
    if plant_id: conditions.append(f"plant_id = {plant_id}")
    if contractor_id: conditions.append(f"contractor_id = {contractor_id}")
    if supervisor_id: conditions.append(f"parent_id = {supervisor_id}")
    where_base = "WHERE " + " AND ".join(conditions)

    def get_doj_style(doj_val):
        if pd.isna(doj_val): return {}
        doj_date = doj_val.date() if hasattr(doj_val, 'date') else doj_val
        diff_days = (date.today() - doj_date).days
        if diff_days <= 1: return {'color': 'white', 'fontWeight': 'bold', 'backgroundColor': '#28a745'} 
        elif diff_days <= 7: return {'color': '#fd7e14', 'fontWeight': 'bold'}
        else: return {'color': '#dc3545', 'fontWeight': 'bold'}

    def process_master_table(cond, title):
        query = f"SELECT create_date, name as \"Name\", employee_code as \"Employee Code\" FROM hr_employee {where_base} AND {cond} ORDER BY create_date DESC LIMIT 50"
        try:
            df = pd.read_sql(query, db_connection)
            count = len(df)
            header_content = html.Div([html.Span(title), dbc.Badge(f"{count}", color="secondary" if count == 0 else "danger", pill=True, className="ms-2")], className="d-flex align-items-center w-100 justify-content-between")
            if df.empty: tbl = dbc.Alert("Clean Data!", color="success", className="mb-0")
            else:
                rows = []
                for _, row in df.iterrows():
                    style = get_doj_style(row['create_date'])
                    date_str = row['create_date'].strftime('%Y-%m-%d') if pd.notnull(row['create_date']) else "N/A"
                    rows.append(html.Tr([html.Td(date_str, style=style), html.Td(row['Name']), html.Td(row['Employee Code'])]))
                tbl = dbc.Table([html.Thead(html.Tr([html.Th("DOJ"), html.Th("Name"), html.Th("Employee Code")])), html.Tbody(rows)], bordered=True, size='sm', hover=True)
            return tbl, header_content
        except: return dbc.Alert("Error", color="danger"), html.Div(title)

    r1 = process_master_table("skills_status IS NULL", "Employees without Skills")
    r2 = process_master_table("contractor_id IS NULL", "Employees without Contractor ID")
    r3 = process_master_table("job_position IS NULL", "Employees without Salary Category")
    r4 = process_master_table("department_id IS NULL", "Employees without Department")
    return r1[0], r1[1], r2[0], r2[1], r3[0], r3[1], r4[0], r4[1]




